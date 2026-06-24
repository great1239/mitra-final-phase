from __future__ import annotations

import pytest

from mitra_companion.errors import ContextRevisionConflict


def test_context_loading_updates_and_revision_control(runtime, atlas_manifest):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="context-user",
        client_type="embedded",
        workspace_id="sales",
        product_id="atlas-workspace",
    )
    session_id = session["session_id"]

    first = runtime.context.update(
        session_id=session_id,
        scope="session",
        patch={"locale": "en-IN"},
        expected_revision=0,
        replace=False,
    )
    assert first["revision"] == 1
    runtime.context.update(
        session_id=session_id,
        scope="workspace",
        patch={"workspace_view": "pipeline"},
        expected_revision=0,
        replace=False,
    )
    runtime.context.update(
        session_id=session_id,
        scope="product",
        patch={"selected_record": "lead-42"},
        expected_revision=0,
        replace=False,
    )

    loaded = runtime.context.load(session_id)
    assert loaded["merged"]["locale"] == "en-IN"
    assert loaded["merged"]["workspace_view"] == "pipeline"
    assert loaded["merged"]["selected_record"] == "lead-42"

    with pytest.raises(ContextRevisionConflict):
        runtime.context.update(
            session_id=session_id,
            scope="session",
            patch={"locale": "hi-IN"},
            expected_revision=0,
            replace=False,
        )


def test_cross_product_transfer_does_not_copy_product_context(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(nova_manifest)
    source = runtime.sessions.create(
        actor_id="transfer-user",
        client_type="standalone",
        workspace_id="atlas-home",
        product_id="atlas-workspace",
    )
    runtime.context.update(
        session_id=source["session_id"],
        scope="product",
        patch={"atlas_private_record": "atlas-991"},
        expected_revision=0,
        replace=True,
    )

    from mitra_companion.contracts import ContextTransferRequest

    result = runtime.transfer_context(
        source["session_id"],
        ContextTransferRequest(
            target_workspace_id="nova-home",
            target_product_id="nova-operations",
            portable_context={"handoff_reference": "case-7"},
        ),
    )
    target_context = result["context"]
    assert target_context["active_product_id"] == "nova-operations"
    assert target_context["merged"]["handoff_reference"] == "case-7"
    assert "atlas_private_record" not in target_context["merged"]
    assert target_context["partitions"]["product"]["data"] == {}


def test_workspace_context_continues_across_sessions(runtime, atlas_manifest):
    runtime.attach(atlas_manifest)
    first = runtime.sessions.create(
        actor_id="workspace-user",
        client_type="embedded",
        workspace_id="shared-workspace",
        product_id="atlas-workspace",
    )
    runtime.context.update(
        session_id=first["session_id"],
        scope="workspace",
        patch={"active_panel": "priority-queue"},
        expected_revision=0,
        replace=True,
    )
    second = runtime.sessions.create(
        actor_id="workspace-user",
        client_type="mobile",
        workspace_id="shared-workspace",
        product_id="atlas-workspace",
    )
    loaded = runtime.context.load(second["session_id"])
    assert loaded["partitions"]["workspace"]["revision"] == 1
    assert loaded["merged"]["active_panel"] == "priority-queue"
