# Production Hardening

The production hardening work stays inside the companion runtime boundary. It
does not add product-specific branches and does not move BHIV product logic into
the runtime.

## Operational Surfaces

| Requirement | Implementation |
| --- | --- |
| FastAPI production deployment | Docker Compose runs the FastAPI app through `mitra-companion serve`, Uvicorn workers, proxy headers, production environment settings, and `/ready` healthchecks. |
| Container hardening | Docker runs as a non-root `mitra` user; Compose uses a read-only filesystem, explicit `/data` and `/tmp` write surfaces, dropped capabilities, `no-new-privileges`, restart policy, and resource bounds. |
| Multi-instance runtime support | Every process/container registers a runtime instance ID, heartbeats into shared storage, exposes `/api/v1/runtime/instances`, and can consume persisted attachments, sessions, routes, and dispatches created by another instance. |
| Structured logging | `RuntimeTelemetry` writes JSONL events to `MITRA_COMPANION_TELEMETRY_LOG_PATH` or `${MITRA_COMPANION_DATA_ROOT}/runtime-telemetry.jsonl`. |
| Runtime metrics | `GET /api/v1/runtime/metrics` returns counters, latency summaries, per-product latency, and last attachment health results. |
| Prometheus metrics | `GET /metrics` exposes the same counters and latency gauges in text exposition format. |
| OpenTelemetry | `mitra_companion.observability` instruments FastAPI and runtime dispatch/health spans; `docker-compose.yml` exports OTLP traces to `otel-collector`. |
| Health monitoring | `GET /health`, `GET /ready`, `POST /api/v1/attachments/health`, and `POST /api/v1/attachments/{product_id}/health`. |
| Dispatch latency metrics | `CompanionRuntime.dispatch` records latency for every completed or failed dispatch. |
| Attachment health monitoring | `CapabilityTransport.check_manifest_health` checks each manifest's published `health_endpoint`. |
| Failure telemetry | Transport failures emit `dispatch.failed` and degrade only the failed attachment. |
| Recovery validation | Healthy attachment checks restore degraded products through the published manifest. |
| Restart validation | Durable SQLite state preserves attachments, sessions, and routing across runtime recreation. |
| Load and concurrency testing | `test_bhiv_dispatch_concurrency_metrics_and_structured_log` runs concurrent UniGuru and Samruddhi dispatches; `scripts/load/k6_companion_runtime.js` provides the production k6 load profile. |
| Production readiness gate | `scripts/production_readiness_gate.py` and `test_production_readiness_gate.py` verify deployment controls, runbooks, SLOs, evidence files, and the clarified two-product BHIV scope. |

## Learning Kit Tactic Map

| Tactic | Artifact |
| --- | --- |
| FastAPI production deployment | `Dockerfile`, `docker-compose.yml`, `mitra_companion/cli.py`, `/ready` healthcheck |
| Production container posture | non-root user, read-only filesystem, restart policy, resource limits, dropped capabilities, log rotation |
| Multi-instance scaling | generated/configured `MITRA_COMPANION_INSTANCE_ID`, SQLite WAL shared state, `/api/v1/runtime/instances`, `test_multiple_runtime_instances_share_state_routes_and_dispatch` |
| OpenTelemetry | `mitra_companion/observability.py`, `deploy/otel-collector-config.yaml`, `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Prometheus metrics | `/metrics`, `RuntimeTelemetry.prometheus_text`, collector exporter `:8889` |
| Structured logging best practices | JSONL events with timestamp, service, environment, severity, event type, product, dispatch, latency, health, and recovery fields |
| Adapter architecture | `TransportAdapter`, `ManifestSourceAdapter`, HTTP/loopback transport registry |
| Contract-first integration | OpenAPI, JSON Schemas, manifest examples, integration contract catalog |
| Load testing using k6 | `scripts/load/k6_companion_runtime.js` |
| Production operations | `docs/PRODUCTION_READINESS.md`, `docs/OPERATIONS_RUNBOOK.md`, `docs/SLO_AND_CAPACITY.md`, `deploy/production.env.example` |

## Evidence Tests

| Test | Proof |
| --- | --- |
| `test_bhiv_products_attach_create_sessions_and_dispatch` | UniGuru and Samruddhi attach from manifests, create sessions, dispatch, and update per-product metrics. |
| `test_attachment_health_monitoring_and_recovery_validation` | Simulated product outage degrades the attachment; restored health validates recovery and dispatch resumes. |
| `test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes` | Runtime restart keeps BHIV attachments, session identity, and routing intact. |
| `test_multiple_runtime_instances_share_state_routes_and_dispatch` | Two runtime instances share persisted attachments and sessions; one instance dispatches routes created by the other, and the survivor continues after the first stops. |
| `test_bhiv_dispatch_concurrency_metrics_and_structured_log` | Thirty concurrent dispatches complete and emit structured telemetry. |
| `test_observability_api_exposes_metrics_telemetry_and_attachment_health` | API surfaces for metrics, Prometheus output, telemetry, and health checks are live. |
| `test_production_tactics_are_deployed_as_first_class_artifacts` | FastAPI deployment, OpenTelemetry, Prometheus, structured logging, adapters, contracts, and k6 artifacts remain present. |
| `test_production_readiness_gate.py` | Enforces container safety controls, operations docs, environment template, and the production-readiness gate script. |

## Graceful Degradation Model

1. A transport failure marks only the affected product attachment as
   `DEGRADED`.
2. Other `ATTACHED` products remain discoverable and dispatchable.
3. A degraded product is discoverable but not routable.
4. A later healthy published health check revalidates the manifest, restores the
   attachment to `ATTACHED`, and records a recovery event.

## BHIV Product Health Notes

UniGuru publishes `GET /health` in `uniguru_ai/backend/service/api.py`.
Samruddhi publishes `GET /tools/health` in
`trade-bot-main/backend/api_server.py`. The manifests record those endpoints, so
the runtime can validate both product attachments without any product-specific
runtime branches.
