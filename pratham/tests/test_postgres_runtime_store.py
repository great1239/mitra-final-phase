from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import pytest

from mitra_companion.depository import CentralDepository
from mitra_companion.store import RuntimeStore
from mitra_context.runtime import ContextRuntime
from mitra_session.runtime import SessionRuntime


POSTGRES_URL = os.environ.get("MITRA_TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="MITRA_TEST_POSTGRES_URL is not configured",
)
def test_postgres_runtime_state_survives_store_recreation(tmp_path: Path):
    import psycopg
    from psycopg import sql

    schema = f"mitra_test_{uuid4().hex}"
    with psycopg.connect(POSTGRES_URL, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema))
        )

    separator = "&" if "?" in POSTGRES_URL else "?"
    database_url = (
        f"{POSTGRES_URL}{separator}"
        f"options={quote(f'-csearch_path={schema}')}"
    )
    try:
        first = RuntimeStore(
            tmp_path / "unused-first.db",
            database_url=database_url,
        )
        sessions = SessionRuntime(first)
        context = ContextRuntime(first, sessions)
        depository = CentralDepository(first)

        session = sessions.create(
            actor_id="postgres-test-user",
            client_type="standalone",
            workspace_id="postgres-test-workspace",
            product_id=None,
        )
        context.update(
            session_id=session["session_id"],
            scope="session",
            patch={"durable_marker": "survived"},
            expected_revision=0,
            replace=True,
        )
        artifact = depository.put(
            artifact_type="postgres-runtime-test",
            artifact={"session_id": session["session_id"]},
        )
        lineage = depository.append_lineage(
            subject_type="session",
            subject_id=session["session_id"],
            artifact_hash=artifact["artifact_hash"],
        )
        lease = first.claim_runtime_lease(
            lease_name="postgres-runtime-test",
            instance_id="instance-a",
            lease_seconds=30,
        )
        assert lease["acquired"] is True

        second = RuntimeStore(
            tmp_path / "unused-second.db",
            database_url=database_url,
        )
        restored_sessions = SessionRuntime(second)
        restored_context = ContextRuntime(second, restored_sessions)
        restored_depository = CentralDepository(second)

        assert restored_sessions.get(session["session_id"])["actor_id"] == (
            "postgres-test-user"
        )
        restored = restored_context.load(
            session["session_id"],
            scopes=["session"],
        )
        assert restored["merged"]["durable_marker"] == "survived"
        assert restored["partitions"]["session"]["revision"] == 1
        assert restored_depository.artifact(artifact["artifact_hash"]) == (
            artifact
        )
        assert restored_depository.lineage(
            subject_type="session",
            subject_id=session["session_id"],
        )[0]["lineage_id"] == lineage["lineage_id"]
        assert second.get_runtime_lease("postgres-runtime-test")[
            "holder_instance_id"
        ] == "instance-a"
    finally:
        with psycopg.connect(POSTGRES_URL, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
