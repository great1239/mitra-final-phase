from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from integration_services.insightflow_bridge import create_app as create_insightflow
from integration_services.karma import DEFAULT_GENESIS_HASH, create_app as create_karma
from integration_services.prana import create_app as create_prana
from integration_services.raj import create_app as create_raj


def test_karma_persists_chain_and_detects_replay(tmp_path) -> None:
    client = TestClient(
        create_karma(
            database_path=tmp_path / "karma.db",
            genesis_hash=DEFAULT_GENESIS_HASH,
        )
    )
    health = client.get("/health").json()
    assert health["storage_backend"] == "sqlite"
    assert health["durable"] is False
    event = {
        "payload": {"value": 1},
        "previous_hash": DEFAULT_GENESIS_HASH,
        "event_id": "event-1",
    }
    appended = client.post("/integrity/append", json=event).json()
    assert appended["status"] == "appended"
    assert len(appended["current_hash"]) == 64

    replay = client.post("/integrity/append", json=event).json()
    assert replay["status"] == "replay_detected"
    assert replay["current_hash"] == appended["current_hash"]

    violation = client.post(
        "/integrity/append-bucket-artifact",
        json={
            "artifact_id": "artifact-bad",
            "trace_id": "trace-bad",
            "parent_hash": DEFAULT_GENESIS_HASH,
        },
    ).json()
    assert violation["status"] == "append_violation"

    artifact = {
        "artifact_id": "artifact-1",
        "trace_id": "trace-1",
        "parent_hash": appended["current_hash"],
        "payload": {"truth": True},
    }
    stored = client.post(
        "/integrity/append-bucket-artifact",
        json=artifact,
    ).json()
    assert stored["status"] == "appended"
    assert stored["trace_id"] == "trace-1"
    entry = client.get("/integrity/entries/artifact-1").json()
    assert entry["payload"] == artifact


def test_prana_forwards_identical_bytes_and_preserves_trace() -> None:
    observed: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.content)
        payload = json.loads(request.content)
        if request.url.path == "/karma":
            import hashlib

            return httpx.Response(
                200,
                json={
                    "status": "accepted",
                    "trace_id": payload["trace_id"],
                    "received_sha256": hashlib.sha256(request.content).hexdigest(),
                },
            )
        return httpx.Response(
            200,
            json={"status": "accepted", "trace_id": payload["trace_id"]},
        )

    app = create_prana(
        strict_target_url="https://insight.test/karma",
        core_target_url="https://insight.test/core",
        target_api_key="bridge-key",
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)
    raw = b'{"artifact_id":"a-1","trace_id":"trace-1"}'
    strict = client.post(
        "/forward/karma-strict",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert strict.status_code == 200
    assert strict.headers["x-prana-strict-bytes-equal"] == "true"
    assert observed[0] == raw

    core_body = b'{"trace_id":"trace-1","source_system":"Mitra"}'
    core = client.post(
        "/forward/core",
        content=core_body,
        headers={"Content-Type": "application/json"},
    )
    assert core.status_code == 200
    assert core.json()["trace_id"] == "trace-1"
    assert observed[1] == core_body


def test_raj_dispatches_selected_manifest_without_product_branch(monkeypatch) -> None:
    monkeypatch.setenv("RAJ_ENDPOINT_OVERRIDES_JSON", "{}")
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"status": "ok", "predictions": [{"symbol": "TCS.NS"}]},
        )

    app = create_raj(transport=httpx.MockTransport(handler))
    client = TestClient(app)
    capability_contract = {
        "product": {"base_url": "https://product.test"},
        "intent": {
            "intent_id": "product.predict",
            "dispatch": {
                "mode": "http",
                "endpoint": "/tools/predict",
                "timeout_seconds": 5,
                "options": {"request_body": "payload"},
            },
            "response_schema": {
                "type": "object",
                "required": ["status", "predictions"],
            },
        },
        "input": {
            "payload": {
                "symbols": ["TCS.NS"],
                "horizon": "short",
                "raj_workflow": {"action_type": "task"},
            }
        },
    }
    response = client.post(
        "/api/workflow/execute",
        json={
            "trace_id": "trace-raj-1",
            "decision": "workflow",
            "data": {
                "workflow_type": "workflow",
                "payload": {
                    "action_type": "task",
                    "mitra_context": {
                        "capability_contract": capability_contract
                    },
                },
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["execution_result"]["success"] is True
    assert observed == {
        "url": "https://product.test/tools/predict",
        "payload": {"horizon": "short", "symbols": ["TCS.NS"]},
    }


def test_raj_returns_typed_product_error_for_conditional_diagnosis(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RAJ_ENDPOINT_OVERRIDES_JSON", "{}")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": "symbols is required"},
        )

    app = create_raj(transport=httpx.MockTransport(handler))
    client = TestClient(app)
    response = client.post(
        "/api/workflow/execute",
        json={
            "trace_id": "trace-raj-product-error",
            "decision": "workflow",
            "data": {
                "workflow_type": "workflow",
                "payload": {
                    "action_type": "task",
                    "mitra_context": {
                        "capability_contract": {
                            "product": {"base_url": "https://product.test"},
                            "intent": {
                                "intent_id": "product.predict",
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/tools/predict",
                                    "options": {"request_body": "payload"},
                                },
                            },
                            "input": {
                                "payload": {
                                    "raj_workflow": {
                                        "action_type": "task"
                                    }
                                }
                            },
                        }
                    },
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "product_error"
    assert body["trace_id"] == "trace-raj-product-error"
    assert body["execution_result"]["success"] is False
    assert body["execution_result"]["http_status"] == 422
    assert body["execution_result"]["error"]["type"] == (
        "product_rejected_workflow"
    )


def test_insightflow_bridge_registers_dataset_and_provenance(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHTFLOW_BRIDGE_API_KEY", "bridge-key")
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "GET" and "/canonical/" in request.url.path:
            return httpx.Response(404, json={"detail": "not found"})
        if request.method == "POST" and request.url.path.endswith("/datasets/"):
            return httpx.Response(201, json={"id": "dataset-1"})
        if request.method == "POST" and request.url.path.endswith("/provenance"):
            return httpx.Response(201, json={"id": "provenance-1"})
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        return httpx.Response(500, json={"detail": "unexpected request"})

    app = create_insightflow(
        registry_base_url="https://registry.test",
        registry_api_key="registry-key",
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)
    response = client.post(
        "/ingest/execution",
        json={
            "event_type": "mitra.tantra.execution.completed.v1",
            "trace_id": "trace-insight-1",
            "execution_id": "execution-1",
            "payload": {"karma_hash": "abc"},
        },
        headers={"X-API-Key": "bridge-key"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "trace_id": "trace-insight-1",
        "received_sha256": response.json()["received_sha256"],
        "dataset_id": "dataset-1",
        "provenance_id": "provenance-1",
        "stage": "execution",
    }
    assert requests == [
        ("GET", "/api/v1/datasets/canonical/BHIV-DS-MITRA-RUNTIME-001"),
        ("POST", "/api/v1/datasets/"),
        ("POST", "/api/v1/datasets/dataset-1/provenance"),
    ]
