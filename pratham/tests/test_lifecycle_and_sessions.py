from __future__ import annotations

import pytest

from mitra_companion.contracts import ContextTransferRequest
from mitra_companion.constants import RuntimeState
from mitra_companion.errors import ResourceConflictError


def test_runtime_lifecycle_is_durable(runtime):
    assert runtime.lifecycle.state == RuntimeState.READY
    history = runtime.lifecycle.history()
    assert history[0]["to_state"] == "INITIALIZING"
    assert history[-1]["to_state"] == "READY"


def test_session_create_and_resume(runtime):
    created = runtime.sessions.create(
        actor_id="user-1",
        client_type="mobile",
        workspace_id="field-workspace",
        product_id=None,
        metadata={"locale": "en-IN"},
    )
    resumed = runtime.sessions.resume(
        created["session_id"],
        created["resume_token"],
    )
    assert resumed["actor_id"] == "user-1"
    assert resumed["client_type"] == "mobile"
    assert resumed["last_resumed_at"]

    with pytest.raises(ResourceConflictError):
        runtime.sessions.resume(created["session_id"], "not-the-token")


def test_session_suspend_resume_and_close_state_machine(runtime):
    created = runtime.sessions.create(
        actor_id="state-user",
        client_type="standalone",
        workspace_id="state-workspace",
        product_id=None,
    )
    suspended = runtime.sessions.suspend(created["session_id"])
    assert suspended["state"] == "SUSPENDED"
    resumed = runtime.sessions.resume(
        created["session_id"],
        created["resume_token"],
    )
    assert resumed["state"] == "ACTIVE"
    closed = runtime.sessions.close(created["session_id"])
    assert closed["state"] == "CLOSED"
    with pytest.raises(ResourceConflictError):
        runtime.sessions.resume(
            created["session_id"],
            created["resume_token"],
        )
    with pytest.raises(ResourceConflictError):
        runtime.sessions.suspend(created["session_id"])


def test_suspended_session_blocks_mutation_routing_and_transfer(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    created = runtime.sessions.create(
        actor_id="suspended-user",
        client_type="embedded",
        workspace_id="suspended-workspace",
        product_id=atlas_manifest.product_id,
    )
    runtime.sessions.suspend(created["session_id"])

    with pytest.raises(ResourceConflictError):
        runtime.context.update(
            session_id=created["session_id"],
            scope="session",
            patch={"blocked": True},
            expected_revision=0,
            replace=True,
        )
    with pytest.raises(ResourceConflictError):
        runtime.router.route(
            session_id=created["session_id"],
            intent_id="workspace.open-record",
            product_id=None,
            capability_id=None,
        )
    with pytest.raises(ResourceConflictError):
        runtime.transfer_context(
            created["session_id"],
            ContextTransferRequest(
                target_workspace_id="target-workspace",
                target_product_id=atlas_manifest.product_id,
                portable_context={},
            ),
        )


def test_session_continuity_survives_runtime_recreation(settings_factory):
    first = __import__(
        "mitra_companion.runtime",
        fromlist=["CompanionRuntime"],
    ).CompanionRuntime(settings_factory())
    first.start()
    created = first.sessions.create(
        actor_id="persistent-user",
        client_type="embedded",
        workspace_id="workspace-a",
        product_id=None,
    )
    first.stop()

    second = __import__(
        "mitra_companion.runtime",
        fromlist=["CompanionRuntime"],
    ).CompanionRuntime(settings_factory())
    second.start()
    try:
        resumed = second.sessions.resume(
            created["session_id"],
            created["resume_token"],
        )
        assert resumed["actor_id"] == "persistent-user"
    finally:
        second.stop()
