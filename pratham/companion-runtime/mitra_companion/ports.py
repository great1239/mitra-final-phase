from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .contracts import DispatchTarget, ProductAttachmentManifest


class TransportAdapter(Protocol):
    """Published port for a product dispatch transport implementation."""

    mode: str

    def validate_target(
        self,
        manifest: ProductAttachmentManifest,
        target: DispatchTarget,
    ) -> None: ...

    async def dispatch(
        self,
        *,
        route: dict[str, Any],
        envelope: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]: ...


class ManifestSourceAdapter(Protocol):
    """Published port for discovering attachment manifests."""

    def load(self) -> list[ProductAttachmentManifest]: ...


class FileReader(Protocol):
    """Small filesystem seam used by manifest-source adapters."""

    def read_text(self, path: Path) -> str: ...


class LifecycleStorePort(Protocol):
    def current_state(self) -> Any: ...

    def record_transition(
        self,
        from_state: Any,
        to_state: Any,
        reason: str,
    ) -> dict[str, Any]: ...

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]: ...


class SessionStorePort(Protocol):
    def create_session(self, **values: Any) -> dict[str, Any]: ...

    def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    def get_session_token_hash(self, session_id: str) -> str | None: ...

    def mark_session_resumed(self, session_id: str) -> dict[str, Any]: ...

    def set_session_state(
        self,
        session_id: str,
        state: Any,
    ) -> dict[str, Any]: ...

    def record_transfer(self, **values: Any) -> dict[str, Any]: ...


class SessionLookupPort(Protocol):
    def get(self, session_id: str) -> dict[str, Any]: ...


class ContextStorePort(Protocol):
    def upsert_context(self, **values: Any) -> dict[str, Any]: ...

    def get_context(
        self,
        session_id: str,
        scope: str,
        scope_key: str,
        owner_id: str | None = None,
    ) -> dict[str, Any]: ...


class AttachmentStorePort(Protocol):
    def attach_product(
        self,
        product_id: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]: ...

    def get_attachment(self, product_id: str) -> dict[str, Any] | None: ...

    def list_attachments(self, **options: Any) -> list[dict[str, Any]]: ...

    def set_attachment_state(
        self,
        product_id: str,
        state: Any,
        error: str | None = None,
    ) -> dict[str, Any]: ...


class AttachmentRegistryPort(Protocol):
    def get(self, product_id: str) -> dict[str, Any]: ...

    def list(self) -> list[dict[str, Any]]: ...
