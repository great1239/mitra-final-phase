from __future__ import annotations

import json
from contextlib import asynccontextmanager
from html import escape
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from .config import RuntimeSettings
from .constants import ContextScope, RuntimeState
from .contracts import (
    AttachmentRequest,
    ContextTransferRequest,
    ContextUpdateRequest,
    IntentDispatchRequest,
    SessionCreateRequest,
    SessionResumeRequest,
    VersionedContract,
    validate_contract,
    versioned_response,
)
from .errors import CompanionRuntimeError
from .manifest_sources import DirectoryManifestSourceAdapter
from .ports import ManifestSourceAdapter
from .runtime import CompanionRuntime


def create_app(
    settings: RuntimeSettings | None = None,
    *,
    runtime: CompanionRuntime | None = None,
    manifest_sources: list[ManifestSourceAdapter] | None = None,
    start_runtime: bool = True,
) -> FastAPI:
    runtime_settings = settings or RuntimeSettings.from_environment()
    companion = runtime or CompanionRuntime(runtime_settings)
    sources = list(manifest_sources or [])
    if runtime_settings.manifest_directory is not None:
        sources.append(
            DirectoryManifestSourceAdapter(
                runtime_settings.manifest_directory
            )
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_runtime:
            companion.start()
            for source in sources:
                companion.attach_many(source.load())
        try:
            yield
        finally:
            if start_runtime:
                companion.stop()

    app = FastAPI(
        title="Mitra Companion Runtime",
        version="1.0.0",
        description=(
            "Reusable session, context, intent-routing, and product-attachment "
            "runtime. Domain intelligence and governance remain external."
        ),
        lifespan=lifespan,
    )
    app.state.runtime = companion

    @app.exception_handler(CompanionRuntimeError)
    async def companion_error_handler(request, exc: CompanionRuntimeError):
        return JSONErrorResponse(
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
        )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        status = companion.status()
        attachments = companion.attachments.list()
        sessions = companion.store.list_sessions(limit=8)
        dispatches = companion.store.list_dispatches(limit=8)
        attachment_rows = "".join(
            "<tr>"
            f"<td><strong>{escape(item['manifest']['display_name'])}</strong>"
            f"<small>{escape(item['product_id'])}</small></td>"
            f"<td><span class='badge {item['state'].lower()}'>"
            f"{escape(item['state'])}</span></td>"
            f"<td>{len(item['manifest']['capabilities'])}</td>"
            f"<td>{sum(len(cap['intents']) for cap in item['manifest']['capabilities'])}</td>"
            "</tr>"
            for item in attachments
        ) or "<tr><td colspan='4'>No products attached</td></tr>"
        session_rows = "".join(
            "<tr>"
            f"<td><code>{escape(item['session_id'][:18])}</code></td>"
            f"<td>{escape(item['client_type'])}</td>"
            f"<td>{escape(item['workspace_id'])}</td>"
            f"<td>{escape(item['active_product_id'] or '-')}</td>"
            "</tr>"
            for item in sessions
        ) or "<tr><td colspan='4'>No active sessions</td></tr>"
        dispatch_rows = "".join(
            "<tr>"
            f"<td><code>{escape(item['dispatch_id'][:18])}</code></td>"
            f"<td>{escape(item['product_id'])}</td>"
            f"<td>{escape(item['intent_id'])}</td>"
            f"<td><span class='badge {item['status'].lower()}'>"
            f"{escape(item['status'])}</span></td>"
            "</tr>"
            for item in dispatches
        ) or "<tr><td colspan='4'>No dispatches yet</td></tr>"
        counts = status["counts"]
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mitra Companion Runtime</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, "Segoe UI", sans-serif;
      --ink:#f7f8ff; --muted:#9aa6c5; --panel:#11182a;
      --line:#273353; --violet:#9f7aea; --cyan:#49d7e8;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; color:var(--ink);
      background:
        radial-gradient(circle at 18% 10%, #2b1652 0, transparent 28%),
        radial-gradient(circle at 80% 0%, #0a5361 0, transparent 24%),
        #070b14;
    }}
    main {{ max-width:1220px; margin:auto; padding:42px 26px 70px; }}
    .eyebrow {{ color:var(--cyan); letter-spacing:.16em; text-transform:uppercase;
      font-weight:700; font-size:12px; }}
    h1 {{ font-size:42px; line-height:1.05; margin:10px 0 8px; }}
    .subtitle {{ color:var(--muted); max-width:760px; font-size:17px; line-height:1.55; }}
    .top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:24px; }}
    .state {{ padding:10px 15px; border:1px solid #48668e; border-radius:999px;
      background:#0e2331; color:#8bf0d0; font-weight:750; }}
    .grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin:30px 0; }}
    .card {{ border:1px solid var(--line); border-radius:17px; padding:20px;
      background:linear-gradient(145deg, #151d32, #0e1423); box-shadow:0 16px 45px #0007; }}
    .label {{ color:var(--muted); font-size:12px; letter-spacing:.1em; text-transform:uppercase; }}
    .value {{ font-size:30px; font-weight:800; margin-top:8px; }}
    .section {{ margin-top:16px; }}
    .section h2 {{ margin:0 0 14px; font-size:18px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ text-align:left; padding:12px 10px; border-bottom:1px solid var(--line); }}
    th {{ color:var(--muted); font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}
    small {{ display:block; color:var(--muted); margin-top:3px; }}
    code {{ color:#bad7ff; }}
    .badge {{ display:inline-block; padding:5px 9px; border-radius:999px;
      background:#202b46; color:#cfd8ef; font-size:11px; font-weight:750; }}
    .attached,.completed {{ background:#123a31; color:#7cf2c4; }}
    .degraded,.failed {{ background:#4a242b; color:#ff9ea9; }}
    .accepted,.active {{ background:#183658; color:#8fd0ff; }}
    .flow {{ color:#cdd6ef; line-height:1.8; }}
    .flow strong {{ color:var(--cyan); }}
    a {{ color:#a9c8ff; }}
    @media (max-width:850px) {{
      .grid {{ grid-template-columns:repeat(2, 1fr); }}
      .top {{ flex-direction:column; }}
    }}
  </style>
</head>
<body><main>
  <div class="top">
    <div>
      <div class="eyebrow">Mitra Phase V / Universal Companion Layer</div>
      <h1>Companion Runtime</h1>
      <div class="subtitle">A bounded execution layer for session continuity,
        isolated context, explicit intent routing, and interface-driven product
        attachment across standalone, embedded, mobile, XR, and robotics clients.</div>
    </div>
    <div class="state">{escape(status['state'])}</div>
  </div>
  <div class="grid">
    <div class="card"><div class="label">Attached products</div>
      <div class="value">{counts['attachments']}</div></div>
    <div class="card"><div class="label">Sessions</div>
      <div class="value">{counts['sessions']}</div></div>
    <div class="card"><div class="label">Intent dispatches</div>
      <div class="value">{counts['dispatches']}</div></div>
    <div class="card"><div class="label">Dispatch failures</div>
      <div class="value">{counts['failed_dispatches']}</div></div>
  </div>
  <div class="card section"><h2>Runtime execution flow</h2>
    <div class="flow"><strong>Client</strong> -> Session Runtime -> Context Runtime
      -> Intent Router -> Capability Lookup -> Product Transport
      <br><small>Explicit intent IDs only. No governance, safety, knowledge,
      certification, or product intelligence is implemented here.</small></div>
  </div>
  <div class="card section"><h2>Product attachments</h2>
    <table><thead><tr><th>Product</th><th>State</th><th>Capabilities</th>
      <th>Intents</th></tr></thead><tbody>{attachment_rows}</tbody></table></div>
  <div class="card section"><h2>Recent sessions</h2>
    <table><thead><tr><th>Session</th><th>Client</th><th>Workspace</th>
      <th>Product</th></tr></thead><tbody>{session_rows}</tbody></table></div>
  <div class="card section"><h2>Recent dispatches</h2>
    <table><thead><tr><th>Dispatch</th><th>Product</th><th>Intent</th>
      <th>Status</th></tr></thead><tbody>{dispatch_rows}</tbody></table></div>
  <div class="card section"><h2>Integration surfaces</h2>
    <div class="flow"><a href="/docs">OpenAPI explorer</a> &nbsp;|&nbsp;
      <a href="/api/v1/runtime/status">Runtime status</a> &nbsp;|&nbsp;
      <a href="/api/v1/intents">Intent registry</a></div></div>
</main></body></html>"""

    @app.get("/health")
    async def health() -> dict:
        state = companion.lifecycle.state
        healthy = state in {RuntimeState.READY, RuntimeState.ACTIVE}
        return versioned_response(
            status="healthy" if healthy else "degraded",
            runtime=companion.status(),
            metrics=companion.metrics_snapshot(),
        )

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics() -> str:
        return companion.prometheus_metrics()

    @app.get("/ready")
    async def ready() -> dict:
        if not companion.accepting:
            raise HTTPException(status_code=503, detail="Runtime is not ready")
        return versioned_response(ready=True, runtime=companion.status())

    @app.get("/api/v1/runtime/status")
    async def runtime_status() -> dict:
        return versioned_response(runtime=companion.status())

    @app.get("/api/v1/runtime/metrics")
    async def runtime_metrics() -> dict:
        return versioned_response(metrics=companion.metrics_snapshot())

    @app.get("/api/v1/runtime/telemetry")
    async def runtime_telemetry(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            events=companion.recent_events(limit),
        )

    @app.get("/api/v1/runtime/lifecycle")
    async def runtime_lifecycle(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            state=companion.lifecycle.state.value,
            transitions=companion.lifecycle.history(limit),
        )

    @app.post("/api/v1/sessions", status_code=201)
    async def create_session(request: SessionCreateRequest) -> dict:
        validate_contract(request)
        if request.product_id:
            companion.attachments.get(request.product_id)
        session = companion.sessions.create(
            actor_id=request.actor_id,
            client_type=request.client_type,
            workspace_id=request.workspace_id,
            product_id=request.product_id,
            metadata=request.metadata,
        )
        return versioned_response(session=session)

    @app.get("/api/v1/sessions")
    async def list_sessions(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            sessions=companion.store.list_sessions(limit)
        )

    @app.get("/api/v1/sessions/{session_id}")
    async def get_session(session_id: str) -> dict:
        return versioned_response(
            session=companion.sessions.get(session_id),
            context=companion.context.load(session_id),
        )

    @app.post("/api/v1/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str,
        request: SessionResumeRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            session=companion.sessions.resume(
                session_id,
                request.resume_token,
            )
        )

    @app.post("/api/v1/sessions/{session_id}/suspend")
    async def suspend_session(
        session_id: str,
        request: VersionedContract,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            session=companion.sessions.suspend(session_id)
        )

    @app.post("/api/v1/sessions/{session_id}/close")
    async def close_session(
        session_id: str,
        request: VersionedContract,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            session=companion.sessions.close(session_id)
        )

    @app.get("/api/v1/sessions/{session_id}/context")
    async def load_context(
        session_id: str,
        scope: list[ContextScope] | None = Query(default=None),
    ) -> dict:
        return versioned_response(
            context=companion.context.load(
                session_id,
                scopes=(
                    [item.value for item in scope]
                    if scope is not None
                    else None
                ),
            )
        )

    @app.patch("/api/v1/sessions/{session_id}/context")
    async def update_context(
        session_id: str,
        request: ContextUpdateRequest,
    ) -> dict:
        validate_contract(request)
        context = companion.context.update(
            session_id=session_id,
            scope=request.scope,
            patch=request.patch,
            expected_revision=request.expected_revision,
            replace=request.replace,
        )
        return versioned_response(context=context)

    @app.post("/api/v1/sessions/{session_id}/transfer", status_code=201)
    async def transfer_context(
        session_id: str,
        request: ContextTransferRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            **companion.transfer_context(session_id, request)
        )

    @app.post("/api/v1/attachments", status_code=201)
    async def attach_product(request: AttachmentRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            attachment=companion.attach(request.manifest)
        )

    @app.get("/api/v1/attachments")
    async def list_attachments(
        include_detached: bool = False,
    ) -> dict:
        return versioned_response(
            attachments=companion.attachments.list(
                include_detached=include_detached,
            )
        )

    @app.get("/api/v1/attachments/{product_id}")
    async def get_attachment(product_id: str) -> dict:
        return versioned_response(
            attachment=companion.attachments.get(product_id)
        )

    @app.post("/api/v1/attachments/health")
    async def check_all_attachment_health() -> dict:
        return versioned_response(
            **await companion.check_attachment_health()
        )

    @app.post("/api/v1/attachments/{product_id}/health")
    async def check_attachment_health(product_id: str) -> dict:
        return versioned_response(
            **await companion.check_attachment_health(product_id)
        )

    @app.delete("/api/v1/attachments/{product_id}")
    async def detach_product(product_id: str) -> dict:
        return versioned_response(
            attachment=companion.detach(product_id)
        )

    @app.get("/api/v1/intents")
    async def discover_intents(
        product_id: str | None = None,
        capability_id: str | None = None,
        intent_id: str | None = None,
        available_only: bool = False,
    ) -> dict:
        return versioned_response(
            intents=companion.router.discover(
                product_id=product_id,
                capability_id=capability_id,
                intent_id=intent_id,
                available_only=available_only,
            )
        )

    @app.get("/api/v1/products/{product_id}/intent-registrations")
    async def get_intent_registrations(product_id: str) -> dict:
        return versioned_response(
            registration=companion.router.register(product_id)
        )

    @app.get("/api/v1/capabilities")
    async def discover_capabilities(
        product_id: str | None = None,
        available_only: bool = False,
    ) -> dict:
        return versioned_response(
            capabilities=companion.router.capabilities(
                product_id=product_id,
                available_only=available_only,
            )
        )

    @app.get(
        "/api/v1/products/{product_id}/capabilities/{capability_id}"
    )
    async def lookup_capability(
        product_id: str,
        capability_id: str,
    ) -> dict:
        return versioned_response(
            capability=companion.router.lookup_capability(
                product_id=product_id,
                capability_id=capability_id,
            )
        )

    @app.post("/api/v1/intents/dispatch")
    async def dispatch_intent(request: IntentDispatchRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            **await companion.dispatch(request)
        )

    @app.get("/api/v1/dispatches")
    async def list_dispatches(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            dispatches=companion.store.list_dispatches(limit)
        )

    @app.get("/api/v1/dispatches/{dispatch_id}")
    async def get_dispatch(dispatch_id: str) -> dict:
        return versioned_response(
            dispatch=companion.get_dispatch(dispatch_id)
        )

    return app


class JSONErrorResponse(Response):
    def __init__(self, *, status_code: int, code: str, message: str):
        content = json.dumps(
            versioned_response(
                error={
                    "code": code,
                    "message": message,
                    "retryable": status_code >= 500,
                }
            ),
            ensure_ascii=False,
        )
        super().__init__(
            content=content,
            status_code=status_code,
            media_type="application/json",
        )
