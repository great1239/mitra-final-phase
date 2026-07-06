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
        assert systems == [
            "Mitra",
            "attached product runtime",
            "TANTRA",
            "SHAKTI",
            "MDU",
            "TMS",
            "Parikshak",
        ]
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
