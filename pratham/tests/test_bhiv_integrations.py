from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mitra_companion.bhiv_integrations import BHIVRuntimeIntegrator
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.utils import canonical_json, sha256_text


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def test_bhiv_integration_catalog_declares_response_contracts(
    settings_factory,
):
    runtime = CompanionRuntime(settings_factory())
    status = runtime.bhiv_integrations.status()
    operations = {item["operation"] for item in status["api_calls"]}

    assert {
        "ashmit.health-system",
        "karma.append",
        "karma.append-bucket-artifact",
        "prana.karma-strict",
        "prana.core",
        "bucket.latest-hash",
        "bucket.artifact",
        "bucket.get-artifact",
        "bucket.validate-chain",
        "bucket.validate-replay",
        "insightflow.execution_trace",
        "central-depository.export",
    }.issubset(operations)
    assert all(item.get("response_schema") for item in status["api_calls"])


def test_example_manifest_intents_publish_response_schemas():
    missing: list[str] = []
    for path in (ROOT / "contracts" / "examples").glob("*.json"):
        manifest = ProductAttachmentManifest.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        for capability in manifest.capabilities:
            for intent in capability.intents:
                if not intent.response_schema:
                    missing.append(f"{path.name}:{intent.intent_id}")

    assert missing == []


@pytest.mark.asyncio
async def test_dispatch_publishes_bhiv_convergence_contracts(settings_factory):
    settings = settings_factory()
    settings.bhiv_karma_base_url = "https://karma.test"
    settings.bhiv_prana_base_url = "https://prana.test"
    settings.bhiv_bucket_base_url = "https://bucket.test"
    settings.bhiv_insightflow_ingest_url = "https://insight.test/ingest"
    settings.bhiv_ashmit_base_url = "https://ashmit.test"
    settings.bhiv_karma_previous_hash = "karma-head-001"
    observed: dict[str, Any] = {
        "paths": [],
        "karma_bodies": [],
        "karma_last_hash": "karma-head-001",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["paths"].append(str(request.url))
        body = request.content
        payload = json.loads(body.decode("utf-8")) if body else {}
        if request.url.host == "karma.test" and request.url.path == "/integrity/append":
            observed["karma_bodies"].append(body)
            assert payload["previous_hash"] == observed["karma_last_hash"]
            observed["karma_last_hash"] = sha256_text(body.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "status": "appended",
                    "current_hash": observed["karma_last_hash"],
                },
            )
        if (
            request.url.host == "karma.test"
            and request.url.path == "/integrity/append-bucket-artifact"
        ):
            observed["karma_bodies"].append(body)
            assert payload["artifact_type"] == "mitra.dispatch.reconstruction"
            assert payload["parent_hash"] == observed["karma_last_hash"]
            observed["karma_last_hash"] = sha256_text(body.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "status": "appended",
                    "trace_id": payload["trace_id"],
                    "current_hash": observed["karma_last_hash"],
                },
            )
        if (
            request.url.host == "prana.test"
            and request.url.path == "/forward/karma-strict"
        ):
            assert body in observed["karma_bodies"]
            return httpx.Response(
                200,
                json={"status": "forwarded"},
                headers={
                    "X-PRANA-Strict-Bytes-Equal": "true",
                    "X-PRANA-Payload-SHA256": sha256_text(
                        body.decode("utf-8")
                    ),
                },
            )
        if (
            request.url.host == "prana.test"
            and request.url.path == "/forward/core"
        ):
            return httpx.Response(
                200,
                json={"status": "forwarded", "trace_id": payload["trace_id"]},
            )
        if (
            request.url.host == "bucket.test"
            and request.url.path == "/bucket/latest-hash"
        ):
            return httpx.Response(200, json={"latest_hash": "bucket-head-001"})
        if (
            request.url.host == "bucket.test"
            and request.url.path == "/bucket/artifact"
        ):
            assert payload["parent_hash"] == "bucket-head-001"
            return httpx.Response(200, json={"status": "stored"})
        if (
            request.url.host == "bucket.test"
            and request.url.path.startswith("/bucket/artifact/")
        ):
            return httpx.Response(
                200,
                json={
                    "status": "found",
                    "artifact_id": request.url.path.rsplit("/", 1)[-1],
                },
            )
        if (
            request.url.host == "bucket.test"
            and request.url.path.startswith("/bucket/validate-chain/")
        ):
            return httpx.Response(
                200,
                json={
                    "status": "valid",
                    "artifact_id": request.url.path.rsplit("/", 1)[-1],
                },
            )
        if (
            request.url.host == "bucket.test"
            and request.url.path == "/bucket/validate-replay"
        ):
            return httpx.Response(
                200,
                json={
                    "status": "valid",
                    "artifact_id": payload["artifact_id"],
                },
            )
        if request.url.host == "insight.test":
            trace = payload["payload"]["execution_trace"]
            assert payload["source_system"] == "Mitra"
            assert trace["stage"] == "runtime"
            assert trace["replay_state"] == "replay_ready"
            return httpx.Response(200, json={"status": "observed"})
        if (
            request.url.host == "ashmit.test"
            and request.url.path == "/health/system"
        ):
            return httpx.Response(200, json={"system": "mitra_runtime"})
        return httpx.Response(404, json={"status": "not_found"})

    runtime = CompanionRuntime(settings)
    runtime.bhiv_integrations = BHIVRuntimeIntegrator(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        runtime.attach(_manifest("product-bucket-insight.json"))
        session = runtime.sessions.create(
            actor_id="integration-runner",
            client_type="standalone",
            workspace_id="bhiv-contracts",
            product_id="bucket-insight",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                product_id="bucket-insight",
                capability_id="artifact-insight",
                intent_id="bucket.lookup-artifact",
                payload={
                    "artifact_hash": "abc123456789def0",
                    "review_depth": "summary",
                },
            )
        )
    finally:
        runtime.stop()

    convergence = result["ecosystem_convergence"]
    assert convergence["accepted_count"] == 14
    assert convergence["failed_count"] == 0
    assert convergence["skipped_count"] == 0
    assert all("response" in item for item in convergence["results"])
    operations = [item["operation"] for item in convergence["results"]]
    assert {
        "ashmit.health-system",
        "bucket.latest-hash",
        "bucket.artifact",
        "bucket.get-artifact",
        "bucket.validate-chain",
        "bucket.validate-replay",
        "central-depository.export",
        "insightflow.execution_trace",
        "karma.append",
        "karma.append-bucket-artifact",
        "prana.karma-strict",
        "prana.core",
    }.issubset(operations)
    assert operations.count("prana.karma-strict") == 2
    assert operations.count("prana.core") == 2
    bucket_result = next(
        item
        for item in convergence["results"]
        if item["operation"] == "bucket.artifact"
    )
    assert bucket_result["parent_lookup"]["operation"] == "bucket.latest-hash"
    assert bucket_result["parent_lookup"]["response"]["latest_hash"] == (
        "bucket-head-001"
    )
    karma_result = next(
        item
        for item in convergence["results"]
        if item["operation"] == "karma.append"
    )
    assert all("response" in item for item in karma_result["prana_forwarding"])
    assert observed["paths"].count("https://prana.test/forward/karma-strict") == 2
    assert observed["paths"].count("https://prana.test/forward/core") == 2
    export_result = next(
        item
        for item in convergence["results"]
        if item["operation"] == "central-depository.export"
    )
    depository_response = export_result["response"]["depository"]
    assert depository_response["subject_id"] == result["dispatch"]["dispatch_id"]
    assert depository_response["lineage_count"] >= 1
    assert depository_response["artifact_hashes"]
    assert "artifacts" not in depository_response
    depository = runtime.central_depository(
        artifact_type="bhiv-runtime-convergence.dispatch"
    )
    assert depository["artifacts"][0]["artifact"]["dispatch_id"] == result[
        "dispatch"
    ]["dispatch_id"]


@pytest.mark.asyncio
async def test_prana_forwarding_is_skipped_when_karma_rejects(
    settings_factory,
):
    settings = settings_factory()
    settings.bhiv_karma_base_url = "https://karma.test"
    settings.bhiv_prana_base_url = "https://prana.test"
    paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        paths.append(str(request.url))
        if request.url.host == "karma.test":
            return httpx.Response(200, json={"status": "append_violation"})
        return httpx.Response(200, json={"status": "unexpected"})

    runtime = CompanionRuntime(settings)
    runtime.bhiv_integrations = BHIVRuntimeIntegrator(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    result = await runtime.bhiv_integrations.publish_dispatch(
        dispatch={
            "dispatch_id": "dsp_rejected",
            "status": "COMPLETED",
            "product_id": "bucket-insight",
            "capability_id": "artifact-insight",
            "intent_id": "bucket.lookup-artifact",
            "request": {"correlation_id": "trace_rejected"},
        },
        route={"product_id": "bucket-insight"},
        reconstruction={
            "package_hash": sha256_text(
                canonical_json({"dispatch_id": "dsp_rejected"})
            )
        },
        proof={"bundle_hash": "proof-hash"},
    )

    assert result["failed_count"] == 1
    assert result["accepted_count"] == 1
    assert result["skipped_count"] == 3
    assert result["results"][0]["status"] == "rejected"
    assert result["results"][0]["prana_forwarding"]["response"]["status"] == (
        "skipped"
    )
    assert result["results"][-1]["operation"] == "central-depository.export"
    depository_response = result["results"][-1]["response"]["depository"]
    assert depository_response["subject_id"] == result["dispatch_id"]
    assert "artifacts" not in depository_response
    assert all("prana.test" not in path for path in paths)
