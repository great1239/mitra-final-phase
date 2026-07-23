from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Awaitable, Callable
from urllib.parse import urljoin
from uuid import uuid4

import httpx

from .config import RuntimeSettings
from .contracts import EcosystemExecutionRequest
from .depository import CentralDepository
from .errors import (
    EcosystemConfigurationError,
    EcosystemIntegrationError,
    ResourceNotFoundError,
)
from .observability import runtime_span
from .store import RuntimeStore
from .telemetry import RuntimeTelemetry
from .utils import canonical_json, sha256_json, utc_now


LEGACY_ECOSYSTEM_STAGE_ORDER: tuple[str, ...] = (
    "capability-selection",
    "dependency-preflight",
    "raj-execution",
    "ashmit-provenance",
    "bucket-truth",
    "karma-integrity",
    "prana-forwarding",
    "insightflow-telemetry",
    "central-depository",
)
ECOSYSTEM_STAGE_ORDER: tuple[str, ...] = (
    *LEGACY_ECOSYSTEM_STAGE_ORDER[:3],
    "keshav-diagnosis",
    *LEGACY_ECOSYSTEM_STAGE_ORDER[3:],
)
ECOSYSTEM_REPLAY_STAGE_ORDERS: dict[str, tuple[str, ...]] = {
    "mitra-tantra-ecosystem-replay-v1": LEGACY_ECOSYSTEM_STAGE_ORDER,
    "mitra-tantra-ecosystem-replay-v2": ECOSYSTEM_STAGE_ORDER,
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return canonical_json(value).encode("utf-8")


def _response_status(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    return str(status).lower() if status is not None else None


class ExternalStageError(EcosystemIntegrationError):
    def __init__(self, message: str, result: dict[str, Any]):
        super().__init__(message)
        self.result = result


class PublishedEcosystemClient:
    """Calls only published owner HTTP contracts, with no local fallback."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.http_transport = http_transport
        self._execution_client: ContextVar[httpx.AsyncClient | None] = (
            ContextVar(
                f"mitra_ecosystem_http_client_{id(self)}",
                default=None,
            )
        )

    def _new_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self.http_transport,
            timeout=self.settings.ecosystem_timeout_seconds,
            follow_redirects=False,
        )

    @asynccontextmanager
    async def execution_scope(self) -> AsyncIterator[None]:
        async with self._new_http_client() as client:
            token = self._execution_client.set(client)
            try:
                yield
            finally:
                self._execution_client.reset(token)

    def readiness(self) -> dict[str, Any]:
        modules = {
            "raj": {
                "configured": bool(self.settings.raj_workflow_base_url),
                "endpoint": self.settings.raj_workflow_base_url,
                "contract": "GET /healthz; POST /api/workflow/execute",
            },
            "ashmit": {
                "configured": bool(
                    self.settings.bhiv_ashmit_base_url
                    and self.settings.bhiv_ashmit_api_key
                ),
                "endpoint": self.settings.bhiv_ashmit_base_url,
                "contract": (
                    "GET /health/system; POST /api/mitra/evaluate"
                ),
            },
            "keshav": {
                "configured": bool(self.settings.bhiv_keshav_base_url),
                "endpoint": self.settings.bhiv_keshav_base_url,
                "contract": "GET /health; POST /analyze on product failure",
            },
            "bucket": {
                "configured": bool(self.settings.bhiv_bucket_base_url),
                "endpoint": self.settings.bhiv_bucket_base_url,
                "contract": (
                    "strict artifact envelope append/read and global replay "
                    "validation"
                ),
            },
            "karma": {
                "configured": bool(self.settings.bhiv_karma_base_url),
                "endpoint": self.settings.bhiv_karma_base_url,
                "contract": "POST /integrity/append-bucket-artifact",
            },
            "prana": {
                "configured": bool(self.settings.bhiv_prana_base_url),
                "endpoint": self.settings.bhiv_prana_base_url,
                "contract": "POST /forward/karma-strict and /forward/core",
            },
            "insightflow": {
                "configured": bool(
                    self.settings.bhiv_insightflow_ingest_url
                ),
                "endpoint": self.settings.bhiv_insightflow_ingest_url,
                "contract": "POST canonical execution telemetry envelope",
            },
            "central_depository": {
                "configured": bool(
                    self.settings.central_depository_base_url
                ),
                "endpoint": self.settings.central_depository_base_url,
                "contract": (
                    "external append-only replay handover artifact"
                ),
            },
        }
        pending = [
            name for name, item in modules.items() if not item["configured"]
        ]
        return {
            "ready": not pending,
            "mode": "strict-published-contracts",
            "embedded_fallback": False,
            "pending_modules": pending,
            "modules": modules,
            "checked_at": utc_now(),
        }

    @staticmethod
    def contracts() -> dict[str, Any]:
        return {
            "contract_set": "mitra-tantra-ecosystem-contracts-v1",
            "flow": [
                "mitra.capability-selection",
                "raj.workflow-execution",
                "keshav.conditional-diagnosis",
                "ashmit.provenance-acceptance",
                "bucket.truth-persistence",
                "karma.integrity-append",
                "prana.strict-forwarding",
                "insightflow.telemetry",
                "mitra.deterministic-reconstruction",
                "central-depository.export",
            ],
            "contracts": {
                "raj": {
                    "method": "POST",
                    "path": "/api/workflow/execute",
                    "health_path": "/healthz",
                    "request_version": "1.0.0",
                    "required_header": None,
                    "source_repository": (
                        "blackholeinfiverse54-creator/8_pillers_Workflow"
                    ),
                    "source_file": "workflow-executor-main/main.py",
                },
                "ashmit": {
                    "operations": [
                        "GET /health/system",
                        "POST /api/mitra/evaluate",
                    ],
                    "required_header": "X-API-Key",
                    "source_repository": (
                        "blackholeinfiverse54-creator/Mitra_T42"
                    ),
                },
                "keshav": {
                    "method": "POST",
                    "path": "/analyze",
                    "health_path": "/health",
                    "invocation": "only when Raj records a product error",
                    "authority": "diagnosis and resolution proposal only",
                    "source_repository": (
                        "blackholeinfiverse106-creator/KESHAV-4"
                    ),
                },
                "bucket": {
                    "operations": [
                        "GET /bucket/latest-hash",
                        "POST /bucket/artifact",
                        "GET /bucket/artifact/{artifact_id}",
                        "POST /bucket/validate-replay",
                    ],
                    "envelope_fields": [
                        "artifact_id",
                        "trace_id",
                        "timestamp_utc",
                        "schema_version",
                        "source_module_id",
                        "artifact_type",
                        "parent_hash",
                        "payload",
                    ],
                },
                "karma": {
                    "method": "POST",
                    "path": "/integrity/append-bucket-artifact",
                    "success_status": "appended",
                },
                "prana": {
                    "operations": [
                        "POST /forward/karma-strict",
                        "POST /forward/core",
                    ],
                    "strict_headers": [
                        "X-PRANA-Strict-Bytes-Equal",
                        "X-PRANA-Payload-SHA256",
                    ],
                },
                "insightflow": {
                    "method": "POST",
                    "path": "configured ingest URL",
                },
                "central_depository": {
                    "method": "POST",
                    "path": "/bucket/artifact",
                    "source_repository": (
                        "blackholeinfiverse54-creator/8_pillers_Workflow"
                    ),
                    "handover_mode": "external append-only replay package",
                },
            },
            "ownership": {
                "mitra": [
                    "interaction",
                    "capability selection",
                    "transport",
                    "checkpoints",
                    "telemetry",
                    "deterministic reconstruction",
                ],
                "external": [
                    "workflow execution",
                    "truth acceptance",
                    "intelligence",
                    "integrity decisions",
                    "product business logic",
                    "external acceptance and authority",
                ],
            },
        }

    def require_ready(self) -> None:
        readiness = self.readiness()
        if not readiness["ready"]:
            missing = ", ".join(readiness["pending_modules"])
            raise EcosystemConfigurationError(
                "Canonical ecosystem execution requires configured owner "
                f"contracts; missing: {missing}"
            )

    async def _request(
        self,
        *,
        module: str,
        operation: str,
        method: str,
        url: str,
        body: bytes | None,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        public_headers = {
            key: value
            for key, value in headers.items()
            if key.lower() not in {"x-api-key", "authorization"}
        }
        try:
            client = self._execution_client.get()
            if client is None:
                async with self._new_http_client() as temporary_client:
                    response = await temporary_client.request(
                        method,
                        url,
                        content=body,
                        headers=headers,
                    )
            else:
                response = await client.request(
                    method,
                    url,
                    content=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            result = {
                "module": module,
                "operation": operation,
                "method": method,
                "url": url,
                "status": "failed",
                "http_status": None,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1000,
                    3,
                ),
                "request_headers": public_headers,
                "request_body_utf8": body.decode("utf-8") if body else None,
                "request_sha256": _sha256_bytes(body) if body else None,
                "response": None,
                "response_sha256": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
            raise ExternalStageError(
                f"{operation} transport failed: {type(exc).__name__}",
                result,
            ) from exc

        response_bytes = response.content
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"body": response.text[:2000]}
        result = {
            "module": module,
            "operation": operation,
            "method": method,
            "url": url,
            "status": (
                "accepted" if 200 <= response.status_code < 300 else "failed"
            ),
            "http_status": response.status_code,
            "duration_ms": round(
                (time.perf_counter() - started) * 1000,
                3,
            ),
            "request_headers": public_headers,
            "request_body_utf8": body.decode("utf-8") if body else None,
            "request_sha256": _sha256_bytes(body) if body else None,
            "response_headers": {
                key.lower(): value for key, value in response.headers.items()
            },
            "response": payload,
            "response_sha256": _sha256_bytes(response_bytes),
            "error": None,
        }
        if not 200 <= response.status_code < 300:
            raise ExternalStageError(
                f"{operation} returned HTTP {response.status_code}",
                result,
            )
        return result

    @staticmethod
    def _require_semantic_success(
        result: dict[str, Any],
        *,
        accepted_statuses: set[str] | None = None,
    ) -> None:
        status = _response_status(result.get("response"))
        rejected = {
            "failed",
            "error",
            "rejected",
            "unhealthy",
            "blocked",
            "append_violation",
        }
        if status in rejected or (
            accepted_statuses is not None and status not in accepted_statuses
        ):
            result["status"] = "failed"
            raise ExternalStageError(
                f"{result['operation']} rejected the published contract "
                f"with status {status!r}",
                result,
            )

    @staticmethod
    def _reject_contract(result: dict[str, Any], message: str) -> None:
        result["status"] = "failed"
        raise ExternalStageError(message, result)

    async def dependency_preflight(self, trace_id: str) -> dict[str, Any]:
        readiness = self.readiness()
        modules = readiness["modules"]
        checks: list[dict[str, Any]] = []
        checks_by_module: dict[str, dict[str, Any]] = {}

        async def probe(
            *,
            module: str,
            operation: str,
            base_url: str,
            path: str,
        ) -> tuple[str, dict[str, Any]]:
            url = urljoin(base_url.rstrip("/") + "/", path)
            try:
                result = await self._request(
                    module=module,
                    operation=operation,
                    method="GET",
                    url=url,
                    body=None,
                    headers={"X-Mitra-Trace-ID": trace_id},
                )
            except ExternalStageError as exc:
                result = exc.result
            return module, result

        probes: list[Awaitable[tuple[str, dict[str, Any]]]] = []
        if modules["raj"]["configured"]:
            probes.append(probe(
                module="raj",
                operation="raj.health",
                base_url=self.settings.raj_workflow_base_url or "",
                path="healthz",
            ))
        if modules["keshav"]["configured"]:
            probes.append(probe(
                module="keshav",
                operation="keshav.health",
                base_url=self.settings.bhiv_keshav_base_url or "",
                path="health",
            ))
        if modules["bucket"]["configured"]:
            probes.append(probe(
                module="bucket",
                operation="bucket.health",
                base_url=self.settings.bhiv_bucket_base_url or "",
                path="health",
            ))
        if modules["ashmit"]["configured"]:
            probes.append(probe(
                module="ashmit",
                operation="ashmit.health-system",
                base_url=self.settings.bhiv_ashmit_base_url or "",
                path="health/system",
            ))
        if modules["prana"]["configured"]:
            probes.append(probe(
                module="prana",
                operation="prana.health",
                base_url=self.settings.bhiv_prana_base_url or "",
                path="health",
            ))
        if modules["central_depository"]["configured"]:
            probes.append(probe(
                module="central_depository",
                operation="central-depository.latest-hash",
                base_url=self.settings.central_depository_base_url or "",
                path="bucket/latest-hash",
            ))

        for module, result in await asyncio.gather(*probes):
            checks.append(result)
            checks_by_module[module] = result

        unhealthy_modules: list[str] = []

        def reject_probe(check: dict[str, Any], message: str) -> None:
            check["status"] = "failed"
            check["semantic_validation"] = {
                "accepted": False,
                "error": message,
            }
            unhealthy_modules.append(str(check["module"]))

        for check in checks:
            if check.get("status") != "accepted":
                unhealthy_modules.append(str(check["module"]))
                continue
            status = _response_status(check.get("response"))
            if status in {
                "failed",
                "error",
                "unhealthy",
                "blocked",
                "append_violation",
            }:
                reject_probe(
                    check,
                    f"{check['operation']} reported status {status!r}",
                )

        raj_check = checks_by_module.get("raj")
        if raj_check and raj_check.get("status") == "accepted":
            raj_health = raj_check.get("response") or {}
            if not (
                isinstance(raj_health, dict)
                and str(raj_health.get("status", "")).lower() == "ok"
                and raj_health.get("service") == "workflow-executor"
            ):
                reject_probe(
                    raj_check,
                    "Raj health response does not identify the Workflow Executor",
                )

        keshav_check = checks_by_module.get("keshav")
        if keshav_check and keshav_check.get("status") == "accepted":
            keshav_health = keshav_check.get("response") or {}
            if not (
                isinstance(keshav_health, dict)
                and keshav_health.get("status") == "OK"
                and keshav_health.get("service") == "KESHAV"
            ):
                reject_probe(
                    keshav_check,
                    "KESHAV health response does not identify the service",
                )

        ashmit_check = checks_by_module.get("ashmit")
        if ashmit_check and ashmit_check.get("status") == "accepted":
            ashmit_health = ashmit_check.get("response") or {}
            ashmit_execution = (
                ashmit_health.get("modules", {}).get("execution", {})
                if isinstance(ashmit_health, dict)
                else {}
            )
            ashmit_bucket = (
                ashmit_health.get("bucket", {})
                if isinstance(ashmit_health, dict)
                else {}
            )
            if not (
                isinstance(ashmit_health, dict)
                and ashmit_health.get("system") == "mitra_runtime"
                and ashmit_execution.get("status") == "active"
                and ashmit_bucket.get("status") == "active"
                and ashmit_bucket.get("mongo_connected") is True
                and ashmit_bucket.get("audit_active") is True
            ):
                reject_probe(
                    ashmit_check,
                    "Ashmit requires active execution and Mongo-backed Bucket audit persistence",
                )

        bucket_check = checks_by_module.get("bucket")
        if bucket_check and bucket_check.get("status") == "accepted":
            bucket_health = bucket_check.get("response") or {}
            append_only = (
                bucket_health.get("append_only_storage", {})
                if isinstance(bucket_health, dict)
                else {}
            )
            if append_only and append_only.get("status") != "active":
                reject_probe(
                    bucket_check,
                    "Bucket append-only storage is not active",
                )

        central_check = checks_by_module.get("central_depository")
        if central_check and central_check.get("status") == "accepted":
            central_health = central_check.get("response") or {}
            if not (
                isinstance(central_health, dict)
                and "last_hash" in central_health
                and isinstance(central_health.get("artifact_count"), int)
            ):
                reject_probe(
                    central_check,
                    "Central Depository latest-hash response is incompatible",
                )

        if readiness["pending_modules"]:
            missing = ", ".join(readiness["pending_modules"])
            result = {
                "trace_id": trace_id,
                "status": "blocked",
                "pending_modules": readiness["pending_modules"],
                "unhealthy_modules": unhealthy_modules,
                "modules": modules,
                "checks": checks,
                "embedded_fallback": False,
            }
            raise EcosystemConfigurationError(
                "Canonical ecosystem execution requires configured owner "
                f"contracts; missing: {missing}",
                result=result,
            )

        if unhealthy_modules:
            first = checks_by_module[unhealthy_modules[0]]
            raise ExternalStageError(
                first.get("semantic_validation", {}).get(
                    "error",
                    f"{first['operation']} did not return a usable response",
                ),
                first,
            )
        return {
            "trace_id": trace_id,
            "status": "healthy",
            "checks": checks,
        }

    async def record_ashmit_provenance(
        self,
        *,
        trace_id: str,
        execution_id: str,
        request: EcosystemExecutionRequest,
        session: dict[str, Any],
        capability_contract: dict[str, Any],
        raj_result: dict[str, Any],
        keshav_result: dict[str, Any],
    ) -> dict[str, Any]:
        event_content = canonical_json(
            {
                "mitra_trace_id": trace_id,
                "execution_id": execution_id,
                "message": request.message,
                "product_id": request.product_id,
                "capability_id": request.capability_id,
                "capability_contract_hash": sha256_json(
                    capability_contract
                ),
                "raj_trace_id": raj_result["raj_trace_id"],
                "raj_execution": raj_result["execution"],
                "keshav_diagnosis": keshav_result,
            }
        )
        owner_payload = {
            "event": {
                "title": "Mitra ecosystem workflow execution",
                "content": event_content,
                "category": "ecosystem_execution_provenance",
            },
            "user_id": request.actor_id or session.get("actor_id"),
            "context": {
                "platform": "mitra-companion-runtime",
                "device": request.client_type,
                "session_id": session.get("session_id"),
                "preferred_language": "auto",
                "authenticated_user_context": {
                    "principal": request.actor_id
                    or session.get("actor_id")
                    or "mitra-runtime",
                    "auth_method": "mitra-owner-contract",
                },
                "system_context": {
                    "mitra_trace_id": trace_id,
                    "execution_id": execution_id,
                    "workspace_id": session.get("workspace_id"),
                    "product_id": request.product_id,
                    "capability_id": request.capability_id,
                },
            },
        }
        body = _canonical_bytes(owner_payload)
        url = urljoin(
            (self.settings.bhiv_ashmit_base_url or "").rstrip("/") + "/",
            "api/mitra/evaluate",
        )
        operation = await self._request(
            module="ashmit",
            operation="ashmit.mitra-evaluate",
            method="POST",
            url=url,
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.settings.bhiv_ashmit_api_key or "",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        response = operation.get("response") or {}
        ashmit_trace_id = (
            response.get("trace_id") if isinstance(response, dict) else None
        )
        bucket_reference = (
            response.get("bucket_log_reference")
            if isinstance(response, dict)
            else None
        )
        valid = bool(
            isinstance(response, dict)
            and response.get("status") in {"ALLOW", "FLAG"}
            and isinstance(ashmit_trace_id, str)
            and ashmit_trace_id
            and isinstance(bucket_reference, dict)
            and bucket_reference.get("trace_id") == ashmit_trace_id
            and bucket_reference.get("backend") == "mongodb"
            and bucket_reference.get("artifact_locator")
        )
        operation["contract_validation"] = {
            "valid": valid,
            "accepted_decisions": ["ALLOW", "FLAG"],
            "mongo_artifact_required": True,
            "mitra_trace_id": trace_id,
            "ashmit_trace_id": ashmit_trace_id,
        }
        if not valid:
            self._reject_contract(
                operation,
                "Ashmit did not return an accepted Mongo-backed provenance record",
            )
        return {
            "trace_id": trace_id,
            "ashmit_trace_id": ashmit_trace_id,
            "status": "recorded",
            "decision": response["status"],
            "risk_level": response.get("risk_level"),
            "bucket_log_reference": bucket_reference,
            "operation": operation,
        }

    async def execute_raj(
        self,
        *,
        trace_id: str,
        execution_id: str,
        request: EcosystemExecutionRequest,
        session: dict[str, Any],
        capability_contract: dict[str, Any],
    ) -> dict[str, Any]:
        workflow_payload = request.payload.get("raj_workflow")
        if workflow_payload is None:
            workflow_payload = request.payload
        if not isinstance(workflow_payload, dict):
            raise EcosystemIntegrationError(
                "Raj requires payload.raj_workflow to be an object"
            )
        action_type = workflow_payload.get("action_type")
        if not isinstance(action_type, str) or not action_type.strip():
            raise EcosystemIntegrationError(
                "Raj owner contract requires an explicit "
                "payload.raj_workflow.action_type; Mitra will not invent a "
                "workflow action"
            )
        owner_payload = {
            **workflow_payload,
            "trace_id": trace_id,
            "product": request.product_id,
            "mitra_context": {
                "execution_id": execution_id,
                "session_id": session.get("session_id"),
                "workspace_id": session.get("workspace_id"),
                "actor_id": session.get("actor_id"),
                "client_type": request.client_type,
                "capability_contract": capability_contract,
            },
        }
        body_payload = {
            "trace_id": trace_id,
            "decision": "workflow",
            "data": {
                "workflow_type": "workflow",
                "payload": owner_payload,
            },
        }
        body = _canonical_bytes(body_payload)
        url = urljoin(
            (self.settings.raj_workflow_base_url or "").rstrip("/") + "/",
            "api/workflow/execute",
        )
        headers = {
            "Content-Type": "application/json",
            "X-Mitra-Trace-ID": trace_id,
        }
        if self.settings.raj_api_key:
            headers["X-API-Key"] = self.settings.raj_api_key
        result = await self._request(
            module="raj",
            operation="raj.workflow-execute",
            method="POST",
            url=url,
            body=body,
            headers=headers,
        )
        payload = result.get("response") or {}
        raj_trace_id = (
            payload.get("trace_id") if isinstance(payload, dict) else None
        )
        execution = (
            payload.get("execution_result")
            if isinstance(payload, dict)
            else None
        )
        product_status = (
            payload.get("status") if isinstance(payload, dict) else None
        )
        product_succeeded = bool(
            isinstance(execution, dict)
            and execution.get("success") is True
        )
        product_failed = bool(
            isinstance(execution, dict)
            and execution.get("success") is False
            and isinstance(execution.get("error"), dict)
        )
        valid = bool(
            isinstance(payload, dict)
            and product_status in {"success", "product_error"}
            and raj_trace_id == trace_id
            and isinstance(execution, dict)
            and execution.get("trace_id") == trace_id
            and (
                (product_status == "success" and product_succeeded)
                or (product_status == "product_error" and product_failed)
            )
        )
        result["contract_validation"] = {
            "valid": valid,
            "required_version": "1.0.0",
            "workflow_execution_required": True,
            "trace_identity_required": True,
            "raj_trace_id": raj_trace_id,
            "product_outcome": product_status,
        }
        result["mitra_trace_id"] = trace_id
        result["raj_trace_id"] = raj_trace_id
        if not valid:
            self._reject_contract(
                result,
                "Raj did not return a typed workflow execution outcome",
            )
        return {
            "trace_id": trace_id,
            "raj_trace_id": raj_trace_id,
            "status": "executed" if product_succeeded else "product_error",
            "operation": result,
            "execution": execution,
        }

    async def diagnose_keshav_product_failure(
        self,
        *,
        trace_id: str,
        execution_id: str,
        capability_contract: dict[str, Any],
        raj_result: dict[str, Any],
    ) -> dict[str, Any]:
        product_execution = raj_result.get("execution") or {}
        if product_execution.get("success") is True:
            return {
                "trace_id": trace_id,
                "execution_id": execution_id,
                "status": "skipped",
                "invoked": False,
                "reason": "product-succeeded",
                "authority": "diagnosis-only",
                "diagnosis": None,
                "operation": None,
            }
        source_error = product_execution.get("error")
        if not (
            raj_result.get("status") == "product_error"
            and product_execution.get("success") is False
            and isinstance(source_error, dict)
        ):
            raise EcosystemIntegrationError(
                "KESHAV requires a typed Raj product-error outcome"
            )
        product_id = str(
            (capability_contract.get("product") or {}).get("product_id")
            or "unknown-product"
        )
        task_id = f"product-runtime-{product_id}"
        affected_tasks = [
            "ashmit-provenance",
            "bucket-truth",
            "karma-integrity",
            "prana-forwarding",
            "insightflow-telemetry",
            "central-depository",
        ]
        owner_payload = {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "tasks": [{"task_id": task_id, "depends_on": []}],
            "constraint_results": [
                {
                    "task_id": task_id,
                    "is_valid": False,
                    "unsatisfied_dependencies": [],
                }
            ],
            "propagation_results": [
                {
                    "task_id": task_id,
                    "affected_tasks": affected_tasks,
                    "impact_score": len(affected_tasks),
                }
            ],
        }
        operation = await self._request(
            module="keshav",
            operation="keshav.analyze",
            method="POST",
            url=urljoin(
                (self.settings.bhiv_keshav_base_url or "").rstrip("/") + "/",
                "analyze",
            ),
            body=_canonical_bytes(owner_payload),
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        response = operation.get("response") or {}
        expected_signal = f"UNBLOCK_DEPENDENCY:{task_id}"
        valid = bool(
            isinstance(response, dict)
            and response.get("trace_id") == trace_id
            and response.get("execution_id") == execution_id
            and response.get("root_cause") == task_id
            and response.get("resolution_signal") == expected_signal
            and response.get("impact_score") == len(affected_tasks)
            and response.get("severity") in {"LOW", "MEDIUM", "HIGH"}
            and isinstance(response.get("timestamp"), str)
            and response.get("timestamp")
        )
        operation["contract_validation"] = {
            "valid": valid,
            "trace_identity_required": True,
            "execution_identity_required": True,
            "expected_root_cause": task_id,
            "expected_resolution_signal": expected_signal,
            "authority": "proposal-only",
        }
        if not valid:
            self._reject_contract(
                operation,
                "KESHAV returned an incompatible diagnosis contract",
            )
        return {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "status": "diagnosed",
            "invoked": True,
            "reason": "product-error",
            "authority": (
                "proposal-only; Mitra does not authorize or execute the "
                "resolution"
            ),
            "source_error": source_error,
            "source_error_hash": sha256_json(source_error),
            "input_contract": owner_payload,
            "diagnosis": response,
            "operation": operation,
        }

    async def persist_bucket(
        self,
        *,
        trace_id: str,
        execution_id: str,
        artifact_timestamp: str,
        capability_contract: dict[str, Any],
        raj_result: dict[str, Any],
        keshav_result: dict[str, Any],
        ashmit_result: dict[str, Any],
    ) -> dict[str, Any]:
        execution_artifact = {
            "artifact_type": "mitra.raj-workflow-execution.v1",
            "execution_id": execution_id,
            "trace_id": trace_id,
            "raj_trace_id": raj_result["raj_trace_id"],
            "ashmit_trace_id": ashmit_result["ashmit_trace_id"],
            "capability_contract": capability_contract,
            "raj_execution": raj_result,
            "keshav_diagnosis": keshav_result,
            "ashmit_provenance": ashmit_result,
        }
        artifact_id = sha256_json(execution_artifact)
        envelope = {
            "artifact_id": artifact_id,
            "trace_id": trace_id,
            "timestamp_utc": artifact_timestamp,
            "schema_version": "1.0.0",
            "source_module_id": "mitra-runtime",
            "artifact_type": "mitra.raj-workflow-execution.v1",
            "parent_hash": None,
            "payload": execution_artifact,
        }
        persisted = await self._append_owner_artifact(
            module="bucket",
            operation_prefix="bucket",
            base_url=self.settings.bhiv_bucket_base_url or "",
            trace_id=trace_id,
            envelope=envelope,
            fallback_parent_hash=self.settings.bhiv_bucket_parent_hash,
        )
        return {
            "trace_id": trace_id,
            "status": "stored",
            "artifact_id": artifact_id,
            "artifact_hash": persisted["server_hash"],
            "envelope_hash": sha256_json(persisted["envelope"]),
            "parent_hash": persisted["parent_hash"],
            "bucket_payload": persisted["envelope"],
            "operations": persisted["operations"],
        }

    async def deposit_central_depository(
        self,
        *,
        trace_id: str,
        execution_id: str,
        artifact_timestamp: str,
        handover_package: dict[str, Any],
    ) -> dict[str, Any]:
        artifact_id = sha256_json(handover_package)
        envelope = {
            "artifact_id": artifact_id,
            "trace_id": trace_id,
            "timestamp_utc": artifact_timestamp,
            "schema_version": "1.0.0",
            "source_module_id": "mitra-runtime",
            "artifact_type": "central-depository.ecosystem-handover.v1",
            "parent_hash": None,
            "payload": {
                "execution_id": execution_id,
                "handover_package": handover_package,
            },
        }
        persisted = await self._append_owner_artifact(
            module="central_depository",
            operation_prefix="central-depository",
            base_url=self.settings.central_depository_base_url or "",
            trace_id=trace_id,
            envelope=envelope,
            fallback_parent_hash=None,
        )
        return {
            "trace_id": trace_id,
            "status": "exported",
            "package_hash": handover_package["package_hash"],
            "artifact_id": artifact_id,
            "artifact_hash": persisted["server_hash"],
            "envelope_hash": sha256_json(persisted["envelope"]),
            "parent_hash": persisted["parent_hash"],
            "operations": persisted["operations"],
        }

    async def _append_owner_artifact(
        self,
        *,
        module: str,
        operation_prefix: str,
        base_url: str,
        trace_id: str,
        envelope: dict[str, Any],
        fallback_parent_hash: str | None,
    ) -> dict[str, Any]:
        base = base_url.rstrip("/") + "/"
        trace_headers = {"X-Mitra-Trace-ID": trace_id}
        operations = []
        latest = await self._request(
            module=module,
            operation=f"{operation_prefix}.latest-hash",
            method="GET",
            url=urljoin(base, "bucket/latest-hash"),
            body=None,
            headers=trace_headers,
        )
        operations.append(latest)
        latest_payload = latest.get("response") or {}
        if not isinstance(latest_payload, dict):
            self._reject_contract(
                latest,
                f"{operation_prefix} latest-hash returned a non-object",
            )
        parent_hash = (
            latest_payload.get("last_hash")
            or latest_payload.get("latest_hash")
            or latest_payload.get("latest-hash")
            or latest_payload.get("hash")
            or fallback_parent_hash
        )
        artifact_count = latest_payload.get("artifact_count")
        if artifact_count and not parent_hash:
            self._reject_contract(
                latest,
                f"{operation_prefix} reported artifacts without a chain head",
            )
        stored_envelope = {**envelope, "parent_hash": parent_hash}
        artifact_result = await self._request(
            module=module,
            operation=f"{operation_prefix}.artifact",
            method="POST",
            url=urljoin(base, "bucket/artifact"),
            body=_canonical_bytes(stored_envelope),
            headers={"Content-Type": "application/json", **trace_headers},
        )
        operations.append(artifact_result)
        append_payload = artifact_result.get("response") or {}
        server_hash = (
            append_payload.get("hash")
            if isinstance(append_payload, dict)
            else None
        )
        if not (
            isinstance(append_payload, dict)
            and append_payload.get("success") is True
            and append_payload.get("artifact_id")
            == stored_envelope["artifact_id"]
            and isinstance(server_hash, str)
            and server_hash
            and append_payload.get("parent_hash") == parent_hash
        ):
            self._reject_contract(
                artifact_result,
                f"{operation_prefix} did not accept the immutable envelope",
            )
        lookup = await self._request(
            module=module,
            operation=f"{operation_prefix}.get-artifact",
            method="GET",
            url=urljoin(
                base,
                f"bucket/artifact/{stored_envelope['artifact_id']}",
            ),
            body=None,
            headers=trace_headers,
        )
        operations.append(lookup)
        lookup_payload = lookup.get("response") or {}
        if not (
            isinstance(lookup_payload, dict)
            and lookup_payload.get("artifact") == stored_envelope
            and lookup_payload.get("chain_verified") is True
        ):
            self._reject_contract(
                lookup,
                f"{operation_prefix} read-back did not match the written artifact",
            )
        replay = await self._request(
            module=module,
            operation=f"{operation_prefix}.validate-replay",
            method="POST",
            url=urljoin(base, "bucket/validate-replay"),
            body=None,
            headers=trace_headers,
        )
        operations.append(replay)
        replay_payload = replay.get("response") or {}
        if not (
            isinstance(replay_payload, dict)
            and replay_payload.get("valid") is True
        ):
            self._reject_contract(
                replay,
                f"{operation_prefix} global replay validation failed",
            )
        return {
            "parent_hash": parent_hash,
            "server_hash": server_hash,
            "envelope": stored_envelope,
            "operations": operations,
        }

    async def append_karma(
        self,
        *,
        trace_id: str,
        bucket_result: dict[str, Any],
        previous_hash: str,
    ) -> dict[str, Any]:
        head_operation = await self._request(
            module="karma",
            operation="karma.health-head",
            method="GET",
            url=urljoin(
                (self.settings.bhiv_karma_base_url or "").rstrip("/") + "/",
                "health",
            ),
            body=None,
            headers={"X-Mitra-Trace-ID": trace_id},
        )
        head_response = head_operation.get("response") or {}
        live_head = (
            head_response.get("last_hash")
            if isinstance(head_response, dict)
            else None
        )
        resolved_previous_hash = (
            live_head
            if isinstance(live_head, str) and live_head
            else previous_hash
        )
        bucket_payload = bucket_result["bucket_payload"]
        karma_payload = {
            **bucket_payload,
            "bucket_parent_hash": bucket_payload.get("parent_hash"),
            "parent_hash": resolved_previous_hash,
        }
        body = _canonical_bytes(karma_payload)
        url = urljoin(
            (self.settings.bhiv_karma_base_url or "").rstrip("/") + "/",
            "integrity/append-bucket-artifact",
        )
        operation = await self._request(
            module="karma",
            operation="karma.append-bucket-artifact",
            method="POST",
            url=url,
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        self._require_semantic_success(
            operation,
            accepted_statuses={"appended"},
        )
        response = operation.get("response") or {}
        accepted_hash = (
            response.get("current_hash")
            or response.get("last_hash")
            or response.get("hash")
            or operation["request_sha256"]
        )
        return {
            "trace_id": trace_id,
            "status": "appended",
            "accepted_hash": accepted_hash,
            "request_payload": karma_payload,
            "request_body_utf8": body.decode("utf-8"),
            "request_sha256": _sha256_bytes(body),
            "head_source": "live-health" if live_head else "runtime-fallback",
            "head_operation": head_operation,
            "operation": operation,
            "operations": [head_operation, operation],
        }

    async def forward_prana(
        self,
        *,
        trace_id: str,
        karma_result: dict[str, Any],
    ) -> dict[str, Any]:
        body = karma_result["request_body_utf8"].encode("utf-8")
        expected_hash = _sha256_bytes(body)
        base = (self.settings.bhiv_prana_base_url or "").rstrip("/") + "/"
        strict = await self._request(
            module="prana",
            operation="prana.karma-strict",
            method="POST",
            url=urljoin(base, "forward/karma-strict"),
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        strict_headers = strict["response_headers"]
        bytes_equal = (
            strict_headers.get("x-prana-strict-bytes-equal", "").lower()
            == "true"
        )
        hash_equal = (
            strict_headers.get("x-prana-payload-sha256") == expected_hash
        )
        strict["strict_validation"] = {
            "bytes_equal": bytes_equal,
            "hash_equal": hash_equal,
            "expected_sha256": expected_hash,
        }
        if not bytes_equal or not hash_equal:
            strict["status"] = "failed"
            raise ExternalStageError(
                "PRANA strict forwarding did not preserve Karma bytes",
                strict,
            )
        core_payload = {
            "trace_id": trace_id,
            "source_system": "Mitra",
            "message_type": "raj_workflow_execution",
        }
        core = await self._request(
            module="prana",
            operation="prana.core",
            method="POST",
            url=urljoin(base, "forward/core"),
            body=_canonical_bytes(core_payload),
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        trace_preserved = (
            isinstance(core.get("response"), dict)
            and core["response"].get("trace_id") == trace_id
        )
        core["trace_validation"] = {
            "preserved": trace_preserved,
            "expected_trace_id": trace_id,
        }
        if not trace_preserved:
            core["status"] = "failed"
            raise ExternalStageError(
                "PRANA core mutated the execution trace ID",
                core,
            )
        return {
            "trace_id": trace_id,
            "status": "forwarded",
            "strict_bytes_sha256": expected_hash,
            "operations": [strict, core],
        }

    async def emit_insightflow(
        self,
        *,
        trace_id: str,
        execution_id: str,
        capability_contract: dict[str, Any],
        raj_result: dict[str, Any],
        keshav_result: dict[str, Any],
        ashmit_result: dict[str, Any],
        bucket_result: dict[str, Any],
        karma_result: dict[str, Any],
        prana_result: dict[str, Any],
    ) -> dict[str, Any]:
        envelope = {
            "event_type": "mitra.tantra.execution.completed.v1",
            "trace_id": trace_id,
            "execution_id": execution_id,
            "source_system": "Mitra",
            "payload": {
                "capability_contract_hash": sha256_json(capability_contract),
                "raj_trace_id": raj_result["raj_trace_id"],
                "raj_execution_hash": sha256_json(raj_result),
                "product_execution_status": raj_result["status"],
                "keshav_status": keshav_result["status"],
                "keshav_invoked": keshav_result["invoked"],
                "keshav_diagnosis_hash": sha256_json(keshav_result),
                "ashmit_trace_id": ashmit_result["ashmit_trace_id"],
                "ashmit_provenance_hash": sha256_json(ashmit_result),
                "bucket_artifact_id": bucket_result["artifact_id"],
                "bucket_artifact_hash": bucket_result["artifact_hash"],
                "karma_hash": karma_result["accepted_hash"],
                "prana_request_hash": prana_result["strict_bytes_sha256"],
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Mitra-Trace-ID": trace_id,
        }
        if self.settings.bhiv_insightflow_api_key:
            headers["X-API-Key"] = self.settings.bhiv_insightflow_api_key
        operation = await self._request(
            module="insightflow",
            operation="insightflow.execution-trace",
            method="POST",
            url=self.settings.bhiv_insightflow_ingest_url or "",
            body=_canonical_bytes(envelope),
            headers=headers,
        )
        self._require_semantic_success(operation)
        return {
            "trace_id": trace_id,
            "status": "observed",
            "envelope": envelope,
            "operation": operation,
        }


class EcosystemReplayLedger:
    """Portable reconstruction of the complete cross-system execution."""

    replay_type = "mitra-tantra-ecosystem-replay-v2"

    @classmethod
    def build(
        cls,
        *,
        execution: dict[str, Any],
        stages: list[dict[str, Any]],
        contracts: dict[str, Any],
    ) -> dict[str, Any]:
        by_name = {stage["stage_name"]: stage for stage in stages}
        missing = [name for name in ECOSYSTEM_STAGE_ORDER if name not in by_name]
        incomplete = [
            name
            for name in ECOSYSTEM_STAGE_ORDER
            if name in by_name and by_name[name]["status"] != "COMPLETED"
        ]
        if missing or incomplete:
            raise EcosystemIntegrationError(
                "Cannot seal ecosystem replay; missing stages "
                f"{missing}, incomplete stages {incomplete}"
            )
        components = []
        previous_hash: str | None = None
        payloads: list[tuple[str, dict[str, Any]]] = [
            (
                "request",
                {
                    "request": execution["request"],
                    "request_hash": execution["request_hash"],
                },
            )
        ]
        for name in ECOSYSTEM_STAGE_ORDER:
            stage = by_name[name]
            payloads.append(
                (
                    name,
                    {
                        "stage_index": stage["stage_index"],
                        "attempts": stage["attempts"],
                        "request": stage["request"],
                        "request_hash": stage["request_hash"],
                        "response": stage["response"],
                        "response_hash": stage["response_hash"],
                        "artifact_hash": stage["artifact_hash"],
                        "lineage_id": stage["lineage_id"],
                        "chain_hash": stage["chain_hash"],
                        "lineage": stage.get("lineage"),
                    },
                )
            )
        for index, (name, payload) in enumerate(payloads):
            component_hash = sha256_json(payload)
            components.append(
                {
                    "index": index,
                    "name": name,
                    "previous_component_hash": previous_hash,
                    "component_hash": component_hash,
                    "payload": payload,
                }
            )
            previous_hash = component_hash
        reconstructed = cls._reconstruct(components)
        core = {
            "replay_type": cls.replay_type,
            "execution_id": execution["execution_id"],
            "trace_id": execution["trace_id"],
            "contracts": contracts,
            "contracts_hash": sha256_json(contracts),
            "components": components,
            "component_chain_head": previous_hash,
            "reconstructed_execution": reconstructed,
            "reconstructed_execution_hash": sha256_json(reconstructed),
        }
        return {**core, "package_hash": sha256_json(core)}

    @staticmethod
    def _reconstruct(components: list[dict[str, Any]]) -> dict[str, Any]:
        payloads = {item["name"]: item["payload"] for item in components}
        stage_names = [
            str(item["name"])
            for item in components
            if item.get("name") != "request"
        ]
        request = payloads["request"]
        capability = payloads["capability-selection"]["response"]
        raj = payloads["raj-execution"]["response"]
        keshav_component = payloads.get("keshav-diagnosis")
        keshav = (
            keshav_component["response"]
            if isinstance(keshav_component, dict)
            else None
        )
        bucket = payloads["bucket-truth"]["response"]
        karma = payloads["karma-integrity"]["response"]
        prana = payloads["prana-forwarding"]["response"]
        insight = payloads["insightflow-telemetry"]["response"]
        depository = payloads["central-depository"]["response"]
        reconstructed = {
            "request_hash": request["request_hash"],
            "selected_capability": capability["capability_contract"],
            "mitra_trace_id": raj["trace_id"],
            "raj_trace_id": raj["raj_trace_id"],
            "raj_execution": raj["execution"],
            "bucket_artifact_id": bucket["artifact_id"],
            "bucket_artifact_hash": bucket["artifact_hash"],
            "karma_hash": karma["accepted_hash"],
            "prana_request_hash": prana["strict_bytes_sha256"],
            "insightflow_envelope_hash": sha256_json(insight["envelope"]),
            "central_depository_package_hash": depository["package_hash"],
            "stage_response_hashes": {
                name: payloads[name]["response_hash"]
                for name in stage_names
            },
            "status": "COMPLETED",
        }
        if isinstance(keshav, dict):
            reconstructed.update(
                {
                    "product_execution_status": raj["status"],
                    "keshav_status": keshav["status"],
                    "keshav_invoked": keshav["invoked"],
                    "keshav_diagnosis": keshav["diagnosis"],
                }
            )
        return reconstructed

    @classmethod
    def validate(cls, package: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def check(name: str, passed: bool) -> None:
            checks.append({"check": name, "passed": bool(passed)})

        replay_type = package.get("replay_type")
        stage_order = ECOSYSTEM_REPLAY_STAGE_ORDERS.get(str(replay_type))
        check("replay-type", stage_order is not None)
        components = package.get("components")
        check("components-present", isinstance(components, list))
        if not isinstance(components, list):
            return {
                "status": "failed",
                "deterministic": False,
                "clean_state": True,
                "checks": checks,
                "failed_checks": [item for item in checks if not item["passed"]],
            }
        expected_names = ["request", *(stage_order or ECOSYSTEM_STAGE_ORDER)]
        check(
            "component-order",
            [item.get("name") for item in components] == expected_names,
        )
        previous_hash: str | None = None
        previous_lineage_hash: str | None = None
        for index, component in enumerate(components):
            component_hash = sha256_json(component.get("payload"))
            check(
                f"component-hash:{component.get('name', index)}",
                component.get("component_hash") == component_hash,
            )
            check(
                f"component-link:{component.get('name', index)}",
                component.get("previous_component_hash") == previous_hash,
            )
            check("component-index:" + str(index), component.get("index") == index)
            previous_hash = component_hash
            if component.get("name") == "request":
                request_payload = component.get("payload") or {}
                check(
                    "request-hash",
                    request_payload.get("request_hash")
                    == sha256_json(request_payload.get("request")),
                )
                continue
            stage_payload = component.get("payload") or {}
            stage_name = str(component.get("name"))
            check(
                f"stage-request-hash:{stage_name}",
                stage_payload.get("request_hash")
                == sha256_json(stage_payload.get("request")),
            )
            check(
                f"stage-response-hash:{stage_name}",
                stage_payload.get("response_hash")
                == sha256_json(stage_payload.get("response")),
            )
            artifact = {
                "artifact_type": "tantra.ecosystem-stage.v1",
                "execution_id": package.get("execution_id"),
                "stage_name": stage_name,
                "stage_index": stage_payload.get("stage_index"),
                "attempts": stage_payload.get("attempts"),
                "request_hash": stage_payload.get("request_hash"),
                "request": stage_payload.get("request"),
                "response_hash": stage_payload.get("response_hash"),
                "response": stage_payload.get("response"),
            }
            check(
                f"stage-artifact-hash:{stage_name}",
                stage_payload.get("artifact_hash") == sha256_json(artifact),
            )
            lineage = stage_payload.get("lineage")
            lineage_metadata = {
                "artifact_type": "tantra.ecosystem-stage.v1",
                "stage_name": stage_name,
            }
            expected_lineage_id = "lin_" + sha256_json(
                {
                    "subject_type": "ecosystem_execution",
                    "subject_id": package.get("execution_id"),
                    "artifact_hash": stage_payload.get("artifact_hash"),
                    "metadata": lineage_metadata,
                }
            )[:32]
            check(
                f"stage-lineage-present:{stage_name}",
                isinstance(lineage, dict),
            )
            if isinstance(lineage, dict):
                expected_chain_hash = sha256_json(
                    {
                        "subject_type": "ecosystem_execution",
                        "subject_id": package.get("execution_id"),
                        "artifact_hash": stage_payload.get("artifact_hash"),
                        "parent_chain_hash": previous_lineage_hash,
                        "sequence": index,
                        "metadata": lineage_metadata,
                    }
                )
                check(
                    f"stage-lineage-id:{stage_name}",
                    stage_payload.get("lineage_id") == expected_lineage_id
                    and lineage.get("lineage_id") == expected_lineage_id,
                )
                check(
                    f"stage-lineage-parent:{stage_name}",
                    lineage.get("parent_chain_hash") == previous_lineage_hash,
                )
                check(
                    f"stage-lineage-sequence:{stage_name}",
                    lineage.get("sequence") == index,
                )
                check(
                    f"stage-lineage-hash:{stage_name}",
                    stage_payload.get("chain_hash") == expected_chain_hash
                    and lineage.get("chain_hash") == expected_chain_hash,
                )
                previous_lineage_hash = expected_chain_hash
        check(
            "component-chain-head",
            package.get("component_chain_head") == previous_hash,
        )
        contracts = package.get("contracts")
        check(
            "contracts-hash",
            isinstance(contracts, dict)
            and package.get("contracts_hash") == sha256_json(contracts),
        )
        reconstructed: dict[str, Any] | None = None
        try:
            reconstructed = cls._reconstruct(components)
            check(
                "reconstructed-execution",
                reconstructed == package.get("reconstructed_execution"),
            )
            check(
                "reconstructed-execution-hash",
                package.get("reconstructed_execution_hash")
                == sha256_json(reconstructed),
            )
        except (KeyError, TypeError):
            check("reconstructed-execution", False)
            check("reconstructed-execution-hash", False)
        core = {key: value for key, value in package.items() if key != "package_hash"}
        check("package-hash", package.get("package_hash") == sha256_json(core))
        trace_id = package.get("trace_id")
        check(
            "trace-continuity",
            bool(trace_id)
            and reconstructed is not None
            and reconstructed.get("mitra_trace_id") == trace_id,
        )
        failed = [item for item in checks if not item["passed"]]
        return {
            "status": "verified" if not failed else "failed",
            "deterministic": not failed,
            "clean_state": True,
            "database_reads": 0,
            "live_service_calls": 0,
            "check_count": len(checks),
            "failed_check_count": len(failed),
            "checks": checks,
            "failed_checks": failed,
            "reconstructed_execution": reconstructed,
        }


class EcosystemRuntime:
    """Coordinates one strict Raj-to-depository execution without owner logic."""

    def __init__(
        self,
        *,
        settings: RuntimeSettings,
        store: RuntimeStore,
        depository: CentralDepository,
        telemetry: RuntimeTelemetry,
        client: PublishedEcosystemClient,
    ) -> None:
        self.settings = settings
        self.store = store
        self.depository = depository
        self.telemetry = telemetry
        self.client = client

    def status(self) -> dict[str, Any]:
        return {
            "readiness": self.client.readiness(),
            "execution_counts": self.store.ecosystem_execution_counts(),
            "stage_failure_counts": self.store.ecosystem_stage_failure_counts(),
            "contracts": self.client.contracts(),
        }

    async def execute(
        self,
        *,
        request: EcosystemExecutionRequest,
        session: dict[str, Any],
        capability_contract: dict[str, Any],
    ) -> dict[str, Any]:
        execution_id = "eco_" + uuid4().hex
        request_payload = request.model_dump(mode="json")
        trace_id = sha256_json(
            {
                "execution_id": execution_id,
                "request_hash": sha256_json(request_payload),
            }
        )
        execution = self.store.create_ecosystem_execution(
            execution_id=execution_id,
            idempotency_key=request.idempotency_key,
            trace_id=trace_id,
            session_id=session.get("session_id"),
            actor_id=str(session.get("actor_id") or request.actor_id or "unknown"),
            request=request_payload,
            runtime_instance_id=self.settings.runtime_instance_id,
        )
        if execution.get("idempotent_reuse"):
            return self.details(execution["execution_id"])
        self.store.update_ecosystem_execution(
            execution_id=execution_id,
            status="RUNNING",
            current_stage=ECOSYSTEM_STAGE_ORDER[0],
            capability=capability_contract,
        )
        try:
            return await self._run(
                execution_id=execution_id,
                request=request,
                session=session,
                capability_contract=capability_contract,
            )
        except Exception as exc:
            current = self.store.get_ecosystem_execution(execution_id) or {}
            if current.get("status") != "FAILED":
                self.store.update_ecosystem_execution(
                    execution_id=execution_id,
                    status="FAILED",
                    current_stage=current.get("current_stage"),
                    error=f"{type(exc).__name__}: {exc}",
                )
            raise

    async def recover(self, execution_id: str) -> dict[str, Any]:
        execution = self.store.get_ecosystem_execution(execution_id)
        if execution is None:
            raise ResourceNotFoundError(
                f"Unknown ecosystem execution: {execution_id}"
            )
        if execution["status"] == "COMPLETED":
            return self.details(execution_id)
        capability = execution.get("capability")
        if not isinstance(capability, dict):
            raise EcosystemIntegrationError(
                "Cannot recover execution without its recorded capability contract"
            )
        request = EcosystemExecutionRequest.model_validate(execution["request"])
        session = {
            "session_id": execution.get("session_id"),
            "actor_id": execution.get("actor_id"),
            "workspace_id": request.workspace_id,
        }
        self.store.update_ecosystem_execution(
            execution_id=execution_id,
            status="RUNNING",
            current_stage=execution.get("current_stage"),
            error=None,
        )
        try:
            return await self._run(
                execution_id=execution_id,
                request=request,
                session=session,
                capability_contract=capability,
            )
        except Exception as exc:
            current = self.store.get_ecosystem_execution(execution_id) or {}
            if current.get("status") != "FAILED":
                self.store.update_ecosystem_execution(
                    execution_id=execution_id,
                    status="FAILED",
                    current_stage=current.get("current_stage"),
                    error=f"{type(exc).__name__}: {exc}",
                )
            raise

    async def _run(
        self,
        *,
        execution_id: str,
        request: EcosystemExecutionRequest,
        session: dict[str, Any],
        capability_contract: dict[str, Any],
    ) -> dict[str, Any]:
        async with self.client.execution_scope():
            return await self._run_scoped(
                execution_id=execution_id,
                request=request,
                session=session,
                capability_contract=capability_contract,
            )

    async def _run_scoped(
        self,
        *,
        execution_id: str,
        request: EcosystemExecutionRequest,
        session: dict[str, Any],
        capability_contract: dict[str, Any],
    ) -> dict[str, Any]:
        execution = self.store.get_ecosystem_execution(execution_id) or {}
        trace_id = execution["trace_id"]
        capability_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="capability-selection",
            request_payload={
                "trace_id": trace_id,
                "message": request.message,
                "capability_contract": capability_contract,
            },
            operation=lambda: self._return(
                {
                    "trace_id": trace_id,
                    "status": "selected",
                    "capability_contract": capability_contract,
                    "capability_contract_hash": sha256_json(capability_contract),
                }
            ),
        )
        await self._run_stage(
            execution_id=execution_id,
            stage_name="dependency-preflight",
            request_payload={
                "trace_id": trace_id,
                "required_modules": self.client.readiness()["modules"],
            },
            operation=lambda: self.client.dependency_preflight(trace_id),
        )
        raj_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="raj-execution",
            request_payload={
                "trace_id": trace_id,
                "execution_id": execution_id,
                "message": request.message,
                "payload": request.payload,
                "capability_contract": capability_result["capability_contract"],
            },
            operation=lambda: self.client.execute_raj(
                trace_id=trace_id,
                execution_id=execution_id,
                request=request,
                session=session,
                capability_contract=capability_result["capability_contract"],
            ),
        )
        keshav_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="keshav-diagnosis",
            request_payload={
                "trace_id": trace_id,
                "execution_id": execution_id,
                "product_execution_status": raj_result["status"],
                "product_execution_hash": sha256_json(raj_result),
                "conditional_invocation": "product-error-only",
            },
            operation=lambda: self.client.diagnose_keshav_product_failure(
                trace_id=trace_id,
                execution_id=execution_id,
                capability_contract=capability_result[
                    "capability_contract"
                ],
                raj_result=raj_result,
            ),
        )
        ashmit_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="ashmit-provenance",
            request_payload={
                "trace_id": trace_id,
                "execution_id": execution_id,
                "raj_result_hash": sha256_json(raj_result),
                "keshav_result_hash": sha256_json(keshav_result),
                "capability_contract_hash": sha256_json(
                    capability_result["capability_contract"]
                ),
            },
            operation=lambda: self.client.record_ashmit_provenance(
                trace_id=trace_id,
                execution_id=execution_id,
                request=request,
                session=session,
                capability_contract=capability_result[
                    "capability_contract"
                ],
                raj_result=raj_result,
                keshav_result=keshav_result,
            ),
        )
        bucket_result, karma_result = await self._run_integrity_chain(
            execution_id=execution_id,
            trace_id=trace_id,
            artifact_timestamp=execution["created_at"],
            capability_contract=capability_result["capability_contract"],
            raj_result=raj_result,
            keshav_result=keshav_result,
            ashmit_result=ashmit_result,
        )
        prana_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="prana-forwarding",
            request_payload={
                "trace_id": trace_id,
                "karma_request_sha256": karma_result["request_sha256"],
                "karma_request_body_utf8": karma_result["request_body_utf8"],
            },
            operation=lambda: self.client.forward_prana(
                trace_id=trace_id,
                karma_result=karma_result,
            ),
        )
        insight_result = await self._run_stage(
            execution_id=execution_id,
            stage_name="insightflow-telemetry",
            request_payload={
                "trace_id": trace_id,
                "execution_id": execution_id,
                "raj_result_hash": sha256_json(raj_result),
                "keshav_result_hash": sha256_json(keshav_result),
                "ashmit_result_hash": sha256_json(ashmit_result),
                "bucket_result_hash": sha256_json(bucket_result),
                "karma_result_hash": sha256_json(karma_result),
                "prana_result_hash": sha256_json(prana_result),
            },
            operation=lambda: self.client.emit_insightflow(
                trace_id=trace_id,
                execution_id=execution_id,
                capability_contract=capability_result["capability_contract"],
                raj_result=raj_result,
                keshav_result=keshav_result,
                ashmit_result=ashmit_result,
                bucket_result=bucket_result,
                karma_result=karma_result,
                prana_result=prana_result,
            ),
        )
        handover_package = self._central_package(
            execution_id=execution_id,
            trace_id=trace_id,
            insight_result=insight_result,
        )
        async with self._chain_head_lease(execution_id):
            await self._run_stage(
                execution_id=execution_id,
                stage_name="central-depository",
                request_payload={
                    "trace_id": trace_id,
                    "execution_id": execution_id,
                    "package_hash": handover_package["package_hash"],
                    "subject_type": "ecosystem_execution",
                },
                operation=lambda: self.client.deposit_central_depository(
                    trace_id=trace_id,
                    execution_id=execution_id,
                    artifact_timestamp=execution["created_at"],
                    handover_package=handover_package,
                ),
            )
        execution = self.store.get_ecosystem_execution(execution_id) or {}
        stages = self._stages_with_lineage(execution_id)
        package = EcosystemReplayLedger.build(
            execution=execution,
            stages=stages,
            contracts=self.client.contracts(),
        )
        validation = EcosystemReplayLedger.validate(package)
        if validation["status"] != "verified":
            raise EcosystemIntegrationError(
                "The sealed ecosystem replay package failed clean-state validation"
            )
        replay_artifact = self.depository.put(
            artifact_type="tantra.ecosystem-replay.v1",
            artifact=package,
            metadata={
                "execution_id": execution_id,
                "trace_id": trace_id,
                "package_hash": package["package_hash"],
            },
        )
        self.depository.append_lineage(
            subject_type="ecosystem_execution",
            subject_id=execution_id,
            artifact_hash=replay_artifact["artifact_hash"],
            metadata={"artifact_type": "tantra.ecosystem-replay.v1"},
        )
        self.store.set_ecosystem_replay_package(
            execution_id=execution_id,
            package=package,
        )
        self.store.update_ecosystem_execution(
            execution_id=execution_id,
            status="COMPLETED",
            current_stage="completed",
            error=None,
        )
        self.telemetry.record_event(
            "ecosystem.execution_completed",
            execution_id=execution_id,
            trace_id=trace_id,
            replay_package_hash=package["package_hash"],
        )
        return self.details(execution_id)

    @staticmethod
    async def _return(value: dict[str, Any]) -> dict[str, Any]:
        return value

    def _karma_previous_hash(self, execution_id: str) -> str:
        latest = self.store.latest_completed_ecosystem_stage(
            "karma-integrity",
            exclude_execution_id=execution_id,
        )
        response = latest.get("response") if latest else None
        accepted_hash = (
            response.get("accepted_hash")
            if isinstance(response, dict)
            else None
        )
        if isinstance(accepted_hash, str) and accepted_hash:
            return accepted_hash
        return self.settings.bhiv_karma_previous_hash

    async def _run_integrity_chain(
        self,
        *,
        execution_id: str,
        trace_id: str,
        artifact_timestamp: str,
        capability_contract: dict[str, Any],
        raj_result: dict[str, Any],
        keshav_result: dict[str, Any],
        ashmit_result: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        async with self._chain_head_lease(execution_id):
            bucket_result = await self._run_stage(
                execution_id=execution_id,
                stage_name="bucket-truth",
                request_payload={
                    "trace_id": trace_id,
                    "execution_id": execution_id,
                    "artifact_timestamp": artifact_timestamp,
                    "raj_result_hash": sha256_json(raj_result),
                    "keshav_result_hash": sha256_json(keshav_result),
                    "ashmit_result_hash": sha256_json(ashmit_result),
                },
                operation=lambda: self.client.persist_bucket(
                    trace_id=trace_id,
                    execution_id=execution_id,
                    artifact_timestamp=artifact_timestamp,
                    capability_contract=capability_contract,
                    raj_result=raj_result,
                    keshav_result=keshav_result,
                    ashmit_result=ashmit_result,
                ),
            )
            karma_previous_hash = self._karma_previous_hash(execution_id)
            karma_result = await self._run_stage(
                execution_id=execution_id,
                stage_name="karma-integrity",
                request_payload={
                    "trace_id": trace_id,
                    "bucket_payload": bucket_result["bucket_payload"],
                    "previous_hash": karma_previous_hash,
                },
                operation=lambda: self.client.append_karma(
                    trace_id=trace_id,
                    bucket_result=bucket_result,
                    previous_hash=karma_previous_hash,
                ),
            )
            return bucket_result, karma_result

    @asynccontextmanager
    async def _chain_head_lease(
        self,
        execution_id: str,
    ) -> AsyncIterator[None]:
        lease_name = "ecosystem-bucket-karma-chain-heads"
        lease_holder = f"{execution_id}:{uuid4().hex}"
        operation_timeout = max(1.0, self.settings.ecosystem_timeout_seconds)
        deadline = time.monotonic() + (operation_timeout * 2)
        acquired = False
        while time.monotonic() < deadline:
            lease = self.store.claim_runtime_lease(
                lease_name=lease_name,
                instance_id=lease_holder,
                lease_seconds=(operation_timeout * 2) + 1,
            )
            if lease["acquired"]:
                acquired = True
                break
            await asyncio.sleep(0.025)
        if not acquired:
            raise EcosystemIntegrationError(
                "Timed out waiting for an external artifact chain head"
            )
        try:
            yield
        finally:
            self.store.release_runtime_leases(lease_holder)

    async def _run_stage(
        self,
        *,
        execution_id: str,
        stage_name: str,
        request_payload: dict[str, Any],
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        stage_index = ECOSYSTEM_STAGE_ORDER.index(stage_name) + 1
        stage = self.store.begin_ecosystem_stage(
            execution_id=execution_id,
            stage_name=stage_name,
            stage_index=stage_index,
            request=request_payload,
        )
        if stage.get("already_completed"):
            self._materialize_stage(stage)
            return stage["response"]
        attempt = int(stage["attempts"])
        self.store.update_ecosystem_execution(
            execution_id=execution_id,
            status="RUNNING",
            current_stage=stage_name,
            error=None,
        )
        started = time.perf_counter()
        try:
            with runtime_span(
                "mitra.ecosystem_stage",
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
            ):
                response = await operation()
            completed = self.store.complete_ecosystem_stage(
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                response=response,
            )
            self._materialize_stage(completed)
            self.telemetry.record_event(
                "ecosystem.stage_completed",
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                duration_ms=round(
                    (time.perf_counter() - started) * 1000,
                    3,
                ),
            )
            return response
        except ExternalStageError as exc:
            error = str(exc)
            self.store.fail_ecosystem_stage(
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                error=error,
                response=exc.result,
            )
            self.store.update_ecosystem_execution(
                execution_id=execution_id,
                status="FAILED",
                current_stage=stage_name,
                error=error,
            )
            self.telemetry.record_event(
                "ecosystem.stage_failed",
                severity="error",
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                error=error,
            )
            raise EcosystemIntegrationError(
                f"Ecosystem execution {execution_id} failed at {stage_name}: "
                f"{error}"
            ) from exc
        except EcosystemConfigurationError as exc:
            error = str(exc)
            readiness = self.client.readiness()
            response = exc.result or {
                "trace_id": request_payload.get("trace_id"),
                "status": "blocked",
                "pending_modules": readiness["pending_modules"],
                "modules": readiness["modules"],
                "embedded_fallback": False,
            }
            response["error"] = error
            self.store.fail_ecosystem_stage(
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                error=error,
                response=response,
            )
            self.store.update_ecosystem_execution(
                execution_id=execution_id,
                status="FAILED",
                current_stage=stage_name,
                error=error,
            )
            self.telemetry.record_event(
                "ecosystem.stage_blocked",
                severity="error",
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                pending_modules=readiness["pending_modules"],
            )
            raise
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.store.fail_ecosystem_stage(
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                error=error,
            )
            self.store.update_ecosystem_execution(
                execution_id=execution_id,
                status="FAILED",
                current_stage=stage_name,
                error=error,
            )
            self.telemetry.record_event(
                "ecosystem.stage_failed",
                severity="error",
                execution_id=execution_id,
                stage_name=stage_name,
                attempt=attempt,
                error=error,
            )
            raise

    def _materialize_stage(self, stage: dict[str, Any]) -> dict[str, Any]:
        if stage.get("artifact_hash"):
            return stage
        artifact_payload = {
            "artifact_type": "tantra.ecosystem-stage.v1",
            "execution_id": stage["execution_id"],
            "stage_name": stage["stage_name"],
            "stage_index": stage["stage_index"],
            "attempts": stage["attempts"],
            "request_hash": stage["request_hash"],
            "request": stage["request"],
            "response_hash": stage["response_hash"],
            "response": stage["response"],
        }
        stored = self.depository.put(
            artifact_type="tantra.ecosystem-stage.v1",
            artifact=artifact_payload,
            metadata={
                "execution_id": stage["execution_id"],
                "stage_name": stage["stage_name"],
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="ecosystem_execution",
            subject_id=stage["execution_id"],
            artifact_hash=stored["artifact_hash"],
            metadata={
                "artifact_type": "tantra.ecosystem-stage.v1",
                "stage_name": stage["stage_name"],
            },
        )
        return self.store.link_ecosystem_stage_artifact(
            execution_id=stage["execution_id"],
            stage_name=stage["stage_name"],
            artifact_hash=stored["artifact_hash"],
            lineage_id=lineage["lineage_id"],
            chain_hash=lineage["chain_hash"],
        )

    def _central_package(
        self,
        *,
        execution_id: str,
        trace_id: str,
        insight_result: dict[str, Any],
    ) -> dict[str, Any]:
        stages = self.store.list_ecosystem_stages(execution_id)
        artifact_references = [
            {
                "stage_name": stage["stage_name"],
                "artifact_hash": stage["artifact_hash"],
                "chain_hash": stage["chain_hash"],
            }
            for stage in stages
            if stage.get("artifact_hash")
        ]
        package_core = {
            "package_type": "central-depository.ecosystem-handover.v1",
            "execution_id": execution_id,
            "trace_id": trace_id,
            "artifact_references": artifact_references,
            "artifact_count": len(artifact_references),
            "insightflow_envelope_hash": sha256_json(
                insight_result["envelope"]
            ),
            "authority_boundary": (
                "Mitra exports runtime facts; the receiving depository retains "
                "acceptance and authority."
            ),
        }
        return {
            **package_core,
            "status": "exported",
            "package_hash": sha256_json(package_core),
        }

    def _stages_with_lineage(
        self,
        execution_id: str,
    ) -> list[dict[str, Any]]:
        stages = self.store.list_ecosystem_stages(execution_id)
        enriched = []
        for stage in stages:
            lineage_id = stage.get("lineage_id")
            lineage = (
                self.store.get_central_lineage_entry(lineage_id)
                if isinstance(lineage_id, str) and lineage_id
                else None
            )
            enriched.append({**stage, "lineage": lineage})
        return enriched

    def details(self, execution_id: str) -> dict[str, Any]:
        execution = self.store.get_ecosystem_execution(execution_id)
        if execution is None:
            raise ResourceNotFoundError(
                f"Unknown ecosystem execution: {execution_id}"
            )
        return {
            "execution": execution,
            "stages": self.store.list_ecosystem_stages(execution_id),
            "attempts": self.store.list_ecosystem_stage_attempts(execution_id),
            "depository": {
                "subject_type": "ecosystem_execution",
                "subject_id": execution_id,
                "lineage": self.depository.lineage(
                    subject_type="ecosystem_execution",
                    subject_id=execution_id,
                    limit=100,
                ),
            },
        }

    def list(
        self,
        *,
        status: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.store.list_ecosystem_executions(
            status=status,
            session_id=session_id,
            limit=limit,
        )

    def replay(self, execution_id: str) -> dict[str, Any]:
        execution = self.store.get_ecosystem_execution(execution_id)
        if execution is None:
            raise ResourceNotFoundError(
                f"Unknown ecosystem execution: {execution_id}"
            )
        package = execution.get("replay_package")
        if not isinstance(package, dict):
            raise EcosystemIntegrationError(
                "Ecosystem replay is unavailable until execution completes"
            )
        return {
            "package": package,
            "validation": EcosystemReplayLedger.validate(package),
        }
