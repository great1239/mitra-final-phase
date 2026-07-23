from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

from .common import require_api_key, sha256_bytes


DATASET_CANONICAL_ID = "BHIV-DS-MITRA-RUNTIME-001"


def parse_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON object is required")
    return payload


def create_app(
    *,
    registry_base_url: str | None = None,
    registry_api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    app = FastAPI(title="Mitra InsightFlow Contract Bridge", version="1.0.0")
    app.state.registry_base_url = (
        registry_base_url
        or os.environ.get("INSIGHTFLOW_REGISTRY_BASE_URL", "")
    ).rstrip("/")
    app.state.registry_api_key = registry_api_key or os.environ.get(
        "INSIGHTFLOW_REGISTRY_API_KEY"
    )
    app.state.transport = transport

    def registry_headers() -> dict[str, str]:
        if not app.state.registry_api_key:
            raise HTTPException(
                status_code=503,
                detail="InsightFlow registry API key is not configured",
            )
        return {
            "Content-Type": "application/json",
            "X-API-Key": app.state.registry_api_key,
        }

    async def ensure_dataset(client: httpx.AsyncClient) -> dict[str, Any]:
        url = (
            f"{app.state.registry_base_url}/api/v1/datasets/canonical/"
            f"{DATASET_CANONICAL_ID}"
        )
        response = await client.get(url, headers=registry_headers())
        if response.status_code == 200:
            return response.json()
        if response.status_code != 404:
            raise HTTPException(
                status_code=502,
                detail=f"InsightFlow dataset lookup returned HTTP {response.status_code}",
            )
        registration = {
            "canonical_id": DATASET_CANONICAL_ID,
            "dataset_name": "Mitra Runtime Execution Telemetry",
            "description": "Canonical execution and integrity telemetry emitted by Mitra.",
            "version": "1.0.0",
            "source_system": "Mitra",
            "source_location": "published-runtime-contract",
            "owner_name": "Mitra Runtime",
            "owner_team": "BHIV Runtime",
            "domain_primary": "runtime-telemetry",
            "domain_tags": ["mitra", "tantra", "execution", "replay"],
            "trust_level": "PROVISIONAL",
            "replay_compatibility": "FULL",
            "replay_notes": "Trace IDs and immutable upstream hashes are retained.",
            "simulation_compatibility": "ADAPTABLE",
            "simulation_notes": "Registry records are metadata, not simulated execution.",
            "ingestion_reference": {
                "system": "Mitra",
                "pipeline_id": "mitra-insightflow-contract-v1",
                "frequency": "per-execution",
            },
            "extended_metadata": {
                "contract": "mitra.tantra.execution.completed.v1"
            },
        }
        created = await client.post(
            f"{app.state.registry_base_url}/api/v1/datasets/",
            json=registration,
            headers=registry_headers(),
        )
        if created.status_code == 409:
            retry = await client.get(url, headers=registry_headers())
            if retry.status_code == 200:
                return retry.json()
        if created.status_code != 201:
            raise HTTPException(
                status_code=502,
                detail=f"InsightFlow dataset registration returned HTTP {created.status_code}",
            )
        return created.json()

    async def record(
        *,
        body: bytes,
        event_type: str,
        trace_id: str,
        stage: str,
    ) -> dict[str, Any]:
        if not app.state.registry_base_url:
            raise HTTPException(
                status_code=503,
                detail="InsightFlow registry URL is not configured",
            )
        payload_hash = sha256_bytes(body)
        payload = parse_payload(body)
        try:
            async with httpx.AsyncClient(
                transport=app.state.transport,
                timeout=float(os.environ.get("INSIGHTFLOW_TIMEOUT_SECONDS", "30")),
            ) as client:
                dataset = await ensure_dataset(client)
                provenance = {
                    "event_type": event_type,
                    "source_system": "Mitra",
                    "source_reference": trace_id,
                    "ingestion_pipeline": "mitra-insightflow-contract-v1",
                    "transformation_reference": {
                        "stage": stage,
                        "payload_sha256": payload_hash,
                        "payload": payload,
                    },
                    "trust_at_event": "PROVISIONAL",
                    "recorded_by": "Mitra InsightFlow Bridge",
                    "notes": "Received through the published Mitra integration contract.",
                    "is_replay_safe": True,
                    "replay_context": {
                        "trace_id": trace_id,
                        "payload_sha256": payload_hash,
                    },
                }
                response = await client.post(
                    f"{app.state.registry_base_url}/api/v1/datasets/{dataset['id']}/provenance",
                    json=provenance,
                    headers=registry_headers(),
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"InsightFlow registry transport failed: {type(exc).__name__}",
            ) from exc
        if response.status_code != 201:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "InsightFlow provenance rejected",
                    "http_status": response.status_code,
                    "body": response.text[:1000],
                },
            )
        stored = response.json()
        return {
            "status": "accepted",
            "trace_id": trace_id,
            "received_sha256": payload_hash,
            "dataset_id": dataset["id"],
            "provenance_id": stored["id"],
            "stage": stage,
        }

    @app.get("/health")
    async def health() -> dict[str, Any]:
        if not app.state.registry_base_url:
            return {"status": "unhealthy", "registry_configured": False}
        try:
            async with httpx.AsyncClient(
                transport=app.state.transport,
                timeout=10,
            ) as client:
                response = await client.get(
                    f"{app.state.registry_base_url}/health"
                )
        except httpx.HTTPError:
            return {"status": "unhealthy", "registry_configured": True}
        return {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "service": "insightflow-contract-bridge",
            "registry_configured": True,
            "registry_http_status": response.status_code,
        }

    @app.post("/ingest/execution")
    async def ingest_execution(request: Request) -> dict[str, Any]:
        require_api_key(request, "INSIGHTFLOW_BRIDGE_API_KEY")
        body = await request.body()
        payload = parse_payload(body)
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        return await record(
            body=body,
            event_type="INGESTION",
            trace_id=trace_id,
            stage="execution",
        )

    @app.post("/ingest/karma")
    async def ingest_karma(request: Request) -> dict[str, Any]:
        require_api_key(request, "INSIGHTFLOW_BRIDGE_API_KEY")
        body = await request.body()
        payload = parse_payload(body)
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        return await record(
            body=body,
            event_type="VALIDATION",
            trace_id=trace_id,
            stage="karma-strict",
        )

    @app.post("/ingest/core")
    async def ingest_core(request: Request) -> dict[str, Any]:
        require_api_key(request, "INSIGHTFLOW_BRIDGE_API_KEY")
        body = await request.body()
        payload = parse_payload(body)
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise HTTPException(status_code=422, detail="trace_id is required")
        return await record(
            body=body,
            event_type="INGESTION",
            trace_id=trace_id,
            stage="prana-core",
        )

    return app


app = create_app()
