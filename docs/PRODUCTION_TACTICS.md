# Production Tactics Compliance

| Tactic | Artifact |
| --- | --- |
| FastAPI production deployment | `mitra_companion.api`, `mitra-companion serve`, Docker Compose |
| OpenTelemetry | `mitra_companion.observability`, collector config |
| Prometheus metrics | `/metrics`, collector exporter `:8889` |
| Structured logging | telemetry JSONL and production process JSONL |
| Production configuration loading | env file, profile, redacted config API |
| Production secrets management | mounted `*_FILE` secrets, redacted secrets API |
| Adapter architecture | `TransportAdapter`, `ManifestSourceAdapter` |
| Contract-first integration | JSON Schemas, OpenAPI, integration catalog |
| Multi-instance runtime operation | runtime instances and shared durable state |
| Runtime startup, restart, and recovery | startup manager, restart, recovery, reconcile endpoints |
| Product-to-product exchange | product connect, exchange inbox, receipt endpoint |
| Load testing using k6 | `scripts/load/k6_companion_runtime.js` |
| Production readiness gate | `scripts/production_readiness_gate.py` |

## Commands

```powershell
docker compose up -d --wait
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
pytest -q
```
