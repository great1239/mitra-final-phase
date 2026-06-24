from __future__ import annotations

from collections.abc import Collection
from typing import Any

from mitra_companion.constants import ContextScope, SessionState
from mitra_companion.errors import ResourceConflictError
from mitra_companion.ports import ContextStorePort, SessionLookupPort
from mitra_companion.utils import merge_context


class ContextRuntime:
    """Maintains isolated session, workspace, product, and handoff context."""

    MERGE_PRECEDENCE = (
        ContextScope.SESSION,
        ContextScope.WORKSPACE,
        ContextScope.HANDOFF,
        ContextScope.PRODUCT,
    )

    def __init__(
        self,
        store: ContextStorePort,
        sessions: SessionLookupPort,
    ):
        self.store = store
        self.sessions = sessions

    @staticmethod
    def _scope_key(session: dict[str, Any], scope: ContextScope) -> str:
        if scope == ContextScope.SESSION:
            return session["session_id"]
        if scope == ContextScope.WORKSPACE:
            return session["workspace_id"]
        if scope == ContextScope.PRODUCT:
            if not session["active_product_id"]:
                raise ResourceConflictError(
                    "Session has no active product context"
                )
            return session["active_product_id"]
        return session["session_id"]

    def update(
        self,
        *,
        session_id: str,
        scope: str,
        patch: dict[str, Any],
        expected_revision: int | None,
        replace: bool,
    ) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session["state"] != SessionState.ACTIVE.value:
            raise ResourceConflictError(
                "Only active sessions can update context"
            )
        scope_value = ContextScope(scope)
        scope_key = self._scope_key(session, scope_value)
        return self.store.upsert_context(
            session_id=session_id,
            scope=scope_value.value,
            scope_key=scope_key,
            owner_id=(
                session["actor_id"]
                if scope_value == ContextScope.WORKSPACE
                else None
            ),
            patch=patch,
            expected_revision=expected_revision,
            replace=replace,
        )

    @classmethod
    def _normalize_scopes(
        cls,
        scopes: Collection[str] | None,
    ) -> tuple[ContextScope, ...]:
        if scopes is None:
            return cls.MERGE_PRECEDENCE
        requested = {ContextScope(scope) for scope in scopes}
        return tuple(
            scope for scope in cls.MERGE_PRECEDENCE if scope in requested
        )

    @staticmethod
    def _empty_product_context(session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "scope": ContextScope.PRODUCT.value,
            "scope_key": None,
            "revision": 0,
            "data": {},
            "updated_at": None,
        }

    def load(
        self,
        session_id: str,
        scopes: Collection[str] | None = None,
    ) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        selected_scopes = self._normalize_scopes(scopes)
        partitions: dict[str, dict[str, Any]] = {}
        for scope in selected_scopes:
            if scope == ContextScope.SESSION:
                partition = self.store.get_context(
                    session_id,
                    scope.value,
                    session_id,
                )
            elif scope == ContextScope.WORKSPACE:
                partition = self.store.get_context(
                    session_id,
                    scope.value,
                    session["workspace_id"],
                    owner_id=session["actor_id"],
                )
            elif scope == ContextScope.HANDOFF:
                partition = self.store.get_context(
                    session_id,
                    scope.value,
                    session_id,
                )
            elif session["active_product_id"]:
                partition = self.store.get_context(
                    session_id,
                    scope.value,
                    session["active_product_id"],
                )
            else:
                partition = self._empty_product_context(session_id)
            partitions[scope.value] = partition

        return {
            "session_id": session_id,
            "workspace_id": session["workspace_id"],
            "active_product_id": session["active_product_id"],
            "continuity": {
                "actor_id": session["actor_id"],
                "client_type": session["client_type"],
                "session_state": session["state"],
                "parent_session_id": session["parent_session_id"],
            },
            "loaded_scopes": [scope.value for scope in selected_scopes],
            "merge_precedence": [
                scope.value for scope in self.MERGE_PRECEDENCE
            ],
            "partitions": partitions,
            "merged": merge_context(
                *(partitions[scope.value]["data"] for scope in selected_scopes)
            ),
        }

    def load_for_capability(
        self,
        session_id: str,
        scopes: Collection[str],
    ) -> dict[str, Any]:
        """Load only the partitions declared by a published capability."""
        return self.load(session_id, scopes=scopes)

    def initialize_transfer(
        self,
        target_session_id: str,
        portable_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not portable_context:
            return self.load(target_session_id)
        self.update(
            session_id=target_session_id,
            scope=ContextScope.HANDOFF.value,
            patch=portable_context,
            expected_revision=0,
            replace=True,
        )
        return self.load(target_session_id)
