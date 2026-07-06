from __future__ import annotations

from fastapi.testclient import TestClient

from mitra_companion.api import create_app


EXPECTED_DISPATCH_PHASES = [
    "request.accepted",
    "route.selected",
    "payload.validated",
    "context.loaded",
    "transport.dispatched",
    "receipt.persisted",
    "dispatch.completed",
]


def test_versioned_api_end_to_end(settings_factory, atlas_manifest):
    app = create_app(settings_factory())
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "Companion Runtime" in client.get("/").text

        attach = client.post(
            "/api/v1/attachments",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "manifest": atlas_manifest.model_dump(mode="json"),
            },
        )
        assert attach.status_code == 201, attach.text
        assert attach.json()["attachment"]["intent_registration_count"] == 2

        registrations = client.get(
            "/api/v1/products/atlas-workspace/intent-registrations"
        )
        assert registrations.status_code == 200, registrations.text
        assert registrations.json()["registration"][
            "registration_count"
        ] == 2

        capabilities = client.get(
            "/api/v1/capabilities",
            params={"product_id": "atlas-workspace"},
        )
        assert capabilities.status_code == 200, capabilities.text
        assert capabilities.json()["capabilities"][0][
            "capability_id"
        ] == "workspace-navigation"

        capability = client.get(
            "/api/v1/products/atlas-workspace/capabilities/"
            "workspace-navigation"
        )
        assert capability.status_code == 200, capability.text
        assert capability.json()["capability"]["intent_count"] == 2

        filtered_intents = client.get(
            "/api/v1/intents",
            params={
                "product_id": "atlas-workspace",
                "intent_id": "workspace.show-queue",
            },
        )
        assert filtered_intents.status_code == 200
        assert [
            item["intent_id"]
            for item in filtered_intents.json()["intents"]
        ] == ["workspace.show-queue"]

        created = client.post(
            "/api/v1/sessions",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "actor_id": "api-user",
                "client_type": "embedded",
                "workspace_id": "atlas",
                "product_id": "atlas-workspace",
            },
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["session"]["session_id"]
        resume_token = created.json()["session"]["resume_token"]

        updated = client.patch(
            f"/api/v1/sessions/{session_id}/context",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "scope": "workspace",
                "patch": {"view": "pipeline"},
                "expected_revision": 0,
                "replace": False,
            },
        )
        assert updated.status_code == 200, updated.text

        loaded = client.get(
            f"/api/v1/sessions/{session_id}/context",
            params=[("scope", "workspace")],
        )
        assert loaded.status_code == 200, loaded.text
        assert loaded.json()["context"]["loaded_scopes"] == ["workspace"]
        assert set(loaded.json()["context"]["partitions"]) == {"workspace"}

        dispatched = client.post(
            "/api/v1/intents/dispatch",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "session_id": session_id,
                "intent_id": "workspace.show-queue",
                "payload": {"queue_id": "my-work"},
            },
        )
        assert dispatched.status_code == 200, dispatched.text
        assert dispatched.json()["dispatch"]["status"] == "COMPLETED"
        dispatch_id = dispatched.json()["dispatch"]["dispatch_id"]

        catalog = client.get("/api/v1/runtime/capability-catalog")
        assert catalog.status_code == 200, catalog.text
        assert catalog.json()["catalog"]["product_count"] == 1
        assert catalog.json()["catalog"]["compatible"] is True

        phases = client.get(f"/api/v1/dispatches/{dispatch_id}/phases")
        assert phases.status_code == 200, phases.text
        assert [item["phase_name"] for item in phases.json()["phases"]] == [
            *EXPECTED_DISPATCH_PHASES,
        ]

        proof = client.get(f"/api/v1/dispatches/{dispatch_id}/proof")
        assert proof.status_code == 200, proof.text
        assert proof.json()["proof"]["proof_type"] == (
            "mitra-dispatch-proof-v1"
        )
        assert proof.json()["proof"]["phase_summary"]["complete"] is True
        assert proof.json()["proof"]["bundle_hash"]

        suspended = client.post(
            f"/api/v1/sessions/{session_id}/suspend",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
            },
        )
        assert suspended.status_code == 200
        assert suspended.json()["session"]["state"] == "SUSPENDED"

        resumed = client.post(
            f"/api/v1/sessions/{session_id}/resume",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "resume_token": resume_token,
            },
        )
        assert resumed.status_code == 200
        assert resumed.json()["session"]["state"] == "ACTIVE"

        closed = client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
            },
        )
        assert closed.status_code == 200
        assert closed.json()["session"]["state"] == "CLOSED"


def test_invalid_contract_returns_stable_error(settings_factory):
    app = create_app(settings_factory())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "schema_version": "1.0.0",
                "contract_version": "9.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "actor_id": "api-user",
                "client_type": "standalone",
                "workspace_id": "home",
            },
        )
        assert response.status_code == 422
