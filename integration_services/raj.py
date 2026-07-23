from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from jsonschema import ValidationError, validate

from .common import canonical_bytes, require_api_key, sha256_bytes, utc_now


def _endpoint_overrides() -> dict[str, str]:
    value = os.environ.get("RAJ_ENDPOINT_OVERRIDES_JSON", "{}")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("RAJ_ENDPOINT_OVERRIDES_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in parsed.items()
    ):
        raise RuntimeError("RAJ_ENDPOINT_OVERRIDES_JSON must be a string map")
    return {
        key.rstrip("/"): item.rstrip("/")
        for key, item in parsed.items()
    }


def _effective_base_url(requested_base_url: str) -> str:
    normalized = requested_base_url.rstrip("/")
    return _endpoint_overrides().get(normalized, normalized)


def create_app(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    app = FastAPI(title="Raj Workflow Executor", version="1.0.0")
    app.state.transport = transport

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "workflow-executor",
            "version": "1.0.0",
            "execution_mode": "manifest-contract",
        }

    @app.post("/api/workflow/execute")
    async def execute(request: Request) -> dict[str, Any]:
        require_api_key(request, "RAJ_API_KEY")
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request must be an object")
        trace_id = payload.get("trace_id")
        owner_payload = payload.get("data", {}).get("payload", {})
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        if not isinstance(owner_payload, dict):
            raise HTTPException(status_code=422, detail="workflow payload is required")
        action_type = owner_payload.get("action_type")
        contract = owner_payload.get("mitra_context", {}).get(
            "capability_contract"
        )
        if not isinstance(action_type, str) or not action_type:
            raise HTTPException(status_code=422, detail="action_type is required")
        if not isinstance(contract, dict):
            raise HTTPException(
                status_code=422,
                detail="selected capability contract is required",
            )

        product = contract.get("product") or {}
        intent = contract.get("intent") or {}
        dispatch = intent.get("dispatch") or {}
        requested_base_url = product.get("base_url")
        endpoint = dispatch.get("endpoint")
        if not isinstance(requested_base_url, str) or not requested_base_url:
            raise HTTPException(status_code=422, detail="product base_url is required")
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            raise HTTPException(status_code=422, detail="HTTP dispatch endpoint is required")
        effective_base_url = _effective_base_url(requested_base_url)
        effective_url = urljoin(effective_base_url.rstrip("/") + "/", endpoint.lstrip("/"))
        if urlparse(effective_url).scheme not in {"http", "https"}:
            raise HTTPException(status_code=422, detail="unsupported dispatch URL")

        original_payload = contract.get("input", {}).get("payload", {})
        if not isinstance(original_payload, dict):
            raise HTTPException(status_code=422, detail="capability input must be an object")
        business_payload = dict(original_payload)
        business_payload.pop("raj_workflow", None)
        arguments = owner_payload.get("arguments")
        if isinstance(arguments, dict):
            business_payload.update(arguments)

        options = dispatch.get("options") or {}
        if options.get("request_body", "payload") != "payload":
            raise HTTPException(
                status_code=422,
                detail="only published payload request bodies are supported",
            )
        headers = {
            "Content-Type": "application/json",
            "X-Mitra-Trace-ID": trace_id,
        }
        configured_headers = options.get("headers") or {}
        if not isinstance(configured_headers, dict):
            raise HTTPException(status_code=422, detail="dispatch headers must be an object")
        headers.update({str(key): str(value) for key, value in configured_headers.items()})
        token_environment = options.get("bearer_token_env")
        if token_environment:
            token = os.environ.get(str(token_environment))
            if not token:
                raise HTTPException(
                    status_code=503,
                    detail=f"required product secret is unavailable: {token_environment}",
                )
            headers["Authorization"] = f"Bearer {token}"

        timeout = float(dispatch.get("timeout_seconds") or 45)
        started_at = utc_now()
        request_bytes = canonical_bytes(business_payload)

        def product_error(
            error_type: str,
            message: str,
            *,
            http_status: int | None = None,
            response_bytes: bytes | None = None,
            response_body: str | None = None,
        ) -> dict[str, Any]:
            return {
                "status": "product_error",
                "trace_id": trace_id,
                "execution_result": {
                    "success": False,
                    "trace_id": trace_id,
                    "action_type": action_type,
                    "intent_id": intent.get("intent_id"),
                    "requested_base_url": requested_base_url,
                    "effective_url": effective_url,
                    "http_status": http_status,
                    "request_sha256": sha256_bytes(request_bytes),
                    "response_sha256": (
                        sha256_bytes(response_bytes)
                        if response_bytes is not None
                        else None
                    ),
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "product_response": None,
                    "error": {
                        "type": error_type,
                        "message": message,
                        "http_status": http_status,
                        "response_body": response_body,
                    },
                },
            }

        try:
            async with httpx.AsyncClient(
                transport=app.state.transport,
                timeout=timeout,
                follow_redirects=bool(options.get("follow_redirects", False)),
            ) as client:
                response = await client.post(
                    effective_url,
                    content=request_bytes,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            return product_error(
                "product_transport_error",
                f"product transport failed: {type(exc).__name__}",
            )
        if not 200 <= response.status_code < 300:
            return product_error(
                "product_rejected_workflow",
                "product rejected workflow",
                http_status=response.status_code,
                response_bytes=response.content,
                response_body=response.text[:1000],
            )
        try:
            product_response = response.json()
        except ValueError:
            return product_error(
                "product_invalid_json",
                "product did not return JSON",
                http_status=response.status_code,
                response_bytes=response.content,
                response_body=response.text[:1000],
            )
        response_schema = intent.get("response_schema")
        if isinstance(response_schema, dict):
            try:
                validate(product_response, response_schema)
            except ValidationError as exc:
                return product_error(
                    "product_response_contract_error",
                    "product response violated manifest schema: "
                    + exc.message,
                    http_status=response.status_code,
                    response_bytes=response.content,
                    response_body=response.text[:1000],
                )

        response_bytes = response.content
        return {
            "status": "success",
            "trace_id": trace_id,
            "execution_result": {
                "success": True,
                "trace_id": trace_id,
                "action_type": action_type,
                "intent_id": intent.get("intent_id"),
                "requested_base_url": requested_base_url,
                "effective_url": effective_url,
                "http_status": response.status_code,
                "request_sha256": sha256_bytes(request_bytes),
                "response_sha256": sha256_bytes(response_bytes),
                "started_at": started_at,
                "completed_at": utc_now(),
                "product_response": product_response,
            },
        }

    return app


app = create_app()
