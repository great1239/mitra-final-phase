from __future__ import annotations

import secrets
from typing import Any
from uuid import uuid4

from mitra_companion.errors import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from mitra_companion.constants import SessionState
from mitra_companion.ports import SessionStorePort
from mitra_companion.utils import sha256_text


class SessionRuntime:
    """Creates and resumes transport-neutral companion sessions."""

    def __init__(self, store: SessionStorePort):
        self.store = store

    def create(
        self,
        *,
        actor_id: str,
        client_type: str,
        workspace_id: str,
        product_id: str | None,
        metadata: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
    ) -> dict[str, Any]:
        session_id = f"ses_{uuid4().hex}"
        resume_token = secrets.token_urlsafe(32)
        session = self.store.create_session(
            session_id=session_id,
            parent_session_id=parent_session_id,
            resume_token_hash=sha256_text(resume_token),
            actor_id=actor_id,
            client_type=client_type,
            workspace_id=workspace_id,
            active_product_id=product_id,
            metadata=metadata or {},
        )
        return {**session, "resume_token": resume_token}

    def get(self, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if session is None:
            raise ResourceNotFoundError(f"Unknown session: {session_id}")
        return session

    def resume(self, session_id: str, resume_token: str) -> dict[str, Any]:
        stored_hash = self.store.get_session_token_hash(session_id)
        if stored_hash is None:
            raise ResourceNotFoundError(f"Unknown session: {session_id}")
        if not secrets.compare_digest(stored_hash, sha256_text(resume_token)):
            raise ResourceConflictError("Session resume token is invalid")
        session = self.get(session_id)
        if session["state"] == "CLOSED":
            raise ResourceConflictError("Closed sessions cannot be resumed")
        return self.store.mark_session_resumed(session_id)

    def suspend(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        if session["state"] == SessionState.CLOSED.value:
            raise ResourceConflictError("Closed sessions cannot be suspended")
        if session["state"] == SessionState.SUSPENDED.value:
            return session
        return self.store.set_session_state(
            session_id,
            SessionState.SUSPENDED,
        )

    def close(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        if session["state"] == SessionState.CLOSED.value:
            return session
        return self.store.set_session_state(
            session_id,
            SessionState.CLOSED,
        )

    def transfer(
        self,
        *,
        source_session_id: str,
        target_workspace_id: str,
        target_product_id: str | None,
        portable_context: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = self.get(source_session_id)
        if source["state"] != SessionState.ACTIVE.value:
            raise ResourceConflictError(
                "Only active sessions can transfer context"
            )
        target = self.create(
            actor_id=source["actor_id"],
            client_type=source["client_type"],
            workspace_id=target_workspace_id,
            product_id=target_product_id,
            metadata={
                **source["metadata"],
                **(metadata or {}),
                "transferred_from": source_session_id,
            },
            parent_session_id=source_session_id,
        )
        transfer = self.store.record_transfer(
            transfer_id=f"xfer_{uuid4().hex}",
            source_session_id=source_session_id,
            target_session_id=target["session_id"],
            target_workspace_id=target_workspace_id,
            target_product_id=target_product_id,
            portable_context=portable_context,
        )
        return {"session": target, "transfer": transfer}
