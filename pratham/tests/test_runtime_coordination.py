from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import ResourceConflictError
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.store import RuntimeStore
from mitra_companion.tantra_handover import TantraHandoverAdapter
from mitra_companion.transport import CapabilityTransport
from mitra_companion.utils import sha256_json


ROOT = Path(__file__).resolve().parents[2]


def _settings(
    tmp_path: Path,
    *,
    instance_id: str,
    database_path: Path | None = None,
) -> RuntimeSettings:
    return RuntimeSettings(
        service_root=ROOT,
        data_root=tmp_path,
        database_path=database_path or tmp_path / "coordination.db",
        telemetry_log_path=tmp_path / f"{instance_id}.jsonl",
        runtime_instance_id=instance_id,
        persistent_runtime_enabled=False,
        persistent_coordination_lease_seconds=0.1,
        tantra_delivery_initial_backoff_seconds=0.0,
        allow_example_manifests=True,
        allow_simulated_manifests=True,
        allow_loopback_manifests=True,
        allow_localhost_manifests=True,
        require_production_bootstrap_manifests=False,
    )


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


async def _bucket_dispatch(runtime: CompanionRuntime) -> dict[str, Any]:
    runtime.attach(_manifest("product-bucket-insight.json"))
    session = runtime.sessions.create(
        actor_id="coordination-user",
        client_type="standalone",
        workspace_id="coordination-space",
        product_id="bucket-insight",
    )
    return await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            product_id="bucket-insight",
            capability_id="artifact-insight",
            intent_id="bucket.lookup-artifact",
            payload={"artifact_hash": "coordination-artifact-0001"},
        )
    )


def test_runtime_lease_is_single_owner_and_peer_takes_over(tmp_path):
    database_path = tmp_path / "lease-takeover.db"
    first_settings = _settings(
        tmp_path,
        instance_id="runtime-a",
        database_path=database_path,
    )
    second_settings = _settings(
        tmp_path,
        instance_id="runtime-b",
        database_path=database_path,
    )
    first_settings.persistent_coordination_lease_seconds = 5.0
    second_settings.persistent_coordination_lease_seconds = 5.0
    first = CompanionRuntime(
        first_settings
    )
    second = CompanionRuntime(
        second_settings
    )
    first.start()
    second.start()
    try:
        assert first.status()["persistent_runtime"]["coordinator"] is True
        assert second.status()["persistent_runtime"]["coordinator"] is False
        owner_tick = first.persistent_tick()
        peer_tick = second.persistent_tick()
        assert owner_tick["maintenance"]["continuity"][
            "status"
        ] == "not-evaluated"
        assert peer_tick["maintenance"] is None

        first.stop()
        takeover = second.persistent_tick(run_maintenance=False)
        assert takeover["is_coordinator"] is True
        assert takeover["coordination_lease"]["holder_instance_id"] == (
            "runtime-b"
        )
    finally:
        second.stop()


def test_expired_delivery_lease_is_fenced_and_reclaimed(tmp_path):
    store = RuntimeStore(tmp_path / "delivery-takeover.db")
    request = {"evidence_bundle": {"trace_id": "a" * 64}}
    store.enqueue_integration_delivery(
        delivery_id="delivery-takeover",
        integration_name="tantra",
        dispatch_id="dispatch-takeover",
        trace_id="a" * 64,
        request_hash=sha256_json(request),
        request=request,
        initial_status="PENDING",
    )
    first = store.claim_integration_deliveries(
        integration_name="tantra",
        instance_id="runtime-a",
        lease_seconds=0.1,
        limit=1,
    )[0]
    time.sleep(0.12)
    second = store.claim_integration_deliveries(
        integration_name="tantra",
        instance_id="runtime-b",
        lease_seconds=1.0,
        limit=1,
    )[0]

    assert first["attempts"] == 1
    assert second["attempts"] == 2
    assert first["lease_token"] != second["lease_token"]
    with pytest.raises(ResourceConflictError, match="lease no longer belongs"):
        store.complete_integration_delivery(
            delivery_id=first["delivery_id"],
            instance_id="runtime-a",
            lease_token=first["lease_token"],
            status="ACCEPTED",
            next_attempt_at=None,
            error=None,
            response={"status": "late"},
        )


def test_outbox_claims_100_deliveries_once_across_parallel_workers(tmp_path):
    store = RuntimeStore(tmp_path / "outbox-contention.db")
    for index in range(100):
        request = {
            "evidence_bundle": {
                "trace_id": f"{index:064x}",
                "execution_id": f"execution-{index}",
            }
        }
        store.enqueue_integration_delivery(
            delivery_id=f"delivery-{index:03d}",
            integration_name="tantra",
            dispatch_id=f"dispatch-{index:03d}",
            trace_id=f"{index:064x}",
            request_hash=sha256_json(request),
            request=request,
            initial_status="PENDING",
        )

    barrier = threading.Barrier(4)

    def claim(worker: int) -> list[str]:
        barrier.wait()
        rows = store.claim_integration_deliveries(
            integration_name="tantra",
            instance_id=f"worker-{worker}",
            lease_seconds=30.0,
            limit=25,
        )
        return [row["delivery_id"] for row in rows]

    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed_groups = list(pool.map(claim, range(4)))

    claimed = [item for group in claimed_groups for item in group]
    assert len(claimed) == 100
    assert len(set(claimed)) == 100
    assert all(len(group) == 25 for group in claimed_groups)


@pytest.mark.asyncio
async def test_retry_survives_restart_and_second_runtime_delivers(tmp_path):
    database_path = tmp_path / "retry-restart.db"
    calls: list[bytes] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            trace_id = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={"trace_id": trace_id, "result": {"trace_id": trace_id}},
            )
        calls.append(request.content)
        payload = json.loads(request.content.decode("utf-8"))
        if len(calls) == 1:
            return httpx.Response(503, json={"detail": "temporarily down"})
        trace_id = payload["evidence_bundle"]["trace_id"]
        return httpx.Response(200, json={"trace_id": trace_id})

    first_settings = _settings(
        tmp_path,
        instance_id="runtime-a",
        database_path=database_path,
    )
    first_settings.tantra_gateway_url = "https://tantra.test"
    first = CompanionRuntime(first_settings)
    first.tantra_handover = TantraHandoverAdapter(
        first_settings,
        first.depository,
        http_transport=httpx.MockTransport(handler),
    )
    first.start()
    result = await _bucket_dispatch(first)
    first.stop()

    initial = result["ecosystem_convergence"]["handoffs"][0]
    assert initial["status"] == "failed"
    assert initial["outbox_status"] == "RETRY"
    assert result["dispatch"]["status"] == "COMPLETED"

    second_settings = _settings(
        tmp_path,
        instance_id="runtime-b",
        database_path=database_path,
    )
    second_settings.tantra_gateway_url = "https://tantra.test"
    second = CompanionRuntime(second_settings)
    second.tantra_handover = TantraHandoverAdapter(
        second_settings,
        second.depository,
        http_transport=httpx.MockTransport(handler),
    )
    second.start()
    try:
        processed = await second.process_integration_deliveries()
        reconciled = await second.reconcile_tantra_traces()
        deliveries = second.integration_deliveries(
            dispatch_id=result["dispatch"]["dispatch_id"]
        )
        trace_health = second.dependency_health_status(
            product_id=(
                "tantra-trace:"
                + reconciled["traces"][0]["trace_id"]
            )
        )
        continuity = second.run_continuity_check(limit=10)
    finally:
        second.stop()

    assert processed["processed_count"] == 1
    assert processed["deliveries"][0]["status"] == "accepted"
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert deliveries[0]["status"] == "ACCEPTED"
    assert deliveries[0]["attempts"] == 2
    assert reconciled["status"] == "healthy"
    assert reconciled["checked_count"] == 1
    assert reconciled["traces"][0]["trace_continuity"] is True
    assert trace_health["products"][0]["latest_status"] == "healthy"
    assert continuity["status"] == "healthy"
    dispatch_check = continuity["dispatches"][0]
    assert dispatch_check["status"] == "healthy"
    assert all(item["passed"] for item in dispatch_check["checks"])


@pytest.mark.asyncio
async def test_remote_trace_mutation_fails_continuity_without_reexecution(
    tmp_path,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"trace_id": "0" * 64})
        payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"trace_id": payload["evidence_bundle"]["trace_id"]},
        )

    settings = _settings(tmp_path, instance_id="trace-mutation-runtime")
    settings.tantra_gateway_url = "https://tantra.test"
    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await _bucket_dispatch(runtime)
        reconciled = await runtime.reconcile_tantra_traces()
        continuity = runtime.run_continuity_check(limit=10)
    finally:
        runtime.stop()

    assert result["dispatch"]["status"] == "COMPLETED"
    assert result["ecosystem_convergence"]["handoffs"][0][
        "status"
    ] == "accepted"
    assert reconciled["status"] == "unhealthy"
    assert reconciled["traces"][0]["trace_continuity"] is False
    assert continuity["status"] == "failed"
    checks = {
        item["check"]: item for item in continuity["dispatches"][0]["checks"]
    }
    assert checks["accepted-trace-reconciliation"]["passed"] is False


@pytest.mark.asyncio
async def test_dependency_health_history_records_real_transitions(tmp_path):
    health_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal health_calls
        assert request.url.path == "/health"
        health_calls += 1
        if health_calls == 1:
            return httpx.Response(200, json={"status": "healthy"})
        return httpx.Response(503, json={"status": "unavailable"})

    settings = _settings(tmp_path, instance_id="health-runtime")
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        runtime.attach(_manifest("product-uniguru-runtime.json"))
        first = await runtime.check_attachment_health("uniguru-ai")
        second = await runtime.check_attachment_health("uniguru-ai")
        summary = runtime.dependency_health_status(product_id="uniguru-ai")
    finally:
        runtime.stop()

    assert first["checks"][0]["health"]["status"] == "healthy"
    assert second["checks"][0]["health"]["status"] == "unhealthy"
    product = summary["products"][0]
    assert product["sample_count"] == 2
    assert product["latest_status"] == "unhealthy"
    assert product["healthy_count"] == 1
    assert product["unhealthy_count"] == 1
    assert product["status_changes"] == 1
    assert product["recent_pattern"] == "mixed"


@pytest.mark.asyncio
async def test_gateway_health_uses_published_endpoint_and_records_response(
    tmp_path,
):
    observed: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed.append(
            {
                "method": request.method,
                "path": request.url.path,
                "api_key": request.headers.get("X-API-Key"),
            }
        )
        return httpx.Response(200, json={"status": "healthy"})

    settings = _settings(tmp_path, instance_id="gateway-health-runtime")
    settings.tantra_gateway_url = "https://tantra.test"
    settings.tantra_api_key = "health-secret"
    runtime = CompanionRuntime(settings)
    runtime.tantra_handover = TantraHandoverAdapter(
        settings,
        runtime.depository,
        http_transport=httpx.MockTransport(handler),
    )
    runtime.start()
    try:
        result = await runtime.check_tantra_gateway_health()
        history = runtime.dependency_health_status(
            product_id="tantra-gateway"
        )
    finally:
        runtime.stop()

    assert observed == [
        {"method": "GET", "path": "/health", "api_key": "health-secret"}
    ]
    assert result["health"]["status"] == "healthy"
    assert result["health"]["response"] == {"status": "healthy"}
    assert history["products"][0]["latest_status"] == "healthy"


def test_operator_apis_expose_live_coordination_surfaces(settings_factory):
    settings = settings_factory()
    settings.persistent_runtime_enabled = False
    app = create_app(settings)
    contract = {"schema_version": "1.0.0", "contract_version": "1.0.0"}

    with TestClient(app) as client:
        continuity = client.get("/api/v1/runtime/continuity")
        deliveries = client.get(
            "/api/v1/runtime/integrations/tantra/deliveries"
        )
        processing = client.post(
            "/api/v1/runtime/integrations/tantra/process",
            json=contract,
        )
        health = client.get("/api/v1/runtime/dependencies/health")
        gateway_health = client.get(
            "/api/v1/runtime/integrations/tantra/health"
        )
        reconciled = client.post(
            "/api/v1/runtime/integrations/tantra/reconcile",
            json=contract,
        )
        checked = client.post(
            "/api/v1/runtime/continuity/check?limit=10",
            json=contract,
        )
        metrics = client.get("/metrics")

    assert continuity.status_code == 200
    assert continuity.json()["continuity"]["status"] == "not-run"
    assert deliveries.json()["deliveries"] == []
    assert processing.json()["processing"]["status"] == "skipped"
    assert health.json()["dependency_health"]["product_count"] == 0
    assert gateway_health.json()["integration_health"]["health"][
        "status"
    ] == "not_configured"
    assert reconciled.json()["reconciliation"]["status"] == "skipped"
    assert checked.json()["continuity"]["status"] == "not-evaluated"
    assert "mitra_runtime_coordinator 1" in metrics.text
    assert "mitra_tantra_outbox_deliveries" in metrics.text
