# Production Tactics Compliance

This assignment uses the requested production tactics as runtime artifacts, not
as external notes. The implementation remains contract-first and adapter-driven:
UniGuru and Samruddhi attach through manifests only, and no product-specific
runtime branch is introduced.

| Tactic | Production use |
| --- | --- |
| FastAPI production deployment | `mitra_companion.api.create_app` exposes the runtime API; `mitra-companion serve` runs Uvicorn from an import string with worker and proxy-header controls; Docker Compose sets production environment variables and a readiness healthcheck. |
| OpenTelemetry | `mitra_companion.observability.configure_opentelemetry` instruments FastAPI and runtime dispatch/attachment-health spans; Compose exports OTLP traces to the bundled OpenTelemetry Collector. |
| Prometheus metrics | `GET /metrics` exposes runtime counters and latency gauges; the OpenTelemetry Collector also exposes its Prometheus exporter on `:8889`. |
| Structured logging best practices | `RuntimeTelemetry` writes JSONL records with timestamp, service, environment, severity, event type, product, dispatch, latency, health, failure, and recovery fields. |
| Adapter architecture | `TransportAdapter` and `ManifestSourceAdapter` ports keep product protocols and manifest discovery behind published interfaces. |
| Contract-first integration | Product manifests, JSON Schema contracts, OpenAPI, and the integration catalog define the integration surface before runtime dispatch. |
| Multi-instance runtime operation | Runtime instance IDs, shared durable state, and `/api/v1/runtime/instances` prove the runtime is not limited to a single process. |
| Load testing using k6 | `scripts/load/k6_companion_runtime.js` attaches UniGuru and Samruddhi, creates sessions, loads context, routes intents, dispatches both products, and enforces error and latency thresholds. |
| Production readiness gate | `scripts/production_readiness_gate.py` blocks release if deployment controls, observability evidence, runbook, SLOs, or the product access boundary are missing. |

## Production Commands

```powershell
docker compose up -d --wait
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
```

Useful endpoints:

- Runtime dashboard: `http://127.0.0.1:8090/`
- Readiness: `http://127.0.0.1:8090/ready`
- Runtime Prometheus metrics: `http://127.0.0.1:8090/metrics`
- Collector Prometheus exporter: `http://127.0.0.1:8889/metrics`
- Runtime status with OpenTelemetry status: `http://127.0.0.1:8090/api/v1/runtime/status`
- Runtime instances: `http://127.0.0.1:8090/api/v1/runtime/instances`
