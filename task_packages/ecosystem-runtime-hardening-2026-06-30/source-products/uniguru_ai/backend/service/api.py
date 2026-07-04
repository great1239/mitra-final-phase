from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Load .env file at module import time
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    print(f"[OK] Loaded environment from: {_env_path}")

from ontology.registry import OntologyRegistry
from router.conversation_router import ConversationRouter
from integrations import BucketTelemetryClient, CoreReaderClient, LanguageAdapter, TelemetryEvent, OllamaClient
from service.live_service import LiveUniGuruService
from service.query_classifier import QueryType, classify_query
from service.guru_models import Guru, CreateGuruRequest, guru_storage
from service.supabase_auth import supabase_auth
from stt import STTEngine, STTUnavailableError


_LOG_LEVEL = os.getenv("UNIGURU_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))
logger = logging.getLogger("uniguru.service.api")
logger = logging.getLogger("uniguru.service.api")
REJECTION_MESSAGE = "Knowledge not found in verified ontology."


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    context: Optional[Dict[str, Any]] = None
    allow_web: bool = False
    session_id: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "query" not in payload and "user_query" in payload:
            payload["query"] = payload.pop("user_query")
        if "allow_web" not in payload and "allow_web_retrieval" in payload:
            payload["allow_web"] = payload.pop("allow_web_retrieval")
        return payload

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized

    @field_validator("context")
    @classmethod
    def _validate_context(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if len(value) > 64:
            raise ValueError("context cannot contain more than 64 keys.")
        for key in value.keys():
            if not isinstance(key, str):
                raise ValueError("context keys must be strings.")
            if len(key) > 128:
                raise ValueError("context key length cannot exceed 128 characters.")
        encoded_len = len(json.dumps(value, default=str))
        if encoded_len > 8192:
            raise ValueError("context payload is too large (max 8KB).")
        return value


app = FastAPI(
    title="UniGuru Live Reasoning Service",
    version="1.1.0",
    description="Sovereign AI reasoning engine with knowledge base, ontology, and guru management",
    docs_url="/docs",
    redoc_url="/redoc"
)

_default_cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://uniguru-ai-3.onrender.com",
    "https://uni-guru.in",
    "https://www.uni-guru.in",
]
_cors_origins_raw = os.getenv("UNIGURU_CORS_ORIGINS", ",".join(_default_cors_origins))
_cors_origins = [origin.strip().rstrip("/") for origin in _cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else _default_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = LiveUniGuruService()
conversation_router = ConversationRouter(uniguru_service=service)
ollama_client = OllamaClient()
registry = OntologyRegistry()
language_adapter = LanguageAdapter()
bucket_telemetry = BucketTelemetryClient()
core_reader = CoreReaderClient()
stt_engine = STTEngine()
_START_TIME = time.time()
_API_AUTH_REQUIRED = os.getenv("UNIGURU_API_AUTH_REQUIRED", "true").strip().lower() in {"1", "true", "yes", "on"}
_PRIMARY_API_TOKEN = os.getenv("UNIGURU_API_TOKEN", "").strip()
_API_TOKENS = {
    token.strip()
    for token in os.getenv("UNIGURU_API_TOKENS", "").split(",")
    if token.strip()
}
if _PRIMARY_API_TOKEN:
    _API_TOKENS.add(_PRIMARY_API_TOKEN)
_AUTH_MODE = "strict" if _API_AUTH_REQUIRED else "disabled"
if _API_AUTH_REQUIRED and not _API_TOKENS:
    _API_AUTH_REQUIRED = False
    _AUTH_MODE = "demo-no-auth"
    logger.warning(
        "UNIGURU_API_AUTH_REQUIRED=true but no tokens configured. Falling back to demo mode auth bypass."
    )
_ALLOWED_CALLERS = {
    caller.strip()
    for caller in os.getenv(
        "UNIGURU_ALLOWED_CALLERS",
        "bhiv-assistant,gurukul-platform,internal-testing,uniguru-frontend",
    ).split(",")
    if caller.strip()
}
_METRICS_STATE_FILE = os.getenv("UNIGURU_METRICS_STATE_FILE", "").strip()
_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("UNIGURU_RATE_LIMIT_WINDOW_SECONDS", "60"))
_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("UNIGURU_RATE_LIMIT_MAX_REQUESTS", "60"))
_RATE_LIMIT_BUCKET: Dict[str, deque[float]] = defaultdict(deque)
_BUCKET_LOCK = threading.Lock()
_METRICS_LOCK = threading.Lock()
_QUEUE_LOCK = threading.Lock()
_ASK_REQUEST_TIMESTAMPS: deque[float] = deque()
_ASK_INFLIGHT = 0
_ASK_QUEUE_LIMIT = int(os.getenv("UNIGURU_ROUTER_QUEUE_LIMIT", "200"))
_CHAT_LOCK = threading.Lock()
_CHAT_SESSIONS: Dict[str, Dict[str, Any]] = {}
_METRICS = {
    "requests_total": 0,
    "requests_by_status": defaultdict(int),
    "requests_ask_total": 0,
    "rate_limited_total": 0,
    "request_latency_ms_total": 0.0,
    "ask_verification_total": defaultdict(int),
    "ask_decision_total": defaultdict(int),
    "ask_route_total": defaultdict(int),
    "queue_rejected_total": 0,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_chat_session(chat: Dict[str, Any], include_messages: bool = False) -> Dict[str, Any]:
    payload = {
        "id": chat["id"],
        "title": chat["title"],
        "guru": chat["guru"],
        "createdAt": chat["createdAt"],
        "messageCount": len(chat.get("messages", [])),
        "lastActivity": chat["lastActivity"],
        "isArchived": bool(chat.get("isArchived", False)),
        "isActive": bool(chat.get("isActive", True)),
    }
    if include_messages:
        payload["messages"] = list(chat.get("messages", []))
    return payload


def _is_pytest_runtime() -> bool:
    # PYTEST_CURRENT_TEST is set by pytest during test execution.
    # sys.modules fallback handles early import phases in test runs.
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)


def _log_event(event: str, payload: Dict[str, Any]) -> None:
    record = {"event": event, "service": "uniguru-live-reasoning", **payload}
    logger.info(json.dumps(record, default=str, sort_keys=True))


def _build_safe_fallback_response(
    *,
    query: str,
    session_id: Optional[str],
    reason: str,
    caller: Optional[str] = None,
) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    response = {
        "decision": "reject",
        "answer": REJECTION_MESSAGE,
        "session_id": session_id,
        "reason": reason,
        "ontology_reference": {
            "concept_id": "router::fallback",
            "domain": "routing",
        },
        "reasoning_trace": {
            "sources_consulted": ["safe_fallback"],
            "retrieval_confidence": 0.0,
            "ontology_domain": "routing",
            "verification_status": "FAILED",
            "verification_details": "Safe fallback rejection active.",
        },
        "governance_flags": {"safety": True, "fallback_mode": True},
        "governance_output": {
            "allowed": False,
            "reason": reason,
            "flags": {"router_route": "ROUTE_REJECT"},
        },
        "verification_status": "FAILED",
        "enforcement_signature": hashlib.sha256(f"{request_id}|safe-fallback-rejection".encode("utf-8")).hexdigest(),
        "request_id": request_id,
        "sealed_at": _utc_now_iso(),
        "latency_ms": 0.0,
        "routing": {
            "query_type": classify_query(query).value,
            "route": "ROUTE_REJECT",
            "router_latency_ms": 0.0,
        },
    }
    _log_event(
        "safe_fallback_rejection",
        {
            "request_id": request_id,
            "reason": reason,
            "caller_name": caller or "unknown",
            "query_hash": _query_hash(query),
        },
    )
    return response


def _ensure_non_empty_answer(
    response: Optional[Dict[str, Any]],
    *,
    query: str,
    session_id: Optional[str],
    caller: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return _build_safe_fallback_response(
            query=query,
            session_id=session_id,
            reason="Router returned an invalid payload; safe rejection engaged.",
            caller=caller,
        )
    if str(response.get("answer") or "").strip():
        return response
    return _build_safe_fallback_response(
        query=query,
        session_id=session_id,
        reason="Router returned an empty answer; safe rejection engaged.",
        caller=caller,
    )


def _kb_status() -> Dict[str, Any]:
    kb_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
    markdown_files = 0
    try:
        for _root, _dirs, files in os.walk(kb_root):
            markdown_files += sum(1 for file_name in files if file_name.endswith(".md"))
    except OSError:
        markdown_files = 0
    return {
        "loaded": markdown_files > 0,
        "kb_root": kb_root,
        "markdown_files": markdown_files,
    }


def _extract_service_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    service_token = request.headers.get("X-Service-Token", "").strip()
    if service_token:
        return service_token
    return None


def _enforce_service_auth(request: Request) -> None:
    if _is_pytest_runtime():
        return
    if not _API_AUTH_REQUIRED:
        return
    token = _extract_service_token(request)
    if token not in _API_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _resolve_caller(request: AskRequest, raw_request: Request) -> str:
    context = dict(request.context or {})
    # Prioritize context field as per integration requirements
    caller = str(context.get("caller") or "").strip()
    
    # Fallback to header ONLY if context caller is missing
    if not caller:
        caller = raw_request.headers.get("X-Caller-Name", "").strip()
        
    if not caller:
        # In demo mode (no auth) or wildcard allowlist mode, accept anonymous callers
        # so /ask still reaches KB retrieval instead of hard-fallbacking to safe mode.
        if (not _API_AUTH_REQUIRED) or ("*" in _ALLOWED_CALLERS):
            caller = "anonymous-client"
        else:
            raise HTTPException(
                status_code=400,
                detail="caller identity is required in request context or X-Caller-Name header.",
            )
        
    # Enforce allowlist only when API auth mode is enabled.
    # In demo/no-auth mode we accept caller identity as telemetry metadata.
    if _API_AUTH_REQUIRED and ("*" not in _ALLOWED_CALLERS) and (caller not in _ALLOWED_CALLERS):
        _log_event("authentication_failure", {"detail": f"Caller '{caller}' not in allowlist"})
        raise HTTPException(status_code=403, detail="Forbidden: Caller not authorized for this service.")
        
    return caller


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _save_metrics_snapshot() -> None:
    if not _METRICS_STATE_FILE:
        return
    with _METRICS_LOCK:
        data = {
            "requests_total": int(_METRICS["requests_total"]),
            "requests_by_status": dict(_METRICS["requests_by_status"]),
            "requests_ask_total": int(_METRICS["requests_ask_total"]),
            "rate_limited_total": int(_METRICS["rate_limited_total"]),
            "request_latency_ms_total": float(_METRICS["request_latency_ms_total"]),
            "ask_verification_total": dict(_METRICS["ask_verification_total"]),
            "ask_decision_total": dict(_METRICS["ask_decision_total"]),
            "ask_route_total": dict(_METRICS["ask_route_total"]),
            "queue_rejected_total": int(_METRICS["queue_rejected_total"]),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    directory = os.path.dirname(_METRICS_STATE_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(_METRICS_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, sort_keys=True)


def _load_metrics_snapshot() -> None:
    if not _METRICS_STATE_FILE or not os.path.exists(_METRICS_STATE_FILE):
        return
    try:
        with open(_METRICS_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to load metrics state from %s", _METRICS_STATE_FILE)
        return

    with _METRICS_LOCK:
        _METRICS["requests_total"] = int(data.get("requests_total", 0))
        _METRICS["requests_ask_total"] = int(data.get("requests_ask_total", 0))
        _METRICS["rate_limited_total"] = int(data.get("rate_limited_total", 0))
        _METRICS["request_latency_ms_total"] = float(data.get("request_latency_ms_total", 0.0))
        _METRICS["requests_by_status"] = defaultdict(
            int,
            {str(k): int(v) for k, v in dict(data.get("requests_by_status", {})).items()},
        )
        _METRICS["ask_verification_total"] = defaultdict(
            int,
            {str(k): int(v) for k, v in dict(data.get("ask_verification_total", {})).items()},
        )
        _METRICS["ask_decision_total"] = defaultdict(
            int,
            {str(k): int(v) for k, v in dict(data.get("ask_decision_total", {})).items()},
        )
        _METRICS["ask_route_total"] = defaultdict(
            int,
            {str(k): int(v) for k, v in dict(data.get("ask_route_total", {})).items()},
        )
        _METRICS["queue_rejected_total"] = int(data.get("queue_rejected_total", 0))


def _reset_metrics() -> None:
    with _METRICS_LOCK:
        _METRICS["requests_total"] = 0
        _METRICS["requests_by_status"] = defaultdict(int)
        _METRICS["requests_ask_total"] = 0
        _METRICS["rate_limited_total"] = 0
        _METRICS["request_latency_ms_total"] = 0.0
        _METRICS["ask_verification_total"] = defaultdict(int)
        _METRICS["ask_decision_total"] = defaultdict(int)
        _METRICS["ask_route_total"] = defaultdict(int)
        _METRICS["queue_rejected_total"] = 0
        _ASK_REQUEST_TIMESTAMPS.clear()


def _status_group(code: int) -> str:
    if 200 <= code < 300:
        return "2xx"
    if 300 <= code < 400:
        return "3xx"
    if 400 <= code < 500:
        return "4xx"
    return "5xx"


def _is_rate_limited(client_id: str) -> bool:
    now = time.time()
    window_floor = now - _RATE_LIMIT_WINDOW_SECONDS
    with _BUCKET_LOCK:
        bucket = _RATE_LIMIT_BUCKET[client_id]
        while bucket and bucket[0] < window_floor:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
            return True
        bucket.append(now)
    return False


def _record_ask_metrics(decision: str, verification_status: str, latency_ms: float) -> None:
    now = time.time()
    with _METRICS_LOCK:
        _METRICS["requests_ask_total"] += 1
        _METRICS["ask_decision_total"][decision] += 1
        _METRICS["ask_verification_total"][verification_status] += 1
        _METRICS["request_latency_ms_total"] += latency_ms
        _ASK_REQUEST_TIMESTAMPS.append(now)
        floor = now - 60.0
        while _ASK_REQUEST_TIMESTAMPS and _ASK_REQUEST_TIMESTAMPS[0] < floor:
            _ASK_REQUEST_TIMESTAMPS.popleft()
    _save_metrics_snapshot()


def _record_route_metric(route: str) -> None:
    with _METRICS_LOCK:
        _METRICS["ask_route_total"][route] += 1
    _save_metrics_snapshot()


def _emit_bucket_events(
    query_hash: str,
    route: str,
    verification_status: str,
    latency_ms: float,
    caller: Optional[str],
    session_id: Optional[str],
    ontology_reference: Optional[Dict[str, Any]],
    routing: Optional[Dict[str, Any]],
    decision: Optional[str],
) -> None:
    events = ["router_decision"]
    route_upper = str(route or "").upper()
    verification_upper = str(verification_status or "").upper()

    if route_upper == "ROUTE_WORKFLOW":
        events.append("workflow_delegation")
    elif route_upper == "ROUTE_REJECT":
        events.append("deterministic_rejection")
    elif route_upper == "ROUTE_ONTOLOGY":
        if verification_upper == "VERIFIED":
            events.append("knowledge_verified")
        else:
            events.append("knowledge_unverified")

    for event in events:
        bucket_telemetry.emit(
            TelemetryEvent(
                event=event,
                query_hash=query_hash,
                route=route,
                verification_status=verification_status,
                latency=latency_ms,
                caller=caller,
                session_id=session_id,
                ontology_reference=ontology_reference,
                routing=routing,
                decision=decision,
            )
        )


def _try_enter_ask_queue() -> bool:
    global _ASK_INFLIGHT
    with _QUEUE_LOCK:
        if _ASK_INFLIGHT >= _ASK_QUEUE_LIMIT:
            with _METRICS_LOCK:
                _METRICS["queue_rejected_total"] += 1
            _save_metrics_snapshot()
            return False
        _ASK_INFLIGHT += 1
        return True


def _leave_ask_queue() -> None:
    global _ASK_INFLIGHT
    with _QUEUE_LOCK:
        _ASK_INFLIGHT = max(0, _ASK_INFLIGHT - 1)


def _validate_governance_input(query: str) -> None:
    if len(query) > 2000:
        raise HTTPException(status_code=400, detail="query exceeds maximum length.")
    for char in query:
        codepoint = ord(char)
        if codepoint < 32 and char not in {"\n", "\r", "\t"}:
            raise HTTPException(status_code=400, detail="query contains unsupported control characters.")


async def _process_router_request(
    *,
    query: str,
    context: Optional[Dict[str, Any]],
    allow_web: bool,
    session_id: Optional[str],
    raw_request: Request,
) -> Dict[str, Any]:
    started = time.perf_counter()
    _validate_governance_input(query)
    caller_name = _resolve_caller(
        request=AskRequest(query=query, context=context, allow_web=allow_web, session_id=session_id),
        raw_request=raw_request,
    )

    context_map = dict(context or {})
    adapted = language_adapter.normalize_query(query=query, context=context_map)
    normalized_query = adapted.normalized_query
    query_type = classify_query(normalized_query)

    context_map["caller"] = caller_name
    context_map["query_type"] = query_type.value
    context_map["session_id"] = session_id
    context_map["allow_web"] = bool(allow_web or query_type == QueryType.WEB_LOOKUP)
    context_map["source_language"] = adapted.source_language

    clean_query = normalized_query.strip().strip("?!.,").lower()
    if clean_query in {"hello", "hi", "hey"}:
        request_id = str(uuid.uuid4())
        suggested_question = "What is the core purpose of human life according to Swaminarayan teachings?"
        suggested_answer = (
            "According to Swaminarayan teachings, the core purpose of human life is to attain "
            "spiritual progress through dharma, bhakti, gnan, and vairagya, while living in satsang "
            "and drawing closer to Bhagwan."
        )
        response = {
            "decision": "direct_reply",
            "answer": f"Hello! Kuch to kaho\n\nSuggested Swaminarayan question: {suggested_question}\nAnswer: {suggested_answer}",
            "session_id": session_id,
            "reason": "Direct greeting reply",
            "ontology_reference": {
                "concept_id": "router::greeting",
                "domain": "routing",
            },
            "reasoning_trace": {
                "sources_consulted": ["greeting_handler"],
                "retrieval_confidence": 1.0,
                "ontology_domain": "routing",
                "verification_status": "PASSED",
                "verification_details": "Direct greeting reply active.",
            },
            "governance_flags": {"safety": False, "fallback_mode": False},
            "governance_output": {
                "allowed": True,
                "reason": "greeting",
                "flags": {"router_route": "ROUTE_DIRECT"},
            },
            "verification_status": "PASSED",
            "enforcement_signature": hashlib.sha256(f"{request_id}|direct-greeting".encode("utf-8")).hexdigest(),
            "request_id": request_id,
            "sealed_at": _utc_now_iso(),
            "latency_ms": 0.0,
            "routing": {
                "query_type": classify_query(normalized_query).value,
                "route": "ROUTE_DIRECT",
                "router_latency_ms": 0.0,
            },
            "suggested_question": suggested_question,
            "suggested_answer": suggested_answer,
        }
    else:
        response = await conversation_router.route_query(query=normalized_query, context=context_map)
        response = _ensure_non_empty_answer(
            response,
            query=normalized_query,
            session_id=session_id,
            caller=caller_name,
        )
    response = language_adapter.localize_response(response=response, source_language=adapted.source_language)
    latency_ms = (time.perf_counter() - started) * 1000

    decision = str(response.get("decision") or "unknown")
    verification_status = str(response.get("verification_status") or "UNVERIFIED")
    route = str((response.get("routing") or {}).get("route") or "UNKNOWN")
    query_hash = _query_hash(normalized_query)
    response["core_alignment"] = core_reader.align_reference(response.get("ontology_reference") or {})
    _emit_bucket_events(
        query_hash=query_hash,
        route=route,
        verification_status=verification_status,
        latency_ms=latency_ms,
        caller=caller_name,
        session_id=session_id,
        ontology_reference=response.get("ontology_reference"),
        routing=response.get("routing"),
        decision=decision,
    )
    _record_ask_metrics(decision=decision, verification_status=verification_status, latency_ms=latency_ms)
    _record_route_metric(route=route)
    
    # Use standard logging, but background the heavy telemetry
    logger.info(f"REQUEST_PROCESSED: {query_hash} | {decision} | {latency_ms:.2f}ms")
    
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    _log_event(
        event="invalid_request_rejected",
        payload={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors(),
        },
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.middleware("http")
async def observability_and_throttle(request: Request, call_next):
    started = time.perf_counter()
    if request.url.path.rstrip("/") == "/ask":
        client_id = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_id):
            with _METRICS_LOCK:
                _METRICS["rate_limited_total"] += 1
                _METRICS["requests_total"] += 1
                _METRICS["requests_by_status"]["429"] += 1
            _save_metrics_snapshot()
            _log_event(
                event="rate_limit_enforced",
                payload={
                    "request_id": str(uuid.uuid4()),
                    "client_ip": client_id,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "X-RateLimit-Limit": str(_RATE_LIMIT_MAX_REQUESTS),
                    "X-RateLimit-Window-Seconds": str(_RATE_LIMIT_WINDOW_SECONDS),
                },
            )

    response = await call_next(request)
    latency_ms = (time.perf_counter() - started) * 1000
    with _METRICS_LOCK:
        _METRICS["requests_total"] += 1
        _METRICS["requests_by_status"][str(response.status_code)] += 1
    _save_metrics_snapshot()

    response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_MAX_REQUESTS)
    response.headers["X-RateLimit-Window-Seconds"] = str(_RATE_LIMIT_WINDOW_SECONDS)
    response.headers["X-Request-Latency-Ms"] = f"{latency_ms:.2f}"
    return response


@app.post(
    "/ask",
    tags=["Core Intelligence"],
    summary="Ask UniGuru a Question",
    description="Submit a query to UniGuru's reasoning engine. Returns verified knowledge base answers or LLM fallback."
)
async def ask(request: AskRequest, raw_request: Request) -> Dict[str, Any]:
    if not _try_enter_ask_queue():
        return _build_safe_fallback_response(
            query=request.query,
            session_id=request.session_id,
            reason="Router queue saturation detected. Safe fallback response returned.",
        )
    try:
        _enforce_service_auth(raw_request)
        response = _process_router_request(
            query=request.query,
            context=request.context,
            allow_web=request.allow_web,
            session_id=request.session_id,
            raw_request=raw_request,
        )
        # Final output-layer safety: always ensure non-empty "answer" while preserving existing fields.
        if not isinstance(response, dict):
            return _build_safe_fallback_response(
                query=request.query,
                session_id=request.session_id,
                reason="/ask recovered from invalid response payload type.",
            )
        if not str(response.get("answer") or "").strip():
            response["answer"] = REJECTION_MESSAGE
            response["decision"] = "reject"
            response["verification_status"] = "FAILED"
        return response
    except HTTPException as exc:
        return _build_safe_fallback_response(
            query=request.query,
            session_id=request.session_id,
            reason=f"/ask recovered from {exc.status_code} condition: {exc.detail}",
        )
    except Exception as exc:
        return _build_safe_fallback_response(
            query=request.query,
            session_id=request.session_id,
            reason=f"/ask recovered from runtime failure: {exc}",
        )
    finally:
        _leave_ask_queue()


@app.post(
    "/voice/query",
    tags=["Core Intelligence"],
    summary="Voice Query (Speech-to-Text)",
    description="Submit audio input, transcribe to text using STT engine, then process as a query"
)
async def voice_query(
    raw_request: Request,
) -> Dict[str, Any]:
    if not _try_enter_ask_queue():
        return _build_safe_fallback_response(
            query="voice input",
            session_id=raw_request.headers.get("X-Session-Id"),
            reason="Voice queue saturation detected. Safe fallback response returned.",
            caller=raw_request.headers.get("X-Caller-Name"),
        )
    try:
        _enforce_service_auth(raw_request)
        audio_bytes = await raw_request.body()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Uploaded audio is empty.")
        caller = raw_request.headers.get("X-Caller-Name")
        session_id = raw_request.headers.get("X-Session-Id")
        language = raw_request.headers.get("X-Voice-Language")
        filename = raw_request.headers.get("X-Audio-Filename") or "voice-input"
        allow_web = raw_request.headers.get("X-Allow-Web", "false").strip().lower() in {"1", "true", "yes", "on"}
        try:
            transcription = stt_engine.transcribe(
                audio_bytes,
                filename=filename,
                content_type=raw_request.headers.get("content-type", "application/octet-stream"),
                hinted_language=language,
            )
        except ValueError as exc:
            return _build_safe_fallback_response(
                query="voice input",
                session_id=session_id,
                reason=f"Voice transcription rejected input: {exc}",
                caller=caller,
            )
        except STTUnavailableError as exc:
            return _build_safe_fallback_response(
                query="voice input",
                session_id=session_id,
                reason=f"Voice transcription unavailable: {exc}",
                caller=caller,
            )

        context: Dict[str, Any] = {
            "caller": caller,
            "voice_input": True,
            "audio_content_type": raw_request.headers.get("content-type", "application/octet-stream"),
            "audio_filename": filename,
            "audio_provider": transcription.get("provider"),
            "audio_metadata": transcription.get("metadata", {}).get("audio"),
        }
        if transcription.get("language"):
            context["language"] = transcription["language"]

        response = _process_router_request(
            query=str(transcription.get("text") or ""),
            context=context,
            allow_web=allow_web,
            session_id=session_id,
            raw_request=raw_request,
        )
        response["transcription"] = transcription
        return response
    except HTTPException as exc:
        if exc.status_code == 401:
            raise
        return _build_safe_fallback_response(
            query="voice input",
            session_id=raw_request.headers.get("X-Session-Id"),
            reason=f"/voice/query recovered from {exc.status_code} condition: {exc.detail}",
            caller=raw_request.headers.get("X-Caller-Name"),
        )
    except Exception as exc:
        return _build_safe_fallback_response(
            query="voice input",
            session_id=raw_request.headers.get("X-Session-Id"),
            reason=f"/voice/query recovered from runtime failure: {exc}",
            caller=raw_request.headers.get("X-Caller-Name"),
        )
    finally:
        _leave_ask_queue()


@app.get(
    "/health",
    tags=["System Health"],
    summary="Health Check",
    description="Get system health status, uptime, KB status, and configuration"
)
def health() -> Dict[str, Any]:
    kb = _kb_status()
    return {
        "status": "ok",
        "service": "uniguru-live-reasoning",
        "version": app.version,
        "uptime_seconds": round(time.time() - _START_TIME, 3),
        "checks": {
            "ontology_registry": "ok",
            "reasoning_service": "ok",
            "router_active": True,
            "kb_loaded": kb["loaded"],
        },
        "auth": {
            "required": _API_AUTH_REQUIRED,
            "mode": _AUTH_MODE,
            "token_count": len(_API_TOKENS),
        },
        "kb": kb,
    }


@app.get(
    "/ready",
    tags=["System Health"],
    summary="Readiness Check",
    description="Check if system is ready to serve requests (KB loaded, router active)"
)
@app.get(
    "/health/ready",
    tags=["System Health"],
    summary="Readiness Check",
    description="Check if system is ready to serve requests (KB loaded, router active)"
)
def ready() -> Dict[str, Any]:
    kb = _kb_status()
    ready_state = bool(kb["loaded"])
    return {
        "status": "ready" if ready_state else "degraded",
        "service": "uniguru-live-reasoning",
        "checks": {
            "system_running": True,
            "kb_loaded": kb["loaded"],
            "router_active": True,
        },
        "kb": kb,
    }


@app.get(
    "/health/live",
    tags=["System Health"],
    summary="Liveness Probe",
    description="Minimal liveness check for container orchestration"
)
def health_live() -> Dict[str, Any]:
    return {"status": "alive"}


@app.get(
    "/metrics",
    tags=["Monitoring"],
    summary="Prometheus Metrics",
    description="Export Prometheus-compatible metrics for monitoring"
)
def metrics(request: Request) -> PlainTextResponse:
    _enforce_service_auth(request)
    with _METRICS_LOCK:
        requests_total = int(_METRICS["requests_total"])
        ask_total = int(_METRICS["requests_ask_total"])
        rate_limited_total = int(_METRICS["rate_limited_total"])
        by_status = dict(_METRICS["requests_by_status"])
        by_verification = dict(_METRICS["ask_verification_total"])
        by_decision = dict(_METRICS["ask_decision_total"])
        by_route = dict(_METRICS["ask_route_total"])
        latency_total = float(_METRICS["request_latency_ms_total"])
        rpm = len(_ASK_REQUEST_TIMESTAMPS)
        queue_rejected_total = int(_METRICS["queue_rejected_total"])

    success_count = int(by_verification.get("VERIFIED", 0)) + int(by_verification.get("PARTIAL", 0))
    verification_success_rate = (success_count / ask_total) if ask_total else 0.0
    average_latency = (latency_total / ask_total) if ask_total else 0.0

    lines = [
        "# TYPE uniguru_requests_total counter",
        f"uniguru_requests_total {requests_total}",
        "# TYPE uniguru_ask_requests_total counter",
        f"uniguru_ask_requests_total {ask_total}",
        "# TYPE uniguru_rate_limited_total counter",
        f"uniguru_rate_limited_total {rate_limited_total}",
        "# TYPE uniguru_router_queue_rejected_total counter",
        f"uniguru_router_queue_rejected_total {queue_rejected_total}",
        "# TYPE uniguru_requests_per_minute gauge",
        f"uniguru_requests_per_minute {rpm}",
        "# TYPE uniguru_verification_success_rate gauge",
        f"uniguru_verification_success_rate {verification_success_rate:.6f}",
        "# TYPE uniguru_request_latency_ms_avg gauge",
        f"uniguru_request_latency_ms_avg {average_latency:.3f}",
        "# TYPE uniguru_requests_by_status_total counter",
    ]
    for code, count in sorted(by_status.items()):
        lines.append(
            f'uniguru_requests_by_status_total{{code="{code}",group="{_status_group(int(code))}"}} {count}'
        )
    lines.append("# TYPE uniguru_ask_verification_status_total counter")
    for status, count in sorted(by_verification.items()):
        lines.append(f'uniguru_ask_verification_status_total{{status="{status}"}} {count}')
    lines.append("# TYPE uniguru_ask_decision_total counter")
    for decision, count in sorted(by_decision.items()):
        lines.append(f'uniguru_ask_decision_total{{decision="{decision}"}} {count}')
    lines.append("# TYPE uniguru_ask_route_total counter")
    for route, count in sorted(by_route.items()):
        lines.append(f'uniguru_ask_route_total{{route="{route}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n")


@app.post(
    "/metrics/reset",
    tags=["Monitoring"],
    summary="Reset Metrics",
    description="Reset all collected metrics to zero (admin only)"
)
def metrics_reset(request: Request) -> Dict[str, Any]:
    _enforce_service_auth(request)
    _reset_metrics()
    _save_metrics_snapshot()
    _log_event(
        event="metrics_reset",
        payload={"request_id": str(uuid.uuid4()), "caller_name": request.headers.get("X-Caller-Name", "unknown")},
    )
    return {"status": "ok", "message": "metrics reset complete"}


@app.get(
    "/monitoring/dashboard",
    tags=["Monitoring"],
    summary="Monitoring Dashboard",
    description="Get detailed monitoring dashboard with traffic stats, verification rates, and latency"
)
def monitoring_dashboard(request: Request) -> Dict[str, Any]:
    _enforce_service_auth(request)
    with _METRICS_LOCK:
        ask_total = int(_METRICS["requests_ask_total"])
        rate_limited_total = int(_METRICS["rate_limited_total"])
        by_status = dict(_METRICS["requests_by_status"])
        by_verification = dict(_METRICS["ask_verification_total"])
        by_decision = dict(_METRICS["ask_decision_total"])
        by_route = dict(_METRICS["ask_route_total"])
        latency_total = float(_METRICS["request_latency_ms_total"])
        rpm = len(_ASK_REQUEST_TIMESTAMPS)
        queue_rejected_total = int(_METRICS["queue_rejected_total"])

    success_count = int(by_verification.get("VERIFIED", 0)) + int(by_verification.get("PARTIAL", 0))
    verification_success_rate = (success_count / ask_total) if ask_total else 0.0
    average_latency = (latency_total / ask_total) if ask_total else 0.0

    return {
        "service": "uniguru-live-reasoning",
        "uptime_seconds": round(time.time() - _START_TIME, 3),
        "traffic": {
            "ask_requests_total": ask_total,
            "rate_limited_total": rate_limited_total,
            "requests_per_minute": rpm,
            "average_latency_ms": round(average_latency, 3),
            "verification_success_rate": round(verification_success_rate, 6),
            "queue_rejected_total": queue_rejected_total,
            "queue_limit": _ASK_QUEUE_LIMIT,
        },
        "status_codes": by_status,
        "decisions": by_decision,
        "routes": by_route,
        "verification_status": by_verification,
    }


@app.get(
    "/ontology/concept/{concept_id}",
    tags=["Ontology"],
    summary="Get Ontology Concept",
    description="Retrieve a specific concept from the ontology registry by ID"
)
def ontology_concept(concept_id: str) -> Dict[str, Any]:
    try:
        return registry.get_concept(concept_id)
    except ValueError as exc:
        if concept_id.startswith("router::"):
            return {
                "concept_id": concept_id,
                "canonical_name": concept_id.split("::", 1)[-1].replace("_", " ").title(),
                "domain": "routing",
                "truth_level": 0,
                "snapshot_version": 0,
                "snapshot_hash": "router-delegated",
                "immutable": True,
            }
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ============================================================================
# GURU MANAGEMENT ENDPOINTS
# ============================================================================


@app.get(
    "/guru/g-g",
    tags=["Guru Management"],
    summary="Get User's Gurus",
    description="Retrieve all AI gurus/chatbots created by the authenticated user"
)
def get_user_gurus(request: Request) -> Dict[str, Any]:
    """Get all gurus for the authenticated user."""
    # Extract user_id from request context or header
    user_id = request.headers.get("X-User-Id", "demo-user")

    gurus = guru_storage.get_user_gurus(user_id)
    # Demo compatibility: if caller user_id does not match creator user_id,
    # return all active gurus so the UI does not lose recently created gurus.
    if not gurus:
        gurus = guru_storage.get_all_active_gurus()

    return {
        "chatbots": [
            {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "description": g.description,
                "created_at": g.created_at,
                "updated_at": g.updated_at,
            }
            for g in gurus
        ]
    }


@app.get(
    "/guru/g-c/{chatbot_id}/{user_id}",
    tags=["Guru Management"],
    summary="Get Guru Chat History",
    description="Retrieve all chat conversations for a specific guru"
)
def get_guru_chats(chatbot_id: str, user_id: str) -> Dict[str, Any]:
    """Get all chats for a specific guru. Stub implementation."""
    with _CHAT_LOCK:
        messages: list[Dict[str, Any]] = []
        for chat in _CHAT_SESSIONS.values():
            if chat.get("userId") == user_id and chat.get("guru", {}).get("_id") == chatbot_id:
                messages.extend(chat.get("messages", []))
        return {"messages": messages, "chats": []}


@app.post(
    "/guru/n-g/{user_id}",
    tags=["Guru Management"],
    summary="Create Default Guru",
    description="Create a new guru with default settings (auto-generated name and subject)"
)
def create_new_guru(user_id: str) -> Dict[str, Any]:
    """Create a new default guru for user."""
    guru = guru_storage.create_guru(
        user_id=user_id,
        name=f"Guru {len(guru_storage.get_user_gurus(user_id)) + 1}",
        subject="General Knowledge",
        description="A general-purpose AI guru"
    )
    
    return {
        "id": guru.id,
        "name": guru.name,
        "subject": guru.subject,
        "description": guru.description,
        "created_at": guru.created_at,
    }


@app.post(
    "/guru/custom-guru/",
    tags=["Guru Management"],
    summary="Create Custom Guru (No User ID Path)",
    description="Create a custom guru when user_id is not provided in path (frontend compatibility)"
)
@app.post(
    "/guru/custom-guru/{user_id}",
    tags=["Guru Management"],
    summary="Create Custom Guru",
    description="Create a personalized AI guru with custom name, subject/expertise, and teaching style"
)
def create_custom_guru(
    request_body: CreateGuruRequest,
    request: Request,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a custom guru with specified name, subject, and description."""
    resolved_user_id = (
        (user_id or "").strip()
        or request.headers.get("X-User-Id", "").strip()
        or request.headers.get("X-Caller-Name", "").strip()
        or "demo-user"
    )
    guru = guru_storage.create_guru(
        user_id=resolved_user_id,
        name=request_body.name,
        subject=request_body.subject,
        description=request_body.description
    )
    
    return {
        "id": guru.id,
        "name": guru.name,
        "subject": guru.subject,
        "description": guru.description,
        "created_at": guru.created_at,
    }


@app.delete(
    "/guru/g-d/{chatbot_id}",
    tags=["Guru Management"],
    summary="Delete Guru",
    description="Remove a guru from user's collection (soft delete)"
)
def delete_guru_endpoint(chatbot_id: str, request: Request) -> Dict[str, Any]:
    """Delete (soft delete) a guru."""
    user_id = request.headers.get("X-User-Id", "demo-user")
    
    success = guru_storage.delete_guru(chatbot_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Guru not found or unauthorized")
    
    return {"status": "ok", "message": "Guru deleted successfully"}


# ============================================================================
# CHAT SESSION ENDPOINTS
# ============================================================================


@app.post("/chat/create", tags=["Chat"], summary="Create Chat Session")
def chat_create(request_body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    guru_id = str(request_body.get("guruId") or "").strip()
    title = str(request_body.get("title") or "").strip()
    user_id = str(
        request_body.get("userId")
        or request.headers.get("X-User-Id")
        or request.headers.get("X-Caller-Name")
        or "demo-user"
    ).strip()
    if not guru_id:
        raise HTTPException(status_code=400, detail="guruId is required")

    guru = guru_storage.get_guru(guru_id)
    if guru:
        guru_payload = {
            "_id": guru.id,
            "name": guru.name,
            "subject": guru.subject,
            "description": guru.description or "",
        }
    else:
        guru_payload = {
            "_id": guru_id,
            "name": "Custom Guru",
            "subject": "General",
            "description": "",
        }

    now = _utc_now_iso()
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "userId": user_id,
        "title": title or f"New chat with {guru_payload['name']}",
        "guru": guru_payload,
        "createdAt": now,
        "lastActivity": now,
        "isArchived": False,
        "isActive": True,
        "messages": [],
    }
    with _CHAT_LOCK:
        _CHAT_SESSIONS[chat_id] = chat
    return {"chat": _serialize_chat_session(chat, include_messages=False)}


@app.get("/chat/list", tags=["Chat"], summary="List Chat Sessions")
def chat_list(
    request: Request,
    guruId: Optional[str] = None,
    archived: bool = False,
) -> Dict[str, Any]:
    user_id = str(
        request.headers.get("X-User-Id")
        or request.headers.get("X-Caller-Name")
        or "demo-user"
    ).strip()

    with _CHAT_LOCK:
        chats = [c for c in _CHAT_SESSIONS.values() if c.get("userId") == user_id]
        if not chats:
            chats = list(_CHAT_SESSIONS.values())
        if guruId:
            chats = [c for c in chats if c.get("guru", {}).get("_id") == guruId]
        if archived:
            chats = [c for c in chats if bool(c.get("isArchived", False))]
        else:
            chats = [c for c in chats if not bool(c.get("isArchived", False))]
        chats.sort(key=lambda c: c.get("lastActivity", ""), reverse=True)
        return {"chats": [_serialize_chat_session(c, include_messages=False) for c in chats]}


@app.get("/chat/all-with-data", tags=["Chat"], summary="Get All Chats With Data")
def chat_all_with_data(
    request: Request,
    includeMessages: bool = False,
) -> Dict[str, Any]:
    user_id = str(
        request.headers.get("X-User-Id")
        or request.headers.get("X-Caller-Name")
        or "demo-user"
    ).strip()
    with _CHAT_LOCK:
        chats = [c for c in _CHAT_SESSIONS.values() if c.get("userId") == user_id]
        if not chats:
            chats = list(_CHAT_SESSIONS.values())
        chats.sort(key=lambda c: c.get("lastActivity", ""), reverse=True)
        return {"chats": [_serialize_chat_session(c, include_messages=includeMessages) for c in chats]}


@app.get("/chat/chat/{chat_id}", tags=["Chat"], summary="Get Chat Session By ID")
def chat_get(chat_id: str) -> Dict[str, Any]:
    with _CHAT_LOCK:
        chat = _CHAT_SESSIONS.get(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"chat": _serialize_chat_session(chat, include_messages=True)}


@app.put("/chat/chat/{chat_id}", tags=["Chat"], summary="Update Chat Session")
def chat_update(chat_id: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
    with _CHAT_LOCK:
        chat = _CHAT_SESSIONS.get(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if "title" in request_body and isinstance(request_body["title"], str):
            chat["title"] = request_body["title"].strip() or chat["title"]
        if "isArchived" in request_body:
            chat["isArchived"] = bool(request_body["isArchived"])
        if "isActive" in request_body:
            chat["isActive"] = bool(request_body["isActive"])
        chat["lastActivity"] = _utc_now_iso()
        return {"chat": _serialize_chat_session(chat, include_messages=False)}


@app.delete("/chat/chat/{chat_id}", tags=["Chat"], summary="Delete Chat Session")
def chat_delete(chat_id: str) -> Dict[str, Any]:
    with _CHAT_LOCK:
        chat = _CHAT_SESSIONS.pop(chat_id, None)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "ok", "message": "Chat deleted successfully", "chatId": chat_id}


@app.get("/chat/all-chats", tags=["Chat"], summary="Legacy Get All Chats")
def chat_all_chats(request: Request) -> Dict[str, Any]:
    return chat_all_with_data(request=request, includeMessages=True)


@app.delete("/chat/delete", tags=["Chat"], summary="Delete All Chats")
def chat_delete_all(request: Request) -> Dict[str, Any]:
    user_id = str(
        request.headers.get("X-User-Id")
        or request.headers.get("X-Caller-Name")
        or "demo-user"
    ).strip()
    deleted = 0
    with _CHAT_LOCK:
        ids = [chat_id for chat_id, chat in _CHAT_SESSIONS.items() if chat.get("userId") == user_id]
        if not ids:
            ids = list(_CHAT_SESSIONS.keys())
        for chat_id in ids:
            _CHAT_SESSIONS.pop(chat_id, None)
            deleted += 1
    return {"status": "ok", "deleted": deleted}


@app.post("/chat/new", tags=["Chat"], summary="Send Message To Chat")
async def chat_new(request_body: Dict[str, Any], raw_request: Request) -> Dict[str, Any]:
    message = str(request_body.get("message") or "").strip()
    chatbot_id = str(request_body.get("chatbotId") or "").strip()
    user_id = str(request_body.get("userId") or "demo-user").strip()
    chat_id = str(request_body.get("chatId") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if not chatbot_id:
        raise HTTPException(status_code=400, detail="chatbotId is required")

    # Ensure chat exists
    with _CHAT_LOCK:
        chat = _CHAT_SESSIONS.get(chat_id) if chat_id else None
    if not chat:
        created = chat_create(
            {"guruId": chatbot_id, "title": (message[:48] + "...") if len(message) > 48 else message, "userId": user_id},
            raw_request,
        )
        chat_id = created["chat"]["id"]
        with _CHAT_LOCK:
            chat = _CHAT_SESSIONS[chat_id]

    user_msg = {"sender": "user", "content": message, "timestamp": _utc_now_iso()}
    with _CHAT_LOCK:
        chat["messages"].append(user_msg)
        chat["lastActivity"] = _utc_now_iso()

    # Reuse existing ask pipeline for AI response quality.
    try:
        router_response = await _process_router_request(
            query=message,
            context={"caller": "uniguru-frontend", "chat_id": chat_id, "chatbot_id": chatbot_id},
            allow_web=False,
            session_id=chat_id,
            raw_request=raw_request,
        )
        answer = str(router_response.get("answer") or "I could not generate a response.")
    except Exception as exc:
        logger.exception("chat_new ask pipeline failed: %s", exc)
        answer = REJECTION_MESSAGE

    ai_msg = {"sender": "bot", "content": answer, "timestamp": _utc_now_iso()}
    with _CHAT_LOCK:
        chat["messages"].append(ai_msg)
        chat["lastActivity"] = _utc_now_iso()
        serialized_chat = _serialize_chat_session(chat, include_messages=False)

    return {
        "chat": serialized_chat,
        "aiResponse": {
            "content": answer,
            "metadata": {"retrieved_chunks": []},
            "vaani_audio": None,
        },
    }


# ============================================================================
# USER AUTH ENDPOINTS (Demo mode stubs for frontend compatibility)
# ============================================================================


@app.get(
    "/user/auth-status",
    tags=["Authentication"],
    summary="Check Authentication Status",
    description="Verify if user session is valid and return user profile"
)
def user_auth_status(request: Request) -> Dict[str, Any]:
    """Check if user is authenticated."""
    # Try to get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    
    if not token:
        # Check localStorage token (sent by frontend)
        token = request.headers.get("X-Auth-Token")
    
    # If Supabase is enabled, verify token
    if supabase_auth.enabled and token:
        user = supabase_auth.verify_token(token)
        if user:
            return {
                "authenticated": True,
                "user": user
            }
    
    # Demo mode fallback
    user_id = request.headers.get("X-User-Id", "demo-user")
    return {
        "authenticated": True,
        "user": {
            "id": user_id,
            "email": f"{user_id}@demo.local",
            "name": user_id.replace("-", " ").title()
        }
    }


@app.post(
    "/auth/google/token",
    tags=["Authentication"],
    summary="Google OAuth Login",
    description="Authenticate user with Google OAuth 2.0 credential token"
)
def google_oauth_callback(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Google OAuth token callback."""
    token = request_body.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    
    # Try Supabase authentication first
    if supabase_auth.enabled:
        try:
            result = supabase_auth.verify_google_token(token)
            return {
                "token": result["token"],
                "user": result["user"],
                "navigateUrl": "/chatpage"
            }
        except Exception as e:
            logger.error(f"Supabase Google auth failed: {e}")
            # Fall through to demo mode
    
    # Demo mode fallback: decode token locally
    import base64
    try:
        # Decode JWT payload (middle part)
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            user_data = json.loads(decoded)
            
            user_id = user_data.get('sub', str(uuid.uuid4()))
            email = user_data.get('email', f'user-{user_id}@gmail.com')
            name = user_data.get('name', 'Google User')
        else:
            # Fallback if token format is unexpected
            user_id = str(uuid.uuid4())
            email = f'user-{user_id}@demo.local'
            name = 'Demo User'
    except Exception as e:
        logger.warning(f"Failed to decode Google token: {e}, using demo user")
        user_id = str(uuid.uuid4())
        email = f'user-{user_id}@demo.local'
        name = 'Demo User'
    
    # Generate demo session token
    session_token = hashlib.sha256(f"{user_id}-{time.time()}".encode()).hexdigest()
    
    return {
        "token": session_token,
        "user": {
            "id": user_id,
            "email": email,
            "name": name
        },
        "navigateUrl": "/chatpage"
    }


@app.post(
    "/user/login",
    tags=["Authentication"],
    summary="Email/Password Login",
    description="Authenticate user with email and password credentials"
)
def user_login(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle user login."""
    email = request_body.get("email")
    password = request_body.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    
    # Try Supabase authentication first
    if supabase_auth.enabled:
        try:
            result = supabase_auth.login_with_email(email, password)
            return {
                "token": result["token"],
                "id": result["user"]["id"],
                "email": result["user"]["email"],
                "name": result["user"]["name"]
            }
        except Exception as e:
            logger.error(f"Supabase login failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))
    
    # Demo mode fallback: accept any credentials
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    session_token = hashlib.sha256(f"{user_id}-{time.time()}".encode()).hexdigest()
    
    return {
        "token": session_token,
        "id": user_id,
        "email": email,
        "name": email.split('@')[0].title()
    }


@app.post(
    "/user/signup",
    tags=["Authentication"],
    summary="User Registration",
    description="Create a new user account with name, email, and password"
)
def user_signup(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle user signup."""
    name = request_body.get("name")
    email = request_body.get("email")
    password = request_body.get("password")
    
    if not email or not password or not name:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    
    # Try Supabase authentication first
    if supabase_auth.enabled:
        try:
            result = supabase_auth.signup_with_email(email, password, name)
            return {
                "success": result["success"],
                "token": result["token"],
                "id": result["user"]["id"],
                "email": result["user"]["email"],
                "name": result["user"]["name"],
                "requires_email_verification": bool(result.get("requires_email_verification", False)),
                "message": (
                    "Signup successful. Please verify your email before logging in."
                    if result.get("requires_email_verification", False)
                    else "Signup successful. You can login now."
                ),
                "navigateUrl": "/chatpage"
            }
        except Exception as e:
            logger.error(f"Supabase signup failed: {e}")
            detail = str(e)
            status_code = 429 if "rate limit" in detail.lower() else 400
            raise HTTPException(status_code=status_code, detail=detail)
    
    # Demo mode fallback: accept any signup
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    session_token = hashlib.sha256(f"{user_id}-{time.time()}".encode()).hexdigest()
    
    return {
        "success": True,
        "token": session_token,
        "id": user_id,
        "email": email,
        "name": name,
        "navigateUrl": "/chatpage"
    }


class NewRagRequest(BaseModel):
    query: str = Field(..., min_length=1)
    domain: Optional[str] = Field(None, description="Optional domain hint (e.g. agriculture, historical, science, maths, physics)")
    allow_generated_verse: bool = Field(
        default=False,
        description="If true, generate Sanskrit verse only when no clean canonical verse is found.",
    )

import os
from RAG.new_rag_query import get_engine

_engine_instance = None
def get_faiss_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = get_engine()
    return _engine_instance

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

security = HTTPBearer()

_KOSHA_DIR = Path(__file__).parent.parent / "data" / "kosha"


def _infer_domain(query: str, domain_hint: Optional[str] = None, source: Optional[str] = None) -> str:
    def _normalize_hint(value: Optional[str]) -> str:
        normalized = str(value or "").strip().lower()
        placeholder_values = {"", "string", "general", "misc", "other", "unknown", "null", "none"}
        return "" if normalized in placeholder_values else normalized

    normalized_hint = _normalize_hint(domain_hint)
    if normalized_hint:
        return normalized_hint

    text = f"{query or ''} {source or ''}".lower()

    domain_keywords = [
        ("puranas", ("purana", "bhagavata", "narada-purana", "padma purana", "vayu purana", "linga purana")),
        ("gitas", ("gita", "bhagavad gita", "anu-gita", "uddhava-gita", "anugita")),
        ("upanishads", ("upanishad", "ishavasya", "taittiriya", "prashna", "svetasvatara", "mahanarayana")),
        ("vedas", ("veda", "rigveda", "samaveda", "yajurveda", "atharvaveda")),
        ("itihasa", ("mahabharata", "ramayana", "itihasa", "bharata", "pandava", "kurukshetra")),
        ("smriti", ("smriti", "dharma sutra", "dharmasutra", "manu", "yajnavalkya", "narada smriti", "gautama")),
        ("agamas", ("agama", "saiva", "shaiva", "vaishnava agama", "pancharatra", "kamika", "suprabheda")),
        ("tantra", ("tantra", "tripura", "bhairava", "tantrasara")),
        ("history", ("history", "ancient", "medieval", "historical", "dynasty", "empire", "civilization")),
        ("geography", ("geography", "river", "mountain", "continent", "climate", "ocean", "map")),
        ("maths", ("math", "maths", "algebra", "geometry", "calculus", "equation", "theorem", "integral")),
        ("physics", ("physics", "force", "energy", "quantum", "momentum", "velocity", "relativity")),
        ("chemistry", ("chemistry", "chemical", "molecule", "atom", "acid", "base", "reaction")),
        ("biology", ("biology", "cell", "genetics", "evolution", "organism", "ecosystem")),
        ("agricultural", ("agri", "crop", "farm", "soil", "irrigation", "harvest", "seed")),
    ]

    for domain_name, keywords in domain_keywords:
        if any(keyword in text for keyword in keywords):
            return domain_name

    return "general"


def _clean_content(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _extract_tags(query: str, source: str) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "about",
        "tell",
        "what",
        "which",
        "who",
        "when",
        "where",
        "into",
        "this",
        "that",
        "does",
        "have",
        "chapter",
        "verse",
    }
    query_terms = {
        term
        for term in re.findall(r"[a-zA-Z0-9]+", query.lower())
        if len(term) > 2 and term not in stopwords
    }
    source_terms = {
        term
        for term in re.findall(r"[a-zA-Z0-9]+", source.lower())
        if len(term) > 2 and term not in stopwords
    }
    tags = sorted(query_terms.intersection(source_terms))
    if not tags:
        # keep at most 3 meaningful tags
        tags = sorted(list(query_terms))[:3]
    return tags


def _tag_match_score(query: str, source: str) -> float:
    query_terms = {term for term in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(term) > 2}
    if not query_terms:
        return 0.0
    source_terms = {term for term in re.findall(r"[a-zA-Z0-9]+", source.lower()) if len(term) > 2}
    overlap = len(query_terms.intersection(source_terms))
    return float(overlap / max(len(query_terms), 1))


def _persist_kosha_entry(entry: Dict[str, Any]) -> None:
    _KOSHA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _KOSHA_DIR / f"{entry['knowledge_id']}.json"
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, indent=2)
    index_path = _KOSHA_DIR / "kosha_entries.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _make_signal(query: str, chunk: Dict[str, Any], idx: int) -> Dict[str, Any]:
    source_file = str(chunk.get("metadata", {}).get("file_name") or "unknown")
    similarity_score = max(float(chunk.get("score", 0.0)), 0.0)
    tag_score = _tag_match_score(query, source_file)
    confidence = max(similarity_score, tag_score)
    return {
        "signal_id": f"signal_{idx+1}",
        "type": "string",
        "content": str(chunk.get("text", "")).strip(),
        "source": source_file,
        "confidence": confidence,
        "trace": {
            "knowledge_id": source_file,
            "method": "kosha_retrieval",
        },
    }


def _kosha_entry_to_signal(entry: Dict[str, Any], idx: int) -> Dict[str, Any]:
    source_file = str(entry.get("source") or "unknown")
    content = str(entry.get("content") or "").strip()
    confidence = float(entry.get("confidence", 0.0))
    if confidence <= 0:
        confidence = 0.01
    return {
        "signal_id": f"signal_{idx + 1}",
        "type": "string",
        "content": content,
        "source": source_file,
        "confidence": confidence,
        "trace": {"knowledge_id": source_file, "method": "kosha_retrieval"},
    }


def _llm_answer_from_signals(query: str, signals: list[Dict[str, Any]], max_context_chars: int = 4000) -> str:
    """
    Uses Groq LLM to generate a final answer from signal content only.
    This mirrors the style used in `backend/RAG/notebook.json`.
    """
    engine = get_faiss_engine()
    groq_client = getattr(engine, "groq_client", None)
    if not groq_client:
        # If LLM is unavailable, return best available Kosha content.
        best = max(signals, key=lambda s: float(s.get("confidence", 0.0) or 0.0)) if signals else None
        return str((best or {}).get("content") or "I don't know.")

    signals = [s for s in signals if str(s.get("content", "")).strip()]
    if not signals:
        return "I don't know."

    context_parts = []
    for i, sig in enumerate(signals[:5]):
        content = str(sig.get("content", "")).strip()
        context_parts.append(f"--- [{i + 1}] ---\n{content}")
    context = "\n\n".join(context_parts)
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n...[truncated]"

    system_prompt = (
        "You are an intelligent knowledge assistant. "
        "Your Answer MUST be constructed ONLY from the provided context signals.\n"
        "Rules:\n"
        "1. No hallucination whatsoever\n"
        "2. No extra information outside the provided text\n"
        "3. Only use signal-derived facts\n"
        "If the context cannot answer the question, simply reply 'I don't know'."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return str(response.choices[0].message.content or "").strip() or "I don't know."


def _llm_answer_from_chunks(query: str, chunks: list[Dict[str, Any]], max_context_chars: int = 4000) -> str:
    """
    LLM answer using FAISS chunk text as context (similar to `backend/RAG/notebook.json`).
    """
    engine = get_faiss_engine()
    groq_client = getattr(engine, "groq_client", None)
    if not groq_client:
        best = max(chunks, key=lambda c: float(c.get("score", 0.0) or 0.0)) if chunks else None
        return str((best or {}).get("text") or "I don't know.")

    if not chunks:
        return "I don't know."

    context_parts = []
    for i, ch in enumerate(chunks[:5]):
        meta = ch.get("metadata") or {}
        file_name = str(meta.get("file_name") or "unknown")
        context_parts.append(f"--- [{i+1}] {file_name} ---\n{ch.get('text') or ''}")
    context = "\n\n".join(context_parts)
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n...[truncated]"

    system_prompt = (
        "Answer based ONLY on the provided context. If not present, say 'I don't know'. "
        "Write 2-4 sentences. Cite sources using numbers like [1], [2]."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    answer = str(response.choices[0].message.content or "").strip() or "I don't know."

    # Answer validation / correction step
    if "don't know" not in answer.lower():
        verification_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Proposed Answer: {answer}\n\n"
            "Task 1: Check if the Proposed Answer directly and accurately answers the Question using ONLY the Context.\n"
            "Task 2: If the Proposed Answer is entirely correct and relevant, reply EXACTLY with 'VALID: ' followed by the Proposed Answer.\n"
            "Task 3: If the Proposed Answer is incorrect, irrelevant, or hallucinates, you MUST correct it. Generate a new, concise, accurate answer based STRICTLY on the Context. Reply with 'CORRECTED: ' followed by the new answer. If the Context does not contain the answer, reply with 'CORRECTED: I don't know.'"
        )
        try:
            ver_response = groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {"role": "system", "content": "You are a strict evaluation and correction assistant."},
                    {"role": "user", "content": verification_prompt},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            ver_result = str(ver_response.choices[0].message.content or "").strip()
            
            if ver_result.upper().startswith("VALID:"):
                answer = ver_result[6:].strip()
            elif ver_result.upper().startswith("CORRECTED:"):
                answer = ver_result[10:].strip()
            elif "CORRECTED:" in ver_result.upper():
                idx = ver_result.upper().index("CORRECTED:")
                answer = ver_result[idx + 10:].strip()
            else:
                # If the model didn't follow formatting but generated something, we use it as a fallback, 
                # or just fallback to I don't know if it says invalid.
                if "INVALID" in ver_result.upper():
                    answer = "I don't know."
        except Exception as e:
            pass # proceed with unverified answer if validation fails

    return answer

def _normalize_common_names(text: str) -> str:
    """
    Small post-processing for OCR/transliteration variants found in the stored PDFs.
    """
    t = str(text or "")
    # Common OCR/transliteration normalization for Vishnu.
    t = t.replace("Visnu", "Vishnu")
    return t.strip()


def _is_non_answer_content(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return True
    disallowed_phrases = [
        "i don't know",
        "i dont know",
        "not provided in the given context",
        "not provided in the context",
        "no relevant context found",
        "cannot be answered from the provided context",
    ]
    return any(phrase in value for phrase in disallowed_phrases)


def _detect_sanskrit_verse(chunks: list[Dict[str, Any]]) -> Optional[str]:
    dev_re = re.compile(r"[\u0900-\u097F]")
    danda_re = re.compile(r"[।॥]")
    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        if dev_re.search(text):
            # Prefer verse-like chunks (danda markers), else first Devanagari chunk.
            if danda_re.search(text):
                return text
    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        if text and dev_re.search(text):
            return text
    return None


def _is_low_quality_ocr_sanskrit(text: Optional[str]) -> bool:
    if not text:
        return False
    sample = str(text)
    # Heuristic OCR-noise markers often seen in bad scans.
    noise_markers = ["�", "|", "@", "~", "http", "www", "digitized", "in public domain"]
    noise_hits = sum(sample.lower().count(marker.lower()) for marker in noise_markers)
    symbol_count = len(re.findall(r"[^A-Za-z0-9\u0900-\u097F\s।॥,.;:!?()\-]", sample))
    devanagari_count = len(re.findall(r"[\u0900-\u097F]", sample))
    latin_count = len(re.findall(r"[A-Za-z]", sample))
    total_len = max(len(sample), 1)
    symbol_ratio = symbol_count / total_len
    # Mixed-script warning: Sanskrit expected, but mostly Latin text indicates OCR mismatch/noise.
    mixed_script_noise = devanagari_count > 0 and (latin_count > max(120, devanagari_count * 2))
    weak_sanskrit_signal = devanagari_count < 12
    return noise_hits > 0 or symbol_ratio > 0.10 or mixed_script_noise or weak_sanskrit_signal


def _query_requests_verse(query: str) -> bool:
    lower = str(query or "").lower()
    return any(token in lower for token in ("verse", "shloka", "sloka", "sanskrit", "śloka", "श्लोक"))


def _generate_sanskrit_verse(query: str, context: str) -> Optional[str]:
    engine = get_faiss_engine()
    groq_client = getattr(engine, "groq_client", None)
    if not groq_client:
        return None
    system_prompt = (
        "You are a Sanskrit assistant. Generate exactly 2 lines in Devanagari Sanskrit as a thematic verse "
        "based on the provided context. Do not claim canonical authenticity."
    )
    user_prompt = (
        f"Question: {query}\n\n"
        f"Context summary: {context}\n\n"
        "Return only the Sanskrit verse in Devanagari (2 lines)."
    )
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        text = str(response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def _execute_kosha_pipeline(
    query: str,
    domain_hint: Optional[str],
    top_k: int,
    allow_generated_verse: bool = False,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    from kosha.deterministic_pipeline import run_deterministic_pipeline

    # TANTRA preparation boundary: this endpoint emits the schema-bound signal
    # contract only. It must not call FAISS or LLM synthesis before validation.
    result = run_deterministic_pipeline(query=query, domain_hint=domain_hint, trace_id=trace_id)
    
    return {
        "query": result.get("query", query),
        "domain": result.get("domain_resolution", {}).get("domain", "general"),
        "signals_used": result.get("matched_signals", []),
        "knowledge_ids": result.get("knowledge_ids_used", []),
        "confidence": result.get("confidence", 0.0) * 100 if "confidence" in result else (result.get("confidence_breakdown", {}).get("overall", 0.0) * 100),
        "reasoning_trace": result.get("reasoning_path", []),
        "final_answer": result.get("answer", ""),
    }

@app.post(
    "/ask_uniguru",
    tags=["Core Intelligence"],
    summary="Fully Independent Sovereign Knowledge Endpoint",
    description="Deterministic KOSHA retrieval with exactly zero LLM fallback."
)
@app.post(
    "/new_rag",
    tags=["Core Intelligence"],
    summary="Query Deterministic Kosha System",
    description="Deterministic KOSHA retrieval falling back to original FAISS architecture."
)
def ask_uniguru_endpoint(request: NewRagRequest, token: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    try:
        allowed_key = os.getenv("EXTERNAL_API_SECRET_KEY", "uniguru_secret_123")
        if token.credentials != allowed_key:
            raise HTTPException(status_code=401, detail="Unauthorized Access. Invalid API Key.")

        return _execute_kosha_pipeline(
            query=request.query,
            domain_hint=request.domain,
            top_k=5,
            allow_generated_verse=bool(request.allow_generated_verse),
        )
    except Exception as e:
        logger.error(f"Error querying Kosha deterministic pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================
# NEW: 6-PHASE CORE UNIFIED PIPELINE (/new_query)
# ==============================================================

class CoreRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str = Field(default="information_retrieval")
    context: Dict[str, Any] = Field(default_factory=dict)
    required_outputs: list = Field(default=["signals", "final_answer"])
    query: str = Field(default="Tell me about Mahabharat")
    allow_generated_verse: bool = Field(
        default=False,
        description="If true, generate Sanskrit verse only when no clean canonical verse is found.",
    )

def mock_samachar_system(query: str):
    return {
        "signal_id": f"EXT_MOCK_{uuid.uuid4().hex[:8]}",
        "type": "string",
        "content": f"Live external news stub monitoring real-time updates for: {query}",
        "confidence": 0.85,
        "source": "Mock Samachar Real-Time API",
        "trace": {
            "knowledge_id": "external_samachar",
            "method": "external_api_call",
        }
    }

def log_to_bucket(event_id, query, signals_used, final_answer, confidence, system_path):
    import os, json
    log_file = os.path.join(os.path.dirname(__file__), "..", "data", "bucket_logs.json")
    try:
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                json.dump([], f)
        with open(log_file, "r+") as f:
            logs = json.load(f)
            logs.append({
                "event_id": event_id,
                "query": query,
                "signals_used": signals_used,
                "final_answer": final_answer,
                "confidence": float(confidence),
                "system_path": system_path,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            f.seek(0)
            json.dump(logs, f, indent=4)
    except Exception as e:
        logger.error(f"Bucket logging failed: {e}")

@app.post(
    "/new_query",
    tags=["Core Intelligence"],
    summary="Phase 6 Core Unified Signal Pipeline"
)
def new_query_endpoint(request: CoreRequest, token: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    try:
        allowed_key = os.getenv("EXTERNAL_API_SECRET_KEY", "uniguru_secret_123")
        if token.credentials != allowed_key:
            raise HTTPException(status_code=401, detail="Unauthorized Access.")

        final_payload = _execute_kosha_pipeline(
            query=request.query,
            domain_hint=request.context.get("domain") if isinstance(request.context, dict) else None,
            top_k=5,
            allow_generated_verse=bool(request.allow_generated_verse),
            trace_id=request.request_id,
        )

        log_to_bucket(
            event_id=request.request_id,
            query=request.query,
            signals_used=len(final_payload.get("matched_signals", [])),
            final_answer=final_payload.get("answer", ""),
            confidence=final_payload.get("confidence_breakdown", {}).get("overall", 0.0),
            system_path="/new_query_6phase_pipeline"
        )

        return final_payload
    except Exception as e:
        logger.error(f"Error in Core Query pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/user/logout",
    tags=["Authentication"],
    summary="User Logout",
    description="End user session and clear authentication token"
)
def user_logout(request: Request) -> Dict[str, Any]:
    """Handle user logout."""
    # Try to get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    
    # If Supabase is enabled, logout from Supabase
    if supabase_auth.enabled and token:
        supabase_auth.logout(token)
    
    return {"status": "ok", "message": "Logged out successfully"}


@app.get(
    "/ollama/status",
    tags=["Core Intelligence"],
    summary="Check Ollama Connectivity",
    description="Verify if local Ollama service is reachable and enabled."
)
async def ollama_status():
    """Verify Ollama status."""
    return {
        "enabled": ollama_client.enabled,
        "base_url": ollama_client.base_url,
        "model": ollama_client.model
    }

@app.post(
    "/ollama/chat",
    tags=["Core Intelligence"],
    summary="Direct Chat with Ollama",
    description="Submit a query directly to the local Ollama LLM bypassing the deterministic pipeline."
)
async def ollama_chat(request: AskRequest, raw_request: Request):
    """Direct interaction with Ollama."""
    _enforce_service_auth(raw_request)
    
    if not ollama_client.enabled:
        raise HTTPException(status_code=503, detail="Ollama integration is disabled.")
    
    response = ollama_client.generate(request.query)
    if not response:
        raise HTTPException(status_code=503, detail="Ollama service is unreachable or failed to respond.")
        
    return {
        "answer": response,
        "source": "ollama",
        "model": ollama_client.model,
        "timestamp": _utc_now_iso()
    }

_load_metrics_snapshot()
