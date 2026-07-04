from __future__ import annotations

import asyncio
import json
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
from mitra_companion.errors import TransportError
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def _recoverable_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        {
            "product_id": "recoverable-product",
            "display_name": "Recoverable Product",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "remote",
            "base_url": "https://recoverable.invalid",
            "health_endpoint": "/health",
            "capabilities": [
                {
                    "capability_id": "recovery-routing",
                    "description": "Routes to a recoverable HTTP fixture",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "recovery.execute",
                            "description": "Execute recovery fixture",
                            "input_schema": {"type": "object"},
                            "dispatch": {
                                "mode": "http",
                                "endpoint": "/dispatch",
                                "options": {"request_body": "payload"},
                            },
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_attachment_health_monitoring_and_recovery_validation(
    settings_factory,
):
    availability = {"healthy": False}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            status = 200 if availability["healthy"] else 503
            return httpx.Response(
                status,
                json={"status": "healthy" if status == 200 else "down"},
            )
        if request.url.path == "/dispatch":
            if availability["healthy"]:
                return httpx.Response(200, json={"accepted": True})
            return httpx.Response(503, json={"error": "offline"})
        return httpx.Response(404, json={"error": request.url.path})

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        runtime.attach(_recoverable_manifest())
        session = runtime.sessions.create(
            actor_id="recovery-user",
            client_type="embedded",
            workspace_id="recovery-space",
            product_id="recoverable-product",
        )
        with pytest.raises(TransportError):
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=session["session_id"],
                    intent_id="recovery.execute",
                    payload={"value": 1},
                )
            )
        assert runtime.attachments.get("recoverable-product")[
            "state"
        ] == "DEGRADED"

        unhealthy = await runtime.check_attachment_health(
            "recoverable-product"
        )
        assert unhealthy["checks"][0]["health"]["status"] == "unhealthy"
        assert unhealthy["checks"][0]["recovered"] is False

        availability["healthy"] = True
        recovered = await runtime.check_attachment_health(
            "recoverable-product"
        )
        assert recovered["checks"][0]["health"]["status"] == "healthy"
        assert recovered["checks"][0]["recovered"] is True
        assert recovered["checks"][0]["attachment"]["state"] == "ATTACHED"

        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="recovery.execute",
                payload={"value": 2},
            )
        )
        assert result["dispatch"]["status"] == "COMPLETED"
        metrics = runtime.metrics_snapshot()["counters"]
        assert metrics["dispatch_failed_total"] == 1
        assert metrics["recovery_success_total"] == 1
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes(
    tmp_path,
):
    received: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        received.append(request.url.path)
        payload = json.loads(request.content.decode("utf-8") or "{}")
        if request.url.path == "/runtime/execute":
            return httpx.Response(
                200,
                json={
                    "schema_version": "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1",
                    "response_payload": {"answer": payload["query"]},
                    "trace_id": "restart-test",
                },
            )
        if request.url.path == "/tools/predict":
            return httpx.Response(
                200,
                json={
                    "metadata": {"count": len(payload["symbols"])},
                    "predictions": [{"symbol": payload["symbols"][0]}],
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    settings = RuntimeSettings(
        service_root=ROOT,
        data_root=tmp_path,
        database_path=tmp_path / "restart.db",
        telemetry_log_path=tmp_path / "restart-telemetry.jsonl",
        http_timeout_seconds=0.2,
    )
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    first = CompanionRuntime(settings, transport=transport)
    first.start()
    first.attach_many(
        [
            _manifest("product-uniguru-runtime.json"),
            _manifest("product-trade-bot-main.json"),
        ]
    )
    session = first.sessions.create(
        actor_id="restart-user",
        client_type="embedded",
        workspace_id="restart-space",
        product_id="uniguru-ai",
    )
    first.stop()

    second = CompanionRuntime(settings, transport=transport)
    second.start()
    try:
        assert set(second.status()["attached_products"]) == {
            "uniguru-ai",
            "trade-bot-main",
        }
        assert second.sessions.get(session["session_id"])[
            "active_product_id"
        ] == "uniguru-ai"
        result = await second.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="uniguru.execute-query",
                payload={"query": "restart continuity", "emit_proof": False},
            )
        )
        assert result["dispatch"]["status"] == "COMPLETED"
        assert received[-1] == "/runtime/execute"
    finally:
        second.stop()


@pytest.mark.asyncio
async def test_bhiv_dispatch_concurrency_metrics_and_structured_log(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.001)
        payload = json.loads(request.content.decode("utf-8") or "{}")
        if request.url.path == "/runtime/execute":
            return httpx.Response(
                200,
                json={
                    "schema_version": "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1",
                    "response_payload": {"answer": payload["query"]},
                    "trace_id": "load-test",
                },
            )
        if request.url.path == "/tools/predict":
            return httpx.Response(
                200,
                json={
                    "metadata": {"count": len(payload["symbols"])},
                    "predictions": [{"symbol": payload["symbols"][0]}],
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        runtime.attach_many(
            [
                _manifest("product-uniguru-runtime.json"),
                _manifest("product-trade-bot-main.json"),
            ]
        )
        uniguru_session = runtime.sessions.create(
            actor_id="load-user",
            client_type="embedded",
            workspace_id="learning-load",
            product_id="uniguru-ai",
        )
        trade_session = runtime.sessions.create(
            actor_id="load-user",
            client_type="standalone",
            workspace_id="trading-load",
            product_id="trade-bot-main",
        )

        async def dispatch_one(index: int) -> dict[str, Any]:
            if index % 2 == 0:
                return await runtime.dispatch(
                    IntentDispatchRequest(
                        session_id=uniguru_session["session_id"],
                        intent_id="uniguru.execute-query",
                        payload={
                            "query": f"question {index}",
                            "emit_proof": False,
                        },
                    )
                )
            return await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=trade_session["session_id"],
                    intent_id="tradebot.predict",
                    payload={
                        "symbols": ["RELIANCE.NS"],
                        "horizon": "intraday",
                    },
                )
            )

        results = await asyncio.gather(
            *(dispatch_one(index) for index in range(30))
        )
        assert {item["dispatch"]["status"] for item in results} == {
            "COMPLETED"
        }
        assert runtime.store.counts()["dispatches"] == 30
        metrics = runtime.metrics_snapshot()
        assert metrics["counters"]["dispatch_completed_total"] == 30
        assert metrics["dispatch_latency_ms"]["count"] == 30
        assert set(metrics["dispatch_latency_by_product"]) == {
            "uniguru-ai",
            "trade-bot-main",
        }

        lines = settings.telemetry_log_path.read_text(
            encoding="utf-8"
        ).splitlines()
        events = [json.loads(line) for line in lines]
        assert any(
            event["event_type"] == "dispatch.completed"
            for event in events
        )
        assert {
            event["service"]
            for event in events
            if event["event_type"].startswith("dispatch.")
        } == {"mitra-companion-runtime"}
        assert {
            event["environment"]
            for event in events
            if event["event_type"].startswith("dispatch.")
        } == {"production"}
        assert {
            event["runtime_instance_id"]
            for event in events
            if event["event_type"].startswith("dispatch.")
        } == {settings.runtime_instance_id}
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_multiple_runtime_instances_share_state_routes_and_dispatch(
    tmp_path,
):
    received: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8") or "{}")
        received.append((request.url.path, request.headers.get("x-session-id", "")))
        if request.url.path == "/runtime/execute":
            return httpx.Response(
                200,
                json={
                    "schema_version": "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1",
                    "response_payload": {"answer": payload["query"]},
                    "trace_id": "multi-instance",
                },
            )
        if request.url.path == "/tools/predict":
            return httpx.Response(
                200,
                json={
                    "metadata": {"count": len(payload["symbols"])},
                    "predictions": [{"symbol": payload["symbols"][0]}],
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    database_path = tmp_path / "multi-instance.db"
    shared = {
        "service_root": ROOT,
        "data_root": tmp_path,
        "database_path": database_path,
        "http_timeout_seconds": 0.2,
    }
    first_settings = RuntimeSettings(
        **shared,
        telemetry_log_path=tmp_path / "runtime-a.jsonl",
        runtime_instance_id="runtime-a",
    )
    second_settings = RuntimeSettings(
        **shared,
        telemetry_log_path=tmp_path / "runtime-b.jsonl",
        runtime_instance_id="runtime-b",
    )
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    first = CompanionRuntime(first_settings, transport=transport)
    second = CompanionRuntime(second_settings, transport=transport)
    first.start()
    second.start()
    try:
        first.attach_many(
            [
                _manifest("product-uniguru-runtime.json"),
                _manifest("product-trade-bot-main.json"),
            ]
        )
        session = first.sessions.create(
            actor_id="multi-instance-user",
            client_type="embedded",
            workspace_id="multi-instance-space",
            product_id="uniguru-ai",
        )

        routed_by_second = await second.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="uniguru.execute-query",
                payload={"query": "shared route", "emit_proof": False},
            )
        )
        assert routed_by_second["dispatch"]["status"] == "COMPLETED"
        assert routed_by_second["route"]["product_id"] == "uniguru-ai"

        instances = second.runtime_instances()
        assert {item["instance_id"] for item in instances} == {
            "runtime-a",
            "runtime-b",
        }
        assert second.status()["active_runtime_instance_count"] == 2

        first.stop()
        after_first_stop = second.runtime_instances()
        assert {item["instance_id"] for item in after_first_stop} == {
            "runtime-b"
        }
        assert second.status()["accepting"] is True

        trade_session = second.sessions.create(
            actor_id="multi-instance-user",
            client_type="standalone",
            workspace_id="multi-instance-trading",
            product_id="trade-bot-main",
        )
        routed_after_stop = await second.dispatch(
            IntentDispatchRequest(
                session_id=trade_session["session_id"],
                intent_id="tradebot.predict",
                payload={"symbols": ["RELIANCE.NS"], "horizon": "intraday"},
            )
        )
        assert routed_after_stop["dispatch"]["status"] == "COMPLETED"
        assert received[-1][0] == "/tools/predict"
    finally:
        second.stop()
        try:
            first.stop()
        except KeyError:
            pass


def test_observability_api_exposes_metrics_telemetry_and_attachment_health(
    settings_factory,
    atlas_manifest,
):
    app = create_app(settings_factory())
    with TestClient(app) as client:
        client.post(
            "/api/v1/attachments",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "manifest": atlas_manifest.model_dump(mode="json"),
            },
        )
        session = client.post(
            "/api/v1/sessions",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "actor_id": "ops-user",
                "client_type": "embedded",
                "workspace_id": "ops-space",
                "product_id": "atlas-workspace",
            },
        ).json()["session"]
        dispatched = client.post(
            "/api/v1/intents/dispatch",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "session_id": session["session_id"],
                "intent_id": "workspace.show-queue",
                "payload": {"queue_id": "ops"},
            },
        )
        assert dispatched.status_code == 200

        metrics = client.get("/api/v1/runtime/metrics")
        assert metrics.json()["metrics"]["counters"][
            "dispatch_completed_total"
        ] == 1
        assert "mitra_dispatch_total 1" in client.get("/metrics").text
        telemetry = client.get("/api/v1/runtime/telemetry")
        assert any(
            event["event_type"] == "dispatch.completed"
            for event in telemetry.json()["events"]
        )
        health = client.post("/api/v1/attachments/health")
        assert health.status_code == 200
        assert health.json()["checked_count"] == 1
        runtime_health = client.get("/health").json()
        assert runtime_health["opentelemetry"]["enabled"] is True
        assert runtime_health["opentelemetry"][
            "service_name"
        ] == "mitra-companion-runtime"
        instances = client.get("/api/v1/runtime/instances")
        assert instances.status_code == 200
        assert instances.json()["instances"]


def test_production_tactics_are_deployed_as_first_class_artifacts():
    root = ROOT
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    cli = (
        root
        / "pratham"
        / "companion-runtime"
        / "mitra_companion"
        / "cli.py"
    ).read_text(encoding="utf-8")
    observability = (
        root
        / "pratham"
        / "companion-runtime"
        / "mitra_companion"
        / "observability.py"
    ).read_text(encoding="utf-8")
    otel_config = (root / "deploy" / "otel-collector-config.yaml").read_text(
        encoding="utf-8"
    )
    k6_script = (root / "scripts" / "load" / "k6_companion_runtime.js").read_text(
        encoding="utf-8"
    )

    for dependency in [
        "opentelemetry-api",
        "opentelemetry-exporter-otlp",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-sdk",
    ]:
        assert dependency in requirements
        assert dependency in pyproject

    assert "FastAPIInstrumentor.instrument_app" in observability
    assert "OTLPSpanExporter" in observability
    assert "MITRA_COMPANION_ENVIRONMENT=production" in dockerfile
    assert "MITRA_COMPANION_UVICORN_WORKERS" in compose
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in compose
    assert "otel-collector" in compose
    assert "proxy_headers=True" in cli
    assert "workers=max(1, args.workers)" in cli
    assert "runtime_instance_id" in (
        root
        / "pratham"
        / "companion-runtime"
        / "mitra_companion"
        / "config.py"
    ).read_text(encoding="utf-8")
    assert "/api/v1/runtime/instances" in (
        root
        / "pratham"
        / "companion-runtime"
        / "mitra_companion"
        / "api.py"
    ).read_text(encoding="utf-8")
    assert "prometheus:" in otel_config
    assert "endpoint: 0.0.0.0:8889" in otel_config

    assert 'import http from "k6/http"' in k6_script
    assert "ramping-vus" in k6_script
    assert "http_req_failed" in k6_script
    assert "product-uniguru-runtime.json" in k6_script
    assert "product-trade-bot-main.json" in k6_script
    assert "/api/v1/intents/dispatch" in k6_script
