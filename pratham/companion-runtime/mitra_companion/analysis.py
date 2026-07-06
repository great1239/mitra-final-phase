from __future__ import annotations

from collections import defaultdict
from typing import Any

import httpx

from .interaction import (
    _candidate_text,
    _tokens,
    build_capability_understanding,
    build_payload_from_message,
    extract_customer_outcome,
)


def _identity(candidate: dict[str, Any]) -> dict[str, str]:
    return {
        "product_id": candidate["product_id"],
        "capability_id": candidate["capability_id"],
        "intent_id": candidate["intent_id"],
    }


def _identity_tuple(value: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (
        value.get("product_id"),
        value.get("capability_id"),
        value.get("intent_id"),
    )


def _overlap(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _endpoint_kind(endpoint: str) -> str:
    if "://" in endpoint:
        return endpoint.split("://", 1)[0]
    if endpoint.startswith("/"):
        return "relative-http"
    return "opaque"


def _assignment_text(
    *,
    assignment: str | None,
    metadata: dict[str, Any],
) -> str:
    if assignment:
        return assignment
    for key in (
        "assignment",
        "assignment_context",
        "task",
        "task_context",
        "expected_outcome",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


class RuntimeAnalyzer:
    """Builds a product-neutral fit model before any capability is run."""

    def __init__(
        self,
        *,
        threshold: float,
        ai_analysis_url: str | None,
        ai_timeout_seconds: float,
    ):
        self.threshold = threshold
        self.ai_analysis_url = ai_analysis_url
        self.ai_timeout_seconds = ai_timeout_seconds

    async def analyze(
        self,
        *,
        message: str,
        assignment: str | None,
        metadata: dict[str, Any],
        explicit_payload: dict[str, Any],
        candidates: list[dict[str, Any]],
        session: dict[str, Any],
        memory: dict[str, Any],
        metrics: dict[str, Any],
        allow_ai_fallback: bool,
    ) -> dict[str, Any]:
        assignment_body = _assignment_text(
            assignment=assignment,
            metadata=metadata,
        )
        outcome = extract_customer_outcome(message, memory)
        assignment_profile = self._assignment_profile(
            assignment_body=assignment_body,
            message=message,
            metadata=metadata,
        )
        user_expectation = self._user_expectation(
            message=message,
            outcome=outcome,
            metadata=metadata,
        )
        product_profiles = self._product_profiles(candidates)
        fit_matrix = self._fit_matrix(
            message=message,
            assignment_profile=assignment_profile,
            outcome=outcome,
            explicit_payload=explicit_payload,
            candidates=candidates,
            memory=memory,
            metrics=metrics,
        )
        deterministic = self._deterministic_decision(fit_matrix)
        analysis = {
            "status": deterministic["status"],
            "resolver": "deterministic",
            "assignment_profile": assignment_profile,
            "user_expectation": user_expectation,
            "product_profiles": product_profiles,
            "fit_matrix": fit_matrix,
            "recommended_candidate": deterministic.get("candidate"),
            "confidence": deterministic.get("confidence", 0.0),
            "reason": deterministic["reason"],
            "gaps": deterministic["gaps"],
            "session_hints": {
                "session_id": session.get("session_id"),
                "active_product_id": session.get("active_product_id"),
            },
            "ai_status": "not-configured",
        }
        if (
            deterministic["status"] == "matched"
            and deterministic.get("margin", 0.0) >= 0.08
            and not deterministic["gaps"]
        ):
            analysis["ai_status"] = "skipped-deterministic-match"
            return analysis
        ai_result = await self._ai_review(
            message=message,
            assignment_profile=assignment_profile,
            user_expectation=user_expectation,
            product_profiles=product_profiles,
            fit_matrix=fit_matrix,
            memory=memory,
            allow=allow_ai_fallback,
        )
        if ai_result is None:
            return analysis
        return self._merge_ai_result(analysis, ai_result)

    def _assignment_profile(
        self,
        *,
        assignment_body: str,
        message: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        combined = " ".join(item for item in (assignment_body, message) if item)
        tokens = sorted(_tokens(combined))
        directives = [
            token
            for token in tokens
            if token
            in {
                "analyze",
                "attach",
                "contextualise",
                "contextualize",
                "discover",
                "execute",
                "match",
                "route",
                "understand",
            }
        ]
        expected_outputs = [
            token
            for token in tokens
            if token
            in {
                "analysis",
                "answer",
                "dispatch",
                "prediction",
                "profile",
                "recommendation",
                "response",
                "result",
                "summary",
            }
        ]
        return {
            "source": "explicit" if assignment_body else "message-only",
            "summary": assignment_body[:1200] if assignment_body else message[:1200],
            "directives": sorted(set(directives)),
            "expected_outputs": sorted(set(expected_outputs)),
            "constraints": {
                "unknown_future_products": any(
                    token in tokens
                    for token in ("future", "unknown", "independent")
                ),
                "requires_product_matching": any(
                    token in tokens
                    for token in ("match", "route", "capability", "product")
                ),
                "metadata_keys": sorted(str(key) for key in metadata.keys()),
            },
            "terms": tokens[:80],
        }

    @staticmethod
    def _user_expectation(
        *,
        message: str,
        outcome: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        explicit_expectation = metadata.get("expected_outcome")
        if not isinstance(explicit_expectation, str):
            explicit_expectation = None
        return {
            "message": message,
            "requested_action": outcome.get("requested_action"),
            "target_terms": outcome.get("target_terms", []),
            "symbols": outcome.get("symbols", []),
            "constraints": outcome.get("constraints", {}),
            "required_result": explicit_expectation
            or outcome.get("required_result")
            or message,
            "confidence": outcome.get("confidence", 0.0),
        }

    @staticmethod
    def _product_profiles(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate["product_id"]].append(candidate)

        profiles = []
        for product_id, items in sorted(grouped.items()):
            first = items[0]
            protocols = []
            required_inputs: set[str] = set()
            optional_inputs: set[str] = set()
            context_scopes: set[str] = set()
            for item in items:
                dispatch = item.get("dispatch") or {}
                endpoint = str(dispatch.get("endpoint") or "")
                protocols.append(
                    {
                        "mode": dispatch.get("mode"),
                        "endpoint_kind": _endpoint_kind(endpoint),
                        "timeout_seconds": dispatch.get("timeout_seconds"),
                    }
                )
                understanding = build_capability_understanding(item)
                required_inputs.update(understanding["required_inputs"])
                optional_inputs.update(understanding["optional_inputs"])
                context_scopes.update(understanding["context_scopes"])
            profiles.append(
                {
                    "product_id": product_id,
                    "product_name": first.get("product_name"),
                    "product_version": first.get("product_version"),
                    "attachment_state": first.get("attachment_state"),
                    "capability_count": len(
                        {item["capability_id"] for item in items}
                    ),
                    "intent_count": len(items),
                    "required_inputs": sorted(required_inputs),
                    "optional_inputs": sorted(optional_inputs),
                    "context_scopes": sorted(context_scopes),
                    "protocols": protocols,
                    "capabilities": [
                        build_capability_understanding(item) for item in items
                    ],
                }
            )
        return profiles

    def _fit_matrix(
        self,
        *,
        message: str,
        assignment_profile: dict[str, Any],
        outcome: dict[str, Any],
        explicit_payload: dict[str, Any],
        candidates: list[dict[str, Any]],
        memory: dict[str, Any],
        metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        message_tokens = _tokens(message)
        assignment_tokens = set(assignment_profile.get("terms") or [])
        outcome_tokens = _tokens(outcome.get("required_result", ""))
        latency_by_product = metrics.get("dispatch_latency_by_product") or {}
        matrix = []
        for candidate in candidates:
            candidate_tokens = _tokens(_candidate_text(candidate))
            payload_result = build_payload_from_message(
                message=message,
                explicit_payload=explicit_payload,
                candidate=candidate,
                memory=memory,
            )
            missing = payload_result["missing"]
            dispatch = candidate.get("dispatch") or {}
            endpoint = str(dispatch.get("endpoint") or "")
            availability_fit = (
                1.0 if candidate.get("attachment_state") == "ATTACHED" else 0.0
            )
            schema_fit = 1.0
            required_count = len(
                build_capability_understanding(candidate)["required_inputs"]
            )
            if required_count:
                schema_fit = max(0.0, 1.0 - (len(missing) / required_count))
            protocol_fit = 1.0 if dispatch.get("mode") and endpoint else 0.0
            context_fit = min(
                1.0,
                0.45 + (0.15 * len(candidate.get("context_scopes") or [])),
            )
            expectation_fit = max(
                _overlap(message_tokens, candidate_tokens),
                _overlap(outcome_tokens, candidate_tokens),
            )
            assignment_fit = _overlap(assignment_tokens, candidate_tokens)
            latency_summary = latency_by_product.get(candidate["product_id"]) or {}
            latency_penalty = min((latency_summary.get("avg") or 0) / 25000, 0.1)
            confidence = (
                (expectation_fit * 0.34)
                + (assignment_fit * 0.12)
                + (schema_fit * 0.18)
                + (protocol_fit * 0.12)
                + (availability_fit * 0.16)
                + (context_fit * 0.08)
                - latency_penalty
            )
            gaps = []
            if missing:
                gaps.append(
                    {
                        "kind": "missing-inputs",
                        "fields": [item["field"] for item in missing],
                    }
                )
            if not availability_fit:
                gaps.append({"kind": "product-unavailable"})
            if expectation_fit < 0.12:
                gaps.append({"kind": "weak-expectation-match"})
            if not protocol_fit:
                gaps.append({"kind": "missing-dispatch-target"})
            matrix.append(
                {
                    **_identity(candidate),
                    "product_name": candidate.get("product_name"),
                    "confidence": round(max(0.0, min(confidence, 1.0)), 4),
                    "scores": {
                        "expectation_fit": round(expectation_fit, 4),
                        "assignment_fit": round(assignment_fit, 4),
                        "schema_fit": round(schema_fit, 4),
                        "protocol_fit": round(protocol_fit, 4),
                        "availability_fit": round(availability_fit, 4),
                        "context_fit": round(context_fit, 4),
                    },
                    "missing_inputs": missing,
                    "candidate_understanding": build_capability_understanding(
                        candidate,
                        outcome=outcome,
                    ),
                    "protocol": {
                        "mode": dispatch.get("mode"),
                        "endpoint_kind": _endpoint_kind(endpoint),
                        "timeout_seconds": dispatch.get("timeout_seconds"),
                    },
                    "gaps": gaps,
                }
            )
        return sorted(
            matrix,
            key=lambda item: (
                item["confidence"],
                item["product_id"],
                item["capability_id"],
                item["intent_id"],
            ),
            reverse=True,
        )

    def _deterministic_decision(
        self,
        fit_matrix: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not fit_matrix:
            return {
                "status": "no-match",
                "reason": "no attached capability profiles are available",
                "gaps": [{"kind": "no-candidates"}],
                "confidence": 0.0,
                "margin": 0.0,
            }
        top = fit_matrix[0]
        second = fit_matrix[1] if len(fit_matrix) > 1 else None
        margin = top["confidence"] - (second["confidence"] if second else 0.0)
        blocking_gaps = [
            gap
            for gap in top["gaps"]
            if gap["kind"] in {"product-unavailable", "missing-dispatch-target"}
        ]
        if top["confidence"] >= self.threshold and not blocking_gaps:
            return {
                "status": "matched",
                "candidate": {
                    "product_id": top["product_id"],
                    "capability_id": top["capability_id"],
                    "intent_id": top["intent_id"],
                },
                "confidence": top["confidence"],
                "reason": "highest fit across expectation, assignment, schema, and protocol",
                "gaps": top["gaps"],
                "margin": round(margin, 4),
            }
        return {
            "status": "needs-more-signal",
            "candidate": {
                "product_id": top["product_id"],
                "capability_id": top["capability_id"],
                "intent_id": top["intent_id"],
            },
            "confidence": top["confidence"],
            "reason": "fit is below threshold or blocked by capability state",
            "gaps": top["gaps"],
            "margin": round(margin, 4),
        }

    async def _ai_review(
        self,
        *,
        message: str,
        assignment_profile: dict[str, Any],
        user_expectation: dict[str, Any],
        product_profiles: list[dict[str, Any]],
        fit_matrix: list[dict[str, Any]],
        memory: dict[str, Any],
        allow: bool,
    ) -> dict[str, Any] | None:
        if not allow or not self.ai_analysis_url or not fit_matrix:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.ai_timeout_seconds) as client:
                response = await client.post(
                    self.ai_analysis_url,
                    json={
                        "contract": "mitra-runtime-analysis-v1",
                        "message": message,
                        "fallback_trigger": self._fallback_trigger(fit_matrix),
                        "assignment_profile": assignment_profile,
                        "user_expectation": user_expectation,
                        "product_profiles": product_profiles,
                        "fit_matrix": fit_matrix[:8],
                        "dialog_summary": memory.get("short_summary", ""),
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return {
                "status": "failed",
                "reason": "ai review endpoint failed or returned invalid JSON",
            }
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _fallback_trigger(fit_matrix: list[dict[str, Any]]) -> dict[str, Any]:
        if not fit_matrix:
            return {
                "reason": "no-candidates",
                "top_candidate": None,
                "gaps": [{"kind": "no-candidates"}],
            }
        top = fit_matrix[0]
        return {
            "reason": "deterministic-path-not-dispatch-ready",
            "top_candidate": {
                "product_id": top["product_id"],
                "capability_id": top["capability_id"],
                "intent_id": top["intent_id"],
                "confidence": top["confidence"],
            },
            "gaps": top.get("gaps", []),
        }

    def _merge_ai_result(
        self,
        analysis: dict[str, Any],
        ai_result: dict[str, Any],
    ) -> dict[str, Any]:
        if ai_result.get("status") == "failed":
            return {**analysis, "ai_status": "failed", "ai_reason": ai_result["reason"]}
        selected = {
            "product_id": ai_result.get("product_id"),
            "capability_id": ai_result.get("capability_id"),
            "intent_id": ai_result.get("intent_id"),
        }
        confidence = float(ai_result.get("confidence") or 0.0)
        known = {
            _identity_tuple(item)
            for item in analysis.get("fit_matrix", [])
        }
        if _identity_tuple(selected) not in known or confidence < self.threshold:
            return {
                **analysis,
                "ai_status": "ignored",
                "ai_reason": "ai review did not select a known candidate above threshold",
            }
        return {
            **analysis,
            "status": "matched",
            "resolver": "ai-assisted",
            "recommended_candidate": selected,
            "confidence": round(confidence, 4),
            "reason": ai_result.get("reason") or analysis["reason"],
            "gaps": ai_result.get("gaps", analysis["gaps"]),
            "ai_status": "used",
            "ai_payload_hints": ai_result.get("payload") or {},
        }
