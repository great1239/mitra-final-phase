from __future__ import annotations

from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.contracts import ProductAttachmentManifest


def _market_manifest() -> ProductAttachmentManifest:
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
                    "description": "Prediction capability for market symbols",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "predict.market",
                            "description": "Predict requested market symbols",
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


def _attach_market(client: TestClient) -> None:
    response = client.post(
        "/api/v1/attachments",
        json={
            "schema_version": "1.0.0",
            "contract_version": "1.0.0",
            "runtime_version": "1.0.0",
            "compatibility_version": "mitra-companion-1",
            "manifest": _market_manifest().model_dump(mode="json"),
        },
    )
    assert response.status_code == 201, response.text


def test_frontend_connector_routes_into_mitra_runtime(settings_factory):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        _attach_market(client)

        capabilities = client.get("/api/companion/capabilities")
        assert capabilities.status_code == 200, capabilities.text
        capability_body = capabilities.json()
        assert capability_body["connector"]["target"] == (
            "mitra-companion-runtime-v1"
        )
        assert capability_body["capabilities"][0]["capability"] == (
            "market-prediction"
        )
        assert capability_body["capabilities"][0]["intents"][0][
            "intent_id"
        ] == "predict.market"

        greeting = client.get("/api/companion/greeting/frontend-user")
        assert greeting.status_code == 200, greeting.text
        assert "attached BHIV runtimes" in greeting.json()["greeting"]

        chat = client.post(
            "/api/companion/chat",
            json={
                "user_id": "frontend-user",
                "message": "Show my market prediction for INFY",
                "platform": "web",
            },
        )
        assert chat.status_code == 200, chat.text
        chat_body = chat.json()
        assert chat_body["status"] == "COMPLETED"
        assert chat_body["intent"] == "predict.market"
        assert chat_body["capability_result"]["capability"] == (
            "market-prediction"
        )
        assert chat_body["capability_result"]["status"] == "success"
        assert chat_body["session_id"].startswith("ses_")
        assert chat_body["mitra_runtime"]["dispatch_id"].startswith("dsp_")
        assert chat_body["mitra_runtime"]["trace_endpoints"][
            "reconstruction"
        ].endswith("/reconstruction")

        memory = client.get("/api/companion/memory/frontend-user")
        assert memory.status_code == 200, memory.text
        memory_body = memory.json()
        assert memory_body["session_id"] == chat_body["session_id"]
        assert memory_body["facts"]["last_status"] == "COMPLETED"
        assert memory_body["messages"][-1]["status"] == "COMPLETED"


def test_frontend_workflow_uses_canonical_ecosystem_and_fails_closed(
    settings_factory,
):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        _attach_market(client)

        workflow = client.post(
            "/api/workflow/run",
            json={
                "workflow_name": "market-prediction",
                "user_id": "workflow-user",
                "message": "Show my market prediction for TCS",
                "payload": {
                    "symbols": ["TCS"],
                    "raj_workflow": {
                        "action_type": "task",
                        "title": "Run market prediction",
                    },
                },
            },
        )

        assert workflow.status_code == 503, workflow.text
        body = workflow.json()
        assert body["error"]["code"] == "ECOSYSTEM_INTEGRATION_NOT_READY"
        assert (
            "missing: raj, ashmit, keshav, bucket, karma, prana, "
            "insightflow, central_depository"
        ) in body["error"]["message"]
        executions = client.get("/api/v1/ecosystem/executions")
        assert executions.status_code == 200, executions.text
        rows = executions.json()["executions"]
        assert len(rows) == 1
        assert rows[0]["status"] == "FAILED"
        assert rows[0]["current_stage"] == "dependency-preflight"
        assert rows[0]["request"]["payload"]["raj_workflow"][
            "action_type"
        ] == "task"
        dispatches = client.get("/api/v1/dispatches")
        assert dispatches.status_code == 200, dispatches.text
        assert dispatches.json()["dispatches"] == []
        assert rows[0]["request"]["metadata"]["frontend_route"] == (
            "/api/workflow/run"
        )


def test_frontend_connector_allows_configured_browser_origin(
    settings_factory,
):
    app = create_app(settings_factory())

    with TestClient(app) as client:
        preflight = client.options(
            "/api/companion/chat",
            headers={
                "Origin": "https://mitra.blackholeinfiverse.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-api-key",
            },
        )

        assert preflight.status_code == 200, preflight.text
        assert preflight.headers["access-control-allow-origin"] == (
            "https://mitra.blackholeinfiverse.com"
        )
