from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


DEFAULT_HOSTED_RUNTIME_URL = "https://mitra-live-runtime-sprint.vercel.app"


READ_ENDPOINTS = (
    ("dashboard", "/"),
    ("health", "/health"),
    ("readiness", "/ready"),
    ("metrics", "/metrics"),
    ("openapi-ui", "/docs"),
    ("openapi-json", "/openapi.json"),
    ("api-status", "/api/v1/runtime/status"),
    ("api-telemetry", "/api/v1/runtime/telemetry?limit=20"),
    ("api-integrations", "/api/v1/runtime/integrations"),
    ("api-depository", "/api/v1/runtime/depository"),
)

CONTRACT_VERSION = {
    "schema_version": "1.0.0",
    "contract_version": "1.0.0",
    "runtime_version": "1.0.0",
    "compatibility_version": "mitra-companion-1",
}

LOCALHOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _target_url() -> str:
    positional = [value for value in sys.argv[1:] if value != "--summary"]
    if positional:
        return positional[0].rstrip("/")
    value = os.getenv("MITRA_HOSTED_RUNTIME_URL")
    return (value or DEFAULT_HOSTED_RUNTIME_URL).rstrip("/")


def _sample_body(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text[:500]
    return response.text[:500]


def _url(base_url: str, path: str) -> str:
    return urljoin(base_url + "/", path.lstrip("/"))


def _record_response(
    *,
    name: str,
    method: str,
    url: str,
    started: float,
    response: httpx.Response | None = None,
    error: Exception | None = None,
    expected_status: set[int] | None = None,
) -> dict[str, Any]:
    expected = expected_status or set(range(200, 400))
    latency_ms = (time.perf_counter() - started) * 1000
    if error is not None:
        return {
            "name": name,
            "method": method,
            "url": url,
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "latency_ms": round(latency_ms, 3),
        }
    assert response is not None
    return {
        "name": name,
        "method": method,
        "url": url,
        "status": "ok" if response.status_code in expected else "failed",
        "http_status": response.status_code,
        "latency_ms": round(latency_ms, 3),
        "content_type": response.headers.get("content-type"),
        "body_sample": _sample_body(response),
    }


def _probe(
    client: httpx.Client,
    base_url: str,
    name: str,
    path: str,
    *,
    expected_status: set[int] | None = None,
) -> dict[str, Any]:
    url = urljoin(base_url + "/", path.lstrip("/"))
    started = time.perf_counter()
    try:
        response = client.get(url)
        return _record_response(
            name=name,
            method="GET",
            url=url,
            started=started,
            response=response,
            expected_status=expected_status,
        )
    except httpx.HTTPError as exc:
        return _record_response(
            name=name,
            method="GET",
            url=url,
            started=started,
            error=exc,
            expected_status=expected_status,
        )


def _post(
    client: httpx.Client,
    base_url: str,
    name: str,
    path: str,
    payload: dict[str, Any],
    *,
    expected_status: set[int] | None = None,
) -> dict[str, Any]:
    url = _url(base_url, path)
    started = time.perf_counter()
    try:
        response = client.post(url, json=payload)
        return _record_response(
            name=name,
            method="POST",
            url=url,
            started=started,
            response=response,
            expected_status=expected_status,
        )
    except httpx.HTTPError as exc:
        return _record_response(
            name=name,
            method="POST",
            url=url,
            started=started,
            error=exc,
            expected_status=expected_status,
        )


def _get_json(
    client: httpx.Client,
    base_url: str,
    name: str,
    path: str,
    *,
    expected_status: set[int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    result = _probe(
        client,
        base_url,
        name,
        path,
        expected_status=expected_status,
    )
    body = result.get("body_sample")
    return result, body if isinstance(body, dict) else None


def _require(
    result: dict[str, Any],
    condition: bool,
    message: str,
) -> None:
    if not condition:
        result["status"] = "failed"
        result["error"] = message


def _sample_value(name: str, schema: dict[str, Any]) -> Any:
    value_type = schema.get("type", "string")
    if isinstance(value_type, list):
        value_type = next((item for item in value_type if item != "null"), "string")
    if value_type == "integer":
        return 1
    if value_type == "number":
        return 1.0
    if value_type == "boolean":
        return True
    if value_type == "array":
        return []
    if value_type == "object":
        return {}
    return f"hosted-runtime-validation-{name}"


def _payload_from_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    payload = {}
    properties = schema.get("properties") or {}
    for name in schema.get("required") or []:
        field_schema = properties.get(name) or {"type": "string"}
        payload[name] = _sample_value(name, field_schema)
    return payload


def _env_payload() -> dict[str, Any] | None:
    raw = os.getenv("MITRA_VALIDATION_PAYLOAD_JSON")
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("MITRA_VALIDATION_PAYLOAD_JSON must be a JSON object")
    return value


def _uses_localhost(manifest: dict[str, Any]) -> bool:
    base_url = manifest.get("base_url")
    if not base_url:
        return False
    return (urlparse(str(base_url)).hostname or "").lower() in LOCALHOSTS


def _real_intents(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    for capability in manifest.get("capabilities") or []:
        for intent in capability.get("intents") or []:
            dispatch = intent.get("dispatch") or {}
            if dispatch.get("mode") == "loopback":
                continue
            intents.append(
                {
                    "capability_id": capability.get("capability_id"),
                    "intent": intent,
                }
            )
    return intents


def _is_real_attachment(attachment: dict[str, Any]) -> bool:
    manifest = attachment.get("manifest") or {}
    metadata = manifest.get("metadata") or {}
    if attachment.get("state") != "ATTACHED":
        return False
    if metadata.get("example") is True or metadata.get("validation_fixture") is True:
        return False
    if manifest.get("attachment_mode") == "simulated":
        return False
    if _uses_localhost(manifest):
        return False
    return bool(_real_intents(manifest))


def _select_validation_target(
    attachments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    configured_product = os.getenv("MITRA_VALIDATION_PRODUCT_ID")
    configured_capability = os.getenv("MITRA_VALIDATION_CAPABILITY_ID")
    configured_intent = os.getenv("MITRA_VALIDATION_INTENT_ID")
    configured_payload = _env_payload()
    candidates = [
        attachment
        for attachment in attachments
        if _is_real_attachment(attachment)
        and (
            configured_product is None
            or attachment.get("product_id") == configured_product
        )
    ]
    for attachment in candidates:
        manifest = attachment.get("manifest") or {}
        for item in _real_intents(manifest):
            intent = item["intent"]
            capability_id = item["capability_id"]
            if configured_capability and capability_id != configured_capability:
                continue
            if configured_intent and intent.get("intent_id") != configured_intent:
                continue
            return {
                "product_id": attachment["product_id"],
                "capability_id": capability_id,
                "intent_id": intent["intent_id"],
                "payload": configured_payload
                if configured_payload is not None
                else _payload_from_schema(intent.get("input_schema")),
                "selection": (
                    "environment"
                    if configured_product or configured_intent
                    else "first-real-attached-product"
                ),
            }
    return None


def _runtime_flow(client: httpx.Client, base_url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    attachment_list_result, attachment_body = _get_json(
        client,
        base_url,
        "attachment-list",
        "/api/v1/attachments",
    )
    results.append(attachment_list_result)
    attachments = (
        attachment_body.get("attachments")
        if isinstance(attachment_body, dict)
        else None
    )
    target = (
        _select_validation_target(attachments)
        if isinstance(attachments, list)
        else None
    )
    if target is None:
        results.append(
            {
                "name": "validation-target",
                "method": "DISCOVER",
                "url": _url(base_url, "/api/v1/attachments"),
                "status": "skipped",
                "error": (
                    "no real attached product was available; examples, "
                    "simulated manifests, loopback dispatches, and localhost "
                    "manifests are ignored"
                ),
            }
        )
        results.append(
            _post(
                client,
                base_url,
                "recovery",
                "/api/v1/runtime/recovery",
                CONTRACT_VERSION,
            )
        )
        return results

    results.append(
        _post(
            client,
            base_url,
            "attachment-health",
            f"/api/v1/attachments/{target['product_id']}/health",
            {},
        )
    )

    session_payload = {
        **CONTRACT_VERSION,
        "actor_id": "hosted-runtime-validator",
        "client_type": "standalone",
        "workspace_id": "phase-3-production",
        "product_id": target["product_id"],
        "metadata": {
            "validation": "production-deployment",
            "target_selection": target["selection"],
        },
    }
    session_result = _post(
        client,
        base_url,
        "session-create",
        "/api/v1/sessions",
        session_payload,
        expected_status={200, 201},
    )
    results.append(session_result)
    session_body = session_result.get("body_sample")
    session_id = None
    if isinstance(session_body, dict):
        session = session_body.get("session")
        if isinstance(session, dict):
            session_id = session.get("session_id")

    if session_id:
        dispatch_payload = {
            **CONTRACT_VERSION,
            "session_id": session_id,
            "product_id": target["product_id"],
            "capability_id": target["capability_id"],
            "intent_id": target["intent_id"],
            "payload": target["payload"],
            "correlation_id": "hosted-production-routing",
        }
        dispatch_result = _post(
            client,
            base_url,
            "routing-dispatch",
            "/api/v1/intents/dispatch",
            dispatch_payload,
        )
        results.append(dispatch_result)
        dispatch_body = dispatch_result.get("body_sample")
        dispatch_id = None
        if isinstance(dispatch_body, dict):
            dispatch = dispatch_body.get("dispatch")
            if isinstance(dispatch, dict):
                dispatch_id = dispatch.get("dispatch_id")
                _require(
                    dispatch_result,
                    dispatch.get("status") == "COMPLETED",
                    "dispatch did not complete",
                )
                response = dispatch.get("response")
                _require(
                    dispatch_result,
                    isinstance(response, dict),
                    "dispatch response was not a JSON object",
                )

        if dispatch_id:
            replay_result, replay_body = _get_json(
                client,
                base_url,
                "replay-reconstruction",
                f"/api/v1/dispatches/{dispatch_id}/reconstruction",
            )
            reconstruction = (
                replay_body.get("reconstruction")
                if isinstance(replay_body, dict)
                else None
            )
            reconstructed_execution = (
                reconstruction.get("reconstructed_execution")
                if isinstance(reconstruction, dict)
                else None
            )
            _require(
                replay_result,
                isinstance(reconstruction, dict)
                and reconstruction.get("status") == "verified"
                and reconstruction.get("verification", {}).get("deterministic")
                is True,
                "reconstruction was not deterministically verified",
            )
            _require(
                replay_result,
                isinstance(reconstructed_execution, dict)
                and reconstructed_execution.get("request", {})
                .get("payload")
                == target["payload"],
                "reconstruction did not reproduce the submitted input",
            )
            _require(
                replay_result,
                isinstance(reconstructed_execution, dict)
                and reconstructed_execution.get("response")
                == dispatch_body.get("dispatch", {}).get("response"),
                "reconstruction did not reproduce the product output",
            )
            results.append(replay_result)
            proof_result, proof_body = _get_json(
                client,
                base_url,
                "dispatch-proof",
                f"/api/v1/dispatches/{dispatch_id}/proof",
            )
            proof = (
                proof_body.get("proof")
                if isinstance(proof_body, dict)
                else None
            )
            _require(
                proof_result,
                isinstance(proof, dict)
                and proof.get("phase_summary", {}).get("complete") is True,
                "dispatch proof reports an incomplete execution",
            )
            results.append(proof_result)
            phases_result, phases_body = _get_json(
                client,
                base_url,
                "dispatch-phases",
                f"/api/v1/dispatches/{dispatch_id}/phases",
            )
            phases = (
                phases_body.get("phases")
                if isinstance(phases_body, dict)
                else None
            )
            _require(
                phases_result,
                isinstance(phases, list)
                and phases
                and all(item.get("status") == "COMPLETED" for item in phases),
                "dispatch phase journal contains missing or failed phases",
            )
            results.append(phases_result)
        else:
            results.append(
                {
                    "name": "replay-reconstruction",
                    "method": "GET",
                    "url": _url(base_url, "/api/v1/dispatches/{dispatch_id}/reconstruction"),
                    "status": "failed",
                    "error": "dispatch_id was not returned by routing-dispatch",
                }
            )
    else:
        results.append(
            {
                "name": "routing-dispatch",
                "method": "POST",
                "url": _url(base_url, "/api/v1/intents/dispatch"),
                "status": "failed",
                "error": "session_id was not returned by session-create",
            }
        )

    results.append(
        _post(
            client,
            base_url,
            "recovery",
            "/api/v1/runtime/recovery",
            CONTRACT_VERSION,
        )
    )
    return results


def main() -> int:
    base_url = _target_url()
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        read_results = [
            _probe(client, base_url, name, path)
            for name, path in READ_ENDPOINTS
        ]
        flow_results = _runtime_flow(client, base_url)
        post_flow_results = [
            _probe(client, base_url, name, path)
            for name, path in (
                ("post-flow-dashboard", "/"),
                ("post-flow-telemetry", "/api/v1/runtime/telemetry?limit=50"),
                ("post-flow-metrics", "/metrics"),
            )
        ]
        results = [*read_results, *flow_results, *post_flow_results]
    coverage = {
        "live_runtime": any(item["name"] == "api-status" and item["status"] == "ok" for item in results),
        "https": base_url.startswith("https://"),
        "api": any(item["url"].endswith("/api/v1/runtime/status") and item["status"] == "ok" for item in results),
        "dashboard": any(item["name"] == "dashboard" and item["status"] == "ok" for item in results),
        "openapi": any(item["name"] == "openapi-json" and item["status"] == "ok" for item in results),
        "routing": any(item["name"] == "routing-dispatch" and item["status"] == "ok" for item in results),
        "attachments": any(
            item["name"] in {
                "attachment-list",
                "attachment-health",
                "validation-target",
            }
            and item["status"] == "ok"
            for item in results
        ),
        "health": any(item["name"] == "health" and item["status"] == "ok" for item in results),
        "metrics": any(item["name"] == "metrics" and item["status"] == "ok" for item in results),
        "telemetry": any(item["name"] == "post-flow-telemetry" and item["status"] == "ok" for item in results),
        "replay": any(item["name"] == "replay-reconstruction" and item["status"] == "ok" for item in results),
        "recovery": any(item["name"] == "recovery" and item["status"] == "ok" for item in results),
    }
    packet = {
        "validation_type": "mitra-hosted-runtime-output-validation",
        "hosted_runtime_url": base_url,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "required_coverage": coverage,
        "results": results,
        "passed": all(item["status"] == "ok" for item in results)
        and all(coverage.values()),
    }
    if "--summary" in sys.argv:
        failed_results = [
            {
                "name": item["name"],
                "http_status": item.get("http_status"),
                "error": item.get("error"),
            }
            for item in results
            if item["status"] != "ok"
        ]
        print(
            json.dumps(
                {
                    "validation_type": packet["validation_type"],
                    "hosted_runtime_url": base_url,
                    "generated_at": packet["generated_at"],
                    "passed": packet["passed"],
                    "required_coverage": coverage,
                    "request_count": len(results),
                    "failed_results": failed_results,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
