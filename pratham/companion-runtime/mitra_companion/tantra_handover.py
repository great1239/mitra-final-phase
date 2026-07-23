from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx

from .config import RuntimeSettings
from .depository import CentralDepository
from .reconstruction import DeterministicReconstructionLedger
from .utils import sha256_json, sha256_text, utc_now


CONTRACT_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0.0"
PACKAGE_TYPE = "mitra-tantra-handover-package-v1"
PACKAGE_ARTIFACT_TYPE = "tantra.handover-package.v1"
RECEIPT_ARTIFACT_TYPE = "tantra.gateway-delivery.v1"
INTEGRATION_NAME = "tantra"
REQUIRED_BUNDLES = (
    "evidence_bundle",
    "lineage_bundle",
    "replay_bundle",
    "handover_bundle",
)
REQUIRED_SOURCE_FIELDS = (
    "trace_id",
    "execution_id",
    "contract_version",
    "schema_version",
    "source_system",
    "target_system",
    "decision_chain",
    "authority_chain",
    "governance_findings",
    "replay_findings",
    "payload",
    "lineage_references",
    "replay_references",
    "handover_references",
)


def _wire_bytes(value: dict[str, Any]) -> bytes:
    rendered = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    return (rendered + "\n").encode("utf-8")


def _wire_hash(value: dict[str, Any]) -> str:
    return sha256_text(_wire_bytes(value).decode("utf-8"))


def _trace_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "trace_id" and isinstance(nested, str):
                values.append(nested)
            else:
                values.extend(_trace_values(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_trace_values(nested))
    return values


class TantraHandoverAdapter:
    """Projects completed Mitra executions into the TANTRA gateway contract."""

    def __init__(
        self,
        settings: RuntimeSettings,
        depository: CentralDepository,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.depository = depository
        self.http_transport = http_transport

    def status(self) -> dict[str, Any]:
        configured = bool(self.settings.tantra_gateway_url)
        outbox_counts = self.depository.store.integration_delivery_counts(
            integration_name=INTEGRATION_NAME
        )
        return {
            "integration_model": "mitra-to-tantra-published-handover",
            "mode": "gateway" if configured else "package-only",
            "package_production": "active",
            "gateway_configured": configured,
            "external_execution": "active" if configured else "not-configured",
            "timeout_seconds": self.settings.tantra_integration_timeout_seconds,
            "delivery_outbox": {
                "durable": True,
                "counts": outbox_counts,
                "max_attempts": self.settings.tantra_delivery_max_attempts,
                "lease_seconds": self.settings.tantra_delivery_lease_seconds,
                "initial_backoff_seconds": (
                    self.settings.tantra_delivery_initial_backoff_seconds
                ),
                "max_backoff_seconds": (
                    self.settings.tantra_delivery_max_backoff_seconds
                ),
            },
            "contract": {
                "method": "POST",
                "path": "/api/v1/execute/evidence-package",
                "integration_mode": "auto",
                "bundles": list(REQUIRED_BUNDLES),
            },
            "ownership": {
                "mitra": [
                    "runtime fact projection",
                    "portable reconstruction attachment",
                    "contract transport",
                    "opaque delivery receipt persistence",
                ],
                "tantra": [
                    "cross-system trace coordination",
                    "downstream authority orchestration",
                    "constitutional history reconstruction",
                ],
            },
        }

    def build(
        self,
        *,
        dispatch: dict[str, Any],
        route: dict[str, Any],
        portable_package: dict[str, Any],
        proof: dict[str, Any],
    ) -> dict[str, Any]:
        clean_check = (
            DeterministicReconstructionLedger.validate_portable_package(
                portable_package
            )
        )
        if clean_check.get("status") != "verified":
            raise ValueError(
                "TANTRA handover requires a verified clean-state package"
            )

        dispatch_id = dispatch["dispatch_id"]
        request = dispatch.get("request") or {}
        response = dispatch.get("response") or {}
        package_hash = portable_package["package_hash"]
        correlation_id = request.get("correlation_id")
        if isinstance(correlation_id, str) and re.fullmatch(
            r"[a-fA-F0-9]{64}", correlation_id
        ):
            trace_id = correlation_id.lower()
        else:
            trace_id = sha256_json(
                {
                    "system": "Mitra",
                    "dispatch_id": dispatch_id,
                    "correlation_id": correlation_id,
                    "portable_package_hash": package_hash,
                }
            )

        finished_at = (
            dispatch.get("finished_at")
            or dispatch.get("created_at")
            or utc_now()
        )
        execution_id = dispatch_id
        request_hash = sha256_json(request)
        response_hash = sha256_json(response)
        reconstructed = clean_check.get("reconstructed_execution") or {}
        reconstructed_response_hash = sha256_json(
            reconstructed.get("response") or {}
        )
        identical = (
            response_hash == reconstructed_response_hash
            and clean_check.get("status") == "verified"
        )
        source_lineage = [
            value
            for value in (
                package_hash,
                *(
                    item.get("chain_hash")
                    for item in portable_package.get("lineage", [])
                ),
            )
            if value
        ]

        evidence_bundle = {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "source_system": "Pratham",
            "target_system": "TANTRA",
            "decision_chain": [],
            "authority_chain": [],
            "governance_findings": [],
            "replay_findings": [
                {
                    "status": "VERIFIED" if identical else "FAILED",
                    "portable_package_hash": package_hash,
                    "state_dependency": "none",
                }
            ],
            "payload": {
                "producer_system": "Mitra",
                "runtime_version": self.settings.runtime_version,
                "compatibility_version": self.settings.compatibility_version,
                "dispatch_id": dispatch_id,
                "session_id": dispatch.get("session_id"),
                "product_id": dispatch.get("product_id"),
                "capability_id": dispatch.get("capability_id"),
                "intent_id": dispatch.get("intent_id"),
                "execution_status": dispatch.get("status"),
                "finished_at": finished_at,
                "request_hash": request_hash,
                "response_hash": response_hash,
                "route_hash": sha256_json(route),
                "phase_journal_hash": sha256_json(
                    proof.get("phase_journal") or []
                ),
                "proof_bundle_hash": proof.get("bundle_hash"),
                "portable_package_hash": package_hash,
            },
            "lineage_references": source_lineage,
            "replay_references": [package_hash],
            "handover_references": [
                f"central://dispatch/{dispatch_id}/tantra-handover"
            ],
            "timestamp": finished_at,
        }

        lineage_bundle = {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "source_lineage_references": source_lineage,
            "nodes": [
                {
                    "node_id": "runtime-input",
                    "owner": "Mitra caller",
                    "artifact_hash": request_hash,
                },
                {
                    "node_id": "runtime-execution",
                    "owner": "Mitra",
                    "artifact_hash": package_hash,
                },
                {
                    "node_id": "attached-capability-output",
                    "owner": dispatch.get("product_id"),
                    "artifact_hash": response_hash,
                },
                {
                    "node_id": "tantra-handover",
                    "owner": "TANTRA",
                    "artifact_hash": None,
                },
            ],
            "edges": [
                {
                    "from": "runtime-input",
                    "to": "runtime-execution",
                    "relationship": "consumed_by",
                },
                {
                    "from": "runtime-execution",
                    "to": "attached-capability-output",
                    "relationship": "produced",
                },
                {
                    "from": "attached-capability-output",
                    "to": "tantra-handover",
                    "relationship": "projected_to",
                },
            ],
        }

        replay_bundle = {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "original_execution": {
                "execution_id": execution_id,
                "dispatch_id": dispatch_id,
                "status": dispatch.get("status"),
                "output_hash": response_hash,
            },
            "replayed_execution": {
                "execution_id": execution_id,
                "dispatch_id": reconstructed.get("dispatch_id"),
                "status": reconstructed.get("status"),
                "output_hash": reconstructed_response_hash,
            },
            "replay_result": "IDENTICAL" if identical else "FAILED",
            "portable_package": portable_package,
            "portable_package_hash": package_hash,
            "clean_state_validation": {
                "status": clean_check.get("status"),
                "state_dependency": clean_check.get("state_dependency"),
                "runtime_state_read": clean_check.get("runtime_state_read"),
                "execution_fidelity": clean_check.get("execution_fidelity"),
            },
        }

        handover_items = [
            {
                "item_reference": name,
                "item_hash": _wire_hash(bundle),
                "hash_basis": "sorted-indented-utf8-json-with-newline",
            }
            for name, bundle in (
                ("evidence_bundle.json", evidence_bundle),
                ("lineage_bundle.json", lineage_bundle),
                ("replay_bundle.json", replay_bundle),
            )
        ]
        handover_bundle = {
            "trace_id": trace_id,
            "execution_id": execution_id,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at": finished_at,
            "source_system": "Mitra",
            "target_system": "TANTRA",
            "handover_items": handover_items,
            "handover_verification": {
                "all_items_present": True,
                "all_hashes_valid": True,
                "handover_complete": True,
            },
            "portable_reconstruction": {
                "package_hash": package_hash,
                "state_dependency": "none",
                "validation_endpoint": "/api/v1/reconstruction/validate",
            },
        }
        package = {
            "package_type": PACKAGE_TYPE,
            "evidence_bundle": evidence_bundle,
            "lineage_bundle": lineage_bundle,
            "replay_bundle": replay_bundle,
            "handover_bundle": handover_bundle,
        }
        package["package_hash"] = sha256_json(
            {name: package[name] for name in REQUIRED_BUNDLES}
        )
        return package

    @classmethod
    def validate(cls, package: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        for name in REQUIRED_BUNDLES:
            if not isinstance(package.get(name), dict):
                errors.append(f"missing package bundle: {name}")
        if errors:
            return {"valid": False, "errors": errors, "checks": {}}

        source = package["evidence_bundle"]
        for field in REQUIRED_SOURCE_FIELDS:
            if field not in source:
                errors.append(f"missing source field: {field}")
        trace_id = source.get("trace_id")
        execution_id = source.get("execution_id")
        source_shape = (
            isinstance(trace_id, str)
            and re.fullmatch(r"[a-f0-9]{64}", trace_id) is not None
            and isinstance(execution_id, str)
            and bool(execution_id)
            and source.get("source_system") == "Pratham"
            and source.get("contract_version") == CONTRACT_VERSION
            and source.get("schema_version") == SCHEMA_VERSION
            and isinstance(source.get("payload"), dict)
            and all(
                isinstance(source.get(field), list)
                for field in (
                    "decision_chain",
                    "authority_chain",
                    "governance_findings",
                    "replay_findings",
                    "lineage_references",
                    "replay_references",
                    "handover_references",
                )
            )
        )
        if not source_shape:
            errors.append("source contract shape is invalid")

        continuity = {
            name: (
                package[name].get("trace_id") == trace_id
                and package[name].get("execution_id") == execution_id
            )
            for name in REQUIRED_BUNDLES
        }
        if not all(continuity.values()):
            errors.append("bundle trace or execution continuity failed")

        handover_items = {
            item.get("item_reference"): item
            for item in package["handover_bundle"].get(
                "handover_items", []
            )
            if isinstance(item, dict)
        }
        wire_checks = {
            file_name: (
                handover_items.get(file_name, {}).get("item_hash")
                == _wire_hash(package[bundle_name])
            )
            for file_name, bundle_name in (
                ("evidence_bundle.json", "evidence_bundle"),
                ("lineage_bundle.json", "lineage_bundle"),
                ("replay_bundle.json", "replay_bundle"),
            )
        }
        if not all(wire_checks.values()):
            errors.append("handover item hash verification failed")

        expected_package_hash = sha256_json(
            {name: package[name] for name in REQUIRED_BUNDLES}
        )
        package_hash_valid = package.get("package_hash") == expected_package_hash
        if not package_hash_valid:
            errors.append("package hash verification failed")

        try:
            clean_check = (
                DeterministicReconstructionLedger.validate_portable_package(
                    package["replay_bundle"].get("portable_package") or {}
                )
            )
        except Exception as exc:
            clean_check = {"status": "failed", "error": str(exc)}
        portable_valid = clean_check.get("status") == "verified"
        if not portable_valid:
            errors.append("portable reconstruction package did not verify")

        original = package["replay_bundle"].get("original_execution") or {}
        replayed = package["replay_bundle"].get("replayed_execution") or {}
        identical = (
            package["replay_bundle"].get("replay_result") == "IDENTICAL"
            and original.get("execution_id") == replayed.get("execution_id")
            and bool(original.get("output_hash"))
            and original.get("output_hash") == replayed.get("output_hash")
        )
        if not identical:
            errors.append("execution reconstruction is not identical")

        return {
            "valid": not errors,
            "errors": errors,
            "checks": {
                "source_contract": source_shape,
                "bundle_continuity": continuity,
                "wire_hashes": wire_checks,
                "package_hash": package_hash_valid,
                "portable_reconstruction": clean_check,
                "execution_identical": identical,
            },
        }

    async def publish(
        self,
        *,
        dispatch: dict[str, Any],
        route: dict[str, Any],
        portable_package: dict[str, Any],
        proof: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            package = self.build(
                dispatch=dispatch,
                route=route,
                portable_package=portable_package,
                proof=proof,
            )
            validation = self.validate(package)
            if not validation["valid"]:
                raise ValueError("; ".join(validation["errors"]))
            package_record = self._persist_package(
                dispatch_id=dispatch["dispatch_id"],
                package=package,
            )
        except Exception as exc:
            return {
                "module": "tantra",
                "operation": "tantra.execute-handover",
                "status": "failed",
                "retryable": False,
                "error_code": "package_projection_failed",
                "error": str(exc),
            }

        trace_id = package["evidence_bundle"]["trace_id"]
        execution_id = package["evidence_bundle"]["execution_id"]
        request = {
            **{name: package[name] for name in REQUIRED_BUNDLES},
            "integration_mode": "auto",
            "metadata": {
                "source": "mitra-companion-runtime",
                "dispatch_id": dispatch["dispatch_id"],
                "package_hash": package["package_hash"],
            },
        }
        request_hash = sha256_json(request)
        delivery_id = "delivery_" + sha256_json(
            {
                "integration_name": INTEGRATION_NAME,
                "dispatch_id": dispatch["dispatch_id"],
                "request_hash": request_hash,
            }
        )[:32]
        queued = self.depository.store.enqueue_integration_delivery(
            delivery_id=delivery_id,
            integration_name=INTEGRATION_NAME,
            dispatch_id=dispatch["dispatch_id"],
            trace_id=trace_id,
            request_hash=request_hash,
            request=request,
            initial_status=(
                "PENDING"
                if self.settings.tantra_gateway_url
                else "WAITING_CONFIGURATION"
            ),
        )
        package_fields = {
            "package_produced": True,
            "trace_id": trace_id,
            "execution_id": execution_id,
            "package_hash": package["package_hash"],
            "artifact_hash": package_record["artifact_hash"],
            "lineage_id": package_record["lineage_id"],
            "delivery_id": delivery_id,
        }
        if not self.settings.tantra_gateway_url:
            receipt_record = self._persist_receipt(
                dispatch_id=dispatch["dispatch_id"],
                trace_id=trace_id,
                package_hash=package["package_hash"],
                receipt={
                    "delivery_status": "NOT_ATTEMPTED",
                    "outbox_status": queued["status"],
                    "delivery_id": delivery_id,
                    "reason": "gateway-not-configured",
                    "request_hash": request_hash,
                    "recorded_at": dispatch.get("finished_at")
                    or dispatch.get("created_at"),
                },
            )
            return {
                "module": "tantra",
                "operation": "tantra.execute-handover",
                "status": "skipped",
                "reason": "gateway-not-configured",
                "retryable": True,
                "outbox_status": queued["status"],
                **package_fields,
                "receipt_artifact_hash": receipt_record["artifact_hash"],
            }

        claimed = self.depository.store.claim_integration_deliveries(
            integration_name=INTEGRATION_NAME,
            instance_id=self.settings.runtime_instance_id,
            lease_seconds=self.settings.tantra_delivery_lease_seconds,
            limit=1,
            delivery_id=delivery_id,
            include_waiting_configuration=True,
        )
        if not claimed:
            return {
                "module": "tantra",
                "operation": "tantra.execute-handover",
                "status": "queued",
                "reason": "delivery-owned-or-not-due",
                "retryable": queued["status"] not in {"ACCEPTED", "FAILED"},
                "outbox_status": queued["status"],
                **package_fields,
            }

        delivery_result = await self._deliver_claimed(claimed[0])
        return {
            **delivery_result,
            **package_fields,
        }

    def deliveries(
        self,
        *,
        dispatch_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = self.depository.store.list_integration_deliveries(
            integration_name=INTEGRATION_NAME,
            dispatch_id=dispatch_id,
            status=status,
            limit=limit,
        )
        return [self._public_delivery(row) for row in rows]

    async def process_pending(self, *, limit: int | None = None) -> dict[str, Any]:
        if not self.settings.tantra_gateway_url:
            return {
                "status": "skipped",
                "reason": "gateway-not-configured",
                "processed_count": 0,
                "deliveries": [],
                "outbox_counts": self.depository.store.integration_delivery_counts(
                    integration_name=INTEGRATION_NAME
                ),
            }
        claimed = self.depository.store.claim_integration_deliveries(
            integration_name=INTEGRATION_NAME,
            instance_id=self.settings.runtime_instance_id,
            lease_seconds=self.settings.tantra_delivery_lease_seconds,
            limit=limit or self.settings.tantra_delivery_batch_size,
            include_waiting_configuration=True,
        )
        results = []
        for delivery in claimed:
            results.append(await self._deliver_claimed(delivery))
        return {
            "status": "completed",
            "processed_count": len(results),
            "deliveries": results,
            "outbox_counts": self.depository.store.integration_delivery_counts(
                integration_name=INTEGRATION_NAME
            ),
        }

    async def check_health(self) -> dict[str, Any]:
        if not self.settings.tantra_gateway_url:
            return {
                "dependency_id": "tantra-gateway",
                "status": "not_configured",
                "transport": "http",
                "endpoint": None,
            }
        url = urljoin(
            self.settings.tantra_gateway_url.rstrip("/") + "/",
            "health",
        )
        headers = {"Accept": "application/json"}
        if self.settings.tantra_api_key:
            headers["X-API-Key"] = self.settings.tantra_api_key
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.settings.tantra_integration_timeout_seconds,
            ) as client:
                response = await client.get(url, headers=headers)
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return {
                "dependency_id": "tantra-gateway",
                "status": "unhealthy",
                "transport": "http",
                "endpoint": url,
                "latency_ms": round(
                    (time.perf_counter() - started) * 1000,
                    3,
                ),
                "error": f"{type(exc).__name__}: {exc}",
            }
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"body": response.text[:500]}
        return {
            "dependency_id": "tantra-gateway",
            "status": (
                "healthy" if 200 <= response.status_code < 400 else "unhealthy"
            ),
            "transport": "http",
            "endpoint": url,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "response": payload,
        }

    async def reconcile_remote_traces(
        self,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        if not self.settings.tantra_gateway_url:
            return {
                "status": "skipped",
                "reason": "gateway-not-configured",
                "checked_count": 0,
                "traces": [],
            }
        deliveries = self.depository.store.list_integration_deliveries(
            integration_name=INTEGRATION_NAME,
            status="ACCEPTED",
            limit=limit,
        )
        results = []
        for delivery in deliveries:
            result = await self._fetch_trace(delivery["trace_id"])
            results.append(
                {
                    "delivery_id": delivery["delivery_id"],
                    "dispatch_id": delivery["dispatch_id"],
                    **result,
                }
            )
        return {
            "status": (
                "healthy"
                if all(item["status"] == "healthy" for item in results)
                else "unhealthy"
            ),
            "checked_count": len(results),
            "traces": results,
        }

    async def _fetch_trace(self, trace_id: str) -> dict[str, Any]:
        url = urljoin(
            self.settings.tantra_gateway_url.rstrip("/") + "/",
            f"api/v1/traces/{trace_id}",
        )
        headers = {"Accept": "application/json"}
        if self.settings.tantra_api_key:
            headers["X-API-Key"] = self.settings.tantra_api_key
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.settings.tantra_integration_timeout_seconds,
            ) as client:
                response = await client.get(url, headers=headers)
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return {
                "trace_id": trace_id,
                "status": "unhealthy",
                "latency_ms": round(
                    (time.perf_counter() - started) * 1000,
                    3,
                ),
                "error": f"{type(exc).__name__}: {exc}",
            }
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"body": response.text[:500]}
        observed = _trace_values(payload)
        continuous = bool(observed) and all(
            value == trace_id for value in observed
        )
        healthy = 200 <= response.status_code < 400 and continuous
        return {
            "trace_id": trace_id,
            "status": "healthy" if healthy else "unhealthy",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "trace_continuity": continuous,
            "response": payload,
        }

    async def _deliver_claimed(
        self,
        queued: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        delivery = await self._send(
            queued["request"],
            trace_id=queued["trace_id"],
        )
        delivery["duration_ms"] = round(
            (time.perf_counter() - started) * 1000,
            3,
        )
        attempts = int(queued["attempts"])
        if delivery["status"] == "accepted":
            outbox_status = "ACCEPTED"
            next_attempt_at = None
        elif (
            delivery["retryable"]
            and attempts < self.settings.tantra_delivery_max_attempts
        ):
            outbox_status = "RETRY"
            delay = min(
                self.settings.tantra_delivery_initial_backoff_seconds
                * (2 ** max(0, attempts - 1)),
                self.settings.tantra_delivery_max_backoff_seconds,
            )
            next_attempt_at = (
                datetime.now(UTC) + timedelta(seconds=max(0.0, delay))
            ).isoformat()
        else:
            outbox_status = "FAILED"
            next_attempt_at = None

        effective_retryable = outbox_status == "RETRY"
        error_code = delivery.get("error_code")
        error = delivery.get("error")
        if (
            outbox_status == "FAILED"
            and delivery.get("retryable")
            and attempts >= self.settings.tantra_delivery_max_attempts
        ):
            error_code = "max-attempts-exhausted"
            error = (
                f"Delivery exhausted {attempts} attempts; last error: "
                f"{error or error_code}"
            )
        completed = self.depository.store.complete_integration_delivery(
            delivery_id=queued["delivery_id"],
            instance_id=self.settings.runtime_instance_id,
            lease_token=queued["lease_token"],
            status=outbox_status,
            next_attempt_at=next_attempt_at,
            error=error,
            response=delivery,
        )
        package_hash = (
            queued.get("request", {}).get("metadata", {}).get("package_hash")
        )
        receipt_record = self._persist_receipt(
            dispatch_id=queued["dispatch_id"],
            trace_id=queued["trace_id"],
            package_hash=package_hash or "",
            receipt={
                **delivery,
                "retryable": effective_retryable,
                "error_code": error_code,
                "error": error,
                "delivery_id": queued["delivery_id"],
                "outbox_status": outbox_status,
                "attempt": attempts,
                "next_attempt_at": next_attempt_at,
                "request_hash": queued["request_hash"],
                "recorded_at": utc_now(),
            },
        )
        return {
            "module": "tantra",
            "operation": "tantra.execute-handover",
            "status": delivery["status"],
            "retryable": effective_retryable,
            "error_code": error_code,
            "error": error,
            "http_status": delivery.get("http_status"),
            "duration_ms": delivery["duration_ms"],
            "delivery_id": queued["delivery_id"],
            "outbox_status": outbox_status,
            "attempts": attempts,
            "next_attempt_at": next_attempt_at,
            "trace_id": queued["trace_id"],
            "execution_id": queued["dispatch_id"],
            "package_hash": package_hash,
            "receipt_artifact_hash": receipt_record["artifact_hash"],
            "response": delivery.get("response"),
            "delivery_record": self._public_delivery(completed),
        }

    @staticmethod
    def _public_delivery(delivery: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in delivery.items()
            if key not in {"request", "lease_token"}
        }

    def _persist_package(
        self,
        *,
        dispatch_id: str,
        package: dict[str, Any],
    ) -> dict[str, Any]:
        trace_id = package["evidence_bundle"]["trace_id"]
        stored = self.depository.put(
            artifact_type=PACKAGE_ARTIFACT_TYPE,
            artifact=package,
            metadata={
                "dispatch_id": dispatch_id,
                "trace_id": trace_id,
                "package_hash": package["package_hash"],
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="dispatch",
            subject_id=dispatch_id,
            artifact_hash=stored["artifact_hash"],
            metadata={
                "artifact_type": PACKAGE_ARTIFACT_TYPE,
                "trace_id": trace_id,
            },
        )
        return {
            "artifact_hash": stored["artifact_hash"],
            "lineage_id": lineage["lineage_id"],
            "chain_hash": lineage["chain_hash"],
        }

    def _persist_receipt(
        self,
        *,
        dispatch_id: str,
        trace_id: str,
        package_hash: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        stored = self.depository.put(
            artifact_type=RECEIPT_ARTIFACT_TYPE,
            artifact={
                "trace_id": trace_id,
                "dispatch_id": dispatch_id,
                "package_hash": package_hash,
                **receipt,
            },
            metadata={
                "dispatch_id": dispatch_id,
                "trace_id": trace_id,
                "package_hash": package_hash,
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="dispatch",
            subject_id=dispatch_id,
            artifact_hash=stored["artifact_hash"],
            metadata={
                "artifact_type": RECEIPT_ARTIFACT_TYPE,
                "trace_id": trace_id,
                "delivery_status": receipt.get("delivery_status")
                or receipt.get("status"),
            },
        )
        return {
            "artifact_hash": stored["artifact_hash"],
            "lineage_id": lineage["lineage_id"],
            "chain_hash": lineage["chain_hash"],
        }

    async def _send(
        self,
        request: dict[str, Any],
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        url = urljoin(
            (self.settings.tantra_gateway_url or "").rstrip("/") + "/",
            "api/v1/execute/evidence-package",
        )
        headers = {"Accept": "application/json"}
        if self.settings.tantra_api_key:
            headers["X-API-Key"] = self.settings.tantra_api_key
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.settings.tantra_integration_timeout_seconds,
            ) as client:
                response = await client.post(url, json=request, headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return {
                "status": "failed",
                "delivery_status": "FAILED",
                "retryable": True,
                "error_code": "gateway-unavailable",
                "error": str(exc),
            }
        except httpx.HTTPError as exc:
            return {
                "status": "failed",
                "delivery_status": "FAILED",
                "retryable": True,
                "error_code": "transport-error",
                "error": str(exc),
            }

        if response.is_error:
            status_code = response.status_code
            return {
                "status": "failed",
                "delivery_status": "REJECTED",
                "retryable": (
                    status_code in {408, 425, 429} or status_code >= 500
                ),
                "error_code": f"gateway-http-{status_code}",
                "error": response.text[:2000],
                "http_status": status_code,
            }
        try:
            payload = response.json()
        except ValueError as exc:
            return {
                "status": "failed",
                "delivery_status": "FAILED",
                "retryable": False,
                "error_code": "invalid-gateway-json",
                "error": str(exc),
                "http_status": response.status_code,
            }
        if not isinstance(payload, dict):
            return {
                "status": "failed",
                "delivery_status": "FAILED",
                "retryable": False,
                "error_code": "invalid-gateway-shape",
                "error": "Gateway response must be a JSON object",
                "http_status": response.status_code,
            }
        observed = _trace_values(payload)
        if observed and any(value != trace_id for value in observed):
            return {
                "status": "failed",
                "delivery_status": "FAILED",
                "retryable": False,
                "error_code": "trace-continuity-failed",
                "error": "Gateway response mutated trace_id",
                "http_status": response.status_code,
                "response": payload,
            }
        return {
            "status": "accepted",
            "delivery_status": "ACCEPTED",
            "retryable": False,
            "http_status": response.status_code,
            "response": payload,
        }
