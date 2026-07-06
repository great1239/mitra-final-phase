# Production Readiness Gate

This is the reviewer-facing readiness summary. Detailed behavior lives in
OpenAPI, tests, and the runbook.

## Gate Status

| Gate | Status | Evidence |
| --- | --- | --- |
| Container runs without root privileges | Met | `Dockerfile`, Compose hardening |
| Multiple runtime instances | Met | instance table, heartbeats, shared storage |
| Runtime startup manager | Met | startup phases and `/api/v1/runtime/startup` |
| Persistent runtime process | Met | supervisor heartbeat, stale-peer cleanup, task recovery |
| Production configuration loading | Met | env-file support and redacted config API |
| Production secrets management | Met | mounted secret files and redacted secrets API |
| Graceful restart and recovery | Met | restart, recovery, and reconcile endpoints |
| Product exchange mailbox | Met | product connect, exchange inbox, acknowledgement tests |
| Observability | Met | JSONL logs, metrics, telemetry, OpenTelemetry |
| Automated production-readiness gate | Met | `scripts/production_readiness_gate.py` |

## Required Commands

```powershell
docker compose up -d --wait
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
pytest -q
```

## Production Acceptance Boundary

The runtime is production-ready for the assignment-scoped independent BHIV
products in this workspace. New products attach by manifest and can share
explicit payloads through product exchanges without runtime code changes.

Downstream authority, validation, provenance, convergence, and review systems
remain outside Mitra and consume dispatch receipts, phase journals, proof
bundles, or product exchange payloads.
