from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mitra_companion.api import create_app
from mitra_companion.contracts import IntentDispatchRequest, ProductAttachmentManifest
from mitra_companion.errors import AttachmentValidationError
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _echo_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / "product-echo.json").read_text(
            encoding="utf-8"
        )
    )


def _attachment_record_validator() -> Draft202012Validator:
    record_schema = json.loads(
        (
            ROOT / "contracts" / "schemas" / "attachment-record.schema.json"
        ).read_text(encoding="utf-8")
    )
    manifest_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "product-attachment.schema.json"
        ).read_text(encoding="utf-8")
    )
    registry = Registry().with_resources(
        [
            (
                "https://contracts.mitra.local/product-attachment/1.0.0",
                Resource.from_contents(manifest_schema),
            )
        ]
    )
    return Draft202012Validator(record_schema, registry=registry)


def test_phase4_product_self_attachment_through_public_api(
    settings_factory,
):
    app = create_app(settings_factory())
    manifest = _echo_manifest()
    validator = _attachment_record_validator()

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
        record = attached.json()["attachment"]
        validator.validate(record)
        assert record["product_id"] == "echo-lab"
        assert record["intent_registration_count"] == 1

        discovered = client.get(
            "/api/v1/intents",
            params={"product_id": "echo-lab"},
        )
        assert [item["intent_id"] for item in discovered.json()["intents"]] == [
            "echo.repeat"
        ]

        detached = client.delete("/api/v1/attachments/echo-lab")
        assert detached.status_code == 200, detached.text
        assert detached.json()["attachment"]["state"] == "DETACHED"

        active = client.get("/api/v1/attachments")
        assert active.json()["attachments"] == []

        audit = client.get(
            "/api/v1/attachments",
            params={"include_detached": True},
        )
        assert [item["state"] for item in audit.json()["attachments"]] == [
            "DETACHED"
        ]
        assert client.get(
            "/api/v1/intents",
            params={"product_id": "echo-lab"},
        ).json()["intents"] == []


@pytest.mark.asyncio
async def test_phase4_new_transport_adapter_requires_no_runtime_code_change(
    settings_factory,
):
    class TicketBusAdapter:
        mode = "ticketbus"

        def validate_target(self, manifest, target):
            if not target.endpoint.startswith("ticketbus://"):
                raise AttachmentValidationError(
                    "ticketbus endpoints must use ticketbus://"
                )

        async def dispatch(
            self,
            *,
            route: dict[str, Any],
            envelope: dict[str, Any],
            manifest: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "accepted": True,
                "adapter": self.mode,
                "product_id": route["product_id"],
                "intent_id": route["intent_id"],
                "ticket_id": envelope["payload"]["ticket_id"],
                "context_scopes": envelope["context"]["loaded_scopes"],
            }

    manifest = ProductAttachmentManifest.model_validate(
        {
            "product_id": "support-desk",
            "display_name": "Support Desk",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "embedded",
            "capabilities": [
                {
                    "capability_id": "ticket-routing",
                    "description": "Routes explicit support-ticket requests",
                    "context_scopes": ["session", "workspace"],
                    "intents": [
                        {
                            "intent_id": "ticket.open",
                            "description": "Open a support ticket by ID",
                            "input_schema": {
                                "type": "object",
                                "required": ["ticket_id"],
                                "properties": {
                                    "ticket_id": {"type": "string"}
                                },
                            },
                            "dispatch": {
                                "mode": "ticketbus",
                                "endpoint": "ticketbus://support/open",
                            },
                        }
                    ],
                }
            ],
        }
    )
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        adapters=[TicketBusAdapter()],
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        attached = runtime.attach(manifest)
        assert attached["product_id"] == "support-desk"

        session = runtime.sessions.create(
            actor_id="phase4-user",
            client_type="embedded",
            workspace_id="support-space",
            product_id="support-desk",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="ticket.open",
                payload={"ticket_id": "TCK-42"},
            )
        )
        assert result["dispatch"]["status"] == "COMPLETED"
        assert result["dispatch"]["response"]["adapter"] == "ticketbus"
        assert result["dispatch"]["response"]["context_scopes"] == [
            "session",
            "workspace",
        ]
    finally:
        runtime.stop()


def test_phase4_manifest_source_bootstrap_uses_interface_only(
    settings_factory,
):
    class MemoryManifestSource:
        def load(self):
            return [_echo_manifest()]

    runtime = CompanionRuntime(settings_factory())
    runtime.start()
    try:
        summary = runtime.attach_many(MemoryManifestSource().load())
        assert summary["attached_count"] == 1
        assert summary["attachments"][0]["product_id"] == "echo-lab"
    finally:
        runtime.stop()
