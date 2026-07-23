from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mitra_companion.bhiv_integrations import BHIVRuntimeIntegrator
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def test_legacy_exporter_declares_canonical_owner_workflow(settings_factory):
    runtime = CompanionRuntime(settings_factory())
    status = runtime.bhiv_integrations.status()
    operations = {item["operation"] for item in status["api_calls"]}

    assert status["integration_model"] == "canonical-ecosystem-runtime-only"
    assert status["legacy_dispatch_exporter"] == "non-executing"
    assert status["canonical_endpoint"] == "/api/v1/ecosystem/execute"
    assert status["readiness"]["state"] == "canonical-only"
    assert status["readiness"]["embedded_contract_modules"] == []
    assert status["readiness"]["contract_adapters_available"] == []
    assert set(status["readiness"]["unavailable_owner_modules"]) == {
        "raj",
        "ashmit",
        "bucket",
        "keshav",
        "karma",
        "prana",
        "insightflow",
        "central_depository",
    }
    assert {
        "raj.workflow-execute",
        "ashmit.health-system",
        "ashmit.mitra-evaluate",
        "bucket.artifact",
        "keshav.analyze",
        "karma.append-bucket-artifact",
        "prana.karma-strict",
        "prana.core",
        "insightflow.execution-trace",
        "central-depository.artifact",
    } == operations
    assert all(item.get("response_schema") for item in status["api_calls"])


@pytest.mark.asyncio
async def test_ordinary_dispatch_never_impersonates_owner_services(
    settings_factory,
):
    runtime = CompanionRuntime(settings_factory())
    runtime.start()
    try:
        runtime.attach(_manifest("product-bucket-insight.json"))
        session = runtime.sessions.create(
            actor_id="ordinary-dispatch-runner",
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
                    "artifact_hash": "ordinary-dispatch-artifact",
                    "review_depth": "full",
                },
            )
        )
    finally:
        runtime.stop()

    convergence = result["ecosystem_convergence"]
    assert convergence["accepted_count"] == 0
    assert convergence["failed_count"] == 0
    assert convergence["skipped_count"] == 8
    assert convergence["overall_status"] == "canonical-execution-required"
    assert all(
        item["status"] == "not_executed"
        and item["method"] is None
        and item["http_status"] is None
        and item["response"]["canonical_endpoint"]
        == "/api/v1/ecosystem/execute"
        for item in convergence["results"]
    )


@pytest.mark.asyncio
async def test_legacy_exporter_performs_zero_http_calls_when_configured(
    settings_factory,
):
    settings = settings_factory()
    settings.raj_workflow_base_url = "https://raj.test"
    settings.bhiv_ashmit_base_url = "https://ashmit.test"
    settings.bhiv_ashmit_api_key = "ashmit-secret"
    settings.bhiv_bucket_base_url = "https://bucket.test"
    settings.bhiv_keshav_base_url = "https://keshav.test"
    settings.bhiv_karma_base_url = "https://karma.test"
    settings.bhiv_prana_base_url = "https://prana.test"
    settings.bhiv_insightflow_ingest_url = "https://insight.test/ingest"
    settings.central_depository_base_url = "https://depository.test"
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(500, json={"status": "unexpected"})

    runtime = CompanionRuntime(settings)
    integrator = BHIVRuntimeIntegrator(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    result = await integrator.publish_dispatch(
        dispatch={
            "dispatch_id": "dsp_compatibility",
            "request": {"correlation_id": "trace_compatibility"},
        },
        route={"product_id": "bucket-insight"},
        reconstruction={"package_hash": "portable-package-hash"},
        proof={"bundle_hash": "proof-hash"},
    )

    assert requests == []
    assert result["overall_status"] == "canonical-execution-required"
    assert result["skipped_count"] == 8


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
