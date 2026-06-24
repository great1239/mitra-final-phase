from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any, Protocol, runtime_checkable

from .constants import RuntimeState
from .contracts import (
    ContextTransferRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
)


@runtime_checkable
class LifecycleInterface(Protocol):
    """Public runtime lifecycle interface."""

    state: RuntimeState

    def transition(
        self,
        target: RuntimeState,
        reason: str,
    ) -> dict[str, Any]: ...

    def history(self, limit: int = 100) -> list[dict[str, Any]]: ...


@runtime_checkable
class SessionRuntimeInterface(Protocol):
    """Public interface for durable session identity and continuity."""

    def create(
        self,
        *,
        actor_id: str,
        client_type: str,
        workspace_id: str,
        product_id: str | None,
        metadata: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
    ) -> dict[str, Any]: ...

    def get(self, session_id: str) -> dict[str, Any]: ...

    def resume(
        self,
        session_id: str,
        resume_token: str,
    ) -> dict[str, Any]: ...

    def suspend(self, session_id: str) -> dict[str, Any]: ...

    def close(self, session_id: str) -> dict[str, Any]: ...

    def transfer(
        self,
        *,
        source_session_id: str,
        target_workspace_id: str,
        target_product_id: str | None,
        portable_context: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class ContextRuntimeInterface(Protocol):
    """Public interface for context loading, updates, and handoff."""

    def update(
        self,
        *,
        session_id: str,
        scope: str,
        patch: dict[str, Any],
        expected_revision: int | None,
        replace: bool,
    ) -> dict[str, Any]: ...

    def load(
        self,
        session_id: str,
        scopes: Collection[str] | None = None,
    ) -> dict[str, Any]: ...

    def load_for_capability(
        self,
        session_id: str,
        scopes: Collection[str],
    ) -> dict[str, Any]: ...

    def initialize_transfer(
        self,
        target_session_id: str,
        portable_context: dict[str, Any],
    ) -> dict[str, Any]: ...


@runtime_checkable
class IntentRouterInterface(Protocol):
    """Public interface for explicit intent discovery and routing."""

    def register(self, product_id: str) -> dict[str, Any]: ...

    def discover(
        self,
        *,
        product_id: str | None = None,
        capability_id: str | None = None,
        intent_id: str | None = None,
        available_only: bool = False,
    ) -> list[dict[str, Any]]: ...

    def capabilities(
        self,
        *,
        product_id: str | None = None,
        available_only: bool = False,
    ) -> list[dict[str, Any]]: ...

    def lookup_capability(
        self,
        *,
        product_id: str,
        capability_id: str,
    ) -> dict[str, Any]: ...

    def route(
        self,
        *,
        session_id: str,
        intent_id: str,
        product_id: str | None,
        capability_id: str | None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class AttachmentRuntimeInterface(Protocol):
    """Public interface for capability and product attachment lifecycle."""

    def attach(
        self,
        manifest: ProductAttachmentManifest,
    ) -> dict[str, Any]: ...

    def get(self, product_id: str) -> dict[str, Any]: ...

    def attach_many(
        self,
        manifests: Iterable[ProductAttachmentManifest],
    ) -> dict[str, Any]: ...

    def list(
        self,
        *,
        include_detached: bool = False,
    ) -> list[dict[str, Any]]: ...

    def detach(self, product_id: str) -> dict[str, Any]: ...

    def mark_degraded(
        self,
        product_id: str,
        error: str,
    ) -> dict[str, Any]: ...


@runtime_checkable
class ContextTransferRuntimeInterface(Protocol):
    """Public orchestration interface for product/workspace context transfer."""

    def transfer_context(
        self,
        source_session_id: str,
        request: ContextTransferRequest,
    ) -> dict[str, Any]: ...


@runtime_checkable
class CompanionRuntimeInterface(
    ContextTransferRuntimeInterface,
    Protocol,
):
    """Top-level public interface for the Companion Runtime."""

    lifecycle: LifecycleInterface
    sessions: SessionRuntimeInterface
    context: ContextRuntimeInterface
    router: IntentRouterInterface
    attachments: AttachmentRuntimeInterface
    accepting: bool

    def start(self) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...

    def status(self) -> dict[str, Any]: ...

    def attach(
        self,
        manifest: ProductAttachmentManifest,
    ) -> dict[str, Any]: ...

    def attach_many(
        self,
        manifests: Iterable[ProductAttachmentManifest],
    ) -> dict[str, Any]: ...

    def detach(self, product_id: str) -> dict[str, Any]: ...

    async def dispatch(
        self,
        request: IntentDispatchRequest,
    ) -> dict[str, Any]: ...

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any]: ...
