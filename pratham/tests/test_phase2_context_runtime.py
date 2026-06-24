from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mitra_companion.constants import ContextScope
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.store import RuntimeStore


ROOT = Path(__file__).resolve().parents[2]


def _update(runtime, session_id: str, scope: str, **data) -> None:
    runtime.context.update(
        session_id=session_id,
        scope=scope,
        patch=data,
        expected_revision=0,
        replace=True,
    )


def test_selective_context_loading_and_merge_precedence(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="scope-user",
        client_type="embedded",
        workspace_id="scope-workspace",
        product_id=atlas_manifest.product_id,
    )
    session_id = session["session_id"]
    _update(runtime, session_id, "session", value="session", session_only=True)
    _update(
        runtime,
        session_id,
        "workspace",
        value="workspace",
        workspace_only=True,
    )
    _update(runtime, session_id, "handoff", value="handoff", handoff_only=True)
    _update(runtime, session_id, "product", value="product", product_only=True)

    loaded = runtime.context.load(
        session_id,
        scopes=["product", "workspace"],
    )

    assert loaded["loaded_scopes"] == ["workspace", "product"]
    assert set(loaded["partitions"]) == {"workspace", "product"}
    assert loaded["merged"]["value"] == "product"
    assert loaded["merged"]["workspace_only"] is True
    assert loaded["merged"]["product_only"] is True
    assert "session_only" not in loaded["merged"]
    assert "handoff_only" not in loaded["merged"]


def test_unknown_context_scope_is_rejected(runtime):
    session = runtime.sessions.create(
        actor_id="scope-user",
        client_type="standalone",
        workspace_id="scope-workspace",
        product_id=None,
    )
    with pytest.raises(ValueError):
        runtime.context.load(session["session_id"], scopes=["knowledge"])


def test_context_policy_and_context_view_contracts(runtime):
    policy = json.loads(
        (ROOT / "contracts" / "context-runtime-policy.json").read_text(
            encoding="utf-8"
        )
    )
    policy_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "context-runtime-policy.schema.json"
        ).read_text(encoding="utf-8")
    )
    view_schema = json.loads(
        (
            ROOT / "contracts" / "schemas" / "context-view.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(policy_schema).validate(policy)

    session = runtime.sessions.create(
        actor_id="contract-user",
        client_type="standalone",
        workspace_id="contract-workspace",
        product_id=None,
    )
    view = runtime.context.load(
        session["session_id"],
        scopes=["session", "workspace"],
    )
    Draft202012Validator(view_schema).validate(view)


def test_workspace_continuity_is_actor_scoped(runtime):
    first = runtime.sessions.create(
        actor_id="actor-a",
        client_type="embedded",
        workspace_id="shared-name",
        product_id=None,
    )
    _update(
        runtime,
        first["session_id"],
        ContextScope.WORKSPACE.value,
        private_layout="actor-a-layout",
    )

    same_actor = runtime.sessions.create(
        actor_id="actor-a",
        client_type="mobile",
        workspace_id="shared-name",
        product_id=None,
    )
    other_actor = runtime.sessions.create(
        actor_id="actor-b",
        client_type="mobile",
        workspace_id="shared-name",
        product_id=None,
    )

    assert (
        runtime.context.load(same_actor["session_id"])["merged"][
            "private_layout"
        ]
        == "actor-a-layout"
    )
    assert runtime.context.load(other_actor["session_id"])[
        "partitions"
    ]["workspace"]["data"] == {}


def test_session_and_context_continuity_survive_runtime_recreation(
    settings_factory,
):
    first = CompanionRuntime(settings_factory())
    first.start()
    created = first.sessions.create(
        actor_id="continuity-user",
        client_type="embedded",
        workspace_id="continuity-workspace",
        product_id=None,
    )
    _update(
        first,
        created["session_id"],
        ContextScope.SESSION.value,
        active_task="task-17",
    )
    _update(
        first,
        created["session_id"],
        ContextScope.WORKSPACE.value,
        active_surface="operations",
    )
    first.sessions.suspend(created["session_id"])
    first.stop()

    second = CompanionRuntime(settings_factory())
    second.start()
    try:
        second.sessions.resume(
            created["session_id"],
            created["resume_token"],
        )
        loaded = second.context.load(created["session_id"])
        assert loaded["continuity"]["session_state"] == "ACTIVE"
        assert loaded["merged"]["active_task"] == "task-17"
        assert loaded["merged"]["active_surface"] == "operations"
    finally:
        second.stop()


def test_product_context_is_private_to_session_and_active_product(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(nova_manifest)
    atlas = runtime.sessions.create(
        actor_id="product-user",
        client_type="embedded",
        workspace_id="product-workspace",
        product_id=atlas_manifest.product_id,
    )
    nova = runtime.sessions.create(
        actor_id="product-user",
        client_type="embedded",
        workspace_id="product-workspace",
        product_id=nova_manifest.product_id,
    )
    _update(
        runtime,
        atlas["session_id"],
        ContextScope.PRODUCT.value,
        atlas_private="atlas-value",
    )
    _update(
        runtime,
        nova["session_id"],
        ContextScope.PRODUCT.value,
        nova_private="nova-value",
    )

    atlas_context = runtime.context.load(atlas["session_id"])
    nova_context = runtime.context.load(nova["session_id"])
    assert atlas_context["merged"]["atlas_private"] == "atlas-value"
    assert "nova_private" not in atlas_context["merged"]
    assert nova_context["merged"]["nova_private"] == "nova-value"
    assert "atlas_private" not in nova_context["merged"]


def test_phase1_workspace_migration_preserves_only_unambiguous_owners(
    tmp_path,
):
    database_path = tmp_path / "phase1.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            parent_session_id TEXT,
            resume_token_hash TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            client_type TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            active_product_id TEXT,
            state TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_resumed_at TEXT
        );
        CREATE TABLE workspace_contexts (
            workspace_id TEXT PRIMARY KEY,
            revision INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO sessions VALUES
            ('s1', NULL, 'hash', 'actor-a', 'embedded', 'unique', NULL,
             'ACTIVE', '{}', 'now', 'now', NULL),
            ('s2', NULL, 'hash', 'actor-a', 'embedded', 'ambiguous', NULL,
             'ACTIVE', '{}', 'now', 'now', NULL),
            ('s3', NULL, 'hash', 'actor-b', 'mobile', 'ambiguous', NULL,
             'ACTIVE', '{}', 'now', 'now', NULL);
        INSERT INTO workspace_contexts VALUES
            ('unique', 1, '{"restored": true}', 'now'),
            ('ambiguous', 1, '{"must_not_leak": true}', 'now');
        """
    )
    connection.close()

    store = RuntimeStore(database_path)

    restored = store.get_context(
        "s1",
        ContextScope.WORKSPACE.value,
        "unique",
        owner_id="actor-a",
    )
    actor_a = store.get_context(
        "s2",
        ContextScope.WORKSPACE.value,
        "ambiguous",
        owner_id="actor-a",
    )
    actor_b = store.get_context(
        "s3",
        ContextScope.WORKSPACE.value,
        "ambiguous",
        owner_id="actor-b",
    )
    assert restored["data"] == {"restored": True}
    assert actor_a["data"] == {}
    assert actor_b["data"] == {}
