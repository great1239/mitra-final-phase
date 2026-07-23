from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from .config import RuntimeSettings
from .depository import CentralDepository
from .utils import canonical_json, utc_now


DEFAULT_JSON_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return the canonical bytes used by published integrity contracts."""

    return canonical_json(payload).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class BHIVEndpoint:
    name: str
    url: str | None

    @property
    def configured(self) -> bool:
        return bool(self.url)


class BHIVRuntimeIntegrator:
    """Compatibility recorder for dispatches outside the owner workflow.

    Owner calls are made only by ``EcosystemRuntime`` through
    ``PublishedEcosystemClient``. Keeping this class as a recorder preserves
    the existing dispatch response shape without maintaining a second owner
    workflow or inventing local responses for unavailable services.
    """

    canonical_endpoint = "/api/v1/ecosystem/execute"

    def __init__(
        self,
        settings: RuntimeSettings,
        depository: CentralDepository,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.depository = depository
        # Retained for constructor compatibility. This recorder performs no I/O.
        self.http_transport = http_transport

    def status(self) -> dict[str, Any]:
        endpoints = self._endpoints()
        pending = [
            {
                "module": name,
                "setting": self._setting_for_endpoint(name),
            }
            for name, endpoint in endpoints.items()
            if not endpoint.configured
        ]
        return {
            "integration_model": "canonical-ecosystem-runtime-only",
            "legacy_dispatch_exporter": "non-executing",
            "canonical_endpoint": self.canonical_endpoint,
            "fail_closed": self.settings.bhiv_integration_fail_closed,
            "readiness": {
                "state": "canonical-only",
                "embedded_contract_modules": [],
                "contract_adapters_available": [],
                "external_endpoints_configured": [
                    name
                    for name, endpoint in endpoints.items()
                    if endpoint.configured
                ],
                "unavailable_owner_modules": [
                    item["module"] for item in pending
                ],
                "external_settings_pending": [
                    item["setting"] for item in pending
                ],
                "live_validation_rule": (
                    "Only the canonical ecosystem runtime may call owner "
                    "services; ordinary dispatch records no owner execution."
                ),
            },
            "endpoints": {
                name: {
                    "configured": endpoint.configured,
                    "url": endpoint.url,
                }
                for name, endpoint in endpoints.items()
            },
            "api_calls": self.api_call_catalog(),
        }

    @classmethod
    def api_call_catalog(cls) -> list[dict[str, Any]]:
        status_schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
            "additionalProperties": True,
        }
        return [
            {
                "module": "raj",
                "operation": "raj.workflow-execute",
                "method": "POST",
                "path": "/api/workflow/execute",
                "response_schema": status_schema,
            },
            {
                "module": "ashmit",
                "operation": "ashmit.health-system",
                "method": "GET",
                "path": "/health/system",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "ashmit",
                "operation": "ashmit.mitra-evaluate",
                "method": "POST",
                "path": "/api/mitra/evaluate",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "keshav",
                "operation": "keshav.analyze",
                "method": "POST",
                "path": "/analyze",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "bucket",
                "operation": "bucket.artifact",
                "method": "POST",
                "path": "/bucket/artifact",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "karma",
                "operation": "karma.append-bucket-artifact",
                "method": "POST",
                "path": "/integrity/append-bucket-artifact",
                "response_schema": status_schema,
            },
            {
                "module": "prana",
                "operation": "prana.karma-strict",
                "method": "POST",
                "path": "/forward/karma-strict",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "prana",
                "operation": "prana.core",
                "method": "POST",
                "path": "/forward/core",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "insightflow",
                "operation": "insightflow.execution-trace",
                "method": "POST",
                "path": "<configured-ingest-url>",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "central_depository",
                "operation": "central-depository.artifact",
                "method": "POST",
                "path": "/bucket/artifact",
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
        ]

    async def publish_dispatch(
        self,
        *,
        dispatch: dict[str, Any],
        route: dict[str, Any],
        reconstruction: dict[str, Any],
        proof: dict[str, Any],
        additional_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del route, proof
        trace_id = (
            dispatch.get("request", {}).get("correlation_id")
            or dispatch["dispatch_id"]
        )
        results = [
            {
                "module": name,
                "operation": f"{name}.not-executed",
                "status": "not_executed",
                "method": None,
                "url": None,
                "http_status": None,
                "response": {
                    "status": "not_executed",
                    "reason": (
                        "Ordinary product dispatch is not the canonical "
                        "cross-owner workflow"
                    ),
                    "canonical_endpoint": self.canonical_endpoint,
                },
            }
            for name in self._endpoints()
        ]
        packet = {
            "artifact_type": "bhiv-runtime-convergence.dispatch",
            "trace_id": trace_id,
            "dispatch_id": dispatch["dispatch_id"],
            "reconstruction_package_hash": reconstruction["package_hash"],
            "result_count": len(results),
            "accepted_count": 0,
            "failed_count": 0,
            "skipped_count": len(results),
            "results": results,
            "handoffs": additional_results or [],
            "recorded_at": utc_now(),
        }
        stored = self.depository.put(
            artifact_type="bhiv-runtime-convergence.dispatch",
            artifact=packet,
            metadata={
                "dispatch_id": dispatch["dispatch_id"],
                "trace_id": trace_id,
                "status": "canonical-execution-required",
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="dispatch",
            subject_id=dispatch["dispatch_id"],
            artifact_hash=stored["artifact_hash"],
            metadata={
                "artifact_type": "bhiv-runtime-convergence.dispatch",
                "accepted_count": 0,
                "failed_count": 0,
                "skipped_count": len(results),
            },
        )
        return {
            **packet,
            "artifact_hash": stored["artifact_hash"],
            "lineage_id": lineage["lineage_id"],
            "chain_hash": lineage["chain_hash"],
            "overall_status": "canonical-execution-required",
        }

    @staticmethod
    def _setting_for_endpoint(name: str) -> str:
        return {
            "raj": "MITRA_RAJ_WORKFLOW_BASE_URL",
            "ashmit": (
                "MITRA_BHIV_ASHMIT_BASE_URL + "
                "MITRA_BHIV_ASHMIT_API_KEY"
            ),
            "bucket": "MITRA_BHIV_BUCKET_BASE_URL",
            "keshav": "MITRA_BHIV_KESHAV_BASE_URL",
            "karma": "MITRA_BHIV_KARMA_BASE_URL",
            "prana": "MITRA_BHIV_PRANA_BASE_URL",
            "insightflow": "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
            "central_depository": "MITRA_CENTRAL_DEPOSITORY_BASE_URL",
        }[name]

    def _endpoints(self) -> dict[str, BHIVEndpoint]:
        return {
            "raj": BHIVEndpoint("raj", self.settings.raj_workflow_base_url),
            "ashmit": BHIVEndpoint(
                "ashmit",
                (
                    self.settings.bhiv_ashmit_base_url
                    if self.settings.bhiv_ashmit_api_key
                    else None
                ),
            ),
            "bucket": BHIVEndpoint(
                "bucket", self.settings.bhiv_bucket_base_url
            ),
            "keshav": BHIVEndpoint(
                "keshav", self.settings.bhiv_keshav_base_url
            ),
            "karma": BHIVEndpoint(
                "karma", self.settings.bhiv_karma_base_url
            ),
            "prana": BHIVEndpoint(
                "prana", self.settings.bhiv_prana_base_url
            ),
            "insightflow": BHIVEndpoint(
                "insightflow", self.settings.bhiv_insightflow_ingest_url
            ),
            "central_depository": BHIVEndpoint(
                "central_depository",
                self.settings.central_depository_base_url,
            ),
        }
