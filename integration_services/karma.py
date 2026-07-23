from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .common import canonical_bytes, sha256_bytes, utc_now


DEFAULT_GENESIS_HASH = "0" * 64


class KarmaStore:
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


def create_app(
    *,
    database_path: str | Path | None = None,
    genesis_hash: str | None = None,
) -> FastAPI:
    store = KarmaStore(
        database_path
        or os.environ.get("KARMA_DATABASE_PATH", "var/karma.db"),
        genesis_hash
        or os.environ.get("KARMA_GENESIS_HASH", DEFAULT_GENESIS_HASH),
    )
    app = FastAPI(title="Karma Integrity Runtime", version="1.0.0")
    app.state.store = store

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "karma-integrity",
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
