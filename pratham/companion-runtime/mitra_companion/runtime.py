from __future__ import annotations

import json
import time
import os
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

from mitra_attachment import AttachmentRuntime
from mitra_context import ContextRuntime
from mitra_intent import IntentRouter
from mitra_session import SessionRuntime

from .analysis import RuntimeAnalyzer
from .config import RuntimeSettings
from .constants import AttachmentState, DispatchStatus, RuntimeState
from .contracts import (
    CompanionMessageRequest,
    ContextTransferRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
    RuntimeAnalysisRequest,
)
from .errors import IntentRoutingError, ResourceNotFoundError, TransportError
from .interaction import (
    NaturalIntentResolver,
    build_capability_understanding,
    build_payload_from_message,
    summarize_memory,
)
from .lifecycle import RuntimeLifecycle
from .observability import runtime_span
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
        self.telemetry = RuntimeTelemetry(
            settings.telemetry_log_path,
            service_name=settings.otel_service_name,
            environment=settings.deployment_environment,
            runtime_instance_id=settings.runtime_instance_id,
        )
        self.intent_resolver = NaturalIntentResolver(
            threshold=settings.deterministic_intent_threshold,
            ai_resolver_url=settings.ai_resolver_url,
            ai_timeout_seconds=settings.ai_resolver_timeout_seconds,
        )
        self.analyzer = RuntimeAnalyzer(
            threshold=settings.deterministic_intent_threshold,
            ai_analysis_url=settings.ai_analysis_url,
            ai_timeout_seconds=settings.ai_analysis_timeout_seconds,
        )
        self.accepting = False

    @property
    def instance_id(self) -> str:
        return self.settings.runtime_instance_id

    def _heartbeat(self) -> dict[str, Any]:
        return self.store.heartbeat_runtime_instance(
            instance_id=self.instance_id,
            state=self.lifecycle.state.value,
        )

    def start(self) -> dict[str, Any]:
        self.store.upsert_runtime_instance(
            instance_id=self.instance_id,
            service_name=self.settings.otel_service_name,
            environment=self.settings.deployment_environment,
            process_id=os.getpid(),
            state=RuntimeState.INITIALIZING.value,
        )
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
        self._heartbeat()
        self.telemetry.record_event(
            "runtime.started",
            runtime_instance_id=self.instance_id,
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
        stopped = self.store.stop_runtime_instance(self.instance_id)
        self.telemetry.record_event(
            "runtime.stopped",
            runtime_instance_id=self.instance_id,
            state=self.lifecycle.state.value,
            accepting=self.accepting,
        )
        return {**self.status(), "stopped_instance": stopped}

    def status(self) -> dict[str, Any]:
        current_instance = self._heartbeat() if self.accepting else (
            self.store.get_runtime_instance(self.instance_id) or {}
        )
        instances = self.store.list_runtime_instances()
        return {
            "runtime_instance_id": self.instance_id,
            "state": self.lifecycle.state.value,
            "accepting": self.accepting,
            "database_path": "${MITRA_COMPANION_DATA_ROOT}/"
            + self.settings.database_path.name,
            "counts": self.store.counts(),
            "current_instance": current_instance,
            "active_runtime_instance_count": len(instances),
            "active_runtime_instances": instances,
            "attached_products": [
                item["product_id"] for item in self.attachments.list()
            ],
            "telemetry": self.telemetry.snapshot(),
        }

    def runtime_instances(
        self,
        *,
        include_stopped: bool = False,
    ) -> list[dict[str, Any]]:
        if self.accepting:
            self._heartbeat()
        return self.store.list_runtime_instances(
            include_stopped=include_stopped
        )

    def ecosystem_chain(self) -> dict[str, Any]:
        model = self._load_chain_contract()
        candidates = self.router.discover(available_only=False)
        return {
            **model,
            "attached_products": [
                item["product_id"] for item in self.attachments.list()
            ],
            "known_capabilities": [
                build_capability_understanding(candidate)
                for candidate in candidates
            ],
        }

    def _load_chain_contract(self) -> dict[str, Any]:
        path = self.settings.service_root / "contracts" / (
            "runtime-command-chain.json"
        )
        if not path.exists():
            return {
                "source": "missing-runtime-command-chain-contract",
                "systems": [],
                "product_execution_path": [],
                "trace_path": [],
            }
        return json.loads(path.read_text(encoding="utf-8"))

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
                with runtime_span(
                    "mitra.dispatch",
                    product_id=route["product_id"],
                    capability_id=route["capability_id"],
                    intent_id=route["intent_id"],
                    dispatch_id=dispatch_id,
                ):
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

    async def companion_message(
        self,
        request: CompanionMessageRequest,
    ) -> dict[str, Any]:
        if not self.accepting:
            raise RuntimeError("Runtime is not accepting companion messages")

        session = self._session_for_companion_message(request)
        memory_before = self.store.latest_companion_summary(
            session["session_id"]
        )
        user_turn = self.store.record_companion_message(
            turn_id=f"turn_{uuid4().hex}",
            session_id=session["session_id"],
            role="user",
            content=request.message,
            status="RECEIVED",
            summary=memory_before,
            metadata={
                "metadata": request.metadata,
                "payload": request.payload,
            },
        )

        candidate_product = request.product_id or session.get("active_product_id")
        candidates = self.router.discover(
            product_id=candidate_product,
            capability_id=request.capability_id,
            available_only=False,
        )
        runtime_analysis = await self.analyzer.analyze(
            message=request.message,
            assignment=request.assignment,
            metadata=request.metadata,
            explicit_payload=request.payload,
            candidates=candidates,
            session=session,
            memory=memory_before,
            metrics=self.metrics_snapshot(),
            allow_ai_fallback=request.allow_ai_fallback,
        )
        selection = await self.intent_resolver.select(
            message=request.message,
            candidates=candidates,
            session=session,
            memory=memory_before,
            metrics=self.metrics_snapshot(),
            allow_ai_fallback=request.allow_ai_fallback,
            runtime_analysis=runtime_analysis,
            product_id=candidate_product,
            capability_id=request.capability_id,
        )
        outcome = selection.get("outcome") or {}

        task: dict[str, Any] | None = None
        dispatch_result: dict[str, Any] | None = None
        assistant_status = "NEEDS_CLARIFICATION"
        assistant_text = selection.get(
            "message",
            "I need a little more detail before I can run that.",
        )
        final_payload: dict[str, Any] | None = None
        missing_fields: list[dict[str, Any]] = []

        if selection["status"] == "selected":
            candidate = selection["candidate"]
            if candidate["attachment_state"] != AttachmentState.ATTACHED.value:
                assistant_status = "UNAVAILABLE"
                assistant_text = (
                    "I found the right published capability, but it is not "
                    "available right now. I can retry after its health check "
                    "recovers."
                )
            else:
                payload_result = build_payload_from_message(
                    message=request.message,
                    explicit_payload={
                        **(runtime_analysis.get("ai_payload_hints") or {}),
                        **(selection.get("ai_payload") or {}),
                        **request.payload,
                    },
                    candidate=candidate,
                    memory=memory_before,
                )
                final_payload = payload_result["payload"]
                missing_fields = payload_result["missing"]
                if missing_fields:
                    assistant_status = "NEEDS_CLARIFICATION"
                    assistant_text = " ".join(
                        item["prompt"] for item in missing_fields
                    )
                elif not request.auto_dispatch:
                    assistant_status = "SELECTED"
                    assistant_text = (
                        "I found a matching published capability and am ready "
                        "to run it when you confirm."
                    )
                else:
                    assistant_status = "RUNNING"
                    task = self.store.create_companion_task(
                        task_id=f"task_{uuid4().hex}",
                        session_id=session["session_id"],
                        kind="capability_execution",
                        status="RUNNING",
                        status_detail=(
                            "Dispatching selected published capability"
                        ),
                        notification={
                            "type": "execution_status",
                            "message": "Capability execution started",
                        },
                        metadata={
                            "product_id": candidate["product_id"],
                            "capability_id": candidate["capability_id"],
                            "intent_id": candidate["intent_id"],
                        },
                    )
                    dispatch_request = IntentDispatchRequest(
                        session_id=session["session_id"],
                        product_id=candidate["product_id"],
                        capability_id=candidate["capability_id"],
                        intent_id=candidate["intent_id"],
                        payload=final_payload,
                    )
                    try:
                        dispatch_result = await self.dispatch(dispatch_request)
                    except TransportError as exc:
                        assistant_status = "FAILED"
                        assistant_text = (
                            "That capability is unavailable right now. I "
                            "recorded the failure and can retry after the "
                            "published health check recovers."
                        )
                        task = self.store.update_companion_task(
                            task["task_id"],
                            status="FAILED",
                            status_detail=str(exc),
                            notification={
                                "type": "execution_status",
                                "message": "Capability execution failed",
                            },
                            result={"error": str(exc)},
                            finished=True,
                        )
                    else:
                        assistant_status = "COMPLETED"
                        assistant_text = (
                            "I routed that through the selected published "
                            "capability and received a product response."
                        )
                        task = self.store.update_companion_task(
                            task["task_id"],
                            status="COMPLETED",
                            status_detail="Capability execution completed",
                            notification={
                                "type": "execution_status",
                                "message": "Capability execution completed",
                            },
                            result={
                                "dispatch_id": dispatch_result["dispatch"][
                                    "dispatch_id"
                                ],
                                "status": dispatch_result["dispatch"][
                                    "status"
                                ],
                            },
                            finished=True,
                        )

        memory_after = summarize_memory(
            previous=memory_before,
            user_message=request.message,
            assistant_message=assistant_text,
            status=assistant_status,
            selection=(
                selection if selection.get("status") == "selected" else None
            ),
            payload=final_payload,
            missing_fields=missing_fields,
            outcome=outcome,
            runtime_analysis=runtime_analysis,
        )
        assistant_turn = self.store.record_companion_message(
            turn_id=f"turn_{uuid4().hex}",
            session_id=session["session_id"],
            role="assistant",
            content=assistant_text,
            status=assistant_status,
            summary=memory_after,
            metadata={
                "selection": selection,
                "analysis": runtime_analysis,
                "dispatch_id": (
                    dispatch_result["dispatch"]["dispatch_id"]
                    if dispatch_result
                    else None
                ),
                "task_id": task["task_id"] if task else None,
            },
        )
        self._persist_companion_memory(session["session_id"], memory_after)
        self.telemetry.record_event(
            "companion.message.completed",
            session_id=session["session_id"],
            status=assistant_status,
            resolver=selection.get("resolver"),
        )
        return {
            "session": session,
            "status": assistant_status,
            "typing_state": "stopped",
            "message": {
                "role": "assistant",
                "content": assistant_text,
            },
            "memory": memory_after,
            "analysis": runtime_analysis,
            "outcome": outcome,
            "selection": selection,
            "payload": final_payload,
            "dispatch": dispatch_result["dispatch"] if dispatch_result else None,
            "route": dispatch_result["route"] if dispatch_result else None,
            "task": task,
            "turns": {
                "user": user_turn,
                "assistant": assistant_turn,
            },
            "notifications": (
                [task["notification"]]
                if task and task.get("notification")
                else []
            ),
        }

    async def analyze_runtime(
        self,
        request: RuntimeAnalysisRequest,
    ) -> dict[str, Any]:
        if not self.accepting:
            raise RuntimeError("Runtime is not accepting analysis requests")
        session = (
            self.sessions.get(request.session_id)
            if request.session_id
            else {}
        )
        memory = (
            self.store.latest_companion_summary(request.session_id)
            if request.session_id
            else {}
        )
        candidates = self.router.discover(
            product_id=request.product_id
            or session.get("active_product_id"),
            capability_id=request.capability_id,
            available_only=False,
        )
        analysis = await self.analyzer.analyze(
            message=request.message,
            assignment=request.assignment,
            metadata=request.metadata,
            explicit_payload=request.payload,
            candidates=candidates,
            session=session,
            memory=memory,
            metrics=self.metrics_snapshot(),
            allow_ai_fallback=request.allow_ai_fallback,
        )
        return {
            "analysis": analysis,
            "candidate_count": len(candidates),
        }

    def companion_memory(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        return {
            "session": session,
            "summary": self.store.latest_companion_summary(session_id),
            "messages": self.store.list_companion_messages(
                session_id,
                limit=limit,
            ),
            "tasks": self.store.list_companion_tasks(
                session_id=session_id,
                limit=limit,
            ),
        }

    def companion_tasks(
        self,
        *,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.store.list_companion_tasks(
            session_id=session_id,
            limit=limit,
        )

    def get_dispatch(self, dispatch_id: str) -> dict[str, Any]:
        dispatch = self.store.get_dispatch(dispatch_id)
        if dispatch is None:
            raise ResourceNotFoundError(f"Unknown dispatch: {dispatch_id}")
        return dispatch

    def _session_for_companion_message(
        self,
        request: CompanionMessageRequest,
    ) -> dict[str, Any]:
        if request.session_id:
            return self.sessions.get(request.session_id)
        if not request.actor_id or not request.workspace_id:
            raise IntentRoutingError(
                "actor_id and workspace_id are required when session_id is "
                "omitted"
            )
        if request.product_id:
            self.attachments.get(request.product_id)
        return self.sessions.create(
            actor_id=request.actor_id,
            client_type=request.client_type,
            workspace_id=request.workspace_id,
            product_id=request.product_id,
            metadata={
                "created_by": "companion-message",
                **request.metadata,
            },
        )

    def _persist_companion_memory(
        self,
        session_id: str,
        memory: dict[str, Any],
    ) -> None:
        self.context.update(
            session_id=session_id,
            scope="session",
            patch={"companion_memory": memory},
            expected_revision=None,
            replace=False,
        )

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
            product = attachment["product_id"]
            with runtime_span(
                "mitra.attachment_health_check",
                product_id=product,
                attachment_state=attachment["state"],
            ):
                health = await self.transport.check_manifest_health(
                    attachment["manifest"]
                )
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
