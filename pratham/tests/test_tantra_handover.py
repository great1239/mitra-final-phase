from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator

from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.tantra_handover import (
    PACKAGE_ARTIFACT_TYPE,
    RECEIPT_ARTIFACT_TYPE,
    TantraHandoverAdapter,
)
from mitra_companion.utils import sha256_json


ROOT = Path(__file__).resolve().parents[2]


def _manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (
            ROOT
            / "contracts"
            / "examples"
            / "product-bucket-insight.json"
        ).read_text(encoding="utf-8")
    )


async def _dispatch(runtime: CompanionRuntime) -> dict[str, Any]:
    runtime.attach(_manifest())
    session = runtime.sessions.create(
        actor_id="tantra-contract-runner",
        client_type="standalone",
        workspace_id="tantra-handover",
        product_id="bucket-insight",
    )
    return await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            product_id="bucket-insight",
            capability_id="artifact-insight",
            intent_id="bucket.lookup-artifact",
            payload={
                "artifact_hash": "tantra-contract-artifact",
                "review_depth": "full",
            },
        )
    )


def _wire_hash(value: dict[str, Any]) -> str:
    rendered = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_handover_is_real_package_projection_without_local_authority(
    settings_factory,
):
    runtime = CompanionRuntime(settings_factory())
    runtime.start()
    try:
        result = await _dispatch(runtime)
        stored_packages = runtime.depository.artifacts(
            artifact_type=PACKAGE_ARTIFACT_TYPE,
            limit=10,
        )
        convergence_artifact = runtime.depository.artifact(
            result["ecosystem_convergence"]["artifact_hash"]
        )
        package = stored_packages[0]["artifact"]
        repeated_record = runtime.tantra_handover._persist_package(
            dispatch_id=result["dispatch"]["dispatch_id"],
            package=package,
        )
        tantra_lineage = [
            item
            for item in runtime.depository.lineage(
                subject_type="dispatch",
                subject_id=result["dispatch"]["dispatch_id"],
                limit=500,
            )
            if item.get("metadata", {}).get("artifact_type")
            == PACKAGE_ARTIFACT_TYPE
        ]
    finally:
        runtime.stop()

    handoff = result["ecosystem_convergence"]["handoffs"][0]
    assert result["dispatch"]["status"] == "COMPLETED"
    assert handoff["status"] == "skipped"
    assert handoff["reason"] == "gateway-not-configured"
    assert handoff["package_produced"] is True
    assert len(stored_packages) == 1

    assert repeated_record["artifact_hash"] == stored_packages[0][
        "artifact_hash"
    ]
    assert len(tantra_lineage) == 1
    validation = TantraHandoverAdapter.validate(package)
    assert validation["valid"] is True
    assert validation["checks"]["portable_reconstruction"]["status"] == (
        "verified"
    )
    assert validation["checks"]["execution_identical"] is True

    schema = json.loads(
        (
            ROOT / "contracts" / "schemas" / "tantra-handover.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert list(Draft202012Validator(schema).iter_errors(package)) == []

    source = package["evidence_bundle"]
    assert len(source["trace_id"]) == 64
    assert source["decision_chain"] == []
    assert source["authority_chain"] == []
    assert source["governance_findings"] == []
    assert source["payload"]["dispatch_id"] == result["dispatch"]["dispatch_id"]

    handover_items = {
        item["item_reference"]: item["item_hash"]
        for item in package["handover_bundle"]["handover_items"]
    }
    assert handover_items == {
        "evidence_bundle.json": _wire_hash(package["evidence_bundle"]),
        "lineage_bundle.json": _wire_hash(package["lineage_bundle"]),
        "replay_bundle.json": _wire_hash(package["replay_bundle"]),
    }

    assert convergence_artifact is not None
    assert convergence_artifact["artifact"]["handoffs"] == [handoff]
    assert convergence_artifact["artifact_hash"] == sha256_json(
        convergence_artifact["artifact"]
    )
    with runtime.store.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "tantra_ingestions" not in tables


@pytest.mark.asyncio
async def test_gateway_receives_exact_published_contract_and_api_key(
    settings_factory,
):
    settings = settings_factory()
    settings.tantra_gateway_url = "https://tantra.test"
    settings.tantra_api_key = "runtime-secret"
    observed: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        observed.append(
            {
                "url": str(request.url),
                "api_key": request.headers.get("X-API-Key"),
                "payload": payload,
            }
        )
        trace_id = payload["evidence_bundle"]["trace_id"]
        return httpx.Response(
            200,
            json={
                "trace_id": trace_id,
                "result": {"trace_id": trace_id, "status": "COMPLETED"},
            },
        )

    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await _dispatch(runtime)
        artifacts = runtime.depository.artifacts(limit=100)
    finally:
        runtime.stop()

    assert len(observed) == 1
    call = observed[0]
    assert call["url"] == (
        "https://tantra.test/api/v1/execute/evidence-package"
    )
    assert call["api_key"] == "runtime-secret"
    assert call["payload"]["integration_mode"] == "auto"
    assert set(call["payload"]) == {
        "evidence_bundle",
        "lineage_bundle",
        "replay_bundle",
        "handover_bundle",
        "integration_mode",
        "metadata",
    }
    handoff = result["ecosystem_convergence"]["handoffs"][0]
    assert handoff["status"] == "accepted"
    assert handoff["retryable"] is False
    assert handoff["response"]["trace_id"] == handoff["trace_id"]
    assert "runtime-secret" not in json.dumps(artifacts)


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(400, False), (429, True), (503, True)],
)
@pytest.mark.asyncio
async def test_gateway_failures_are_classified_without_failing_product(
    settings_factory,
    status_code,
    retryable,
):
    settings = settings_factory()
    settings.tantra_gateway_url = "https://tantra.test"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "not accepted"})

    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await _dispatch(runtime)
        receipts = runtime.depository.artifacts(
            artifact_type=RECEIPT_ARTIFACT_TYPE,
            limit=10,
        )
    finally:
        runtime.stop()

    handoff = result["ecosystem_convergence"]["handoffs"][0]
    assert result["dispatch"]["status"] == "COMPLETED"
    assert result["ecosystem_convergence"]["overall_status"] == (
        "canonical-execution-required"
    )
    assert handoff["status"] == "failed"
    assert handoff["http_status"] == status_code
    assert handoff["retryable"] is retryable
    assert len(receipts) == 1
    assert receipts[0]["artifact"]["delivery_status"] == "REJECTED"


@pytest.mark.asyncio
async def test_gateway_trace_mutation_is_rejected(settings_factory):
    settings = settings_factory()
    settings.tantra_gateway_url = "https://tantra.test"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"trace_id": "0" * 64})

    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await _dispatch(runtime)
    finally:
        runtime.stop()

    handoff = result["ecosystem_convergence"]["handoffs"][0]
    assert result["dispatch"]["status"] == "COMPLETED"
    assert handoff["status"] == "failed"
    assert handoff["retryable"] is False
    assert handoff["error_code"] == "trace-continuity-failed"


@pytest.mark.asyncio
async def test_gateway_timeout_is_retryable_and_does_not_escape(
    settings_factory,
):
    settings = settings_factory()
    settings.tantra_gateway_url = "https://tantra.test"

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("gateway timeout", request=request)

    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await _dispatch(runtime)
    finally:
        runtime.stop()

    handoff = result["ecosystem_convergence"]["handoffs"][0]
    assert result["dispatch"]["status"] == "COMPLETED"
    assert handoff["status"] == "failed"
    assert handoff["retryable"] is True
    assert handoff["error_code"] == "gateway-unavailable"


def test_tampered_handover_fails_validation():
    package = {
        "package_type": "mitra-tantra-handover-package-v1",
        "package_hash": "0" * 64,
        "evidence_bundle": {},
        "lineage_bundle": {},
        "replay_bundle": {},
        "handover_bundle": {},
    }
    result = TantraHandoverAdapter.validate(package)
    assert result["valid"] is False
    assert "package hash verification failed" in result["errors"]
