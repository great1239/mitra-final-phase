from __future__ import annotations

from typing import Any

from .constants import (
    CONTRACT_VERSION,
    DISPATCH_PHASE_MODEL,
    RUNTIME_VERSION,
    SCHEMA_VERSION,
)
from .utils import sha256_json, utc_now


class DispatchProofBuilder:
    """Creates portable proof bundles from existing dispatch receipts."""

    def __init__(self, *, runtime_instance_id: str):
        self.runtime_instance_id = runtime_instance_id

    def build(
        self,
        *,
        dispatch: dict[str, Any],
        phases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        request = dispatch.get("request") or {}
        response = dispatch.get("response")
        input_payload = request.get("payload") or {}
        context = request.get("context") or {}
        bundle = {
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "proof_type": "mitra-dispatch-proof-v1",
            "generated_at": utc_now(),
            "dispatch": {
                "dispatch_id": dispatch["dispatch_id"],
                "correlation_id": request.get("correlation_id"),
                "session_id": dispatch["session_id"],
                "product_id": dispatch["product_id"],
                "capability_id": dispatch["capability_id"],
                "intent_id": dispatch["intent_id"],
                "status": dispatch["status"],
                "created_at": dispatch["created_at"],
                "finished_at": dispatch.get("finished_at"),
                "runtime_instance_id": self.runtime_instance_id,
            },
            "input": {
                "payload": input_payload,
                "payload_hash": sha256_json(input_payload),
                "loaded_scopes": context.get("loaded_scopes") or [],
                "context_hash": sha256_json(context),
                "request_hash": sha256_json(request),
            },
            "output": {
                "response": response,
                "response_hash": sha256_json(response or {}),
                "error": dispatch.get("error"),
                "terminal": dispatch["status"] in {"COMPLETED", "FAILED"},
            },
            "phase_journal": [
                self._phase_entry(phase) for phase in phases
            ],
            "phase_summary": self._phase_summary(phases),
            "lineage": self._lineage(dispatch, request, response),
            "reconstruction": {
                "method": "immutable-runtime-artifact-replay",
                "required_inputs": [
                    "deterministic replay package",
                    "content-addressed lifecycle snapshot",
                    "content-addressed session snapshot",
                    "content-addressed routing snapshot",
                    "product attachment manifest",
                    "dispatch request envelope",
                    "declared context scopes",
                    "dispatch phase journal",
                    "telemetry snapshot",
                    "recovery snapshot",
                    "failure snapshot",
                    "product transport response",
                ],
                "replay_boundary": (
                    "Replay reconstructs the Mitra runtime execution from "
                    "immutable artifacts. It does not re-execute attached "
                    "product business logic."
                ),
                "request_hash": sha256_json(request),
                "expected_response_hash": sha256_json(response or {}),
            },
            "handover": {
                "summary": (
                    "Dispatch proof bundle generated from durable Mitra "
                    "receipt, phase journal, request, context summary, and "
                    "product response."
                ),
                "consumer_steps": [
                    "verify bundle_hash",
                    "verify request_hash and response_hash",
                    "inspect phase_journal for failed or missing phases",
                    "use lineage nodes to identify runtime and product boundary",
                    "load deterministic_reconstruction and verify every component artifact hash",
                    "confirm replay scope coverage for lifecycle, sessions, routing, attachments, context, dispatch, telemetry, recovery, and failures",
                ],
            },
        }
        bundle["artifact_hashes"] = {
            "dispatch": sha256_json(bundle["dispatch"]),
            "input": sha256_json(bundle["input"]),
            "output": sha256_json(bundle["output"]),
            "phase_journal": sha256_json(bundle["phase_journal"]),
            "phase_summary": sha256_json(bundle["phase_summary"]),
            "lineage": sha256_json(bundle["lineage"]),
            "reconstruction": sha256_json(bundle["reconstruction"]),
            "handover": sha256_json(bundle["handover"]),
        }
        bundle["bundle_hash"] = sha256_json(bundle)
        return bundle

    @staticmethod
    def _phase_entry(phase: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase_name": phase["phase_name"],
            "phase_index": phase["phase_index"],
            "status": phase["status"],
            "attempts": phase.get("attempts", 0),
            "started_at": phase.get("started_at"),
            "finished_at": phase.get("finished_at"),
            "duration_ms": phase.get("duration_ms"),
            "detail": phase.get("detail"),
            "output_hash": phase.get("output_hash"),
            "last_error": phase.get("last_error"),
        }

    @staticmethod
    def _phase_summary(phases: list[dict[str, Any]]) -> dict[str, Any]:
        by_name = {phase["phase_name"]: phase for phase in phases}
        failed = [
            name
            for name, phase in by_name.items()
            if phase.get("status") == "FAILED"
        ]
        missing = [
            phase_name
            for phase_name in DISPATCH_PHASE_MODEL
            if phase_name not in by_name
        ]
        return {
            "expected_phases": list(DISPATCH_PHASE_MODEL),
            "recorded_phase_count": len(phases),
            "missing_phases": missing,
            "failed_phases": failed,
            "complete": not missing and not failed,
        }

    @staticmethod
    def _lineage(
        dispatch: dict[str, Any],
        request: dict[str, Any],
        response: dict[str, Any] | None,
    ) -> dict[str, Any]:
        dispatch_id = dispatch["dispatch_id"]
        product_id = dispatch["product_id"]
        return {
            "nodes": [
                {
                    "id": f"{dispatch_id}:request",
                    "kind": "dispatch-request",
                    "hash": sha256_json(request),
                },
                {
                    "id": f"{dispatch_id}:runtime",
                    "kind": "mitra-runtime",
                    "runtime_version": RUNTIME_VERSION,
                },
                {
                    "id": f"{dispatch_id}:product",
                    "kind": "attached-product",
                    "product_id": product_id,
                    "capability_id": dispatch["capability_id"],
                    "intent_id": dispatch["intent_id"],
                },
                {
                    "id": f"{dispatch_id}:response",
                    "kind": "product-response",
                    "hash": sha256_json(response or {}),
                },
            ],
            "edges": [
                {
                    "from": f"{dispatch_id}:request",
                    "to": f"{dispatch_id}:runtime",
                    "action": "accepted",
                },
                {
                    "from": f"{dispatch_id}:runtime",
                    "to": f"{dispatch_id}:product",
                    "action": "routed",
                },
                {
                    "from": f"{dispatch_id}:product",
                    "to": f"{dispatch_id}:response",
                    "action": "returned",
                },
            ],
        }
