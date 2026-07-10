from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from .contracts import CompanionMessageRequest
from .runtime import CompanionRuntime
from .utils import utc_now


class FrontendChatRequest(BaseModel):
    """Compatibility contract used by the Mitra command-center frontend."""

    model_config = ConfigDict(extra="allow")

    user_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    platform: str = "web"
    session_id: str | None = Field(default=None, min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=200)
    product_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{2,63}$")
    capability_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{2,63}$")
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_dispatch: bool = True


class FrontendWorkflowRequest(BaseModel):
    """Legacy workflow request shape from the command-center frontend."""

    model_config = ConfigDict(extra="allow")

    workflow_name: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    platform: str = "web"
    session_id: str | None = Field(default=None, min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=200)
    product_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{2,63}$")
    capability_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{2,63}$")
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


ClientType = Literal["standalone", "embedded", "mobile", "xr", "robotics"]


def create_frontend_connector_router(
    companion: CompanionRuntime,
) -> APIRouter:
    router = APIRouter(tags=["Frontend Connector"])

    @router.post("/api/companion/chat")
    async def frontend_chat(request: FrontendChatRequest) -> dict[str, Any]:
        result = await companion.companion_message(
            _to_companion_request(request)
        )
        return _chat_response(result)

    @router.get("/api/companion/greeting/{user_id}")
    async def frontend_greeting(user_id: str) -> dict[str, Any]:
        latest = _latest_session_for_user(companion, user_id)
        memory = _memory_payload(companion, user_id, latest)
        counts = companion.status()["counts"]
        if counts["attachments"] > 0:
            greeting = (
                f"Hi {memory['facts'].get('name', user_id)}. Mitra is ready "
                "to route your request through the attached BHIV runtimes."
            )
        else:
            greeting = (
                f"Hi {memory['facts'].get('name', user_id)}. Mitra is online, "
                "but no production BHIV runtime is attached yet."
            )
        return {
            "greeting": greeting,
            "user_id": user_id,
            "session_id": latest.get("session_id") if latest else None,
            "runtime": _runtime_summary(companion),
            "connector": _connector_summary(),
        }

    @router.get("/api/companion/memory/{user_id}")
    async def frontend_memory(
        user_id: str,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        latest = _latest_session_for_user(companion, user_id)
        return _memory_payload(companion, user_id, latest, limit=limit)

    @router.get("/api/companion/capabilities")
    async def frontend_capabilities(
        available_only: bool = False,
    ) -> dict[str, Any]:
        return {
            "capabilities": _frontend_capabilities(
                companion,
                available_only=available_only,
            ),
            "attachments": companion.attachments.list(),
            "runtime": _runtime_summary(companion),
            "connector": _connector_summary(),
        }

    @router.post("/api/workflow/run")
    async def frontend_workflow(
        request: FrontendWorkflowRequest,
    ) -> dict[str, Any]:
        chat_request = FrontendChatRequest(
            user_id=request.user_id,
            message=request.message or _workflow_message(request.workflow_name),
            platform=request.platform,
            session_id=request.session_id,
            workspace_id=request.workspace_id,
            product_id=request.product_id,
            capability_id=request.capability_id,
            payload={
                "workflow_name": request.workflow_name,
                **request.payload,
            },
            metadata={
                **request.metadata,
                "frontend_workflow_name": request.workflow_name,
                "frontend_route": "/api/workflow/run",
            },
        )
        result = await companion.companion_message(
            _to_companion_request(chat_request)
        )
        return {
            "workflow_name": request.workflow_name,
            "status": result["status"],
            "session_id": result["session"]["session_id"],
            "message": result["message"]["content"],
            "result": _chat_response(result),
            "connector": _connector_summary(),
        }

    return router


def _to_companion_request(
    request: FrontendChatRequest,
) -> CompanionMessageRequest:
    metadata = {
        **request.metadata,
        "frontend_connector": "mitra-command-center",
        "frontend_route": "/api/companion/chat",
        "frontend_platform": request.platform,
    }
    if request.model_extra:
        metadata["frontend_extra"] = dict(request.model_extra)
    return CompanionMessageRequest(
        session_id=request.session_id,
        actor_id=request.user_id,
        client_type=_client_type(request.platform),
        workspace_id=request.workspace_id or f"frontend:{request.user_id}",
        product_id=request.product_id,
        capability_id=request.capability_id,
        message=request.message,
        payload=request.payload,
        auto_dispatch=request.auto_dispatch,
        allow_ai_fallback=True,
        metadata=metadata,
    )


def _chat_response(result: dict[str, Any]) -> dict[str, Any]:
    dispatch = result.get("dispatch") or {}
    session = result["session"]
    return {
        "message": result["message"]["content"],
        "capability_result": _capability_result(result),
        "session_id": session["session_id"],
        "intent": _intent_id(result),
        "suggested_actions": _suggested_actions(result),
        "status": result["status"],
        "mitra_runtime": {
            "connector": _connector_summary(),
            "session": session,
            "analysis": result.get("analysis"),
            "selection": result.get("selection"),
            "capability_plan": result.get("capability_plan"),
            "dispatch_id": dispatch.get("dispatch_id"),
            "task_id": (result.get("task") or {}).get("task_id"),
            "trace_endpoints": _trace_endpoints(dispatch),
            "recorded_at": utc_now(),
        },
    }


def _capability_result(result: dict[str, Any]) -> dict[str, Any] | None:
    selection = result.get("selection") or {}
    candidate = selection.get("candidate") or {}
    dispatch = result.get("dispatch") or {}
    if not candidate and not dispatch:
        return None
    status = result.get("status")
    frontend_status = (
        "success"
        if status == "COMPLETED"
        else "pending"
        if status in {"RUNNING", "SELECTED", "NEEDS_CLARIFICATION"}
        else "error"
    )
    return {
        "capability": candidate.get("capability_id")
        or dispatch.get("capability_id"),
        "intent": candidate.get("intent_id") or dispatch.get("intent_id"),
        "status": frontend_status,
        "summary": result["message"]["content"],
        "data": {
            "product_id": candidate.get("product_id")
            or dispatch.get("product_id"),
            "payload": result.get("payload"),
            "dispatch": dispatch or None,
            "route": result.get("route"),
            "task": result.get("task"),
            "runtime_status": status,
            "trace_endpoints": _trace_endpoints(dispatch),
        },
    }


def _intent_id(result: dict[str, Any]) -> str | None:
    selection = result.get("selection") or {}
    candidate = selection.get("candidate") or {}
    dispatch = result.get("dispatch") or {}
    analysis = result.get("analysis") or {}
    recommended = analysis.get("recommended_candidate") or {}
    return (
        candidate.get("intent_id")
        or dispatch.get("intent_id")
        or recommended.get("intent_id")
    )


def _suggested_actions(result: dict[str, Any]) -> list[str]:
    memory = result.get("memory") or {}
    clarification = memory.get("open_clarification") or []
    if clarification:
        return [item["prompt"] for item in clarification if item.get("prompt")]
    dispatch = result.get("dispatch") or {}
    if dispatch.get("dispatch_id"):
        return [
            "Inspect dispatch reconstruction",
            "Review runtime telemetry",
            "Check Central Depository export",
        ]
    if result.get("status") == "UNAVAILABLE":
        return ["Check attached runtime health", "Retry after recovery"]
    return ["Attach a BHIV runtime", "Check capability catalog"]


def _trace_endpoints(dispatch: dict[str, Any]) -> dict[str, str | None]:
    dispatch_id = dispatch.get("dispatch_id")
    if not dispatch_id:
        return {
            "dispatch": None,
            "phases": None,
            "proof": None,
            "reconstruction": None,
            "telemetry": "/api/v1/runtime/telemetry",
            "depository": "/api/v1/runtime/depository",
        }
    return {
        "dispatch": f"/api/v1/dispatches/{dispatch_id}",
        "phases": f"/api/v1/dispatches/{dispatch_id}/phases",
        "proof": f"/api/v1/dispatches/{dispatch_id}/proof",
        "reconstruction": f"/api/v1/dispatches/{dispatch_id}/reconstruction",
        "telemetry": "/api/v1/runtime/telemetry",
        "depository": (
            "/api/v1/runtime/depository"
            f"?subject_type=dispatch&subject_id={dispatch_id}"
        ),
    }


def _frontend_capabilities(
    companion: CompanionRuntime,
    *,
    available_only: bool,
) -> list[dict[str, Any]]:
    intents = companion.router.discover(available_only=available_only)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for intent in intents:
        key = (intent["product_id"], intent["capability_id"])
        grouped.setdefault(key, []).append(
            {
                "intent_id": intent["intent_id"],
                "description": intent["description"],
                "input_schema": intent["input_schema"],
                "response_schema": intent["response_schema"],
                "dispatch": intent["dispatch"],
            }
        )
    capabilities = []
    for capability in companion.router.capabilities(
        available_only=available_only,
    ):
        key = (capability["product_id"], capability["capability_id"])
        capabilities.append(
            {
                **capability,
                "capability": capability["capability_id"],
                "name": capability["capability_id"],
                "status": (
                    "available"
                    if capability["attachment_state"] == "ATTACHED"
                    else "degraded"
                ),
                "intents": grouped.get(key, []),
            }
        )
    return capabilities


def _latest_session_for_user(
    companion: CompanionRuntime,
    user_id: str,
) -> dict[str, Any] | None:
    sessions = companion.store.list_sessions(limit=200)
    preferred = [
        item
        for item in sessions
        if item.get("actor_id") == user_id
        and item.get("state") != "CLOSED"
        and (item.get("metadata") or {}).get("frontend_connector")
        == "mitra-command-center"
    ]
    if preferred:
        return preferred[0]
    for item in sessions:
        if item.get("actor_id") == user_id and item.get("state") != "CLOSED":
            return item
    return None


def _memory_payload(
    companion: CompanionRuntime,
    user_id: str,
    latest: dict[str, Any] | None,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    if latest is None:
        return {
            "facts": {"name": user_id},
            "user_id": user_id,
            "session_id": None,
            "summary": {},
            "messages": [],
            "tasks": [],
            "runtime": _runtime_summary(companion),
            "connector": _connector_summary(),
        }
    memory = companion.companion_memory(
        latest["session_id"],
        limit=limit,
    )
    summary = memory.get("summary") or {}
    facts = {
        "name": (
            (summary.get("companion_profile") or {})
            .get("identity_continuity", {})
            .get("actor_id")
            or user_id
        ),
        "last_status": summary.get("last_status"),
        "slots": summary.get("slots") or {},
        "last_outcome": summary.get("last_outcome") or {},
        "open_clarification": summary.get("open_clarification") or [],
        "companion_profile": summary.get("companion_profile") or {},
    }
    return {
        "facts": facts,
        "user_id": user_id,
        "session_id": latest["session_id"],
        "summary": summary,
        "messages": memory.get("messages") or [],
        "tasks": memory.get("tasks") or [],
        "runtime": _runtime_summary(companion),
        "connector": _connector_summary(),
    }


def _workflow_message(workflow_name: str) -> str:
    normalized = workflow_name.strip().replace("_", " ").replace("-", " ")
    return f"Run workflow: {normalized}"


def _client_type(platform: str) -> ClientType:
    normalized = platform.strip().lower()
    if normalized in {"mobile", "android", "ios", "ipad"}:
        return "mobile"
    if normalized in {"xr", "vr", "ar"}:
        return "xr"
    if normalized in {"robot", "robotics"}:
        return "robotics"
    if normalized == "embedded":
        return "embedded"
    return "standalone"


def _runtime_summary(companion: CompanionRuntime) -> dict[str, Any]:
    status = companion.status()
    return {
        "runtime_instance_id": status["runtime_instance_id"],
        "state": status["state"],
        "accepting": status["accepting"],
        "counts": status["counts"],
        "attached_products": status["attached_products"],
    }


def _connector_summary() -> dict[str, str]:
    return {
        "name": "mitra-frontend-compatibility-connector",
        "contract": "command-center-frontend-v1",
        "target": "mitra-companion-runtime-v1",
    }
