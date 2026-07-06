from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from mitra_companion.api import create_app
from mitra_companion.contracts import (
    ProductExchangeAckRequest,
    ProductExchangeRequest,
)
from mitra_companion.errors import ResourceConflictError


ROOT = Path(__file__).resolve().parents[2]
VERSIONED = {
    "schema_version": "1.0.0",
    "contract_version": "1.0.0",
    "runtime_version": "1.0.0",
    "compatibility_version": "mitra-companion-1",
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_product_exchange_runtime_persists_inbox_and_acknowledgement(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(nova_manifest)
    session = runtime.sessions.create(
        actor_id="exchange-user",
        client_type="embedded",
        workspace_id="exchange-workspace",
        product_id=atlas_manifest.product_id,
    )

    exchange = runtime.create_product_exchange(
        ProductExchangeRequest(
            source_product_id=atlas_manifest.product_id,
            target_product_ids=[nova_manifest.product_id],
            session_id=session["session_id"],
            workspace_id=session["workspace_id"],
            exchange_type="context",
            subject="portable customer context",
            payload={
                "customer_goal": "compare attached product capability",
                "handoff_reference": "case-42",
            },
            schema_ref="https://contracts.example/context-handoff/1.0.0",
            metadata={"reason": "product handoff"},
        )
    )

    assert exchange["source_product_id"] == atlas_manifest.product_id
    assert exchange["target_product_ids"] == [nova_manifest.product_id]
    assert exchange["targets"][0]["status"] == "PENDING"
    assert runtime.status()["counts"]["product_exchanges"] == 1

    inbox = runtime.product_exchanges(
        target_product_id=nova_manifest.product_id
    )
    assert [item["exchange_id"] for item in inbox] == [
        exchange["exchange_id"]
    ]

    acknowledged = runtime.record_product_exchange_receipt(
        exchange["exchange_id"],
        ProductExchangeAckRequest(
            product_id=nova_manifest.product_id,
            status="CONSUMED",
            note="loaded into target product workflow",
        ),
    )
    assert acknowledged["targets"][0]["status"] == "CONSUMED"
    assert acknowledged["targets"][0]["acknowledgement_note"] == (
        "loaded into target product workflow"
    )

    consumed = runtime.product_exchanges(
        target_product_id=nova_manifest.product_id,
        status="CONSUMED",
    )
    assert [item["exchange_id"] for item in consumed] == [
        exchange["exchange_id"]
    ]


def test_product_exchange_rejects_invalid_relationship(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    with pytest.raises(ResourceConflictError):
        runtime.create_product_exchange(
            ProductExchangeRequest(
                source_product_id=atlas_manifest.product_id,
                target_product_ids=[atlas_manifest.product_id],
                subject="self target is not allowed",
            )
        )


def test_product_exchange_api_contract(settings_factory, atlas_manifest, nova_manifest):
    app = create_app(settings_factory())
    with TestClient(app) as client:
        for manifest in (atlas_manifest, nova_manifest):
            connected = client.post(
                "/api/v1/products/connect",
                json={
                    **VERSIONED,
                    "manifest": manifest.model_dump(mode="json"),
                },
            )
            assert connected.status_code == 201
            assert connected.json()["connection"]["product_id"] == (
                manifest.product_id
            )

        created = client.post(
            "/api/v1/product-exchanges",
            json={
                **VERSIONED,
                "source_product_id": atlas_manifest.product_id,
                "target_product_ids": [nova_manifest.product_id],
                "exchange_type": "artifact",
                "classification": "internal",
                "subject": "shared runtime artifact",
                "payload": {"artifact_id": "artifact-1"},
            },
        )
        assert created.status_code == 201
        exchange = created.json()["exchange"]

        inbox = client.get(
            f"/api/v1/products/{nova_manifest.product_id}/exchange-inbox"
        )
        assert inbox.status_code == 200
        assert [item["exchange_id"] for item in inbox.json()["exchanges"]] == [
            exchange["exchange_id"]
        ]

        ack = client.post(
            f"/api/v1/product-exchanges/{exchange['exchange_id']}/ack",
            json={
                **VERSIONED,
                "product_id": nova_manifest.product_id,
                "status": "RECEIVED",
            },
        )
        assert ack.status_code == 200
        assert ack.json()["exchange"]["targets"][0]["status"] == "RECEIVED"


def test_product_exchange_json_schemas_validate_example_payload():
    request_schema = _json("contracts/schemas/product-exchange.schema.json")
    ack_schema = _json("contracts/schemas/product-exchange-ack.schema.json")
    record_schema = _json(
        "contracts/schemas/product-exchange-record.schema.json"
    )

    Draft202012Validator(request_schema).validate(
        {
            **VERSIONED,
            "source_product_id": "source-product",
            "target_product_ids": ["target-product"],
            "subject": "portable context",
            "payload": {"goal": "handoff"},
        }
    )
    Draft202012Validator(ack_schema).validate(
        {
            **VERSIONED,
            "product_id": "target-product",
            "status": "CONSUMED",
        }
    )
    Draft202012Validator(record_schema).validate(
        {
            "exchange_id": "exchange_123",
            "source_product_id": "source-product",
            "target_product_ids": ["target-product"],
            "targets": [
                {
                    "target_product_id": "target-product",
                    "status": "PENDING",
                    "acknowledgement_metadata": {},
                }
            ],
            "session_id": None,
            "workspace_id": None,
            "exchange_type": "context",
            "classification": "internal",
            "subject": "portable context",
            "payload": {"goal": "handoff"},
            "schema_ref": None,
            "metadata": {},
            "correlation_id": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": None,
        }
    )
