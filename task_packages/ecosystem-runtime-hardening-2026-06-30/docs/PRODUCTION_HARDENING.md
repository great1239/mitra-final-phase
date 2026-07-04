# Production Hardening

The production hardening work stays inside the companion runtime boundary. It
does not add product-specific branches and does not move BHIV product logic into
the runtime.

## Operational Surfaces

| Requirement | Implementation |
| --- | --- |
| Structured logging | `RuntimeTelemetry` writes JSONL events to `MITRA_COMPANION_TELEMETRY_LOG_PATH` or `${MITRA_COMPANION_DATA_ROOT}/runtime-telemetry.jsonl`. |
| Runtime metrics | `GET /api/v1/runtime/metrics` returns counters, latency summaries, per-product latency, and last attachment health results. |
| Prometheus metrics | `GET /metrics` exposes the same counters and latency gauges in text exposition format. |
| Health monitoring | `GET /health`, `GET /ready`, `POST /api/v1/attachments/health`, and `POST /api/v1/attachments/{product_id}/health`. |
| Dispatch latency metrics | `CompanionRuntime.dispatch` records latency for every completed or failed dispatch. |
| Attachment health monitoring | `CapabilityTransport.check_manifest_health` checks each manifest's published `health_endpoint`. |
| Failure telemetry | Transport failures emit `dispatch.failed` and degrade only the failed attachment. |
| Recovery validation | Healthy attachment checks restore degraded products through the published manifest. |
| Restart validation | Durable SQLite state preserves attachments, sessions, and routing across runtime recreation. |
| Load and concurrency testing | `test_bhiv_dispatch_concurrency_metrics_and_structured_log` runs concurrent UniGuru AI and Trade Bot Main dispatches. |

## Evidence Tests

| Test | Proof |
| --- | --- |
| `test_bhiv_products_attach_create_sessions_and_dispatch` | Both BHIV products attach from manifests, create sessions, dispatch, and update per-product metrics. |
| `test_attachment_health_monitoring_and_recovery_validation` | Simulated product outage degrades the attachment; restored health validates recovery and dispatch resumes. |
| `test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes` | Runtime restart keeps BHIV attachments, session identity, and routing intact. |
| `test_bhiv_dispatch_concurrency_metrics_and_structured_log` | Thirty concurrent dispatches complete and emit structured telemetry. |
| `test_observability_api_exposes_metrics_telemetry_and_attachment_health` | API surfaces for metrics, Prometheus output, telemetry, and health checks are live. |

## Graceful Degradation Model

1. A transport failure marks only the affected product attachment as
   `DEGRADED`.
2. Other `ATTACHED` products remain discoverable and dispatchable.
3. A degraded product is discoverable but not routable.
4. A later healthy published health check revalidates the manifest, restores the
   attachment to `ATTACHED`, and records a recovery event.

## BHIV Product Health Notes

UniGuru AI publishes `GET /health` in `uniguru_ai/backend/service/api.py`.
Trade Bot Main publishes `GET /tools/health` in
`trade-bot-main/backend/api_server.py`. The manifests record those endpoints, so
the runtime can validate both product attachments without any product-specific
runtime branches.
