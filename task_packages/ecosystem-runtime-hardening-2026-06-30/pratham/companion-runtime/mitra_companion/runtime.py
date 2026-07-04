from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

from mitra_attachment import AttachmentRuntime
from mitra_context import ContextRuntime
from mitra_intent import IntentRouter
from mitra_session import SessionRuntime

from .config import RuntimeSettings
from .constants import AttachmentState, DispatchStatus, RuntimeState
from .contracts import (
    ContextTransferRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from .errors import IntentRoutingError, ResourceNotFoundError, TransportError
from .lifecycle import RuntimeLifecycle
from .store import RuntimeStore
from .telemetry import RuntimeTelemetry
from .transport import CapabilityTransport
from .utils import utc_now


class CompanionRuntime:
    """Composition root for lifecycle, sessions, context, routing, and attachments."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        transport: CapabilityTransport | None = None,
    ):
        self.settings = settings
        self.settings.prepare()
        self.store = RuntimeStore(settings.database_path)
        self.lifecycle = RuntimeLifecycle(self.store)
        self.sessions = SessionRuntime(self.store)
        self.context = ContextRuntime(self.store, self.sessions)
        self.attachments = AttachmentRuntime(self.store)
        self.router = IntentRouter(self.attachments, self.sessions)
        self.transport = transport or CapabilityTransport(
            default_timeout_seconds=settings.http_timeout_seconds,
        )
        self.telemetry = RuntimeTelemetry(settings.telemetry_log_path)
        self.accepting = False

    def start(self) -> dict[str, Any]:
        if self.lifecycle.state == RuntimeState.STOPPED:
            self.lifecycle.transition(
                RuntimeState.INITIALIZING,
                "Runtime process started",
            )
        self.accepting = True
        self.lifecycle.transition(
            RuntimeState.READY,
            "Runtime storage and interfaces are ready",
        )
        self.telemetry.record_event(
            "runtime.started",
            state=self.lifecycle.state.value,
            accepting=self.accepting,
        )
        return self.status()

    def stop(self) -> dict[str, Any]:
        if self.lifecycle.state != RuntimeState.STOPPED:
            if self.lifecycle.state not in {
                RuntimeState.DRAINING,
                RuntimeState.INITIALIZING,
            }:
                self.lifecycle.transition(
                    RuntimeState.DRAINING,
                    "Runtime is draining new work",
                )
            self.accepting = False
            self.lifecycle.transition(
                RuntimeState.STOPPED,
                "Runtime stopped cleanly",
            )
        self.telemetry.record_event(
            "runtime.stopped",
            state=self.lifecycle.state.value,
            accepting=self.accepting,
        )
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "state": self.lifecycle.state.value,
            "accepting": self.accepting,
            "database_path": "${MITRA_COMPANION_DATA_ROOT}/"
            + self.settings.database_path.name,
            "counts": self.store.counts(),
            "attached_products": [
                item["product_id"] for item in self.attachments.list()
            ],
            "telemetry": self.telemetry.snapshot(),
        }

    def attach(self, manifest: ProductAttachmentManifest) -> dict[str, Any]:
        if not self.accepting:
            raise RuntimeError("Runtime is not accepting attachments")
        self.transport.validate_manifest(manifest)
        attachment = self.attachments.attach(manifest)
        registration = self.router.register(manifest.product_id)
        if (
            self.lifecycle.state == RuntimeState.DEGRADED
            and all(
                item["state"] == "ATTACHED"
                for item in self.attachments.list()
            )
        ):
            self.lifecycle.transition(
                RuntimeState.READY,
                "All attached product transports were restored",
            )
        self.telemetry.record_event(
            "attachment.attached",
            product_id=manifest.product_id,
            state=attachment["state"],
            capability_count=len(manifest.capabilities),
            intent_registration_count=registration["registration_count"],
        )
        return {
            **attachment,
            "intent_registration_count": registration[
                "registration_count"
            ],
        }

    def attach_many(
        self,
        manifests: Iterable[ProductAttachmentManifest],
    ) -> dict[str, Any]:
        attachments = [self.attach(manifest) for manifest in manifests]
        return {
            "attached_count": len(attachments),
            "attachments": attachments,
        }

    def detach(self, product_id: str) -> dict[str, Any]:
        if not self.accepting:
            raise RuntimeError("Runtime is not accepting detachments")
        attachment = self.attachments.detach(product_id)
        if (
            self.lifecycle.state == RuntimeState.DEGRADED
            and all(
                item["state"] == "ATTACHED"
                for item in self.attachments.list()
            )
        ):
            self.lifecycle.transition(
                RuntimeState.READY,
                "Detached degraded product no longer affects routing",
            )
        self.telemetry.record_event(
            "attachment.detached",
            product_id=product_id,
            state=attachment["state"],
        )
        return {
            **attachment,
            "intent_registration_count": 0,
        }

    def transfer_context(
        self,
        source_session_id: str,
        request: ContextTransferRequest,
    ) -> dict[str, Any]:
        if request.target_product_id:
            self.attachments.get(request.target_product_id)
        transfer = self.sessions.transfer(
            source_session_id=source_session_id,
            target_workspace_id=request.target_workspace_id,
            target_product_id=request.target_product_id,
            portable_context=request.portable_context,
            metadata=request.metadata,
        )
        context = self.context.initialize_transfer(
            transfer["session"]["session_id"],
            request.portable_context,
        )
        return {**transfer, "context": context}

    async def dispatch(
        self,
        request: IntentDispatchRequest,
    ) -> dict[str, Any]:
        if not self.accepting:
            raise RuntimeError("Runtime is not accepting dispatches")
        route = self.router.route(
            session_id=request.session_id,
            intent_id=request.intent_id,
            product_id=request.product_id,
            capability_id=request.capability_id,
        )
        validation_errors = sorted(
            Draft202012Validator(route["input_schema"]).iter_errors(
                request.payload
            ),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if validation_errors:
            detail = "; ".join(error.message for error in validation_errors[:3])
            raise IntentRoutingError(
                f"Intent payload does not satisfy {route['intent_id']} input "
                f"schema: {detail}"
            )
        attachment = self.attachments.get(route["product_id"])
        context = self.context.load_for_capability(
            request.session_id,
            route["context_scopes"],
        )
        dispatch_id = f"dsp_{uuid4().hex}"
        correlation_id = request.correlation_id or f"corr_{uuid4().hex}"
        envelope = {
            "schema_version": request.schema_version,
            "contract_version": request.contract_version,
            "runtime_version": request.runtime_version,
            "compatibility_version": request.compatibility_version,
            "dispatch_id": dispatch_id,
            "correlation_id": correlation_id,
            "session_id": request.session_id,
            "product_id": route["product_id"],
            "capability_id": route["capability_id"],
            "intent_id": route["intent_id"],
            "occurred_at": utc_now(),
            "payload": request.payload,
            "context": {
                "loaded_scopes": context["loaded_scopes"],
                "merge_precedence": context["merge_precedence"],
                "partitions": context["partitions"],
                "merged": context["merged"],
            },
        }
        self.store.create_dispatch(
            dispatch_id=dispatch_id,
            session_id=request.session_id,
            product_id=route["product_id"],
            capability_id=route["capability_id"],
            intent_id=route["intent_id"],
            status=DispatchStatus.ACCEPTED.value,
            request=envelope,
        )
        if self.lifecycle.state == RuntimeState.READY:
            self.lifecycle.transition(
                RuntimeState.ACTIVE,
                "Intent dispatch started",
            )
        dispatch_started = time.perf_counter()
        try:
            try:
                response = await self.transport.dispatch(
                    route=route,
                    envelope=envelope,
                    manifest=attachment["manifest"],
                )
            except TransportError:
                raise
            except Exception as exc:
                raise TransportError(
                    "Capability transport raised an unexpected error: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            dispatch = self.store.complete_dispatch(
                dispatch_id,
                status=DispatchStatus.COMPLETED.value,
                response=response,
            )
            self.telemetry.record_dispatch(
                product_id=route["product_id"],
                capability_id=route["capability_id"],
                intent_id=route["intent_id"],
                dispatch_id=dispatch_id,
                status=DispatchStatus.COMPLETED.value,
                latency_ms=(time.perf_counter() - dispatch_started) * 1000,
            )
        except TransportError as exc:
            self.attachments.mark_degraded(route["product_id"], str(exc))
            self.lifecycle.transition(
                RuntimeState.DEGRADED,
                f"Capability transport failed for {route['product_id']}",
            )
            dispatch = self.store.complete_dispatch(
                dispatch_id,
                status=DispatchStatus.FAILED.value,
                error=str(exc),
            )
            self.telemetry.record_dispatch(
                product_id=route["product_id"],
                capability_id=route["capability_id"],
                intent_id=route["intent_id"],
                dispatch_id=dispatch_id,
                status=DispatchStatus.FAILED.value,
                latency_ms=(time.perf_counter() - dispatch_started) * 1000,
                error=str(exc),
            )
            raise
        finally:
            if self.lifecycle.state == RuntimeState.ACTIVE:
                self.lifecycle.transition(
                    RuntimeState.READY,
                    "Intent dispatch completed",
                )
        return {
            "dispatch": dispatch,
            "route": route,
        }

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any]:
        dispatch = self.store.get_dispatch(dispatch_id)
        if dispatch is None:
            raise ResourceNotFoundError(f"Unknown dispatch: {dispatch_id}")
        return dispatch

    async def check_attachment_health(
        self,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        attachments = (
            [self.attachments.get(product_id)]
            if product_id is not None
            else self.attachments.list()
        )
        checks = []
        for attachment in attachments:
            health = await self.transport.check_manifest_health(
                attachment["manifest"]
            )
            product = attachment["product_id"]
            recovered = False
            if (
                health["status"] == "unhealthy"
                and attachment["state"] == AttachmentState.ATTACHED.value
            ):
                self.attachments.mark_degraded(
                    product,
                    health.get("error")
                    or health.get("message")
                    or "Attachment health check failed",
                )
                if self.lifecycle.state in {
                    RuntimeState.READY,
                    RuntimeState.ACTIVE,
                }:
                    self.lifecycle.transition(
                        RuntimeState.DEGRADED,
                        f"Health check failed for {product}",
                    )
            if (
                health["status"] == "healthy"
                and attachment["state"] == AttachmentState.DEGRADED.value
            ):
                manifest = ProductAttachmentManifest.model_validate(
                    attachment["manifest"]
                )
                self.attach(manifest)
                recovered = True
            self.telemetry.record_attachment_health(product, health)
            self.telemetry.record_recovery_validation(
                product_id=product,
                recovered=recovered,
                health=health,
            )
            checks.append(
                {
                    "product_id": product,
                    "previous_attachment_state": attachment["state"],
                    "health": health,
                    "recovered": recovered,
                    "attachment": self.attachments.get(product),
                }
            )
        return {
            "checked_count": len(checks),
            "checks": checks,
        }

    def metrics_snapshot(self) -> dict[str, Any]:
        return self.telemetry.snapshot()

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.telemetry.recent_events(limit)

    def prometheus_metrics(self) -> str:
        return self.telemetry.prometheus_text()
