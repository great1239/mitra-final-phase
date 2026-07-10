from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from .config import RuntimeSettings
from .depository import CentralDepository
from .utils import canonical_json, sha256_json, utc_now


DEFAULT_JSON_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical JSON bytes used by Karma and PRANA byte-identity checks."""

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
    """Publishes runtime evidence through assigned BHIV contracts.

    The runtime remains manifest-first and product-neutral. This client only
    emits immutable runtime facts to configured ecosystem endpoints; when an
    endpoint is not configured, it records an explicit skipped integration
    result for the evidence package.
    """

    def __init__(
        self,
        settings: RuntimeSettings,
        depository: CentralDepository,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        self.depository = depository
        self.http_transport = http_transport

    def status(self) -> dict[str, Any]:
        endpoints = self._endpoints()
        return {
            "integration_model": "contract-first-runtime-evidence-export",
            "fail_closed": self.settings.bhiv_integration_fail_closed,
            "timeout_seconds": self.settings.bhiv_integration_timeout_seconds,
            "endpoints": {
                name: {
                    "configured": endpoint.configured,
                    "url": endpoint.url,
                }
                for name, endpoint in endpoints.items()
            },
            "contracts": {
                "karma": [
                    "POST /integrity/append",
                    "POST /integrity/append-bucket-artifact",
                ],
                "prana": [
                    "POST /forward/karma-strict",
                    "POST /forward/core",
                ],
                "bucket": [
                    "GET /bucket/latest-hash",
                    "POST /bucket/artifact",
                    "GET /bucket/artifact/{artifact_id}",
                    "POST /bucket/validate-chain/{artifact_id}",
                    "POST /bucket/validate-replay",
                ],
                "insightflow": [
                    "HTTP POST canonical convergence envelope JSON",
                ],
                "ashmit": [
                    "GET /health/system",
                ],
            },
            "api_calls": self.api_call_catalog(),
        }

    @classmethod
    def api_call_catalog(cls) -> list[dict[str, Any]]:
        status_response_schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
            "additionalProperties": True,
        }
        return [
            {
                "module": "ashmit",
                "operation": "ashmit.health-system",
                "method": "GET",
                "path": "/health/system",
                "request_schema": {"type": "object", "maxProperties": 0},
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "karma",
                "operation": "karma.append",
                "method": "POST",
                "path": "/integrity/append",
                "request_schema": {
                    "type": "object",
                    "required": ["payload", "previous_hash", "event_id"],
                    "properties": {
                        "payload": {"type": "object"},
                        "previous_hash": {"type": ["string", "null"]},
                        "event_id": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
                "response_schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {
                            "enum": [
                                "appended",
                                "replay_detected",
                                "append_violation",
                            ]
                        }
                    },
                    "additionalProperties": True,
                },
            },
            {
                "module": "karma",
                "operation": "karma.append-bucket-artifact",
                "method": "POST",
                "path": "/integrity/append-bucket-artifact",
                "request_schema": {
                    "type": "object",
                    "required": ["artifact_id", "trace_id", "parent_hash"],
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "trace_id": {"type": "string"},
                        "parent_hash": {"type": ["string", "null"]},
                    },
                    "additionalProperties": True,
                },
                "response_schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {
                            "enum": [
                                "appended",
                                "replay_detected",
                                "append_violation",
                            ]
                        },
                        "trace_id": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            },
            {
                "module": "prana",
                "operation": "prana.karma-strict",
                "method": "POST",
                "path": "/forward/karma-strict",
                "request_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
                "response_schema": status_response_schema,
                "response_headers": {
                    "X-PRANA-Strict-Bytes-Equal": "true",
                    "X-PRANA-Payload-SHA256": "sha256 hex of forwarded bytes",
                },
            },
            {
                "module": "prana",
                "operation": "prana.core",
                "method": "POST",
                "path": "/forward/core",
                "request_schema": {
                    "type": "object",
                    "required": ["trace_id"],
                    "properties": {"trace_id": {"type": "string"}},
                    "additionalProperties": True,
                },
                "response_schema": {
                    "type": "object",
                    "required": ["trace_id"],
                    "properties": {"trace_id": {"type": "string"}},
                    "additionalProperties": True,
                },
            },
            {
                "module": "bucket",
                "operation": "bucket.latest-hash",
                "method": "GET",
                "path": "/bucket/latest-hash",
                "request_schema": {"type": "object", "maxProperties": 0},
                "response_schema": {
                    "type": "object",
                    "anyOf": [
                        {"required": ["latest_hash"]},
                        {"required": ["latest-hash"]},
                        {"required": ["hash"]},
                    ],
                    "additionalProperties": True,
                },
            },
            {
                "module": "bucket",
                "operation": "bucket.artifact",
                "method": "POST",
                "path": "/bucket/artifact",
                "request_schema": {
                    "type": "object",
                    "required": ["artifact_id", "trace_id", "parent_hash"],
                    "additionalProperties": True,
                },
                "response_schema": status_response_schema,
            },
            {
                "module": "bucket",
                "operation": "bucket.get-artifact",
                "method": "GET",
                "path": "/bucket/artifact/{artifact_id}",
                "request_schema": {
                    "type": "object",
                    "required": ["artifact_id"],
                    "properties": {"artifact_id": {"type": "string"}},
                    "additionalProperties": False,
                },
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "bucket",
                "operation": "bucket.validate-chain",
                "method": "POST",
                "path": "/bucket/validate-chain/{artifact_id}",
                "request_schema": {
                    "type": "object",
                    "required": ["artifact_id"],
                    "properties": {"artifact_id": {"type": "string"}},
                    "additionalProperties": True,
                },
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "bucket",
                "operation": "bucket.validate-replay",
                "method": "POST",
                "path": "/bucket/validate-replay",
                "request_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
                "response_schema": DEFAULT_JSON_RESPONSE_SCHEMA,
            },
            {
                "module": "insightflow",
                "operation": "insightflow.execution_trace",
                "method": "POST",
                "path": "<configured-ingest-url>",
                "request_schema": {
                    "type": "object",
                    "required": ["trace_id", "payload"],
                    "additionalProperties": True,
                },
                "response_schema": status_response_schema,
            },
            {
                "module": "central_depository",
                "operation": "central-depository.export",
                "method": "GET",
                "path": "/api/v1/runtime/depository",
                "request_schema": {
                    "type": "object",
                    "properties": {
                        "artifact_type": {"type": ["string", "null"]},
                        "subject_type": {"type": ["string", "null"]},
                        "subject_id": {"type": ["string", "null"]},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
                "response_schema": {
                    "type": "object",
                    "required": ["depository"],
                    "properties": {"depository": DEFAULT_JSON_RESPONSE_SCHEMA},
                    "additionalProperties": True,
                },
            },
        ]

    async def publish_dispatch(
        self,
        *,
        dispatch: dict[str, Any],
        route: dict[str, Any],
        reconstruction: dict[str, Any],
        proof: dict[str, Any],
    ) -> dict[str, Any]:
        trace_id = (
            dispatch.get("request", {}).get("correlation_id")
            or dispatch["dispatch_id"]
        )
        package_hash = reconstruction["package_hash"]
        runtime_event = {
            "event_id": f"mitra-dispatch:{dispatch['dispatch_id']}",
            "trace_id": trace_id,
            "payload": {
                "system": "mitra-companion-runtime",
                "event_type": "runtime.dispatch.completed",
                "dispatch_id": dispatch["dispatch_id"],
                "status": dispatch["status"],
                "product_id": dispatch["product_id"],
                "capability_id": dispatch["capability_id"],
                "intent_id": dispatch["intent_id"],
                "route_hash": sha256_json(route),
                "reconstruction_package_hash": package_hash,
                "proof_bundle_hash": proof.get("bundle_hash"),
                "occurred_at": dispatch.get("finished_at")
                or dispatch.get("created_at")
                or utc_now(),
            },
        }
        bucket_artifact = {
            "artifact_id": package_hash,
            "trace_id": trace_id,
            "execution_id": dispatch["dispatch_id"],
            "artifact_type": "mitra.dispatch.reconstruction",
            "artifact_hash": package_hash,
            "artifact": reconstruction,
            "metadata": {
                "source_system": "Mitra",
                "route_hash": sha256_json(route),
                "proof_bundle_hash": proof.get("bundle_hash"),
            },
        }
        insight_event = self._insightflow_envelope(
            dispatch=dispatch,
            trace_id=trace_id,
            package_hash=package_hash,
            proof=proof,
        )
        results: list[dict[str, Any]] = []
        karma_event_result = await self._append_karma_event(
            event=runtime_event,
            previous_hash=self.settings.bhiv_karma_previous_hash,
        )
        karma_parent_hash = self._accepted_hash(
            karma_event_result,
            fallback=self.settings.bhiv_karma_previous_hash,
        )
        self._remember_karma_hash(karma_event_result)
        results.append(karma_event_result)
        prana_results = karma_event_result.get("prana_forwarding")
        if isinstance(prana_results, list):
            results.extend(prana_results)
        results.extend(
            await self._publish_bucket_artifact(
                artifact=bucket_artifact,
                karma_parent_hash=karma_parent_hash,
            )
        )
        for item in results:
            if item.get("operation") == "karma.append-bucket-artifact":
                self._remember_karma_hash(item)
        results.append(
            await self._emit_insightflow(envelope=insight_event)
        )
        results.append(await self._probe_ashmit_health())
        results.append(
            self._central_depository_export(
                dispatch_id=dispatch["dispatch_id"],
            )
        )

        accepted = [
            item
            for item in results
            if item.get("status")
            in {"appended", "accepted", "stored", "observed", "healthy"}
        ]
        failed = [
            item
            for item in results
            if item.get("status") in {"failed", "rejected", "unhealthy"}
        ]
        skipped = [item for item in results if item.get("status") == "skipped"]
        packet = {
            "artifact_type": "bhiv-runtime-convergence.dispatch",
            "trace_id": trace_id,
            "dispatch_id": dispatch["dispatch_id"],
            "reconstruction_package_hash": package_hash,
            "result_count": len(results),
            "accepted_count": len(accepted),
            "failed_count": len(failed),
            "skipped_count": len(skipped),
            "results": results,
            "recorded_at": utc_now(),
        }
        stored = self.depository.put(
            artifact_type="bhiv-runtime-convergence.dispatch",
            artifact=packet,
            metadata={
                "dispatch_id": dispatch["dispatch_id"],
                "trace_id": trace_id,
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="dispatch",
            subject_id=dispatch["dispatch_id"],
            artifact_hash=stored["artifact_hash"],
            metadata={
                "artifact_type": "bhiv-runtime-convergence.dispatch",
                "accepted_count": len(accepted),
                "failed_count": len(failed),
                "skipped_count": len(skipped),
            },
        )
        return {
            **packet,
            "artifact_hash": stored["artifact_hash"],
            "lineage_id": lineage["lineage_id"],
            "chain_hash": lineage["chain_hash"],
            "overall_status": (
                "failed"
                if failed and self.settings.bhiv_integration_fail_closed
                else "completed"
            ),
        }

    async def _append_karma_event(
        self,
        *,
        event: dict[str, Any],
        previous_hash: str | None,
    ) -> dict[str, Any]:
        endpoint = self._endpoints()["karma"]
        if not endpoint.configured:
            return self._skipped("karma.append", "MITRA_BHIV_KARMA_BASE_URL")
        payload = {
            "payload": event["payload"],
            "previous_hash": previous_hash,
            "event_id": event["event_id"],
        }
        body = canonical_json_bytes(payload)
        result = await self._post_json_bytes(
            endpoint=endpoint,
            path="/integrity/append",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": event["trace_id"],
            },
        )
        result["operation"] = "karma.append"
        result["request_sha256"] = sha256_bytes(body)
        if result.get("response", {}).get("status") == "appended":
            result["accepted_hash"] = self._accepted_hash(
                result,
                fallback=result["request_sha256"],
            )
            prana = await self._forward_prana_after_karma(
                trace_id=event["trace_id"],
                karma_request_body=body,
                source_operation="karma.append",
            )
            result["prana_forwarding"] = prana
        else:
            result["prana_forwarding"] = {
                "operation": "prana.forward-after-karma",
                "status": "skipped",
                "reason": "karma status was not appended",
                "http_status": None,
                "response": {
                    "status": "skipped",
                    "reason": "karma status was not appended",
                    "source_status": result.get("response", {}).get("status"),
                },
            }
        return self._normalize_append_result(result)

    async def _publish_bucket_artifact(
        self,
        *,
        artifact: dict[str, Any],
        karma_parent_hash: str | None,
    ) -> list[dict[str, Any]]:
        endpoint = self._endpoints()["bucket"]
        if not endpoint.configured:
            return [self._skipped("bucket.artifact", "MITRA_BHIV_BUCKET_BASE_URL")]
        latest = await self._get_json(
            endpoint=endpoint,
            path="/bucket/latest-hash",
        )
        latest["operation"] = "bucket.latest-hash"
        latest = self._normalize_status(latest, accepted_status="accepted")
        parent_hash = (
            latest.get("response", {}).get("latest_hash")
            or latest.get("response", {}).get("latest-hash")
            or latest.get("response", {}).get("hash")
            or self.settings.bhiv_bucket_parent_hash
        )
        bucket_payload = {**artifact, "parent_hash": parent_hash}
        body = canonical_json_bytes(bucket_payload)
        bucket_result = await self._post_json_bytes(
            endpoint=endpoint,
            path="/bucket/artifact",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": artifact["trace_id"],
            },
        )
        bucket_result["operation"] = "bucket.artifact"
        bucket_result["request_sha256"] = sha256_bytes(body)
        bucket_result["parent_lookup"] = latest

        artifact_id = bucket_payload["artifact_id"]
        artifact_lookup = await self._get_json(
            endpoint=endpoint,
            path=f"/bucket/artifact/{artifact_id}",
        )
        artifact_lookup["operation"] = "bucket.get-artifact"
        chain_body = canonical_json_bytes(
            {
                "artifact_id": artifact_id,
                "trace_id": bucket_payload["trace_id"],
                "parent_hash": parent_hash,
            }
        )
        chain_validation = await self._post_json_bytes(
            endpoint=endpoint,
            path=f"/bucket/validate-chain/{artifact_id}",
            body=chain_body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": artifact["trace_id"],
            },
        )
        chain_validation["operation"] = "bucket.validate-chain"
        chain_validation["request_sha256"] = sha256_bytes(chain_body)

        validation_body = canonical_json_bytes(
            {
                "artifact_id": artifact_id,
                "trace_id": bucket_payload["trace_id"],
                "artifact_hash": bucket_payload["artifact_hash"],
                "dispatch_id": bucket_payload["execution_id"],
                "source_system": "Mitra",
            }
        )
        validation = await self._post_json_bytes(
            endpoint=endpoint,
            path="/bucket/validate-replay",
            body=validation_body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": artifact["trace_id"],
            },
        )
        validation["operation"] = "bucket.validate-replay"
        validation["request_sha256"] = sha256_bytes(validation_body)

        karma_payload = {
            **bucket_payload,
            "bucket_parent_hash": parent_hash,
            "parent_hash": karma_parent_hash,
        }
        karma_result = await self._append_karma_bucket_artifact(
            bucket_payload=karma_payload,
        )
        results = [
            latest,
            self._normalize_bucket_result(bucket_result),
            self._normalize_status(
                artifact_lookup,
                accepted_status="accepted",
            ),
            self._normalize_status(
                chain_validation,
                accepted_status="accepted",
            ),
            self._normalize_status(
                validation,
                accepted_status="accepted",
            ),
            karma_result,
        ]
        prana_results = karma_result.get("prana_forwarding")
        if isinstance(prana_results, list):
            results.extend(prana_results)
        return results

    async def _append_karma_bucket_artifact(
        self,
        *,
        bucket_payload: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = self._endpoints()["karma"]
        if not endpoint.configured:
            return self._skipped(
                "karma.append-bucket-artifact",
                "MITRA_BHIV_KARMA_BASE_URL",
            )
        body = canonical_json_bytes(bucket_payload)
        result = await self._post_json_bytes(
            endpoint=endpoint,
            path="/integrity/append-bucket-artifact",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": bucket_payload["trace_id"],
            },
        )
        result["operation"] = "karma.append-bucket-artifact"
        result["request_sha256"] = sha256_bytes(body)
        if result.get("response", {}).get("status") == "appended":
            result["accepted_hash"] = self._accepted_hash(
                result,
                fallback=result["request_sha256"],
            )
            prana = await self._forward_prana_after_karma(
                trace_id=bucket_payload["trace_id"],
                karma_request_body=body,
                source_operation="karma.append-bucket-artifact",
            )
            result["prana_forwarding"] = prana
        else:
            result["prana_forwarding"] = {
                "operation": "prana.forward-after-karma",
                "source_operation": "karma.append-bucket-artifact",
                "status": "skipped",
                "reason": "karma status was not appended",
                "http_status": None,
                "response": {
                    "status": "skipped",
                    "reason": "karma status was not appended",
                    "source_status": result.get("response", {}).get("status"),
                },
            }
        return self._normalize_append_result(result)

    @staticmethod
    def _accepted_hash(
        result: dict[str, Any],
        *,
        fallback: str | None,
    ) -> str | None:
        response = result.get("response") or {}
        return (
            response.get("current_hash")
            or response.get("last_hash")
            or response.get("hash")
            or result.get("accepted_hash")
            or fallback
        )

    def _remember_karma_hash(self, result: dict[str, Any]) -> None:
        if result.get("status") not in {"appended", "accepted"}:
            return
        accepted = self._accepted_hash(
            result,
            fallback=result.get("request_sha256"),
        )
        if accepted:
            self.settings.bhiv_karma_previous_hash = accepted

    async def _forward_prana_after_karma(
        self,
        *,
        trace_id: str,
        karma_request_body: bytes,
        source_operation: str,
    ) -> list[dict[str, Any]]:
        endpoint = self._endpoints()["prana"]
        if not endpoint.configured:
            return [self._skipped("prana.forward", "MITRA_BHIV_PRANA_BASE_URL")]
        strict = await self._post_json_bytes(
            endpoint=endpoint,
            path="/forward/karma-strict",
            body=karma_request_body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        expected_sha = sha256_bytes(karma_request_body)
        strict["operation"] = "prana.karma-strict"
        strict["source_operation"] = source_operation
        strict["strict_bytes_equal"] = (
            strict.get("headers", {})
            .get("x-prana-strict-bytes-equal", "")
            .lower()
            == "true"
        )
        strict["payload_sha256_header"] = strict.get("headers", {}).get(
            "x-prana-payload-sha256"
        )
        strict["payload_sha256_expected"] = expected_sha

        core_body = canonical_json_bytes(
            {
                "trace_id": trace_id,
                "source_system": "Mitra",
                "message_type": "runtime_signal",
            }
        )
        core = await self._post_json_bytes(
            endpoint=endpoint,
            path="/forward/core",
            body=core_body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": trace_id,
            },
        )
        core["operation"] = "prana.core"
        core["source_operation"] = source_operation
        core["trace_id_preserved"] = (
            core.get("response", {}).get("trace_id", trace_id) == trace_id
        )
        return [strict, core]

    async def _emit_insightflow(
        self,
        *,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = self._endpoints()["insightflow"]
        if not endpoint.configured:
            return self._skipped(
                "insightflow.execution_trace",
                "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
            )
        body = canonical_json_bytes(envelope)
        result = await self._post_absolute_json_bytes(
            url=endpoint.url or "",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Mitra-Trace-ID": envelope["trace_id"],
            },
        )
        result["operation"] = "insightflow.execution_trace"
        result["request_sha256"] = sha256_bytes(body)
        return self._normalize_status(result, accepted_status="observed")

    async def _probe_ashmit_health(self) -> dict[str, Any]:
        endpoint = self._endpoints()["ashmit"]
        if not endpoint.configured:
            return self._skipped("ashmit.health-system", "MITRA_BHIV_ASHMIT_BASE_URL")
        result = await self._get_json(endpoint=endpoint, path="/health/system")
        result["operation"] = "ashmit.health-system"
        return self._normalize_status(result, accepted_status="healthy")

    def _central_depository_export(
        self,
        *,
        dispatch_id: str,
    ) -> dict[str, Any]:
        lineage = self.depository.lineage(
            subject_type="dispatch",
            subject_id=dispatch_id,
            limit=100,
        )
        return {
            "operation": "central-depository.export",
            "status": "accepted",
            "method": "GET",
            "url": (
                "mitra://runtime/api/v1/runtime/depository"
                f"?subject_type=dispatch&subject_id={dispatch_id}"
            ),
            "http_status": 200,
            "response": {
                "depository": {
                    "depository_type": (
                        "mitra-runtime-central-depository-reference"
                    ),
                    "subject_type": "dispatch",
                    "subject_id": dispatch_id,
                    "lineage_count": len(lineage),
                    "artifact_hashes": [
                        item["artifact_hash"]
                        for item in lineage
                    ],
                },
            },
        }

    async def _get_json(
        self,
        *,
        endpoint: BHIVEndpoint,
        path: str,
    ) -> dict[str, Any]:
        url = urljoin((endpoint.url or "").rstrip("/") + "/", path.lstrip("/"))
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.settings.bhiv_integration_timeout_seconds,
            ) as client:
                response = await client.get(url)
            result = self._response_result(response, started)
            result["method"] = "GET"
            result["url"] = url
            return result
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            result = self._failed(type(exc).__name__, str(exc), started)
            result["method"] = "GET"
            result["url"] = url
            return result

    async def _post_json_bytes(
        self,
        *,
        endpoint: BHIVEndpoint,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        url = urljoin((endpoint.url or "").rstrip("/") + "/", path.lstrip("/"))
        return await self._post_absolute_json_bytes(
            url=url,
            body=body,
            headers=headers,
        )

    async def _post_absolute_json_bytes(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.settings.bhiv_integration_timeout_seconds,
            ) as client:
                response = await client.post(
                    url,
                    content=body,
                    headers=headers,
                )
            result = self._response_result(response, started)
            result["method"] = "POST"
            result["url"] = url
            return result
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            result = self._failed(type(exc).__name__, str(exc), started)
            result["method"] = "POST"
            result["url"] = url
            return result

    @staticmethod
    def _response_result(
        response: httpx.Response,
        started: float,
    ) -> dict[str, Any]:
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"body": response.text[:500]}
        return {
            "status": "accepted" if response.status_code < 400 else "failed",
            "http_status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "headers": {
                key.lower(): value
                for key, value in response.headers.items()
            },
            "response": payload,
        }

    @staticmethod
    def _failed(
        error_type: str,
        message: str,
        started: float,
    ) -> dict[str, Any]:
        return {
            "status": "failed",
            "error_type": error_type,
            "error": message,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "http_status": None,
            "response": {
                "status": "failed",
                "error_type": error_type,
                "error": message,
            },
        }

    @staticmethod
    def _normalize_append_result(result: dict[str, Any]) -> dict[str, Any]:
        response_status = result.get("response", {}).get("status")
        if response_status == "appended":
            result["status"] = "appended"
        elif response_status in {"replay_detected", "append_violation"}:
            result["status"] = "rejected"
        return result

    @staticmethod
    def _normalize_bucket_result(result: dict[str, Any]) -> dict[str, Any]:
        response_status = result.get("response", {}).get("status")
        if response_status in {"stored", "appended", "accepted"}:
            result["status"] = "stored"
        return result

    @staticmethod
    def _normalize_status(
        result: dict[str, Any],
        *,
        accepted_status: str,
    ) -> dict[str, Any]:
        if result.get("http_status", 500) < 400:
            result["status"] = accepted_status
        return result

    @staticmethod
    def _skipped(operation: str, missing_setting: str) -> dict[str, Any]:
        return {
            "operation": operation,
            "status": "skipped",
            "reason": "endpoint-not-configured",
            "missing_setting": missing_setting,
            "http_status": None,
            "response": {
                "status": "skipped",
                "reason": "endpoint-not-configured",
                "missing_setting": missing_setting,
            },
        }

    def _endpoints(self) -> dict[str, BHIVEndpoint]:
        return {
            "ashmit": BHIVEndpoint(
                "ashmit",
                self.settings.bhiv_ashmit_base_url,
            ),
            "bucket": BHIVEndpoint(
                "bucket",
                self.settings.bhiv_bucket_base_url,
            ),
            "insightflow": BHIVEndpoint(
                "insightflow",
                self.settings.bhiv_insightflow_ingest_url,
            ),
            "karma": BHIVEndpoint(
                "karma",
                self.settings.bhiv_karma_base_url,
            ),
            "prana": BHIVEndpoint(
                "prana",
                self.settings.bhiv_prana_base_url,
            ),
        }

    @staticmethod
    def _insightflow_envelope(
        *,
        dispatch: dict[str, Any],
        trace_id: str,
        package_hash: str,
        proof: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "trace_id": trace_id,
            "schema_version": "1.0",
            "contract_version": "tantra.convergence.v1",
            "source_system": "Mitra",
            "target_system": "InsightFlow",
            "message_type": "execution_result",
            "timestamp_utc": utc_now(),
            "payload": {
                "execution_trace": {
                    "schema_version": "1.0",
                    "execution_id": dispatch["dispatch_id"],
                    "trace_id": trace_id,
                    "cet_hash": (
                        dispatch.get("request", {})
                        .get("payload", {})
                        .get("cet_hash")
                        or package_hash
                    ),
                    "event_type": "execution_committed",
                    "stage": "runtime",
                    "boundary": "Bridge->Runtime",
                    "validation_status": (
                        "accepted"
                        if dispatch["status"] == "COMPLETED"
                        else "rejected"
                    ),
                    "replay_state": "replay_ready",
                    "rejection_reason": dispatch.get("error"),
                    "provenance_reference": (
                        "mitra_reconstruction:"
                        f"{dispatch['dispatch_id']}:{package_hash}"
                    ),
                    "timestamp": dispatch.get("finished_at") or utc_now(),
                }
            },
            "metadata": {
                "producer": "Mitra",
                "environment": "production",
                "dispatch_status": dispatch["status"],
                "proof_bundle_hash": proof.get("bundle_hash"),
                "hash_origin": "incoming_cet_hash_or_mitra_reconstruction_hash",
            },
        }
