# Production Readiness Gate

This document is the reviewer-facing production gate for the Mitra Companion
Runtime assignment. It is intentionally stricter than the functional tests:
the runtime must be deployable, observable, recoverable, and operable without
product-specific code paths.

## Gate Status

| Gate | Status | Evidence |
| --- | --- | --- |
| Container runs without root privileges | Met | `Dockerfile` creates and runs as `mitra`; Compose also drops Linux capabilities and enables `no-new-privileges`. |
| Multiple runtime instances | Met | Runtime instances register unique IDs, heartbeat into shared state, expose `/api/v1/runtime/instances`, and share attachments, sessions, routes, and dispatches through persisted storage. |
| Persistent runtime process | Met | Runtime startup enables a background supervisor by default for heartbeat refresh, stale peer cleanup, interrupted task recovery, and periodic attachment maintenance. |
| Health and readiness probes | Met | Image and Compose healthchecks call `/ready`; API exposes `/health` and `/api/v1/runtime/status`. |
| Restart and graceful shutdown posture | Met | Compose uses `restart: unless-stopped`, `init: true`, and `stop_grace_period: 30s`; runtime records lifecycle transitions. |
| Writable surface is constrained | Met | Compose sets the service read-only with explicit `/data` volume and `/tmp` tmpfs. |
| Runtime resources are bounded | Met | Compose declares CPU and memory limits/reservations and `pids_limit`. |
| Structured operational logs | Met | JSONL telemetry records timestamp, service, environment, severity, event type, product, dispatch, latency, failure, health, and recovery fields. |
| Metrics and tracing | Met | `/metrics`, `/api/v1/runtime/metrics`, FastAPI OpenTelemetry instrumentation, runtime spans, and OTLP collector config. |
| Load and concurrency evidence | Met | `scripts/load/k6_companion_runtime.js` plus concurrent dispatch tests. |
| Failure containment and recovery | Met | Simulated product failure degrades only the affected attachment and healthy checks restore it. |
| Contract-first ecosystem integration | Met | UniGuru and Samruddhi attach through published manifests, schemas, OpenAPI, adapter ports, and contract tests. |
| Operational documentation | Met | `docs/OPERATIONS_RUNBOOK.md`, `docs/SLO_AND_CAPACITY.md`, `docs/PRODUCTION_HARDENING.md`, and `docs/PRODUCTION_TACTICS.md`. |
| Automated production-readiness gate | Met | `scripts/production_readiness_gate.py` and `test_production_readiness_gate.py`. |

## Required Production Commands

```powershell
docker compose up -d --wait
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
pytest -q
```

## Production Acceptance Boundary

The runtime is production-ready for the assignment-scoped independent BHIV
products in this workspace: UniGuru and Samruddhi/trade-bot. They consume the
runtime through published manifests, adapter interfaces, versioned API
contracts, and generic dispatch paths only.

The runtime is not restricted to a single process. Each runtime process or
container has a unique runtime instance ID and shares durable ecosystem state
through the configured database path. A load balancer can route clients across
instances while sessions, attachments, routes, and dispatch receipts remain
available to every instance. It is also not a single-invocation runtime: normal
service startup leaves the persistent supervisor running until shutdown, so the
process keeps its heartbeat fresh, cleans stale peer records, and closes
interrupted companion tasks after restart.

The original PDF also contains a three-product target. If a third real BHIV
product is supplied later, the runtime path is already production-ready:
publish a manifest, validate the contract, attach, create a session, dispatch,
and capture evidence without changing runtime code.
