from __future__ import annotations

import pytest

from mitra_companion.constants import RuntimeState
from mitra_companion.contracts import (
    ContextTransferRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import (
    AttachmentValidationError,
    IntentRoutingError,
    TransportError,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


@pytest.mark.asyncio
async def test_phase6_runtime_simulation_multiple_products_and_transfer(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    summary = runtime.attach_many([atlas_manifest, nova_manifest])
    assert summary["attached_count"] == 2
    assert runtime.store.counts()["attachments"] == 2

    atlas = runtime.sessions.create(
        actor_id="phase6-user",
        client_type="embedded",
        workspace_id="phase6-atlas",
        product_id=atlas_manifest.product_id,
    )
    runtime.context.update(
        session_id=atlas["session_id"],
        scope="session",
        patch={"locale": "en-US"},
        expected_revision=0,
        replace=True,
    )
    runtime.context.update(
        session_id=atlas["session_id"],
        scope="workspace",
        patch={"workspace_view": "pipeline"},
        expected_revision=0,
        replace=True,
    )
    runtime.context.update(
        session_id=atlas["session_id"],
        scope="product",
        patch={"atlas_only": "lead-42"},
        expected_revision=0,
        replace=True,
    )

    atlas_result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=atlas["session_id"],
            intent_id="workspace.open-record",
            capability_id="workspace-navigation",
            payload={"record_type": "lead", "record_id": "lead-42"},
        )
    )
    assert atlas_result["dispatch"]["status"] == "COMPLETED"
    assert atlas_result["route"]["product_id"] == "atlas-workspace"
    assert atlas_result["route"]["capability_resolution"] == "explicit"
    assert atlas_result["dispatch"]["response"][
        "received_context_scopes"
    ] == ["handoff", "product", "session", "workspace"]

    with pytest.raises(IntentRoutingError):
        await runtime.dispatch(
            IntentDispatchRequest(
                session_id=atlas["session_id"],
                intent_id="workspace.open-record",
                capability_id="workspace-navigation",
                payload={"record_type": "lead"},
            )
        )

    transferred = runtime.transfer_context(
        atlas["session_id"],
        ContextTransferRequest(
            target_workspace_id="phase6-nova",
            target_product_id=nova_manifest.product_id,
            portable_context={"handoff_reference": "lead-42"},
        ),
    )
    nova = transferred["session"]
    assert nova["parent_session_id"] == atlas["session_id"]
    assert transferred["context"]["merged"]["handoff_reference"] == "lead-42"
    assert "atlas_only" not in transferred["context"]["merged"]

    nova_result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=nova["session_id"],
            intent_id="operations.show-status",
            payload={"resource_id": "lead-42"},
        )
    )
    assert nova_result["route"]["product_id"] == "nova-operations"
    assert nova_result["route"]["product_resolution"] == "session"
    assert nova_result["dispatch"]["status"] == "COMPLETED"


def test_phase6_attachment_validation_rejects_invalid_manifests(
    runtime,
    atlas_manifest,
):
    duplicate_capability = atlas_manifest.model_copy(deep=True)
    duplicate_capability.capabilities.append(
        duplicate_capability.capabilities[0].model_copy(deep=True)
    )
    with pytest.raises(AttachmentValidationError):
        runtime.attach(duplicate_capability)

    bad_schema = atlas_manifest.model_copy(deep=True)
    bad_schema.capabilities[0].intents[0].input_schema = {
        "type": "object",
        "properties": {"bad": {"type": 7}},
    }
    with pytest.raises(AttachmentValidationError):
        runtime.attach(bad_schema)


@pytest.mark.asyncio
async def test_phase6_failure_handling_degrades_only_failed_attachment(
    settings_factory,
    atlas_manifest,
):
    class FailingAdapter:
        mode = "phase6-fail"

        def validate_target(self, manifest, target):
            if not target.endpoint.startswith("phase6-fail://"):
                raise AttachmentValidationError("invalid failure fixture")

        async def dispatch(self, *, route, envelope, manifest):
            raise TransportError("phase6 transport fixture failed")

    failing_manifest = ProductAttachmentManifest.model_validate(
        {
            "product_id": "failure-fixture",
            "display_name": "Failure Fixture",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "embedded",
            "capabilities": [
                {
                    "capability_id": "failure-routing",
                    "description": "Routes to a failing transport fixture",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "fixture.fail",
                            "description": "Trigger failure handling",
                            "input_schema": {"type": "object"},
                            "dispatch": {
                                "mode": "phase6-fail",
                                "endpoint": "phase6-fail://dispatch",
                            },
                        }
                    ],
                }
            ],
        }
    )
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        adapters=[FailingAdapter()],
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        runtime.attach_many([atlas_manifest, failing_manifest])
        failed_session = runtime.sessions.create(
            actor_id="phase6-failure-user",
            client_type="embedded",
            workspace_id="failure-space",
            product_id=failing_manifest.product_id,
        )
        with pytest.raises(TransportError):
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=failed_session["session_id"],
                    intent_id="fixture.fail",
                    payload={},
                )
            )

        assert runtime.lifecycle.state == RuntimeState.DEGRADED
        assert runtime.attachments.get("failure-fixture")["state"] == (
            "DEGRADED"
        )
        assert runtime.store.list_dispatches()[0]["status"] == "FAILED"

        healthy_session = runtime.sessions.create(
            actor_id="phase6-failure-user",
            client_type="embedded",
            workspace_id="healthy-space",
            product_id=atlas_manifest.product_id,
        )
        healthy = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=healthy_session["session_id"],
                intent_id="workspace.show-queue",
                payload={"queue_id": "healthy"},
            )
        )
        assert healthy["dispatch"]["status"] == "COMPLETED"
        assert runtime.attachments.get("atlas-workspace")["state"] == (
            "ATTACHED"
        )
    finally:
        runtime.stop()
