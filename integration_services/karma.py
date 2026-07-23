from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request

from .common import canonical_bytes, sha256_bytes, utc_now


DEFAULT_GENESIS_HASH = "0" * 64


class IntegrityStore(Protocol):
    backend: str
    durable: bool

    def state(self) -> dict[str, Any]: ...

    def append(
        self,
        *,
        record_kind: str,
        replay_key: str,
        trace_id: str | None,
        parent_hash: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def get(self, replay_key: str) -> dict[str, Any] | None: ...


class KarmaStore:
    backend = "sqlite"
    durable = False

    def __init__(self, database_path: str | Path, genesis_hash: str) -> None:
        self.database_path = str(database_path)
        self.genesis_hash = genesis_hash
        self._lock = Lock()
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS integrity_chain (
                    chain_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_kind TEXT NOT NULL,
                    replay_key TEXT NOT NULL,
                    trace_id TEXT,
                    parent_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(record_kind, replay_key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def state(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT current_hash FROM integrity_chain ORDER BY chain_index DESC LIMIT 1"
            ).fetchone()
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM integrity_chain"
            ).fetchone()["count"]
        return {
            "last_hash": row["current_hash"] if row else self.genesis_hash,
            "entry_count": int(count),
        }

    def append(
        self,
        *,
        record_kind: str,
        replay_key: str,
        trace_id: str | None,
        parent_hash: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        encoded = canonical_bytes(payload)
        request_hash = sha256_bytes(encoded)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT current_hash, request_sha256, trace_id
                FROM integrity_chain
                WHERE record_kind = ? AND replay_key = ?
                """,
                (record_kind, replay_key),
            ).fetchone()
            if existing:
                connection.commit()
                return {
                    "status": "replay_detected",
                    "current_hash": existing["current_hash"],
                    "request_sha256": existing["request_sha256"],
                    "trace_id": existing["trace_id"],
                    "replay_key": replay_key,
                }

            latest = connection.execute(
                "SELECT current_hash FROM integrity_chain ORDER BY chain_index DESC LIMIT 1"
            ).fetchone()
            expected_parent = (
                latest["current_hash"] if latest else self.genesis_hash
            )
            if parent_hash != expected_parent:
                connection.commit()
                return {
                    "status": "append_violation",
                    "expected_parent_hash": expected_parent,
                    "received_parent_hash": parent_hash,
                    "trace_id": trace_id,
                    "replay_key": replay_key,
                }

            current_hash = request_hash
            created_at = utc_now()
            connection.execute(
                """
                INSERT INTO integrity_chain (
                    record_kind, replay_key, trace_id, parent_hash,
                    current_hash, request_sha256, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_kind,
                    replay_key,
                    trace_id,
                    parent_hash,
                    current_hash,
                    request_hash,
                    encoded.decode("utf-8"),
                    created_at,
                ),
            )
            connection.commit()
        return {
            "status": "appended",
            "current_hash": current_hash,
            "last_hash": current_hash,
            "request_sha256": request_hash,
            "trace_id": trace_id,
            "replay_key": replay_key,
            "created_at": created_at,
        }

    def get(self, replay_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM integrity_chain WHERE replay_key = ? ORDER BY chain_index DESC LIMIT 1",
                (replay_key,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result


class PostgresKarmaStore:
    backend = "postgresql"
    durable = True

    def __init__(self, database_url: str, genesis_hash: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required when KARMA_DATABASE_URL is configured"
            ) from exc

        self.database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )
        self.genesis_hash = genesis_hash
        self._psycopg = psycopg
        self._dict_row = dict_row
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS karma_chain_state (
                        chain_name TEXT PRIMARY KEY,
                        last_hash TEXT NOT NULL,
                        entry_count BIGINT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS karma_integrity_chain (
                        chain_index BIGINT PRIMARY KEY,
                        record_kind TEXT NOT NULL,
                        replay_key TEXT NOT NULL,
                        trace_id TEXT,
                        parent_hash TEXT NOT NULL,
                        current_hash TEXT NOT NULL,
                        request_sha256 TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(record_kind, replay_key)
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO karma_chain_state (
                        chain_name, last_hash, entry_count
                    ) VALUES ('default', %s, 0)
                    ON CONFLICT (chain_name) DO NOTHING
                    """,
                    (self.genesis_hash,),
                )
            connection.commit()

    def _connect(self):
        return self._psycopg.connect(
            self.database_url,
            row_factory=self._dict_row,
            connect_timeout=15,
        )

    def state(self) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT last_hash, entry_count
                    FROM karma_chain_state
                    WHERE chain_name = 'default'
                    """
                )
                row = cursor.fetchone()
        if row is None:
            return {
                "last_hash": self.genesis_hash,
                "entry_count": 0,
            }
        return {
            "last_hash": row["last_hash"],
            "entry_count": int(row["entry_count"]),
        }

    def append(
        self,
        *,
        record_kind: str,
        replay_key: str,
        trace_id: str | None,
        parent_hash: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        encoded = canonical_bytes(payload)
        request_hash = sha256_bytes(encoded)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT last_hash, entry_count
                    FROM karma_chain_state
                    WHERE chain_name = 'default'
                    FOR UPDATE
                    """
                )
                state = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT current_hash, request_sha256, trace_id
                    FROM karma_integrity_chain
                    WHERE record_kind = %s AND replay_key = %s
                    """,
                    (record_kind, replay_key),
                )
                existing = cursor.fetchone()
                if existing:
                    connection.commit()
                    return {
                        "status": "replay_detected",
                        "current_hash": existing["current_hash"],
                        "request_sha256": existing["request_sha256"],
                        "trace_id": existing["trace_id"],
                        "replay_key": replay_key,
                    }

                expected_parent = (
                    state["last_hash"] if state else self.genesis_hash
                )
                if parent_hash != expected_parent:
                    connection.commit()
                    return {
                        "status": "append_violation",
                        "expected_parent_hash": expected_parent,
                        "received_parent_hash": parent_hash,
                        "trace_id": trace_id,
                        "replay_key": replay_key,
                    }

                chain_index = int(state["entry_count"]) + 1 if state else 1
                current_hash = request_hash
                created_at = utc_now()
                cursor.execute(
                    """
                    INSERT INTO karma_integrity_chain (
                        chain_index, record_kind, replay_key, trace_id,
                        parent_hash, current_hash, request_sha256,
                        payload_json, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    """,
                    (
                        chain_index,
                        record_kind,
                        replay_key,
                        trace_id,
                        parent_hash,
                        current_hash,
                        request_hash,
                        encoded.decode("utf-8"),
                        created_at,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE karma_chain_state
                    SET last_hash = %s, entry_count = %s
                    WHERE chain_name = 'default'
                    """,
                    (current_hash, chain_index),
                )
            connection.commit()
        return {
            "status": "appended",
            "current_hash": current_hash,
            "last_hash": current_hash,
            "request_sha256": request_hash,
            "trace_id": trace_id,
            "replay_key": replay_key,
            "created_at": created_at,
        }

    def get(self, replay_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM karma_integrity_chain
                    WHERE replay_key = %s
                    ORDER BY chain_index DESC
                    LIMIT 1
                    """,
                    (replay_key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        result = dict(row)
        payload = result.pop("payload_json")
        result["payload"] = (
            payload if isinstance(payload, dict) else json.loads(payload)
        )
        return result


def create_app(
    *,
    database_path: str | Path | None = None,
    database_url: str | None = None,
    genesis_hash: str | None = None,
) -> FastAPI:
    selected_genesis = genesis_hash or os.environ.get(
        "KARMA_GENESIS_HASH",
        DEFAULT_GENESIS_HASH,
    )
    selected_database_url = database_url
    if selected_database_url is None and database_path is None:
        selected_database_url = os.environ.get("KARMA_DATABASE_URL")
    store: IntegrityStore
    if selected_database_url:
        store = PostgresKarmaStore(
            selected_database_url,
            selected_genesis,
        )
    else:
        store = KarmaStore(
            database_path
            or os.environ.get("KARMA_DATABASE_PATH", "var/karma.db"),
            selected_genesis,
        )
    app = FastAPI(title="Karma Integrity Runtime", version="1.0.0")
    app.state.store = store

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "karma-integrity",
            "storage_backend": store.backend,
            "durable": store.durable,
            **store.state(),
        }

    @app.post("/integrity/append")
    async def append(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request must be an object")
        event_id = payload.get("event_id")
        parent_hash = payload.get("previous_hash")
        if not isinstance(event_id, str) or not event_id:
            raise HTTPException(status_code=422, detail="event_id is required")
        if not isinstance(parent_hash, str) or not parent_hash:
            raise HTTPException(status_code=422, detail="previous_hash is required")
        return store.append(
            record_kind="event",
            replay_key=event_id,
            trace_id=None,
            parent_hash=parent_hash,
            payload=payload,
        )

    @app.post("/integrity/append-bucket-artifact")
    async def append_bucket_artifact(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request must be an object")
        artifact_id = payload.get("artifact_id")
        trace_id = payload.get("trace_id")
        parent_hash = payload.get("parent_hash")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise HTTPException(status_code=422, detail="artifact_id is required")
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        if not isinstance(parent_hash, str) or not parent_hash:
            raise HTTPException(status_code=422, detail="parent_hash is required")
        return store.append(
            record_kind="bucket_artifact",
            replay_key=artifact_id,
            trace_id=trace_id,
            parent_hash=parent_hash,
            payload=payload,
        )

    @app.get("/integrity/entries/{replay_key}")
    async def get_entry(replay_key: str) -> dict[str, Any]:
        entry = store.get(replay_key)
        if entry is None:
            raise HTTPException(status_code=404, detail="entry not found")
        return entry

    return app


app = create_app()
