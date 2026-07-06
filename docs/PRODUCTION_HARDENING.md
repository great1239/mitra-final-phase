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
| Attached-product information sharing | Connected products use `/api/v1/product-exchanges` and `/api/v1/products/{product_id}/exchange-inbox` as a durable mailbox with acknowledgement state. |
| Runtime startup manager | FastAPI lifespan uses `RuntimeStartupManager` to load production configuration, start the runtime process, attach configured manifest sources, and verify the persistent supervisor. `GET /api/v1/runtime/startup` exposes the latest phase report. |
| Persistent runtime supervisor | The runtime starts a background supervisor by default. It refreshes heartbeats, marks stale peers as stopped, recovers interrupted companion tasks, and runs periodic attachment maintenance while the service process remains alive. |
| Graceful restart and recovery controls | `POST /api/v1/runtime/restart`, `POST /api/v1/runtime/recovery`, and `POST /api/v1/runtime/instances/reconcile` run controlled restart/recovery paths without changing product code. |
| Production configuration and secrets | `RuntimeSettings.from_environment` supports env-file loading, mounted secret files, redacted config summaries, and `GET /api/v1/runtime/config` plus `GET /api/v1/runtime/secrets`. |
| Previous submission systems reused | Source-scope catalog, manifest-backed capability catalog, public contract summaries, semantic-version dependency validation, seven-phase dispatch checkpoints, and portable dispatch proof bundles are implemented as Mitra-owned runtime surfaces. |
| Structured logging | `RuntimeTelemetry` writes JSONL events to `MITRA_COMPANION_TELEMETRY_LOG_PATH`; process-level production logs write JSONL to `MITRA_COMPANION_LOG_PATH` with stdout control and log-level selection. |
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
| Persistent multi-instance scaling | generated/configured `MITRA_COMPANION_INSTANCE_ID`, persistent supervisor heartbeat, stale peer cleanup, interrupted task recovery, SQLite WAL shared state, `/api/v1/runtime/instances`, `/api/v1/runtime/instances/reconcile`, `test_multiple_runtime_instances_share_state_routes_and_dispatch` |
| Product-to-product exchange | `ProductExchangeRequest`, `ProductExchangeAckRequest`, `product_exchanges`, `product_exchange_targets`, `/api/v1/product-exchanges`, `/api/v1/products/{product_id}/exchange-inbox`, `test_product_exchange_api_contract` |
| Production startup and restart | `RuntimeStartupManager`, `/api/v1/runtime/startup`, `/api/v1/runtime/restart`, `/api/v1/runtime/recovery`, `test_runtime_operations_api_exposes_production_mode` |
| Production configuration and secrets | `MITRA_COMPANION_ENV_FILE`, `MITRA_COMPANION_CONFIG_PROFILE`, `MITRA_COMPANION_SECRETS_DIR`, `*_FILE` secret inputs, `/api/v1/runtime/config`, `/api/v1/runtime/secrets`, `test_production_configuration_loads_env_file_and_secret_files` |
| Production process logging | `mitra_companion.production_logging`, `MITRA_COMPANION_LOG_PATH`, `MITRA_COMPANION_LOG_LEVEL`, `MITRA_COMPANION_LOG_TO_STDOUT`, `test_production_logging_writes_process_events` |
| Prior runtime feature reuse | `SourceScopeRegistry`, `CapabilityDependencyRegistry`, `DispatchProofBuilder`, source-scope catalog, seven-phase dispatch journal, `/api/v1/runtime/source-scope`, `/api/v1/runtime/capability-catalog`, `/api/v1/dispatches/{dispatch_id}/phases`, `/api/v1/dispatches/{dispatch_id}/proof` |
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
| `test_persistent_runtime_supervisor_refreshes_heartbeat` | A started runtime remains alive as a persistent service loop and refreshes its heartbeat without an external request. |
| `test_persistent_runtime_marks_stale_peer_instances` | A surviving runtime marks a peer with an expired heartbeat as stopped. |
| `test_persistent_runtime_recovers_interrupted_tasks_on_restart` | Restart with the same runtime instance ID fails a previously running companion task with a durable recovery record. |
| `test_product_exchange_runtime_persists_inbox_and_acknowledgement` | Source product creates a durable exchange envelope; target product reads inbox and records consumption. |
| `test_product_exchange_api_contract` | Product connection, exchange creation, target inbox, and acknowledgement work through public APIs. |
| `test_production_configuration_loads_env_file_and_secret_files` | Production config loads from an env file and secret files while API summaries redact secret values. |
| `test_runtime_operations_api_exposes_production_mode` | Startup, restart, recovery, redacted config/secrets, and instance reconciliation APIs are live. |
| `test_production_logging_writes_process_events` | Runtime start, recovery, and stop emit JSONL production process logs. |
| `test_loopback_dispatch_receives_only_declared_context` | Dispatch creates seven durable phase checkpoints and a portable proof bundle for the product response. |
| `test_capability_catalog_validates_manifest_dependencies` | Manifest-declared product/capability dependencies and public contracts validate through the runtime capability catalog. |
| `test_source_scope_catalog_validates_previous_submission_imports` | Previous-submission features and externalized systems validate against the source-scope schema. |
| `test_runtime_exposes_source_scope_and_uses_it_in_analysis` | Runtime API, status, and analysis expose prior-submission import hints. |
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
