from __future__ import annotations

import json
from contextlib import asynccontextmanager
from html import escape
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)

from .config import RuntimeSettings
from .constants import ContextScope, RuntimeState
from .contracts import (
    AttachmentRequest,
    CompanionMessageRequest,
    ContextTransferRequest,
    ContextUpdateRequest,
    EcosystemExecutionRequest,
    EcosystemReplayValidationRequest,
    IntentDispatchRequest,
    ProductExchangeAckRequest,
    ProductExchangeRequest,
    ReconstructionValidationRequest,
    RuntimeAnalysisRequest,
    SessionCreateRequest,
    SessionResumeRequest,
    VersionedContract,
    validate_contract,
    versioned_response,
)
from .errors import CompanionRuntimeError
from .frontend_connector import create_frontend_connector_router
from .manifest_sources import DirectoryManifestSourceAdapter
from .observability import configure_opentelemetry
from .ports import ManifestSourceAdapter
from .runtime import CompanionRuntime
from .utils import utc_now


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
                runtime_settings.manifest_directory,
                allow_examples=runtime_settings.allow_example_manifests,
                allow_simulated=runtime_settings.allow_simulated_manifests,
                allow_loopback=runtime_settings.allow_loopback_manifests,
                allow_localhost=runtime_settings.allow_localhost_manifests,
                require_production_bootstrap=(
                    runtime_settings.require_production_bootstrap_manifests
                ),
            )
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_runtime:
            companion.startup_manager.start(sources)
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
    if runtime_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key"],
            allow_credentials=False,
        )
    app.state.runtime = companion
    app.state.opentelemetry = configure_opentelemetry(app, runtime_settings)

    @app.exception_handler(CompanionRuntimeError)
    async def companion_error_handler(request, exc: CompanionRuntimeError):
        return JSONErrorResponse(
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
        )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        captured_at = utc_now()
        status = companion.status()
        attachments = companion.attachments.list()
        sessions = companion.store.list_sessions(limit=8)
        dispatches = companion.store.list_dispatches(limit=8)
        instances = companion.runtime_instances(include_stopped=True)
        startup = companion.startup_status()
        production_config = runtime_settings.production_summary()
        secrets = runtime_settings.secrets_summary()
        continuity = companion.continuity_status()
        deliveries = companion.integration_deliveries(limit=8)
        dependency_health = companion.dependency_health_status(limit=100)
        ecosystem = companion.ecosystem.status()
        ecosystem_executions = companion.ecosystem_executions(limit=8)
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
        instance_rows = "".join(
            "<tr>"
            f"<td><code>{escape(item['instance_id'])}</code></td>"
            f"<td><span class='badge {item['state'].lower()}'>"
            f"{escape(item['state'])}</span></td>"
            f"<td>{escape(item['environment'])}</td>"
            f"<td>{escape(item['last_heartbeat_at'])}</td>"
            "</tr>"
            for item in instances
        ) or "<tr><td colspan='4'>No runtime instances</td></tr>"
        startup_rows = "".join(
            "<tr>"
            f"<td>{escape(item['name'])}</td>"
            f"<td>{escape(item['completed_at'])}</td>"
            "</tr>"
            for item in startup.get("phases", [])
        ) or "<tr><td colspan='2'>Startup has not completed</td></tr>"
        delivery_rows = "".join(
            "<tr>"
            f"<td><code>{escape(item['delivery_id'][:18])}</code></td>"
            f"<td><code>{escape(item['dispatch_id'][:18])}</code></td>"
            f"<td><span class='badge {item['status'].lower()}'>"
            f"{escape(item['status'])}</span></td>"
            f"<td>{item['attempts']}</td>"
            f"<td>{escape(item['updated_at'])}</td>"
            "</tr>"
            for item in deliveries
        ) or "<tr><td colspan='5'>No TANTRA deliveries</td></tr>"
        dependency_rows = "".join(
            "<tr>"
            f"<td>{escape(item['product_id'])}</td>"
            f"<td><span class='badge {item['latest_status'].lower()}'>"
            f"{escape(item['latest_status'])}</span></td>"
            f"<td>{item['sample_count']}</td>"
            f"<td>{item['consecutive_failures']}</td>"
            f"<td>{escape(str(item['average_latency_ms'] or '-'))}</td>"
            "</tr>"
            for item in dependency_health["products"]
        ) or "<tr><td colspan='5'>No dependency observations</td></tr>"
        ecosystem_rows = "".join(
            "<tr>"
            f"<td><a href='/operator/ecosystem/{escape(item['execution_id'])}'>"
            f"<code>{escape(item['execution_id'][:18])}</code></a></td>"
            f"<td><code>{escape(item['trace_id'][:18])}</code></td>"
            f"<td>{escape(str(item.get('current_stage') or '-'))}</td>"
            f"<td><span class='badge {item['status'].lower()}'>"
            f"{escape(item['status'])}</span></td>"
            f"<td>{escape(item['updated_at'])}</td>"
            "</tr>"
            for item in ecosystem_executions
        ) or "<tr><td colspan='5'>No ecosystem executions yet</td></tr>"
        counts = status["counts"]
        outbox_counts = status["tantra_integration"]["delivery_outbox"][
            "counts"
        ]
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mitra Companion Runtime</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      --page:#f5f7f3; --surface:#ffffff; --surface-alt:#edf2ee;
      --ink:#17201d; --muted:#62706b; --line:#d7dfd9;
      --signal:#17735d; --signal-soft:#dff3ec; --blue:#2f68d8;
      --danger:#b42318; --shadow:#17201d18;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; color:var(--ink);
      background:var(--page);
    }}
    main {{ max-width:1240px; margin:auto; padding:34px 24px 64px; }}
    .top {{
      display:flex; justify-content:space-between; align-items:flex-start; gap:24px;
      padding:22px 0 24px; border-bottom:1px solid var(--line);
    }}
    .eyebrow {{
      color:var(--signal); letter-spacing:0; text-transform:uppercase;
      font-weight:800; font-size:12px;
    }}
    h1 {{ font-size:40px; line-height:1.08; margin:8px 0 8px; font-weight:850; }}
    .subtitle {{ color:var(--muted); max-width:780px; font-size:16px; line-height:1.55; }}
    .timestamp {{ color:var(--muted); font-size:12px; margin-top:8px; }}
    .state {{
      min-width:112px; text-align:center; padding:9px 14px; border:1px solid #9dc9b9;
      border-radius:999px; background:var(--signal-soft); color:#0d5c49; font-weight:800;
      box-shadow:0 8px 20px var(--shadow);
    }}
    .grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin:24px 0; }}
    .card {{
      border:1px solid var(--line); border-radius:8px; padding:18px;
      background:var(--surface);
      overflow:auto;
    }}
    .grid .card {{ min-height:112px; display:flex; flex-direction:column; justify-content:space-between; }}
    .label {{ color:var(--muted); font-size:12px; letter-spacing:0; text-transform:uppercase; font-weight:800; }}
    .value {{ font-size:30px; font-weight:850; margin-top:10px; color:#101815; }}
    .section {{
      margin-top:14px; padding:22px 0; border:0; border-top:1px solid var(--line);
      border-radius:0; background:transparent; box-shadow:none;
    }}
    .section h2 {{ margin:0 0 12px; font-size:18px; line-height:1.25; }}
    table {{ width:100%; border-collapse:collapse; min-width:620px; }}
    th, td {{ text-align:left; padding:12px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{
      color:var(--muted); font-size:11px; letter-spacing:0; text-transform:uppercase;
      background:var(--surface-alt); font-weight:800;
    }}
    tr:last-child td {{ border-bottom:0; }}
    small {{ display:block; color:var(--muted); margin-top:3px; }}
    code {{ color:#224fba; background:#eef3ff; padding:1px 5px; border-radius:5px; }}
    .badge {{
      display:inline-block; padding:5px 9px; border-radius:999px;
      background:#eef2ed; color:#35423d; font-size:11px; font-weight:800;
    }}
    .attached,.completed {{ background:var(--signal-soft); color:#0d5c49; }}
    .degraded,.failed {{ background:#fde7e7; color:var(--danger); }}
    .accepted,.active {{ background:#e6efff; color:#224fba; }}
    .flow {{ color:#33413c; line-height:1.8; }}
    .flow strong {{ color:var(--signal); }}
    a {{ color:var(--blue); font-weight:750; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    @media (max-width:850px) {{
      .grid {{ grid-template-columns:repeat(2, 1fr); }}
      .top {{ flex-direction:column; }}
    }}
    @media (max-width:560px) {{
      main {{ padding:24px 14px 44px; }}
      h1 {{ font-size:32px; }}
      .grid {{ grid-template-columns:1fr; }}
      .card {{ padding:15px; }}
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
      <div class="timestamp">Snapshot UTC: {escape(captured_at)}</div>
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
    <div class="card"><div class="label">Product exchanges</div>
      <div class="value">{counts['product_exchanges']}</div></div>
    <div class="card"><div class="label">Runtime instances</div>
      <div class="value">{status['active_runtime_instance_count']}</div></div>
    <div class="card"><div class="label">Supervisor</div>
      <div class="value">{'ON' if status['persistent_runtime']['supervisor_running'] else 'OFF'}</div></div>
    <div class="card"><div class="label">Log level</div>
      <div class="value">{escape(str(production_config['production_log_level']))}</div></div>
    <div class="card"><div class="label">Secrets</div>
      <div class="value">{len(secrets['secret_keys_configured'])}</div></div>
    <div class="card"><div class="label">Coordinator</div>
      <div class="value">{'YES' if status['persistent_runtime']['coordinator'] else 'NO'}</div></div>
    <div class="card"><div class="label">Delivery outbox</div>
      <div class="value">{outbox_counts.get('TOTAL', 0)}</div></div>
    <div class="card"><div class="label">Continuity</div>
      <div class="value">{escape(str(continuity.get('status', 'not-run')).upper())}</div></div>
    <div class="card"><div class="label">Ecosystem contracts</div>
      <div class="value">{'READY' if ecosystem['readiness']['ready'] else 'PENDING'}</div></div>
    <div class="card"><div class="label">Ecosystem executions</div>
      <div class="value">{ecosystem['execution_counts'].get('TOTAL', 0)}</div></div>
  </div>
  <div class="card section"><h2>TANTRA ecosystem convergence</h2>
    <div class="flow"><strong>Mitra capability selection</strong> -> Raj workflow
      execution -> Bucket truth -> Karma integrity -> PRANA strict forwarding ->
      InsightFlow telemetry -> deterministic replay -> Central Depository export
      <br><small>Owner services are invoked through published contracts. A failed
      or unconfigured stage stops downstream execution; no embedded fallback is used.</small></div>
  </div>
  <div class="card section"><h2>Recent ecosystem executions</h2>
    <table><thead><tr><th>Execution</th><th>Trace</th><th>Stage</th>
      <th>Status</th><th>Updated</th></tr></thead>
      <tbody>{ecosystem_rows}</tbody></table></div>
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
  <div class="card section"><h2>Runtime instances</h2>
    <table><thead><tr><th>Instance</th><th>State</th><th>Environment</th>
      <th>Heartbeat</th></tr></thead><tbody>{instance_rows}</tbody></table></div>
  <div class="card section"><h2>TANTRA delivery outbox</h2>
    <table><thead><tr><th>Delivery</th><th>Dispatch</th><th>Status</th>
      <th>Attempts</th><th>Updated</th></tr></thead>
      <tbody>{delivery_rows}</tbody></table></div>
  <div class="card section"><h2>Dependency health history</h2>
    <table><thead><tr><th>Product</th><th>Latest</th><th>Samples</th>
      <th>Consecutive failures</th><th>Average latency ms</th></tr></thead>
      <tbody>{dependency_rows}</tbody></table></div>
  <div class="card section"><h2>Startup manager</h2>
    <table><thead><tr><th>Phase</th><th>Completed</th></tr></thead>
      <tbody>{startup_rows}</tbody></table></div>
  <div class="card section"><h2>Production configuration</h2>
    <div class="flow">Profile <strong>{escape(str(production_config['profile']))}</strong>
      | Config sources {escape(', '.join(production_config['config_sources']))}
      | Log {escape(str(production_config['production_log_path']))}
      <br><small>{escape(str(secrets['redaction']))}</small></div></div>
  <div class="card section"><h2>Integration surfaces</h2>
    <div class="flow"><a href="/docs">OpenAPI explorer</a> &nbsp;|&nbsp;
      <a href="/api/v1/runtime/status">Runtime status</a> &nbsp;|&nbsp;
      <a href="/api/v1/runtime/continuity">Continuity</a> &nbsp;|&nbsp;
      <a href="/api/v1/runtime/dependencies/health">Dependencies</a> &nbsp;|&nbsp;
      <a href="/api/v1/runtime/integrations/tantra/deliveries">Deliveries</a>
      &nbsp;|&nbsp; <a href="/api/v1/ecosystem/readiness">Ecosystem readiness</a>
      &nbsp;|&nbsp; <a href="/api/v1/intents">Intent registry</a></div></div>
</main></body></html>"""

    @app.get(
        "/operator/ecosystem/{execution_id}",
        response_class=HTMLResponse,
    )
    async def ecosystem_operator_execution(
        execution_id: str,
        stage: str | None = Query(default=None),
    ) -> str:
        captured_at = utc_now()
        detail = companion.ecosystem_execution(execution_id)
        execution = detail["execution"]
        stages = detail["stages"]
        selected = None
        if stage is not None:
            selected = next(
                (item for item in stages if item["stage_name"] == stage),
                None,
            )
            if selected is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown ecosystem stage: {stage}",
                )

        stage_rows = "".join(
            "<tr>"
            f"<td><a href='/operator/ecosystem/{escape(execution_id)}"
            f"?stage={escape(item['stage_name'])}#stage-detail'>"
            f"{escape(item['stage_name'])}</a></td>"
            f"<td>{escape(item['status'])}</td>"
            f"<td>{item['attempts']}</td>"
            f"<td><code>{escape(str(item.get('response_hash') or '-'))}</code></td>"
            f"<td>{escape(str(item.get('finished_at') or '-'))}</td>"
            "</tr>"
            for item in stages
        )
        selected_content = ""
        if selected is not None:
            response = selected.get("response") or {}
            facts: dict[str, Any] = {
                "stage": selected["stage_name"],
                "status": response.get("status"),
                "trace_id": response.get("trace_id"),
            }
            if selected["stage_name"] == "dependency-preflight":
                facts["owner_checks"] = [
                    {
                        "module": operation.get("module"),
                        "operation": operation.get("operation"),
                        "http_status": operation.get("http_status"),
                        "transport_status": operation.get("status"),
                        "owner_response": operation.get("response"),
                    }
                    for operation in response.get("checks", [])
                ]
            elif selected["stage_name"] == "raj-execution":
                operation = response.get("operation") or {}
                facts.update(
                    {
                        "mitra_trace_id": response.get("trace_id"),
                        "raj_trace_id": response.get("raj_trace_id"),
                        "workflow_status": (
                            response.get("execution") or {}
                        ).get("status"),
                        "owner_http": {
                            "module": operation.get("module"),
                            "operation": operation.get("operation"),
                            "http_status": operation.get("http_status"),
                            "contract_validation": operation.get(
                                "contract_validation"
                            ),
                            "owner_status": (
                                operation.get("response") or {}
                            ).get("status"),
                        },
                    }
                )
            elif selected["stage_name"] == "keshav-diagnosis":
                operation = response.get("operation") or {}
                facts.update(
                    {
                        "invoked": response.get("invoked"),
                        "reason": response.get("reason"),
                        "authority": response.get("authority"),
                        "source_error_hash": response.get(
                            "source_error_hash"
                        ),
                        "diagnosis": response.get("diagnosis"),
                        "owner_http": (
                            {
                                "module": operation.get("module"),
                                "operation": operation.get("operation"),
                                "http_status": operation.get("http_status"),
                                "contract_validation": operation.get(
                                    "contract_validation"
                                ),
                            }
                            if operation
                            else None
                        ),
                    }
                )
            elif selected["stage_name"] == "bucket-truth":
                facts.update(
                    {
                        "artifact_id": response.get("artifact_id"),
                        "artifact_hash": response.get("artifact_hash"),
                        "parent_hash": response.get("parent_hash"),
                        "owner_operations": [
                            {
                                "operation": operation.get("operation"),
                                "http_status": operation.get("http_status"),
                                "owner_status": (
                                    operation.get("response") or {}
                                ).get("status"),
                            }
                            for operation in response.get("operations", [])
                        ],
                    }
                )
            elif selected["stage_name"] == "karma-integrity":
                operation = response.get("operation") or {}
                facts.update(
                    {
                        "accepted_hash": response.get("accepted_hash"),
                        "request_sha256": response.get("request_sha256"),
                        "owner_http": {
                            "operation": operation.get("operation"),
                            "http_status": operation.get("http_status"),
                            "owner_response": operation.get("response"),
                        },
                    }
                )
            elif selected["stage_name"] == "prana-forwarding":
                operations = response.get("operations", [])
                strict = operations[0] if len(operations) > 0 else {}
                core = operations[1] if len(operations) > 1 else {}
                facts.update(
                    {
                        "strict_bytes_sha256": response.get(
                            "strict_bytes_sha256"
                        ),
                        "strict_forward": {
                            "http_status": strict.get("http_status"),
                            "owner_status": (
                                strict.get("response") or {}
                            ).get("status"),
                            "strict_validation": strict.get(
                                "strict_validation"
                            ),
                            "response_headers": {
                                key: value
                                for key, value in (
                                    strict.get("response_headers") or {}
                                ).items()
                                if key.startswith("x-prana-")
                            },
                        },
                        "core_forward": {
                            "http_status": core.get("http_status"),
                            "owner_status": (
                                core.get("response") or {}
                            ).get("status"),
                            "trace_validation": core.get(
                                "trace_validation"
                            ),
                        },
                    }
                )
            elif selected["stage_name"] == "insightflow-telemetry":
                operation = response.get("operation") or {}
                facts.update(
                    {
                        "event_type": (
                            response.get("envelope") or {}
                        ).get("event_type"),
                        "owner_http": {
                            "operation": operation.get("operation"),
                            "http_status": operation.get("http_status"),
                            "owner_response": operation.get("response"),
                        },
                    }
                )
            facts_json = escape(
                json.dumps(
                    facts,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            request_json = escape(
                json.dumps(
                    selected.get("request"),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            response_json = escape(
                json.dumps(
                    selected.get("response"),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            selected_content = f"""
  <section class="stage-detail" id="stage-detail">
    <div class="stage-heading">
      <div><div class="eyebrow">Selected stage</div>
        <h2>{escape(selected['stage_name'])}</h2></div>
      <strong class="status">{escape(selected['status'])}</strong>
    </div>
    <dl class="hashes">
      <div><dt>Request SHA-256</dt><dd><code>{escape(str(selected.get('request_hash') or '-'))}</code></dd></div>
      <div><dt>Response SHA-256</dt><dd><code>{escape(str(selected.get('response_hash') or '-'))}</code></dd></div>
      <div><dt>Artifact SHA-256</dt><dd><code>{escape(str(selected.get('artifact_hash') or '-'))}</code></dd></div>
      <div><dt>Lineage chain</dt><dd><code>{escape(str(selected.get('chain_hash') or '-'))}</code></dd></div>
    </dl>
    <section class="contract-facts"><h3>Contract facts</h3>
      <pre>{facts_json}</pre></section>
    <div class="payload-grid">
      <section><h3>Recorded request</h3><pre>{request_json}</pre></section>
      <section><h3>Recorded response</h3><pre>{response_json}</pre></section>
    </div>
  </section>"""

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(execution_id)} | Mitra execution ledger</title>
  <style>
    :root {{
      color-scheme:light; font-family:Inter,"Segoe UI",Arial,sans-serif;
      --page:#f5f7f3; --surface:#fff; --ink:#17201d; --muted:#62706b;
      --line:#d7dfd9; --signal:#17735d; --soft:#dff3ec; --blue:#2f68d8;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--page); }}
    main {{ max-width:1380px; margin:auto; padding:30px 24px 60px; }}
    header {{ display:flex; justify-content:space-between; gap:24px;
      border-bottom:1px solid var(--line); padding-bottom:22px; }}
    .eyebrow {{ color:var(--signal); font-weight:800; font-size:12px;
      text-transform:uppercase; }}
    h1 {{ margin:7px 0; font-size:32px; overflow-wrap:anywhere; }}
    h2 {{ margin:6px 0 0; font-size:24px; }}
    h3 {{ margin:0; padding:12px 14px; border-bottom:1px solid var(--line);
      font-size:14px; }}
    .meta {{ color:var(--muted); line-height:1.6; font-size:13px; }}
    .status {{ align-self:flex-start; color:#0d5c49; background:var(--soft);
      border:1px solid #9dc9b9; padding:8px 11px; border-radius:6px; }}
    .summary {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px;
      margin:22px 0; }}
    .summary div {{ background:var(--surface); border:1px solid var(--line);
      border-radius:6px; padding:14px; min-width:0; }}
    .summary span {{ display:block; color:var(--muted); font-size:11px;
      font-weight:800; text-transform:uppercase; margin-bottom:7px; }}
    code {{ color:#224fba; overflow-wrap:anywhere; }}
    .ledger {{ overflow:auto; border-top:1px solid var(--line);
      border-bottom:1px solid var(--line); }}
    table {{ width:100%; border-collapse:collapse; min-width:920px;
      background:var(--surface); }}
    th,td {{ text-align:left; padding:11px 10px; border-bottom:1px solid var(--line);
      vertical-align:top; }}
    th {{ color:var(--muted); font-size:11px; text-transform:uppercase;
      background:#edf2ee; }}
    td code {{ font-size:11px; }}
    a {{ color:var(--blue); font-weight:750; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .stage-detail {{ margin-top:26px; border-top:1px solid var(--line); }}
    .stage-heading {{ display:flex; justify-content:space-between; gap:20px;
      align-items:flex-start; padding:20px 0 16px; }}
    .hashes {{ display:grid; grid-template-columns:repeat(2,1fr); gap:1px;
      background:var(--line); border:1px solid var(--line); margin:0 0 14px; }}
    .hashes div {{ background:var(--surface); padding:12px; min-width:0; }}
    dt {{ color:var(--muted); font-size:11px; font-weight:800;
      text-transform:uppercase; margin-bottom:5px; }}
    dd {{ margin:0; overflow-wrap:anywhere; }}
    .payload-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
    .payload-grid section,.contract-facts {{ background:var(--surface); border:1px solid var(--line);
      min-width:0; }}
    .contract-facts {{ margin-bottom:14px; }}
    .contract-facts pre {{ max-height:none; }}
    pre {{ margin:0; padding:14px; color:#152923; background:#fbfcfa;
      font:12px/1.55 Consolas,"SFMono-Regular",monospace; white-space:pre-wrap;
      overflow-wrap:anywhere; max-height:680px; overflow:auto; }}
    footer {{ margin-top:24px; color:var(--muted); font-size:13px; }}
    @media(max-width:850px) {{
      header,.stage-heading {{ flex-direction:column; }}
      .summary,.hashes,.payload-grid {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body><main>
  <header><div><div class="eyebrow">Mitra immutable execution ledger</div>
    <h1>{escape(execution_id)}</h1>
    <div class="meta">Trace {escape(execution['trace_id'])}<br>
      Environment {escape(runtime_settings.deployment_environment)}<br>
      Snapshot UTC {escape(captured_at)}</div></div>
    <strong class="status">{escape(execution['status'])}</strong>
  </header>
  <section class="summary">
    <div><span>Current stage</span>{escape(str(execution.get('current_stage') or '-'))}</div>
    <div><span>Recorded stages</span>{len(stages)}</div>
    <div><span>Replay package</span><code>{escape(str(execution.get('replay_package_hash') or 'not sealed'))}</code></div>
    <div><span>Updated UTC</span>{escape(execution['updated_at'])}</div>
  </section>
  <section class="ledger"><table><thead><tr><th>Stage</th><th>Status</th>
    <th>Attempts</th><th>Response SHA-256</th><th>Finished UTC</th></tr></thead>
    <tbody>{stage_rows}</tbody></table></section>
  {selected_content}
  <footer><a href="/">Dashboard</a> &nbsp;|&nbsp;
    <a href="/api/v1/ecosystem/executions/{escape(execution_id)}">Execution API</a>
    &nbsp;|&nbsp; <a href="/api/v1/ecosystem/executions/{escape(execution_id)}/replay">Replay API</a></footer>
</main></body></html>"""

    @app.get("/operator/runtime", response_class=HTMLResponse)
    async def operator_runtime_view(
        view: str = Query(default="status"),
        execution_id: str | None = Query(default=None),
    ) -> str:
        captured_at = utc_now()
        state = companion.lifecycle.state
        healthy = state in {RuntimeState.READY, RuntimeState.ACTIVE}
        metrics_snapshot = companion.metrics_snapshot()
        resources: dict[str, tuple[str, Any]] = {
            "status": (
                "Runtime status",
                {
                    "captured_at": captured_at,
                    "runtime": companion.status(),
                    "opentelemetry": app.state.opentelemetry,
                },
            ),
            "startup": (
                "Runtime startup",
                {
                    "captured_at": captured_at,
                    "startup": companion.startup_status(),
                },
            ),
            "attachments": (
                "Attached products",
                {
                    "captured_at": captured_at,
                    "attachments": [
                        {
                            "product_id": item["product_id"],
                            "display_name": item["manifest"]["display_name"],
                            "state": item["state"],
                            "base_url": item["manifest"].get("base_url"),
                            "capability_ids": [
                                capability["capability_id"]
                                for capability in item["manifest"][
                                    "capabilities"
                                ]
                            ],
                            "updated_at": item["updated_at"],
                        }
                        for item in companion.attachments.list()
                    ],
                },
            ),
            "health": (
                "Health and readiness",
                {
                    "captured_at": captured_at,
                    "health": {
                        "status": "healthy" if healthy else "degraded",
                        "runtime_state": state.value,
                        "accepting": companion.accepting,
                    },
                    "readiness": {
                        "ready": companion.accepting,
                        "ecosystem_ready": companion.ecosystem_readiness()[
                            "ready"
                        ],
                    },
                    "ecosystem": companion.ecosystem_readiness(),
                },
            ),
            "metrics": (
                "Production metrics",
                {
                    "captured_at": captured_at,
                    "durable_ecosystem_convergence": {
                        "execution_counts": metrics_snapshot[
                            "ecosystem_convergence"
                        ]["execution_counts"],
                        "stage_failure_counts": metrics_snapshot[
                            "ecosystem_convergence"
                        ]["stage_failure_counts"],
                        "readiness": metrics_snapshot[
                            "ecosystem_convergence"
                        ]["readiness"],
                    },
                    "runtime_coordination": metrics_snapshot["coordination"],
                    "process_event_counters": metrics_snapshot["counters"],
                    "dispatch_latency_ms": metrics_snapshot[
                        "dispatch_latency_ms"
                    ],
                    "dependency_health": metrics_snapshot[
                        "dependency_health"
                    ],
                },
            ),
            "telemetry": (
                "Runtime telemetry",
                {
                    "captured_at": captured_at,
                    "events": companion.recent_events(40),
                },
            ),
            "instances": (
                "Runtime instances",
                {
                    "captured_at": captured_at,
                    "current_instance_id": companion.instance_id,
                    "active_instance_count": len(
                        companion.runtime_instances()
                    ),
                    "coordination": companion.status()["persistent_runtime"],
                    "active_instances": companion.runtime_instances(),
                    "stopped_instances": [
                        item
                        for item in companion.runtime_instances(
                            include_stopped=True
                        )
                        if item.get("state") == "STOPPED"
                    ],
                },
            ),
        }
        if view == "replay":
            if not execution_id:
                raise HTTPException(
                    status_code=400,
                    detail="execution_id is required for the replay view",
                )
            replay = companion.ecosystem_replay(execution_id)
            resources[view] = (
                "Deterministic replay reconstruction",
                {
                    "captured_at": captured_at,
                    "execution_id": execution_id,
                    "package_hash": replay["package"]["package_hash"],
                    "reconstructed_execution_hash": replay["package"][
                        "reconstructed_execution_hash"
                    ],
                    "validation": replay["validation"],
                },
            )
        elif view == "depository":
            if not execution_id:
                raise HTTPException(
                    status_code=400,
                    detail="execution_id is required for the depository view",
                )
            resources[view] = (
                "Central Depository export",
                {
                    "captured_at": captured_at,
                    "execution_id": execution_id,
                    "depository": companion.central_depository(
                        subject_type="ecosystem_execution",
                        subject_id=execution_id,
                        limit=100,
                    ),
                },
            )
        elif view == "recovery":
            recovered = (
                companion.ecosystem_execution(execution_id)
                if execution_id
                else None
            )
            replay_validation = (
                companion.ecosystem_replay(execution_id)["validation"]
                if execution_id
                else None
            )
            resources[view] = (
                "Durable runtime recovery",
                {
                    "captured_at": captured_at,
                    "runtime_instance_id": companion.instance_id,
                    "recovered_execution": (
                        recovered["execution"] if recovered else None
                    ),
                    "replay_validation": replay_validation,
                    "instances": companion.runtime_instances(
                        include_stopped=True
                    ),
                    "startup": companion.startup_status(),
                },
            )
        if view not in resources:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown operator runtime view: {view}",
            )
        title, payload = resources[view]
        pretty = escape(
            json.dumps(
                payload,
                indent=2,
                sort_keys=False,
                ensure_ascii=False,
            )
        )
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Mitra</title>
  <style>
    :root {{ color-scheme:light; font-family:Inter,"Segoe UI",Arial,sans-serif;
      --page:#f5f7f3; --surface:#fff; --ink:#17201d; --muted:#62706b;
      --line:#d7dfd9; --signal:#17735d; --blue:#2f68d8; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--page); }}
    main {{ max-width:1320px; margin:auto; padding:30px 24px 56px; }}
    header {{ display:flex; justify-content:space-between; gap:24px;
      padding-bottom:20px; border-bottom:1px solid var(--line); }}
    .eyebrow {{ color:var(--signal); font-weight:800; font-size:12px;
      text-transform:uppercase; }}
    h1 {{ margin:7px 0; font-size:34px; }}
    .meta {{ color:var(--muted); font-size:13px; line-height:1.6; }}
    nav {{ align-self:flex-start; text-align:right; line-height:1.8; }}
    a {{ color:var(--blue); font-weight:750; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    pre {{ margin:20px 0 0; padding:20px; border:1px solid var(--line);
      border-radius:6px; color:#152923; background:var(--surface);
      font:13px/1.58 Consolas,"SFMono-Regular",monospace; white-space:pre-wrap;
      overflow-wrap:anywhere; overflow:auto; }}
    @media(max-width:700px) {{ header {{ flex-direction:column; }}
      nav {{ text-align:left; }} main {{ padding:22px 14px 42px; }} }}
  </style>
</head><body><main><header><div>
  <div class="eyebrow">Mitra operator output</div><h1>{escape(title)}</h1>
  <div class="meta">Environment {escape(runtime_settings.deployment_environment)}<br>
    Snapshot UTC {escape(captured_at)}</div></div>
  <nav><a href="/">Dashboard</a><br><a href="/docs">OpenAPI</a></nav>
</header><pre>{pretty}</pre></main></body></html>"""

    @app.get("/health")
    async def health() -> dict:
        state = companion.lifecycle.state
        healthy = state in {RuntimeState.READY, RuntimeState.ACTIVE}
        return versioned_response(
            status="healthy" if healthy else "degraded",
            runtime=companion.status(),
            metrics=companion.metrics_snapshot(),
            opentelemetry=app.state.opentelemetry,
        )

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics() -> str:
        return companion.prometheus_metrics()

    @app.get("/ready")
    async def ready() -> dict:
        if not companion.accepting:
            raise HTTPException(status_code=503, detail="Runtime is not ready")
        return versioned_response(
            ready=True,
            ecosystem_ready=companion.ecosystem_readiness()["ready"],
            runtime=companion.status(),
        )

    @app.get("/api/v1/runtime/status")
    async def runtime_status() -> dict:
        return versioned_response(
            runtime=companion.status(),
            opentelemetry=app.state.opentelemetry,
        )

    @app.get("/api/v1/runtime/startup")
    async def runtime_startup() -> dict:
        return versioned_response(startup=companion.startup_status())

    @app.post("/api/v1/runtime/restart")
    async def runtime_restart(request: VersionedContract) -> dict:
        validate_contract(request)
        return versioned_response(
            restart=companion.graceful_restart(sources)
        )

    @app.post("/api/v1/runtime/recovery")
    async def runtime_recovery(request: VersionedContract) -> dict:
        validate_contract(request)
        return versioned_response(recovery=companion.recover_runtime())

    @app.get("/api/v1/runtime/config")
    async def runtime_config() -> dict:
        return versioned_response(
            configuration=runtime_settings.production_summary()
        )

    @app.get("/api/v1/runtime/secrets")
    async def runtime_secrets() -> dict:
        return versioned_response(secrets=runtime_settings.secrets_summary())

    @app.get("/api/v1/runtime/instances")
    async def runtime_instances(
        include_stopped: bool = False,
    ) -> dict:
        return versioned_response(
            instances=companion.runtime_instances(
                include_stopped=include_stopped,
            )
        )

    @app.post("/api/v1/runtime/instances/reconcile")
    async def runtime_instances_reconcile(request: VersionedContract) -> dict:
        validate_contract(request)
        return versioned_response(recovery=companion.recover_runtime())

    @app.get("/api/v1/runtime/instances/{instance_id}")
    async def runtime_instance(instance_id: str) -> dict:
        return versioned_response(
            instance=companion.runtime_instance(instance_id)
        )

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

    @app.get("/api/v1/runtime/chain")
    async def runtime_chain() -> dict:
        return versioned_response(chain=companion.ecosystem_chain())

    @app.get("/api/v1/runtime/source-scope")
    async def runtime_source_scope() -> dict:
        return versioned_response(source_scope=companion.source_scope())

    @app.get("/api/v1/runtime/capability-catalog")
    async def runtime_capability_catalog() -> dict:
        return versioned_response(catalog=companion.capability_catalog())

    @app.get("/api/v1/runtime/capability-graph")
    async def runtime_capability_graph(
        product_id: str | None = None,
        capability_id: str | None = None,
        available_only: bool = False,
        message: str | None = None,
    ) -> dict:
        return versioned_response(
            graph=companion.capability_graph(
                product_id=product_id,
                capability_id=capability_id,
                available_only=available_only,
                message=message,
            )
        )

    @app.post("/api/v1/runtime/capability-plan")
    async def runtime_capability_plan(request: RuntimeAnalysisRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            plan=companion.capability_plan(
                message=request.message,
                product_id=request.product_id,
                capability_id=request.capability_id,
                available_only=False,
            )
        )

    @app.get("/api/v1/runtime/depository")
    async def runtime_depository(
        artifact_type: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            depository=companion.central_depository(
                artifact_type=artifact_type,
                subject_type=subject_type,
                subject_id=subject_id,
                limit=limit,
            )
        )

    @app.get("/api/v1/runtime/integrations")
    async def runtime_integrations() -> dict:
        return versioned_response(
            integrations={
                "bhiv": companion.bhiv_integrations.status(),
                "tantra": companion.tantra_status(),
            }
        )

    @app.get("/api/v1/runtime/integrations/tantra/deliveries")
    async def runtime_tantra_deliveries(
        dispatch_id: str | None = None,
        status: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            deliveries=companion.integration_deliveries(
                dispatch_id=dispatch_id,
                status=status,
                limit=limit,
            )
        )

    @app.post("/api/v1/runtime/integrations/tantra/process")
    async def runtime_tantra_process(
        request: VersionedContract,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            processing=await companion.process_integration_deliveries(
                limit=limit
            )
        )

    @app.get("/api/v1/runtime/integrations/tantra/health")
    async def runtime_tantra_health() -> dict:
        return versioned_response(
            integration_health=await companion.check_tantra_gateway_health()
        )

    @app.post("/api/v1/runtime/integrations/tantra/reconcile")
    async def runtime_tantra_reconcile(
        request: VersionedContract,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            reconciliation=await companion.reconcile_tantra_traces(
                limit=limit
            )
        )

    @app.get("/api/v1/runtime/continuity")
    async def runtime_continuity() -> dict:
        return versioned_response(
            continuity=companion.continuity_status()
        )

    @app.post("/api/v1/runtime/continuity/check")
    async def runtime_continuity_check(
        request: VersionedContract,
        limit: int = Query(default=25, ge=1, le=500),
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            continuity=companion.run_continuity_check(limit=limit)
        )

    @app.get("/api/v1/runtime/dependencies/health")
    async def runtime_dependency_health(
        product_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            dependency_health=companion.dependency_health_status(
                product_id=product_id,
                limit=limit,
            )
        )

    @app.post("/api/v1/reconstruction/validate")
    async def validate_reconstruction(
        request: ReconstructionValidationRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            reconstruction=companion.validate_reconstruction_package(
                request.package
            )
        )

    @app.post("/api/v1/runtime/analysis")
    async def runtime_analysis(request: RuntimeAnalysisRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            **await companion.analyze_runtime(request)
        )

    @app.get("/api/v1/ecosystem/readiness")
    async def ecosystem_readiness() -> dict:
        return versioned_response(
            ecosystem=companion.ecosystem_readiness()
        )

    @app.get("/api/v1/ecosystem/contracts")
    async def ecosystem_contracts() -> dict:
        return versioned_response(
            ecosystem=companion.ecosystem_contracts()
        )

    @app.post("/api/v1/ecosystem/replay/validate")
    async def ecosystem_replay_validate(
        request: EcosystemReplayValidationRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            replay=companion.validate_ecosystem_replay(request.package)
        )

    @app.post("/api/v1/ecosystem/execute", status_code=201)
    async def ecosystem_execute(
        request: EcosystemExecutionRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            ecosystem=await companion.execute_ecosystem(request)
        )

    @app.get("/api/v1/ecosystem/executions")
    async def ecosystem_executions(
        status: str | None = None,
        session_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            executions=companion.ecosystem_executions(
                status=status,
                session_id=session_id,
                limit=limit,
            )
        )

    @app.get("/api/v1/ecosystem/executions/{execution_id}")
    async def ecosystem_execution(execution_id: str) -> dict:
        return versioned_response(
            ecosystem=companion.ecosystem_execution(execution_id)
        )

    @app.post("/api/v1/ecosystem/executions/{execution_id}/recover")
    async def ecosystem_recover(
        execution_id: str,
        request: VersionedContract,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            ecosystem=await companion.recover_ecosystem_execution(
                execution_id
            )
        )

    @app.get("/api/v1/ecosystem/executions/{execution_id}/replay")
    async def ecosystem_replay(execution_id: str) -> dict:
        return versioned_response(
            replay=companion.ecosystem_replay(execution_id)
        )

    @app.post("/api/v1/companion/messages")
    async def companion_message(request: CompanionMessageRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            **await companion.companion_message(request)
        )

    @app.post("/api/v1/companion/messages/stream")
    async def companion_message_stream(
        request: CompanionMessageRequest,
    ) -> StreamingResponse:
        validate_contract(request)

        async def events():
            yield json.dumps(
                versioned_response(
                    event="typing",
                    typing_state="started",
                ),
                ensure_ascii=False,
            ) + "\n"
            try:
                result = await companion.companion_message(request)
                yield json.dumps(
                    versioned_response(
                        event="execution_status",
                        status=result["status"],
                        task=result.get("task"),
                    ),
                    ensure_ascii=False,
                ) + "\n"
                yield json.dumps(
                    versioned_response(
                        event="message",
                        **result,
                    ),
                    ensure_ascii=False,
                ) + "\n"
            except Exception as exc:
                yield json.dumps(
                    versioned_response(
                        event="error",
                        error={
                            "code": "COMPANION_STREAM_ERROR",
                            "message": str(exc),
                            "retryable": False,
                        },
                    ),
                    ensure_ascii=False,
                ) + "\n"
            finally:
                yield json.dumps(
                    versioned_response(
                        event="typing",
                        typing_state="stopped",
                    ),
                    ensure_ascii=False,
                ) + "\n"

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
        )

    @app.get("/api/v1/companion/sessions/{session_id}/memory")
    async def companion_memory(
        session_id: str,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            memory=companion.companion_memory(session_id, limit=limit)
        )

    @app.get("/api/v1/companion/tasks")
    async def companion_tasks(
        session_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        return versioned_response(
            tasks=companion.companion_tasks(
                session_id=session_id,
                limit=limit,
            )
        )

    @app.get("/api/v1/companion/tasks/{task_id}")
    async def companion_task(task_id: str) -> dict:
        return versioned_response(task=companion.companion_task(task_id))

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

    @app.post("/api/v1/products/connect", status_code=201)
    async def connect_product(request: AttachmentRequest) -> dict:
        validate_contract(request)
        return versioned_response(
            connection=companion.attach(request.manifest)
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

    @app.post("/api/v1/product-exchanges", status_code=201)
    async def create_product_exchange(
        request: ProductExchangeRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            exchange=companion.create_product_exchange(request)
        )

    @app.get("/api/v1/product-exchanges")
    async def list_product_exchanges(
        source_product_id: str | None = None,
        target_product_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        include_expired: bool = False,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            exchanges=companion.product_exchanges(
                source_product_id=source_product_id,
                target_product_id=target_product_id,
                session_id=session_id,
                status=status,
                include_expired=include_expired,
                limit=limit,
            )
        )

    @app.get("/api/v1/products/{product_id}/exchange-inbox")
    async def product_exchange_inbox(
        product_id: str,
        status: str | None = None,
        include_expired: bool = False,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        return versioned_response(
            exchanges=companion.product_exchanges(
                target_product_id=product_id,
                status=status,
                include_expired=include_expired,
                limit=limit,
            )
        )

    @app.get("/api/v1/product-exchanges/{exchange_id}")
    async def get_product_exchange(exchange_id: str) -> dict:
        return versioned_response(
            exchange=companion.get_product_exchange(exchange_id)
        )

    @app.post("/api/v1/product-exchanges/{exchange_id}/ack")
    async def record_product_exchange_receipt(
        exchange_id: str,
        request: ProductExchangeAckRequest,
    ) -> dict:
        validate_contract(request)
        return versioned_response(
            exchange=companion.record_product_exchange_receipt(
                exchange_id,
                request,
            )
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

    @app.get("/api/v1/dispatches/{dispatch_id}/phases")
    async def get_dispatch_phases(dispatch_id: str) -> dict:
        return versioned_response(
            phases=companion.dispatch_phases(dispatch_id)
        )

    @app.get("/api/v1/dispatches/{dispatch_id}/proof")
    async def get_dispatch_proof(dispatch_id: str) -> dict:
        return versioned_response(
            proof=companion.dispatch_proof(dispatch_id)
        )

    @app.get("/api/v1/dispatches/{dispatch_id}/reconstruction")
    async def get_dispatch_reconstruction(dispatch_id: str) -> dict:
        return versioned_response(
            reconstruction=companion.dispatch_reconstruction(dispatch_id)
        )

    app.include_router(create_frontend_connector_router(companion))

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
