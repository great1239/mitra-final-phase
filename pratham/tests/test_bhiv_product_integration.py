from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    path = ROOT / "contracts" / "examples" / name
    return ProductAttachmentManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


@pytest.mark.asyncio
async def test_bhiv_products_attach_create_sessions_and_dispatch(
    settings_factory,
):
    received: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8") or "{}")
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "uniguru-live-reasoning",
                },
            )
        if request.url.path == "/tools/health":
            return httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "service": "trade-bot-main",
                },
            )
        received.append(
            {
                "path": request.url.path,
                "payload": payload,
                "session": request.headers["X-Companion-Session"],
                "correlation": request.headers["X-Correlation-ID"],
            }
        )
        if request.url.path == "/runtime/execute":
            return httpx.Response(
                200,
                json={
                    "schema_version": "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1",
                    "response_payload": {"answer": "balanced diet"},
                    "trace_id": "uniguru-test",
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

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        manifests = [
            _manifest("product-uniguru-runtime.json"),
            _manifest("product-trade-bot-main.json"),
        ]
        attached = runtime.attach_many(manifests)
        assert attached["attached_count"] == 2
        assert {
            item["product_id"] for item in attached["attachments"]
        } == {"uniguru-ai", "trade-bot-main"}

        uniguru_session = runtime.sessions.create(
            actor_id="bhiv-user",
            client_type="embedded",
            workspace_id="learning-workspace",
            product_id="uniguru-ai",
        )
        trade_session = runtime.sessions.create(
            actor_id="bhiv-user",
            client_type="standalone",
            workspace_id="trading-workspace",
            product_id="trade-bot-main",
        )

        uniguru_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=uniguru_session["session_id"],
                intent_id="uniguru.execute-query",
                payload={
                    "query": "What is a balanced diet?",
                    "grade": 6,
                    "subject": "Science",
                    "emit_proof": False,
                },
            )
        )
        trade_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=trade_session["session_id"],
                intent_id="tradebot.predict",
                payload={
                    "symbols": ["RELIANCE.NS"],
                    "horizon": "intraday",
                    "risk_profile": "moderate",
                },
            )
        )

        assert uniguru_dispatch["dispatch"]["status"] == "COMPLETED"
        assert trade_dispatch["dispatch"]["status"] == "COMPLETED"
        assert runtime.store.counts()["dispatches"] == 2
        assert [item["path"] for item in received] == [
            "/runtime/execute",
            "/tools/predict",
        ]
        assert received[0]["payload"] == {
            "query": "What is a balanced diet?",
            "grade": 6,
            "subject": "Science",
            "emit_proof": False,
        }
        assert received[1]["payload"] == {
            "symbols": ["RELIANCE.NS"],
            "horizon": "intraday",
            "risk_profile": "moderate",
        }
        metrics = runtime.metrics_snapshot()
        assert metrics["counters"]["dispatch_completed_total"] == 2
        assert set(metrics["dispatch_latency_by_product"]) == {
            "uniguru-ai",
            "trade-bot-main",
        }
        health = await runtime.check_attachment_health()
        assert health["checked_count"] == 2
        assert {
            item["product_id"]: item["health"]["status"]
            for item in health["checks"]
        } == {
            "uniguru-ai": "healthy",
            "trade-bot-main": "healthy",
        }
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_http_adapter_can_post_native_payload_body(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {"value": 42}
        assert "dispatch_id" not in payload
        return httpx.Response(200, json={"accepted": True})

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "native-http-product",
                "display_name": "Native HTTP Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://native.invalid",
                "capabilities": [
                    {
                        "capability_id": "native-capability",
                        "description": "Native payload projection fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "native.execute",
                                "description": "Execute native payload",
                                "input_schema": {
                                    "type": "object",
                                    "required": ["value"],
                                },
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/execute",
                                    "options": {"request_body": "payload"},
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="native-user",
            client_type="standalone",
            workspace_id="native-workspace",
            product_id="native-http-product",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="native.execute",
                payload={"value": 42},
            )
        )
        assert result["dispatch"]["response"] == {"accepted": True}
    finally:
        runtime.stop()
