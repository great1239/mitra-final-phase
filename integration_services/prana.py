from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

from .common import sha256_bytes


def create_app(
    *,
    strict_target_url: str | None = None,
    core_target_url: str | None = None,
    signal_target_url: str | None = None,
    target_api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    app = FastAPI(title="PRANA Forwarding Runtime", version="1.0.0")
    app.state.strict_target_url = strict_target_url or os.environ.get(
        "PRANA_STRICT_TARGET_URL"
    )
    app.state.core_target_url = core_target_url or os.environ.get(
        "PRANA_CORE_TARGET_URL"
    )
    app.state.signal_target_url = signal_target_url or os.environ.get(
        "PRANA_SIGNAL_TARGET_URL"
    )
    app.state.target_api_key = target_api_key or os.environ.get(
        "PRANA_TARGET_API_KEY"
    )
    app.state.transport = transport

    async def forward_bytes(
        *,
        body: bytes,
        target_url: str | None,
        trace_id: str | None,
    ) -> tuple[dict[str, Any], str]:
        if not target_url:
            raise HTTPException(status_code=503, detail="forward target is not configured")
        headers = {"Content-Type": "application/json"}
        if trace_id:
            headers["X-Mitra-Trace-ID"] = trace_id
        if app.state.target_api_key:
            headers["X-API-Key"] = app.state.target_api_key
        try:
            async with httpx.AsyncClient(
                transport=app.state.transport,
                timeout=float(os.environ.get("PRANA_FORWARD_TIMEOUT_SECONDS", "30")),
            ) as client:
                response = await client.post(
                    target_url,
                    content=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"forward transport failed: {type(exc).__name__}",
            ) from exc
        if not 200 <= response.status_code < 300:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "forward target rejected payload",
                    "http_status": response.status_code,
                    "body": response.text[:1000],
                },
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="forward target returned non-JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="forward target returned invalid JSON")
        return payload, sha256_bytes(body)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        configured = bool(
            app.state.strict_target_url and app.state.core_target_url
        )
        return {
            "status": "healthy" if configured else "unhealthy",
            "service": "prana-forwarder",
            "strict_target_configured": bool(app.state.strict_target_url),
            "core_target_configured": bool(app.state.core_target_url),
        }

    @app.post("/forward/karma-strict")
    async def karma_strict(request: Request, response: Response) -> dict[str, Any]:
        body = await request.body()
        source_hash = sha256_bytes(body)
        target, _ = await forward_bytes(
            body=body,
            target_url=app.state.strict_target_url,
            trace_id=request.headers.get("x-mitra-trace-id"),
        )
        target_hash = target.get("received_sha256")
        if target_hash != source_hash:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "STRICT_BYTE_MISMATCH",
                    "source_sha256": source_hash,
                    "target_sha256": target_hash,
                },
            )
        response.headers["X-PRANA-Strict-Bytes-Equal"] = "true"
        response.headers["X-PRANA-Payload-SHA256"] = source_hash
        return {
            "status": "forwarded",
            "trace_id": target.get("trace_id"),
            "payload_sha256": source_hash,
            "target_receipt": target,
        }

    @app.post("/forward/core")
    async def core(request: Request) -> dict[str, Any]:
        body = await request.body()
        try:
            source = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        trace_id = source.get("trace_id") if isinstance(source, dict) else None
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        target, payload_hash = await forward_bytes(
            body=body,
            target_url=app.state.core_target_url,
            trace_id=trace_id,
        )
        if target.get("trace_id") != trace_id:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "TRACE_ID_MUTATED",
                    "expected_trace_id": trace_id,
                    "received_trace_id": target.get("trace_id"),
                },
            )
        return {
            "status": "forwarded",
            "trace_id": trace_id,
            "payload_sha256": payload_hash,
            "target_receipt": target,
        }

    @app.post("/forward/karma")
    async def karma(request: Request) -> dict[str, Any]:
        body = await request.body()
        target, payload_hash = await forward_bytes(
            body=body,
            target_url=app.state.strict_target_url,
            trace_id=request.headers.get("x-mitra-trace-id"),
        )
        return {
            "status": "forwarded",
            "trace_id": target.get("trace_id"),
            "payload_sha256": payload_hash,
            "target_receipt": target,
        }

    @app.post("/forward/signal")
    async def signal(request: Request) -> dict[str, Any]:
        body = await request.body()
        target, payload_hash = await forward_bytes(
            body=body,
            target_url=app.state.signal_target_url or app.state.core_target_url,
            trace_id=request.headers.get("x-mitra-trace-id"),
        )
        return {
            "status": "forwarded",
            "trace_id": target.get("trace_id"),
            "payload_sha256": payload_hash,
            "target_receipt": target,
        }

    return app


app = create_app()
