from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.contracts import (
    CompanionMessageRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def _sparse_market_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        {
            "product_id": "market-bridge",
            "display_name": "Market Bridge",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "capabilities": [
                {
                    "capability_id": "market-prediction",
                    "description": "Prediction capability",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "predict.market",
                            "description": "Predict requested symbols",
                            "input_schema": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["symbols"],
                                "properties": {
                                    "symbols": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                },
                            },
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": "loopback://market/predict",
                            },
                        }
                    ],
                }
            ],
        }
    )


def _fallback_market_manifest(
    *,
    product_id: str,
    display_name: str,
    capability_description: str,
    intent_description: str,
) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        {
            "product_id": product_id,
            "display_name": display_name,
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "capabilities": [
                {
                    "capability_id": "market-forecast",
                    "description": capability_description,
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "market.forecast",
                            "description": intent_description,
                            "input_schema": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["symbols"],
                                "properties": {
                                    "symbols": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string"},
                                    }
                                },
                            },
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": f"loopback://{product_id}/forecast",
                            },
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_companion_message_selects_executes_and_persists_memory(
    settings_factory,
):
    received: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8") or "{}")
        received.append({"path": request.url.path, "payload": payload})
        return httpx.Response(
            200,
            json={
                "predictions": [
                    {
                        "symbol": payload["symbols"][0],
                        "direction": "watch",
                    }
                ]
            },
        )

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        runtime.attach(_manifest("product-trade-bot-main.json"))
        result = await runtime.companion_message(
            CompanionMessageRequest(
                actor_id="market-user",
                client_type="standalone",
                workspace_id="market-workspace",
                message="Show my market prediction for RELIANCE.NS",
            )
        )

        assert result["status"] == "COMPLETED"
        assert result["analysis"]["status"] == "matched"
        assert result["analysis"]["recommended_candidate"]["intent_id"] == (
            "tradebot.predict"
        )
        assert result["outcome"]["requested_action"] == "predict"
        assert "market" in result["outcome"]["target_terms"]
        assert result["selection"]["candidate"]["intent_id"] == "tradebot.predict"
        assert result["selection"]["recommendations"][0]["understanding"][
            "required_inputs"
        ] == ["symbols"]
        assert result["payload"] == {"symbols": ["RELIANCE.NS"]}
        assert result["dispatch"]["status"] == "COMPLETED"
        assert result["execution_explanation"]["selected_candidate"] == {
            "product_id": "trade-bot-main",
            "capability_id": "market-prediction",
            "intent_id": "tradebot.predict",
        }
        assert result["execution_explanation"]["fallback"]["used"] is False
        assert received == [
            {
                "path": "/tools/predict",
                "payload": {"symbols": ["RELIANCE.NS"]},
            }
        ]
        memory = runtime.companion_memory(result["session"]["session_id"])
        assert memory["summary"]["slots"]["symbols"] == ["RELIANCE.NS"]
        assert len(memory["messages"]) == 2
        assert memory["tasks"][0]["status"] == "COMPLETED"
        context = runtime.context.load(result["session"]["session_id"])
        assert (
            context["merged"]["companion_memory"]["last_status"]
            == "COMPLETED"
        )
        assert context["merged"]["companion_memory"]["last_analysis"][
            "recommended_candidate"
        ]["intent_id"] == "tradebot.predict"
        metrics = runtime.metrics_snapshot()["counters"]
        assert metrics["companion_messages_total"] == 1
        assert metrics["companion_messages_completed_total"] == 1
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_companion_message_requests_clarification_for_missing_schema_field(
    runtime,
):
    runtime.attach(_manifest("product-trade-bot-main.json"))

    result = await runtime.companion_message(
        CompanionMessageRequest(
            actor_id="market-user",
            client_type="standalone",
            workspace_id="market-workspace",
            message="Show my market prediction",
        )
    )

    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["dispatch"] is None
    assert result["memory"]["open_clarification"] == [
        {
            "field": "symbols",
            "prompt": "Which market symbol should I use?",
        }
    ]
    assert result["selection"]["recommendations"][0]["intent_id"] == (
        "tradebot.predict"
    )


@pytest.mark.asyncio
async def test_companion_understands_sparse_attached_bhiv_capability(
    runtime,
):
    runtime.attach(_sparse_market_manifest())

    result = await runtime.companion_message(
        CompanionMessageRequest(
            actor_id="new-product-user",
            client_type="standalone",
            workspace_id="new-product-space",
            message="Show my market prediction for INFY",
        )
    )

    assert result["status"] == "COMPLETED"
    assert result["outcome"]["requested_action"] == "predict"
    assert result["selection"]["candidate"]["product_id"] == "market-bridge"
    assert result["selection"]["candidate"]["intent_id"] == "predict.market"
    assert result["payload"] == {"symbols": ["INFY"]}
    assert result["dispatch"]["response"]["product_id"] == "market-bridge"
    assert result["memory"]["last_outcome"]["required_result"] == (
        "predict market INFY"
    )


@pytest.mark.asyncio
async def test_ai_analysis_payload_is_used_when_deterministic_payload_is_missing(
    runtime,
    monkeypatch,
):
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "product_id": "market-bridge",
                "capability_id": "market-prediction",
                "intent_id": "predict.market",
                "confidence": 0.91,
                "reason": "AI inferred the missing market symbol from context.",
                "payload": {"symbols": ["INFY"]},
            }

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any]):
            calls.append(json)
            return FakeResponse()

    monkeypatch.setattr(
        "mitra_companion.analysis.httpx.AsyncClient",
        FakeAsyncClient,
    )
    runtime.analyzer.ai_analysis_url = "https://ai.example/runtime-analysis"
    runtime.attach(_sparse_market_manifest())

    result = await runtime.companion_message(
        CompanionMessageRequest(
            actor_id="auto-ai-user",
            client_type="standalone",
            workspace_id="auto-ai-space",
            message="Show my market prediction",
        )
    )

    assert calls
    assert calls[0]["fallback_trigger"]["gaps"] == [
        {"kind": "missing-inputs", "fields": ["symbols"]}
    ]
    assert result["analysis"]["ai_status"] == "used"
    assert result["analysis"]["ai_payload_hints"] == {"symbols": ["INFY"]}
    assert result["status"] == "COMPLETED"
    assert result["payload"] == {"symbols": ["INFY"]}
    assert result["dispatch"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_companion_falls_back_to_next_published_capability(
    settings_factory,
):
    transport = CapabilityTransport(default_timeout_seconds=0.2)

    async def failing_primary(envelope: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("primary product endpoint is offline")

    async def working_fallback(envelope: dict[str, Any]) -> dict[str, Any]:
        return {
            "fallback": True,
            "product_id": envelope["product_id"],
            "payload": envelope["payload"],
        }

    transport.register_handler(
        "alpha-market",
        "market-forecast",
        "market.forecast",
        failing_primary,
    )
    transport.register_handler(
        "beta-market",
        "market-forecast",
        "market.forecast",
        working_fallback,
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        runtime.attach(
            _fallback_market_manifest(
                product_id="alpha-market",
                display_name="Alpha Market",
                capability_description=(
                    "Primary alpha market forecast prediction execution"
                ),
                intent_description=(
                    "Run primary alpha market forecast predictions"
                ),
            )
        )
        runtime.attach(
            _fallback_market_manifest(
                product_id="beta-market",
                display_name="Beta Market",
                capability_description=(
                    "Backup market forecast prediction execution"
                ),
                intent_description="Run backup market forecast predictions",
            )
        )

        result = await runtime.companion_message(
            CompanionMessageRequest(
                actor_id="fallback-user",
                client_type="standalone",
                workspace_id="fallback-workspace",
                message="Use alpha primary market forecast for INFY",
            )
        )

        assert result["status"] == "COMPLETED"
        assert result["dispatch"]["product_id"] == "beta-market"
        assert result["dispatch"]["response"]["fallback"] is True
        assert result["payload"] == {"symbols": ["INFY"]}
        explanation = result["execution_explanation"]
        assert explanation["fallback"]["used"] is True
        assert explanation["fallback"]["used_candidate"] == {
            "product_id": "beta-market",
            "capability_id": "market-forecast",
            "intent_id": "market.forecast",
        }
        assert explanation["fallback"]["attempts"][-1]["status"] == "COMPLETED"
        task = runtime.companion_task(result["task"]["task_id"])
        assert task["status"] == "COMPLETED"
        assert task["result"]["fallback_used"]["product_id"] == "beta-market"
        metrics = runtime.metrics_snapshot()["counters"]
        assert metrics["dispatch_total"] == 2
        assert metrics["dispatch_failed_total"] == 1
        assert metrics["dispatch_completed_total"] == 1
        assert metrics["fallback_dispatch_attempts_total"] == 1
        assert metrics["fallback_dispatch_success_total"] == 1
    finally:
        runtime.stop()


def test_companion_api_exposes_message_memory_task_and_stream(
    settings_factory,
):
    app = create_app(settings_factory())
    manifest = _manifest("product-trade-bot-main.json")

    with TestClient(app) as client:
        attached = client.post(
            "/api/v1/attachments",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "manifest": manifest.model_dump(mode="json"),
            },
        )
        assert attached.status_code == 201, attached.text

        chain = client.get("/api/v1/runtime/chain")
        assert chain.status_code == 200, chain.text
        systems = [item["system"] for item in chain.json()["chain"]["systems"]]
        assert systems[:7] == [
            "Mitra",
            "attached product runtime",
            "TANTRA",
            "SHAKTI",
            "MDU",
            "TMS",
            "Parikshak",
        ]
        assert {
            "Bucket Insight",
            "PRANA",
            "Karma",
            "SETU",
            "KESHAV",
            "SARATHI",
        }.issubset(systems)
        assert chain.json()["chain"]["known_capabilities"][0][
            "product_id"
        ] == "trade-bot-main"

        message = client.post(
            "/api/v1/companion/messages",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "actor_id": "api-market-user",
                "client_type": "standalone",
                "workspace_id": "api-market-workspace",
                "message": "Show my market prediction",
            },
        )
        assert message.status_code == 200, message.text
        body = message.json()
        assert body["status"] == "NEEDS_CLARIFICATION"
        session_id = body["session"]["session_id"]

        memory = client.get(
            f"/api/v1/companion/sessions/{session_id}/memory"
        )
        assert memory.status_code == 200, memory.text
        assert memory.json()["memory"]["summary"]["last_status"] == (
            "NEEDS_CLARIFICATION"
        )

        tasks = client.get("/api/v1/companion/tasks")
        assert tasks.status_code == 200, tasks.text
        assert tasks.json()["tasks"] == []

        stream = client.post(
            "/api/v1/companion/messages/stream",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "actor_id": "api-market-user",
                "client_type": "standalone",
                "workspace_id": "api-market-workspace",
                "message": "Show my market prediction",
            },
        )
        assert stream.status_code == 200, stream.text
        assert '"event": "typing"' in stream.text
        assert '"event": "message"' in stream.text
