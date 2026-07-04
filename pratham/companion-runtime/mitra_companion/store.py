from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .constants import AttachmentState, RuntimeState, SessionState
from .errors import ContextRevisionConflict, ResourceConflictError
from .utils import utc_now


class RuntimeStore:
    """Durable state for lifecycle, sessions, contexts, attachments, and dispatches."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._schema_lock, self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_instances (
                    instance_id TEXT PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    process_id INTEGER,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    stopped_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
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
                    last_resumed_at TEXT,
                    FOREIGN KEY(parent_session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_actor
                    ON sessions(actor_id, updated_at);

                CREATE TABLE IF NOT EXISTS contexts (
                    session_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, scope, scope_key),
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS workspace_contexts (
                    actor_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(actor_id, workspace_id)
                );
                CREATE INDEX IF NOT EXISTS idx_workspace_contexts_workspace
                    ON workspace_contexts(workspace_id);

                CREATE TABLE IF NOT EXISTS attachments (
                    product_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    attached_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_dispatches_session
                    ON dispatches(session_id, created_at);

                CREATE TABLE IF NOT EXISTS context_transfers (
                    transfer_id TEXT PRIMARY KEY,
                    source_session_id TEXT NOT NULL,
                    target_session_id TEXT NOT NULL,
                    target_workspace_id TEXT NOT NULL,
                    target_product_id TEXT,
                    portable_context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY(target_session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS companion_messages (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_companion_messages_session
                    ON companion_messages(session_id, created_at);

                CREATE TABLE IF NOT EXISTS companion_tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    status_detail TEXT,
                    notification_json TEXT NOT NULL,
                    result_json TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_companion_tasks_session
                    ON companion_tasks(session_id, updated_at);
                """
            )
            self._migrate_legacy_workspace_contexts(connection)

    def upsert_runtime_instance(
        self,
        *,
        instance_id: str,
        service_name: str,
        environment: str,
        process_id: int,
        state: str,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO runtime_instances(
                    instance_id, service_name, environment, process_id, state,
                    started_at, last_heartbeat_at, stopped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(instance_id) DO UPDATE SET
                    service_name = excluded.service_name,
                    environment = excluded.environment,
                    process_id = excluded.process_id,
                    state = excluded.state,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    stopped_at = NULL
                """,
                (
                    instance_id,
                    service_name,
                    environment,
                    process_id,
                    state,
                    now,
                    now,
                ),
            )
        return self.get_runtime_instance(instance_id) or {}

    def heartbeat_runtime_instance(
        self,
        *,
        instance_id: str,
        state: str,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE runtime_instances
                SET state = ?, last_heartbeat_at = ?
                WHERE instance_id = ?
                """,
                (state, now, instance_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(instance_id)
        return self.get_runtime_instance(instance_id) or {}

    def stop_runtime_instance(self, instance_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE runtime_instances
                SET state = ?, last_heartbeat_at = ?, stopped_at = ?
                WHERE instance_id = ?
                """,
                (RuntimeState.STOPPED.value, now, now, instance_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(instance_id)
        return self.get_runtime_instance(instance_id) or {}

    def get_runtime_instance(
        self,
        instance_id: str,
    ) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_runtime_instances(
        self,
        *,
        include_stopped: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM runtime_instances"
        params: tuple[Any, ...] = ()
        if not include_stopped:
            query += " WHERE state != ?"
            params = (RuntimeState.STOPPED.value,)
        query += " ORDER BY last_heartbeat_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _migrate_legacy_workspace_contexts(
        connection: sqlite3.Connection,
    ) -> None:
        """Safely migrate the Phase 1 workspace table without cross-actor leaks."""
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(workspace_contexts)"
            ).fetchall()
        }
        if not columns or "actor_id" in columns:
            return

        legacy_table = "workspace_contexts_phase1"
        legacy_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (legacy_table,),
        ).fetchone()
        if legacy_exists:
            raise RuntimeError(
                "Cannot migrate workspace contexts: legacy table already exists"
            )

        connection.execute(
            f"ALTER TABLE workspace_contexts RENAME TO {legacy_table}"
        )
        connection.execute(
            "DROP INDEX IF EXISTS idx_workspace_contexts_workspace"
        )
        connection.executescript(
            """
            CREATE TABLE workspace_contexts (
                actor_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(actor_id, workspace_id)
            );
            CREATE INDEX idx_workspace_contexts_workspace
                ON workspace_contexts(workspace_id);
            """
        )
        connection.execute(
            f"""
            INSERT INTO workspace_contexts(
                actor_id, workspace_id, revision, data_json, updated_at
            )
            SELECT MIN(s.actor_id), legacy.workspace_id, legacy.revision,
                   legacy.data_json, legacy.updated_at
            FROM {legacy_table} AS legacy
            JOIN sessions AS s
              ON s.workspace_id = legacy.workspace_id
            GROUP BY legacy.workspace_id
            HAVING COUNT(DISTINCT s.actor_id) = 1
            """
        )

    def record_transition(
        self,
        from_state: RuntimeState | str | None,
        to_state: RuntimeState | str,
        reason: str,
    ) -> dict[str, Any]:
        source = from_state.value if isinstance(from_state, RuntimeState) else from_state
        target = to_state.value if isinstance(to_state, RuntimeState) else to_state
        occurred_at = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runtime_transitions(from_state, to_state, reason, occurred_at)
                VALUES (?, ?, ?, ?)
                """,
                (source, target, reason, occurred_at),
            )
        return {
            "sequence": cursor.lastrowid,
            "from_state": source,
            "to_state": target,
            "reason": reason,
            "occurred_at": occurred_at,
        }

    def current_state(self) -> RuntimeState | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT to_state FROM runtime_transitions ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        return RuntimeState(row["to_state"]) if row else None

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, from_state, to_state, reason, occurred_at
                FROM runtime_transitions ORDER BY sequence DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def create_session(
        self,
        *,
        session_id: str,
        parent_session_id: str | None,
        resume_token_hash: str,
        actor_id: str,
        client_type: str,
        workspace_id: str,
        active_product_id: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    session_id, parent_session_id, resume_token_hash, actor_id,
                    client_type, workspace_id, active_product_id, state,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    parent_session_id,
                    resume_token_hash,
                    actor_id,
                    client_type,
                    workspace_id,
                    active_product_id,
                    SessionState.ACTIVE.value,
                    json.dumps(metadata, sort_keys=True, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get_session(session_id) or {}

    @staticmethod
    def _decode_session(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        data.pop("resume_token_hash", None)
        return data

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return self._decode_session(row)

    def get_session_token_hash(self, session_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT resume_token_hash FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row["resume_token_hash"] if row else None

    def mark_session_resumed(self, session_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET state = ?, last_resumed_at = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (SessionState.ACTIVE.value, now, now, session_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(session_id)
        return self.get_session(session_id) or {}

    def set_session_state(
        self,
        session_id: str,
        state: SessionState,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET state = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (state.value, now, session_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(session_id)
        return self.get_session(session_id) or {}

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode_session(row) or {} for row in rows]

    def upsert_context(
        self,
        *,
        session_id: str,
        scope: str,
        scope_key: str,
        owner_id: str | None,
        patch: dict[str, Any],
        expected_revision: int | None,
        replace: bool,
    ) -> dict[str, Any]:
        now = utc_now()
        if scope == "workspace":
            if not owner_id:
                raise ValueError(
                    "Workspace context requires an actor isolation owner"
                )
            return self._upsert_workspace_context(
                session_id=session_id,
                actor_id=owner_id,
                workspace_id=scope_key,
                patch=patch,
                expected_revision=expected_revision,
                replace=replace,
                updated_at=now,
            )
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT revision, data_json FROM contexts
                WHERE session_id = ? AND scope = ? AND scope_key = ?
                """,
                (session_id, scope, scope_key),
            ).fetchone()
            current_revision = int(row["revision"]) if row else 0
            if (
                expected_revision is not None
                and expected_revision != current_revision
            ):
                connection.execute("ROLLBACK")
                raise ContextRevisionConflict(
                    f"Expected context revision {expected_revision}, "
                    f"found {current_revision}"
                )
            current = json.loads(row["data_json"]) if row else {}
            data = dict(patch) if replace else {**current, **patch}
            revision = current_revision + 1
            connection.execute(
                """
                INSERT INTO contexts(
                    session_id, scope, scope_key, revision, data_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, scope, scope_key) DO UPDATE SET
                    revision = excluded.revision,
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    scope,
                    scope_key,
                    revision,
                    json.dumps(data, sort_keys=True, ensure_ascii=False),
                    now,
                ),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            connection.execute("COMMIT")
        return {
            "session_id": session_id,
            "scope": scope,
            "scope_key": scope_key,
            "revision": revision,
            "data": data,
            "updated_at": now,
        }

    def _upsert_workspace_context(
        self,
        *,
        session_id: str,
        actor_id: str,
        workspace_id: str,
        patch: dict[str, Any],
        expected_revision: int | None,
        replace: bool,
        updated_at: str,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT revision, data_json FROM workspace_contexts
                WHERE actor_id = ? AND workspace_id = ?
                """,
                (actor_id, workspace_id),
            ).fetchone()
            current_revision = int(row["revision"]) if row else 0
            if (
                expected_revision is not None
                and expected_revision != current_revision
            ):
                connection.execute("ROLLBACK")
                raise ContextRevisionConflict(
                    f"Expected workspace context revision {expected_revision}, "
                    f"found {current_revision}"
                )
            current = json.loads(row["data_json"]) if row else {}
            data = dict(patch) if replace else {**current, **patch}
            revision = current_revision + 1
            connection.execute(
                """
                INSERT INTO workspace_contexts(
                    actor_id, workspace_id, revision, data_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(actor_id, workspace_id) DO UPDATE SET
                    revision = excluded.revision,
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (
                    actor_id,
                    workspace_id,
                    revision,
                    json.dumps(data, sort_keys=True, ensure_ascii=False),
                    updated_at,
                ),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (updated_at, session_id),
            )
            connection.execute("COMMIT")
        return {
            "session_id": session_id,
            "scope": "workspace",
            "scope_key": workspace_id,
            "revision": revision,
            "data": data,
            "updated_at": updated_at,
        }

    def get_context(
        self,
        session_id: str,
        scope: str,
        scope_key: str,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            if scope == "workspace":
                if not owner_id:
                    raise ValueError(
                        "Workspace context requires an actor isolation owner"
                    )
                row = connection.execute(
                    """
                    SELECT revision, data_json, updated_at
                    FROM workspace_contexts
                    WHERE actor_id = ? AND workspace_id = ?
                    """,
                    (owner_id, scope_key),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT revision, data_json, updated_at FROM contexts
                    WHERE session_id = ? AND scope = ? AND scope_key = ?
                    """,
                    (session_id, scope, scope_key),
                ).fetchone()
        if row is None:
            return {
                "session_id": session_id,
                "scope": scope,
                "scope_key": scope_key,
                "revision": 0,
                "data": {},
                "updated_at": None,
            }
        return {
            "session_id": session_id,
            "scope": scope,
            "scope_key": scope_key,
            "revision": row["revision"],
            "data": json.loads(row["data_json"]),
            "updated_at": row["updated_at"],
        }

    def attach_product(
        self,
        product_id: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT manifest_json, state FROM attachments WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            if row and row["state"] != AttachmentState.DETACHED.value:
                if row["manifest_json"] != encoded:
                    raise ResourceConflictError(
                        f"Product is already attached with a different manifest: "
                        f"{product_id}"
                    )
                if row["state"] == AttachmentState.DEGRADED.value:
                    connection.execute(
                        """
                        UPDATE attachments
                        SET state = ?, last_error = NULL, updated_at = ?
                        WHERE product_id = ?
                        """,
                        (
                            AttachmentState.ATTACHED.value,
                            now,
                            product_id,
                        ),
                    )
                return self.get_attachment(product_id) or {}
            connection.execute(
                """
                INSERT INTO attachments(
                    product_id, state, manifest_json, attached_at, updated_at, last_error
                ) VALUES (?, ?, ?, ?, ?, NULL)
                ON CONFLICT(product_id) DO UPDATE SET
                    state = excluded.state,
                    manifest_json = excluded.manifest_json,
                    attached_at = excluded.attached_at,
                    updated_at = excluded.updated_at,
                    last_error = NULL
                """,
                (
                    product_id,
                    AttachmentState.ATTACHED.value,
                    encoded,
                    now,
                    now,
                ),
            )
        return self.get_attachment(product_id) or {}

    @staticmethod
    def _decode_attachment(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["manifest"] = json.loads(data.pop("manifest_json"))
        return data

    def get_attachment(self, product_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM attachments WHERE product_id = ?",
                (product_id,),
            ).fetchone()
        return self._decode_attachment(row)

    def list_attachments(
        self,
        *,
        include_detached: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM attachments"
        params: tuple[Any, ...] = ()
        if not include_detached:
            query += " WHERE state != ?"
            params = (AttachmentState.DETACHED.value,)
        query += " ORDER BY attached_at"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decode_attachment(row) or {} for row in rows]

    def set_attachment_state(
        self,
        product_id: str,
        state: AttachmentState,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE attachments
                SET state = ?, last_error = ?, updated_at = ?
                WHERE product_id = ?
                """,
                (state.value, error, utc_now(), product_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(product_id)
        return self.get_attachment(product_id) or {}

    def create_dispatch(
        self,
        *,
        dispatch_id: str,
        session_id: str,
        product_id: str,
        capability_id: str,
        intent_id: str,
        status: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO dispatches(
                    dispatch_id, session_id, product_id, capability_id,
                    intent_id, status, request_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dispatch_id,
                    session_id,
                    product_id,
                    capability_id,
                    intent_id,
                    status,
                    json.dumps(request, sort_keys=True, ensure_ascii=False),
                    utc_now(),
                ),
            )
        return self.get_dispatch(dispatch_id) or {}

    def complete_dispatch(
        self,
        dispatch_id: str,
        *,
        status: str,
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE dispatches
                SET status = ?, response_json = ?, error = ?, finished_at = ?
                WHERE dispatch_id = ?
                """,
                (
                    status,
                    (
                        json.dumps(response, sort_keys=True, ensure_ascii=False)
                        if response is not None
                        else None
                    ),
                    error,
                    utc_now(),
                    dispatch_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(dispatch_id)
        return self.get_dispatch(dispatch_id) or {}

    @staticmethod
    def _decode_dispatch(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["request"] = json.loads(data.pop("request_json"))
        raw_response = data.pop("response_json")
        data["response"] = json.loads(raw_response) if raw_response else None
        return data

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM dispatches WHERE dispatch_id = ?",
                (dispatch_id,),
            ).fetchone()
        return self._decode_dispatch(row)

    def list_dispatches(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM dispatches ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode_dispatch(row) or {} for row in rows]

    def record_transfer(
        self,
        *,
        transfer_id: str,
        source_session_id: str,
        target_session_id: str,
        target_workspace_id: str,
        target_product_id: str | None,
        portable_context: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO context_transfers(
                    transfer_id, source_session_id, target_session_id,
                    target_workspace_id, target_product_id,
                    portable_context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer_id,
                    source_session_id,
                    target_session_id,
                    target_workspace_id,
                    target_product_id,
                    json.dumps(
                        portable_context,
                        sort_keys=True,
                        ensure_ascii=False,
                    ),
                    created_at,
                ),
            )
        return {
            "transfer_id": transfer_id,
            "source_session_id": source_session_id,
            "target_session_id": target_session_id,
            "target_workspace_id": target_workspace_id,
            "target_product_id": target_product_id,
            "portable_context": portable_context,
            "created_at": created_at,
        }

    def record_companion_message(
        self,
        *,
        turn_id: str,
        session_id: str,
        role: str,
        content: str,
        status: str,
        summary: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO companion_messages(
                    turn_id, session_id, role, content, status,
                    summary_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    session_id,
                    role,
                    content,
                    status,
                    json.dumps(summary, sort_keys=True, ensure_ascii=False),
                    json.dumps(metadata, sort_keys=True, ensure_ascii=False),
                    created_at,
                ),
            )
        return self.get_companion_message(turn_id) or {}

    @staticmethod
    def _decode_companion_message(
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["summary"] = json.loads(data.pop("summary_json"))
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    def get_companion_message(self, turn_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM companion_messages WHERE turn_id = ?",
                (turn_id,),
            ).fetchone()
        return self._decode_companion_message(row)

    def list_companion_messages(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM companion_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            self._decode_companion_message(row) or {}
            for row in reversed(rows)
        ]

    def latest_companion_summary(self, session_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT summary_json FROM companion_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return json.loads(row["summary_json"]) if row else {}

    def create_companion_task(
        self,
        *,
        task_id: str,
        session_id: str,
        kind: str,
        status: str,
        status_detail: str | None,
        notification: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO companion_tasks(
                    task_id, session_id, kind, status, status_detail,
                    notification_json, result_json, metadata_json,
                    created_at, updated_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL)
                """,
                (
                    task_id,
                    session_id,
                    kind,
                    status,
                    status_detail,
                    json.dumps(
                        notification,
                        sort_keys=True,
                        ensure_ascii=False,
                    ),
                    json.dumps(metadata, sort_keys=True, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get_companion_task(task_id) or {}

    def update_companion_task(
        self,
        task_id: str,
        *,
        status: str,
        status_detail: str | None,
        notification: dict[str, Any],
        result: dict[str, Any] | None,
        finished: bool,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE companion_tasks
                SET status = ?, status_detail = ?, notification_json = ?,
                    result_json = ?, updated_at = ?, finished_at = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    status_detail,
                    json.dumps(
                        notification,
                        sort_keys=True,
                        ensure_ascii=False,
                    ),
                    (
                        json.dumps(result, sort_keys=True, ensure_ascii=False)
                        if result is not None
                        else None
                    ),
                    now,
                    now if finished else None,
                    task_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(task_id)
        return self.get_companion_task(task_id) or {}

    @staticmethod
    def _decode_companion_task(
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["notification"] = json.loads(data.pop("notification_json"))
        raw_result = data.pop("result_json")
        data["result"] = json.loads(raw_result) if raw_result else None
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    def get_companion_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM companion_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return self._decode_companion_task(row)

    def list_companion_tasks(
        self,
        *,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM companion_tasks"
        params: tuple[Any, ...]
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id, limit)
        else:
            params = (limit,)
        query += " ORDER BY updated_at DESC LIMIT ?"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decode_companion_task(row) or {} for row in rows]

    def counts(self) -> dict[str, int]:
        with self.connection() as connection:
            sessions = connection.execute(
                "SELECT COUNT(*) AS count FROM sessions"
            ).fetchone()["count"]
            attachments = connection.execute(
                "SELECT COUNT(*) AS count FROM attachments WHERE state != ?",
                (AttachmentState.DETACHED.value,),
            ).fetchone()["count"]
            dispatches = connection.execute(
                "SELECT COUNT(*) AS count FROM dispatches"
            ).fetchone()["count"]
            failures = connection.execute(
                "SELECT COUNT(*) AS count FROM dispatches WHERE status = 'FAILED'"
            ).fetchone()["count"]
        return {
            "sessions": sessions,
            "attachments": attachments,
            "dispatches": dispatches,
            "failed_dispatches": failures,
        }
