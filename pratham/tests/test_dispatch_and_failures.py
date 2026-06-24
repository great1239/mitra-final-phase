from __future__ import annotations

import httpx
import pytest

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import (
    IntentRoutingError,
    ResourceConflictError,
    TransportError,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


@pytest.mark.asyncio
async def test_loopback_dispatch_receives_only_declared_context(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="dispatch-user",
        client_type="embedded",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    runtime.context.update(
        session_id=session["session_id"],
        scope="product",
        patch={"record_id": "lead-42"},
        expected_revision=0,
        replace=True,
    )
    result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            intent_id="workspace.open-record",
            payload={"record_type": "lead", "record_id": "lead-42"},
        )
    )
    dispatch = result["dispatch"]
    assert dispatch["status"] == "COMPLETED"
    assert dispatch["response"]["transport"] == "loopback"
    assert dispatch["response"]["payload"]["record_id"] == "lead-42"
    assert dispatch["request"]["context"]["loaded_scopes"] == [
        "session",
        "workspace",
        "handoff",
        "product",
    ]


@pytest.mark.asyncio
async def test_cross_product_dispatch_requires_transfer(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(nova_manifest)
    session = runtime.sessions.create(
        actor_id="dispatch-user",
        client_type="standalone",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    with pytest.raises(ResourceConflictError):
        await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                product_id="nova-operations",
                intent_id="operations.show-status",
                payload={"resource_id": "worker-1"},
            )
        )


@pytest.mark.asyncio
async def test_dispatch_validates_registered_input_schema(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="schema-user",
        client_type="embedded",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    with pytest.raises(IntentRoutingError):
        await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="workspace.open-record",
                payload={"record_type": "lead"},
            )
        )
    assert runtime.store.counts()["dispatches"] == 0


@pytest.mark.asyncio
async def test_http_transport_failure_degrades_attachment(settings_factory):
    async def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(failing_handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "remote-product",
                "display_name": "Remote Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://remote.invalid",
                "capabilities": [
                    {
                        "capability_id": "remote-navigation",
                        "description": "Remote navigation test capability",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "remote.open",
                                "description": "Open remote resource",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/dispatch"
                                }
                            }
                        ]
                    }
                ]
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="remote-user",
            client_type="standalone",
            workspace_id="remote",
            product_id="remote-product",
        )
        with pytest.raises(TransportError):
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=session["session_id"],
                    intent_id="remote.open",
                    payload={"resource_id": "r-1"},
                )
            )
        assert runtime.attachments.get("remote-product")["state"] == "DEGRADED"
        assert runtime.lifecycle.state.value == "DEGRADED"
        assert runtime.store.counts()["failed_dispatches"] == 1
        restored = runtime.attach(manifest)
        assert restored["state"] == "ATTACHED"
        assert runtime.lifecycle.state.value == "READY"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_custom_transport_adapter_requires_no_runtime_product_branch(
    settings_factory,
):
    class MemoryTransportAdapter:
        mode = "memory"

        def validate_target(self, manifest, target):
            assert target.endpoint.startswith("memory://")

        async def dispatch(self, *, route, envelope, manifest):
            return {
                "accepted": True,
                "transport": self.mode,
                "endpoint": route["dispatch"]["endpoint"],
                "payload": envelope["payload"],
            }

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        adapters=[MemoryTransportAdapter()],
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "adapter-fixture",
                "display_name": "Adapter Fixture",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "simulated",
                "capabilities": [
                    {
                        "capability_id": "fixture-capability",
                        "description": "Adapter boundary fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "fixture.execute",
                                "description": "Execute through a custom adapter",
                                "input_schema": {
                                    "type": "object",
                                    "required": ["value"]
                                },
                                "dispatch": {
                                    "mode": "memory",
                                    "endpoint": "memory://fixture/execute",
                                    "options": {"fixture": True}
                                }
                            }
                        ]
                    }
                ]
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="adapter-user",
            client_type="standalone",
            workspace_id="adapter-workspace",
            product_id="adapter-fixture",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="fixture.execute",
                payload={"value": 7},
            )
        )
        assert result["dispatch"]["response"] == {
            "accepted": True,
            "transport": "memory",
            "endpoint": "memory://fixture/execute",
            "payload": {"value": 7},
        }
    finally:
        runtime.stop()
