from __future__ import annotations

import pytest

from mitra_companion.contracts import ProductAttachmentManifest
from mitra_companion.errors import (
    AttachmentValidationError,
    IntentRoutingError,
    ResourceConflictError,
)


def test_product_attachment_and_intent_discovery(runtime, atlas_manifest):
    attached = runtime.attach(atlas_manifest)
    assert attached["state"] == "ATTACHED"
    intents = runtime.router.discover(product_id="atlas-workspace")
    assert {item["intent_id"] for item in intents} == {
        "workspace.open-record",
        "workspace.show-queue",
    }


def test_duplicate_attachment_is_idempotent_but_manifest_change_conflicts(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(atlas_manifest)
    changed = atlas_manifest.model_copy(
        update={"display_name": "Changed Atlas Workspace"}
    )
    with pytest.raises(ResourceConflictError):
        runtime.attach(changed)


def test_incompatible_attachment_contract_is_rejected(runtime, atlas_manifest):
    incompatible = ProductAttachmentManifest.model_validate(
        {
            **atlas_manifest.model_dump(mode="json"),
            "contract_version": "2.0.0",
        }
    )
    with pytest.raises(AttachmentValidationError):
        runtime.attach(incompatible)


def test_unknown_intent_fails_closed(runtime, atlas_manifest):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="router-user",
        client_type="embedded",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    with pytest.raises(IntentRoutingError):
        runtime.router.route(
            session_id=session["session_id"],
            intent_id="workspace.nonexistent",
            product_id=None,
            capability_id=None,
        )

