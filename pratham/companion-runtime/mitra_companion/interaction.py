from __future__ import annotations

import re
from typing import Any

import httpx


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "can",
    "do",
    "for",
    "from",
    "give",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "show",
    "tell",
    "the",
    "to",
    "use",
    "what",
    "with",
}

_SYMBOL_EXCLUSIONS = {
    "AI",
    "API",
    "BHIV",
    "JSON",
    "HTTP",
    "HTTPS",
    "MCP",
    "MITRA",
    "RAG",
    "SDK",
}

_QUESTION_STARTS = (
    "what ",
    "why ",
    "how ",
    "when ",
    "where ",
    "which ",
    "explain ",
    "teach ",
)

_ACTION_ALIASES = {
    "predict": {"forecast", "predict", "prediction", "projection"},
    "analyze": {"analysis", "analyze", "diagnose", "inspect"},
    "recommend": {"recommend", "suggest", "advise"},
    "teach": {"explain", "learn", "teach", "understand"},
    "summarize": {"brief", "recap", "summarize", "summary"},
    "show": {"display", "get", "open", "show", "view"},
    "execute": {"do", "execute", "run", "start"},
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1 and token not in _STOPWORDS
    }


def _flatten_metadata(value: Any, *, depth: int = 0) -> str:
    if depth > 2:
        return ""
    if isinstance(value, dict):
        return " ".join(
            _flatten_metadata(item, depth=depth + 1)
            for item in value.values()
        )
    if isinstance(value, list):
        return " ".join(
            _flatten_metadata(item, depth=depth + 1) for item in value
        )
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        str(item)
        for item in (
            candidate.get("product_id", ""),
            candidate.get("product_name", ""),
            candidate.get("capability_id", ""),
            candidate.get("capability_description", ""),
            candidate.get("intent_id", ""),
            candidate.get("description", ""),
            _flatten_metadata(candidate.get("capability_metadata", {})),
            _flatten_metadata(candidate.get("metadata", {})),
            " ".join(
                candidate.get("input_schema", {})
                .get("properties", {})
                .keys()
            ),
        )
        if item
    )


def extract_customer_outcome(
    message: str,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a user utterance into a product-neutral requested outcome."""
    memory = memory or {}
    message_tokens = _tokens(message)
    all_action_words = set().union(*_ACTION_ALIASES.values())
    requested_action = "execute"
    action_confidence = 0.0
    for action, aliases in _ACTION_ALIASES.items():
        if message_tokens & aliases:
            requested_action = action
            action_confidence = 0.25
            break

    symbols = extract_symbols(message)
    target_terms = [
        token
        for token in sorted(message_tokens)
        if token not in all_action_words
        and token not in {item.lower().split(".")[0] for item in symbols}
        and token not in {"ns"}
    ]
    slots = memory.get("slots") or {}
    constraints: dict[str, Any] = {}
    for key in ("horizon", "risk_profile", "medium", "subject", "grade"):
        if key in slots:
            constraints[key] = slots[key]
    lowered = message.lower()
    for horizon in ("intraday", "short", "long"):
        if horizon in lowered:
            constraints["horizon"] = horizon
    for risk_profile in ("low", "moderate", "high"):
        if risk_profile in lowered:
            constraints["risk_profile"] = risk_profile

    confidence = min(
        1.0,
        0.3
        + action_confidence
        + (0.15 if target_terms else 0)
        + (0.15 if symbols else 0),
    )
    return {
        "source": "user-message",
        "original_message": message,
        "requested_action": requested_action,
        "target_terms": target_terms,
        "symbols": symbols,
        "constraints": constraints,
        "required_result": " ".join(
            [requested_action, *target_terms, *symbols]
        ).strip()
        or message,
        "confidence": round(confidence, 4),
    }


def build_capability_understanding(
    candidate: dict[str, Any],
    *,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize an attached capability without relying on product internals."""
    schema = candidate.get("input_schema") or {}
    properties = schema.get("properties") or {}
    required = set(_schema_required_fields(candidate))
    candidate_tokens = _tokens(_candidate_text(candidate))
    outcome_terms = set((outcome or {}).get("target_terms") or [])
    action = (outcome or {}).get("requested_action")
    if action:
        outcome_terms.add(str(action))
    return {
        "known_from": [
            "manifest",
            "intent-registration",
            "input-schema",
            "runtime-metadata",
        ],
        "product_id": candidate.get("product_id"),
        "product_name": candidate.get("product_name"),
        "capability_id": candidate.get("capability_id"),
        "intent_id": candidate.get("intent_id"),
        "published_summary": " ".join(
            item
            for item in (
                candidate.get("capability_description", ""),
                candidate.get("description", ""),
            )
            if item
        ),
        "required_inputs": sorted(required),
        "optional_inputs": sorted(
            name for name in properties if name not in required
        ),
        "context_scopes": candidate.get("context_scopes", []),
        "fit_signals": sorted(outcome_terms & candidate_tokens),
    }


def _schema_required_fields(candidate: dict[str, Any]) -> list[str]:
    schema = candidate.get("input_schema") or {}
    required = schema.get("required") or []
    return [str(item) for item in required]


def _is_question(message: str) -> bool:
    lowered = message.strip().lower()
    return lowered.endswith("?") or lowered.startswith(_QUESTION_STARTS)


def extract_symbols(message: str) -> list[str]:
    symbols: list[str] = []
    for match in re.findall(r"\b[A-Z][A-Z0-9]{1,14}(?:\.[A-Z]{1,4})?\b", message):
        if match in _SYMBOL_EXCLUSIONS:
            continue
        if match not in symbols:
            symbols.append(match)
    return symbols


def _coerce_number(
    message: str,
    *,
    integer: bool,
    minimum: float | int | None,
    maximum: float | int | None,
) -> int | float | None:
    for raw in re.findall(r"\d+(?:\.\d+)?", message):
        value: float | int = int(float(raw)) if integer else float(raw)
        if minimum is not None and value < minimum:
            continue
        if maximum is not None and value > maximum:
            continue
        return value
    return None


def _slot_lookup(slots: dict[str, Any], field_name: str) -> Any:
    if field_name in slots:
        return slots[field_name]
    singular = field_name[:-1] if field_name.endswith("s") else field_name
    plural = f"{field_name}s"
    if singular in slots:
        return slots[singular]
    if plural in slots:
        return slots[plural]
    return None


def _infer_field_value(
    *,
    field_name: str,
    field_schema: dict[str, Any],
    message: str,
    slots: dict[str, Any],
) -> Any:
    field_type = field_schema.get("type")
    if isinstance(field_type, list):
        field_type = next(
            (item for item in field_type if item != "null"),
            field_type[0] if field_type else None,
        )

    existing = _slot_lookup(slots, field_name)
    if existing is not None:
        return existing

    lowered_name = field_name.lower()
    enum_values = field_schema.get("enum")
    if enum_values:
        lowered_message = message.lower()
        for value in enum_values:
            if str(value).lower() in lowered_message:
                return value
        return None

    if field_type == "array":
        item_schema = field_schema.get("items") or {}
        if item_schema.get("type") == "string" and "symbol" in lowered_name:
            symbols = extract_symbols(message)
            return symbols or None
        return None

    if field_type == "string":
        if lowered_name in {
            "input",
            "instruction",
            "message",
            "prompt",
            "query",
            "question",
            "text",
            "utterance",
        }:
            return message
        if "symbol" in lowered_name or "ticker" in lowered_name:
            symbols = extract_symbols(message)
            return symbols[0] if symbols else None
        return message

    if field_type == "integer":
        return _coerce_number(
            message,
            integer=True,
            minimum=field_schema.get("minimum"),
            maximum=field_schema.get("maximum"),
        )

    if field_type == "number":
        return _coerce_number(
            message,
            integer=False,
            minimum=field_schema.get("minimum"),
            maximum=field_schema.get("maximum"),
        )

    if field_type == "boolean":
        lowered_message = message.lower()
        if any(item in lowered_message for item in ("yes", "true", "enable")):
            return True
        if any(item in lowered_message for item in ("no", "false", "without")):
            return False
        return False

    return None


def build_payload_from_message(
    *,
    message: str,
    explicit_payload: dict[str, Any],
    candidate: dict[str, Any],
    memory: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(explicit_payload)
    schema = candidate.get("input_schema") or {}
    properties = schema.get("properties") or {}
    slots = dict(memory.get("slots") or {})
    missing: list[dict[str, str]] = []

    for field_name in _schema_required_fields(candidate):
        if field_name in payload:
            continue
        field_schema = properties.get(field_name) or {}
        value = _infer_field_value(
            field_name=field_name,
            field_schema=field_schema,
            message=message,
            slots=slots,
        )
        if value is None or value == []:
            missing.append(
                {
                    "field": field_name,
                    "prompt": clarification_prompt_for_field(field_name),
                }
            )
        else:
            payload[field_name] = value

    return {"payload": payload, "missing": missing}


def clarification_prompt_for_field(field_name: str) -> str:
    label = field_name.replace("_", " ")
    if "symbol" in field_name:
        return "Which market symbol should I use?"
    return f"What {label} should I use?"


class NaturalIntentResolver:
    """Schema-driven natural-language selection over published capabilities."""

    def __init__(
        self,
        *,
        threshold: float,
        ai_resolver_url: str | None,
        ai_timeout_seconds: float,
    ):
        self.threshold = threshold
        self.ai_resolver_url = ai_resolver_url
        self.ai_timeout_seconds = ai_timeout_seconds

    async def select(
        self,
        *,
        message: str,
        candidates: list[dict[str, Any]],
        session: dict[str, Any],
        memory: dict[str, Any],
        metrics: dict[str, Any],
        allow_ai_fallback: bool,
        runtime_analysis: dict[str, Any] | None = None,
        product_id: str | None = None,
        capability_id: str | None = None,
    ) -> dict[str, Any]:
        outcome = extract_customer_outcome(message, memory)
        ranked = self.rank(
            message=message,
            candidates=candidates,
            session=session,
            memory=memory,
            metrics=metrics,
            product_id=product_id,
            capability_id=capability_id,
            outcome=outcome,
            runtime_analysis=runtime_analysis,
        )
        deterministic = self._decide(
            message=message,
            ranked=ranked,
            product_id=product_id,
            capability_id=capability_id,
            session=session,
        )
        if deterministic["status"] == "selected":
            return deterministic

        ai_selection = await self._ai_fallback(
            message=message,
            ranked=ranked,
            memory=memory,
            allow=allow_ai_fallback,
            outcome=outcome,
        )
        if ai_selection is not None:
            return ai_selection
        return {**deterministic, "outcome": outcome}

    def rank(
        self,
        *,
        message: str,
        candidates: list[dict[str, Any]],
        session: dict[str, Any],
        memory: dict[str, Any],
        metrics: dict[str, Any],
        product_id: str | None,
        capability_id: str | None,
        outcome: dict[str, Any],
        runtime_analysis: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        message_tokens = _tokens(message)
        outcome_tokens = _tokens(outcome.get("required_result", ""))
        ranked: list[dict[str, Any]] = []
        active_product = session.get("active_product_id")
        last_selection = memory.get("last_selection") or {}
        latency_by_product = metrics.get("dispatch_latency_by_product") or {}
        preferred = (runtime_analysis or {}).get("recommended_candidate") or {}
        fit_lookup = {
            (
                item.get("product_id"),
                item.get("capability_id"),
                item.get("intent_id"),
            ): item
            for item in (runtime_analysis or {}).get("fit_matrix", [])
        }

        for candidate in candidates:
            candidate_tokens = _tokens(_candidate_text(candidate))
            overlap = (
                len(message_tokens & candidate_tokens) / max(len(message_tokens), 1)
                if message_tokens
                else 0.0
            )
            outcome_overlap = (
                len(outcome_tokens & candidate_tokens) / max(len(outcome_tokens), 1)
                if outcome_tokens
                else 0.0
            )
            required_fields = set(_schema_required_fields(candidate))
            score = overlap + (outcome_overlap * 0.18)
            if product_id and candidate["product_id"] == product_id:
                score += 0.22
            if capability_id and candidate["capability_id"] == capability_id:
                score += 0.18
            if active_product and candidate["product_id"] == active_product:
                score += 0.14
            if last_selection.get("product_id") == candidate["product_id"]:
                score += 0.05
            if _is_question(message) and required_fields & {
                "query",
                "question",
                "prompt",
                "text",
            }:
                score += 0.23
            if extract_symbols(message) and any(
                "symbol" in field for field in required_fields
            ):
                score += 0.18
            if candidate.get("attachment_state") != "ATTACHED":
                score -= 0.5
            identity = (
                candidate["product_id"],
                candidate["capability_id"],
                candidate["intent_id"],
            )
            fit = fit_lookup.get(identity) or {}
            if fit:
                score += min(float(fit.get("confidence") or 0) * 0.18, 0.18)
            if identity == (
                preferred.get("product_id"),
                preferred.get("capability_id"),
                preferred.get("intent_id"),
            ):
                score += 0.16

            latency_summary = latency_by_product.get(candidate["product_id"]) or {}
            avg_latency = latency_summary.get("avg")
            latency_penalty = min((avg_latency or 0) / 20000, 0.12)
            score -= latency_penalty
            score = max(0.0, min(score, 1.0))

            ranked.append(
                {
                    "candidate": candidate,
                    "confidence": round(score, 4),
                    "outcome": outcome,
                    "reason": self._reason(
                        candidate=candidate,
                        overlap=overlap,
                        outcome_overlap=outcome_overlap,
                        active_product=active_product,
                        product_id=product_id,
                        capability_id=capability_id,
                    ),
                    "understanding": build_capability_understanding(
                        candidate,
                        outcome=outcome,
                    ),
                    "estimated_cost": self._estimated_cost(candidate),
                    "latency_awareness": {
                        "observed_avg_ms": avg_latency,
                        "penalty_applied": round(latency_penalty, 4),
                    },
                    "retry_strategy": {
                        "retryable": True,
                        "strategy": "health-check-then-retry",
                    },
                }
            )
        return sorted(
            ranked,
            key=lambda item: (
                item["confidence"],
                item["candidate"]["product_id"],
                item["candidate"]["capability_id"],
                item["candidate"]["intent_id"],
            ),
            reverse=True,
        )

    def _decide(
        self,
        *,
        message: str,
        ranked: list[dict[str, Any]],
        product_id: str | None,
        capability_id: str | None,
        session: dict[str, Any],
    ) -> dict[str, Any]:
        if not ranked:
            return self._needs_clarification(
                reason="no-capabilities",
                message=(
                    "I do not see an attached published capability that can "
                    "handle that yet."
                ),
                ranked=[],
            )
        top = ranked[0]
        active_product = session.get("active_product_id")
        explicit_or_session_target = bool(product_id or capability_id or active_product)
        if explicit_or_session_target and len(ranked) == 1:
            top = {**top, "confidence": max(top["confidence"], self.threshold)}
            return self._selected(top, ranked, resolver="deterministic")
        if top["confidence"] < self.threshold:
            return self._needs_clarification(
                reason="low-confidence",
                message=(
                    "I found published capabilities, but I need a little more "
                    "detail before choosing one."
                ),
                ranked=ranked,
            )
        if len(ranked) > 1 and ranked[1]["confidence"] >= top["confidence"] - 0.08:
            return self._needs_clarification(
                reason="ambiguous",
                message=(
                    "I found multiple capabilities that could handle this. "
                    "Please choose one or provide a little more detail."
                ),
                ranked=ranked,
            )
        return self._selected(top, ranked, resolver="deterministic")

    async def _ai_fallback(
        self,
        *,
        message: str,
        ranked: list[dict[str, Any]],
        memory: dict[str, Any],
        allow: bool,
        outcome: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not allow or not self.ai_resolver_url or not ranked:
            return None
        candidates = [
            {
                "product_id": item["candidate"]["product_id"],
                "product_name": item["candidate"]["product_name"],
                "capability_id": item["candidate"]["capability_id"],
                "intent_id": item["candidate"]["intent_id"],
                "description": item["candidate"]["description"],
                "input_schema": item["candidate"].get("input_schema", {}),
                "deterministic_confidence": item["confidence"],
            }
            for item in ranked[:8]
        ]
        try:
            async with httpx.AsyncClient(
                timeout=self.ai_timeout_seconds,
            ) as client:
                response = await client.post(
                    self.ai_resolver_url,
                    json={
                        "message": message,
                        "outcome": outcome,
                        "candidates": candidates,
                        "conversation_summary": memory.get("short_summary", ""),
                        "contract": "mitra-companion-ai-intent-resolver-v1",
                    },
                )
                response.raise_for_status()
                selected = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        identity = (
            selected.get("product_id"),
            selected.get("capability_id"),
            selected.get("intent_id"),
        )
        confidence = float(selected.get("confidence") or 0)
        if confidence < self.threshold:
            return None
        for item in ranked:
            candidate = item["candidate"]
            if identity == (
                candidate["product_id"],
                candidate["capability_id"],
                candidate["intent_id"],
            ):
                picked = {
                    **item,
                    "confidence": round(confidence, 4),
                    "ai_payload": selected.get("payload") or {},
                    "ai_explanation": selected.get("explanation"),
                }
                return self._selected(picked, ranked, resolver="ai-fallback")
        return None

    @staticmethod
    def _selected(
        top: dict[str, Any],
        ranked: list[dict[str, Any]],
        *,
        resolver: str,
    ) -> dict[str, Any]:
        return {
            "status": "selected",
            "resolver": resolver,
            "candidate": top["candidate"],
            "confidence": top["confidence"],
            "reason": top["reason"],
            "estimated_cost": top["estimated_cost"],
            "latency_awareness": top["latency_awareness"],
            "retry_strategy": top["retry_strategy"],
            "recommendations": _recommendations(ranked),
            "fallback_candidates": _recommendations(ranked[1:4]),
            "outcome": top.get("outcome"),
            "ai_payload": top.get("ai_payload", {}),
            "ai_explanation": top.get("ai_explanation"),
        }

    @staticmethod
    def _needs_clarification(
        *,
        reason: str,
        message: str,
        ranked: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "status": "needs_clarification",
            "resolver": "deterministic",
            "reason": reason,
            "message": message,
            "recommendations": _recommendations(ranked),
            "fallback_candidates": [],
        }

    @staticmethod
    def _estimated_cost(candidate: dict[str, Any]) -> dict[str, Any]:
        dispatch = candidate.get("dispatch") or {}
        timeout = dispatch.get("timeout_seconds") or 10
        context_scope_count = len(candidate.get("context_scopes") or [])
        required_count = len(_schema_required_fields(candidate))
        score = context_scope_count + required_count + (float(timeout) / 20)
        if score <= 4:
            relative = "low"
        elif score <= 7:
            relative = "medium"
        else:
            relative = "high"
        return {
            "relative": relative,
            "timeout_seconds": timeout,
            "context_scope_count": context_scope_count,
            "required_field_count": required_count,
        }

    @staticmethod
    def _reason(
        *,
        candidate: dict[str, Any],
        overlap: float,
        outcome_overlap: float,
        active_product: str | None,
        product_id: str | None,
        capability_id: str | None,
    ) -> str:
        reasons = []
        if overlap:
            reasons.append("message terms matched the published capability")
        if outcome_overlap:
            reasons.append("requested outcome matched the published interface")
        if product_id == candidate["product_id"]:
            reasons.append("product was explicitly requested")
        if capability_id == candidate["capability_id"]:
            reasons.append("capability was explicitly requested")
        if active_product == candidate["product_id"]:
            reasons.append("session is already attached to this product")
        return "; ".join(reasons) or "ranked from published capability metadata"


def _recommendations(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "product_id": item["candidate"]["product_id"],
            "product_name": item["candidate"]["product_name"],
            "capability_id": item["candidate"]["capability_id"],
            "intent_id": item["candidate"]["intent_id"],
            "confidence": item["confidence"],
            "reason": item["reason"],
            "understanding": item["understanding"],
            "estimated_cost": item["estimated_cost"],
            "latency_awareness": item["latency_awareness"],
        }
        for item in ranked[:3]
    ]


def summarize_memory(
    *,
    previous: dict[str, Any],
    user_message: str,
    assistant_message: str,
    status: str,
    selection: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    missing_fields: list[dict[str, Any]] | None,
    outcome: dict[str, Any] | None = None,
    runtime_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slots = dict(previous.get("slots") or {})
    for key, value in (payload or {}).items():
        if isinstance(value, (str, int, float, bool)) or (
            isinstance(value, list)
            and all(isinstance(item, (str, int, float, bool)) for item in value)
        ):
            slots[key] = value
    if "symbols" in slots and "symbol" not in slots and slots["symbols"]:
        slots["symbol"] = slots["symbols"][0]
    if "symbol" in slots and "symbols" not in slots:
        slots["symbols"] = [slots["symbol"]]

    last_selection = None
    if selection and selection.get("candidate"):
        candidate = selection["candidate"]
        last_selection = {
            "product_id": candidate["product_id"],
            "capability_id": candidate["capability_id"],
            "intent_id": candidate["intent_id"],
            "confidence": selection.get("confidence"),
        }

    turn_count = int(previous.get("turn_count") or 0) + 2
    summary_parts = [
        previous.get("short_summary", "").strip(),
        f"User asked: {user_message.strip()[:220]}",
        f"Assistant status: {status}",
    ]
    if last_selection:
        summary_parts.append(
            "Last selected intent: "
            f"{last_selection['product_id']}/"
            f"{last_selection['capability_id']}/"
            f"{last_selection['intent_id']}"
        )
    compact_analysis = None
    if runtime_analysis:
        compact_analysis = {
            "status": runtime_analysis.get("status"),
            "resolver": runtime_analysis.get("resolver"),
            "recommended_candidate": runtime_analysis.get(
                "recommended_candidate"
            ),
            "confidence": runtime_analysis.get("confidence"),
            "gap_count": len(runtime_analysis.get("gaps") or []),
        }
    short_summary = " | ".join(part for part in summary_parts if part)
    if len(short_summary) > 1000:
        short_summary = short_summary[-1000:]

    return {
        "short_summary": short_summary,
        "turn_count": turn_count,
        "last_user_message": user_message,
        "last_assistant_message": assistant_message,
        "last_status": status,
        "last_outcome": outcome or previous.get("last_outcome"),
        "last_analysis": compact_analysis or previous.get("last_analysis"),
        "last_selection": last_selection,
        "open_clarification": missing_fields or [],
        "slots": slots,
    }
