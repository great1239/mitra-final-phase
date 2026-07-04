# SLO And Capacity Targets

These targets define the minimum production-readiness bar for the assignment
runtime. They are intentionally small because the validation environment uses
local product fixtures, but the same signals scale to a larger deployment.

## Service Level Objectives

| Signal | Target | Evidence |
| --- | --- | --- |
| Readiness | `/ready` returns HTTP 200 while accepting work | FastAPI readiness route and Compose healthcheck |
| Dispatch success | At least 98% successful dispatch checks under k6 load | `scripts/load/k6_companion_runtime.js` threshold `checks: rate>0.98` |
| Dispatch failure rate | Less than 2% HTTP request failures under k6 load | k6 threshold `http_req_failed: rate<0.02` |
| Dispatch latency | p95 under 1500 ms in the k6 profile | k6 threshold `http_req_duration: p(95)<1500` |
| Attachment recovery | degraded attachment returns to `ATTACHED` after healthy published health check | `test_attachment_health_monitoring_and_recovery_validation` |
| Restart recovery | attachments, sessions, and routes survive runtime restart | `test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes` |
| Multi-instance continuity | one runtime instance can consume attachments and sessions created by another instance | `test_multiple_runtime_instances_share_state_routes_and_dispatch` |

## Capacity Envelope

The production Compose profile starts with:

- `MITRA_COMPANION_UVICORN_WORKERS=2`
- generated or orchestrator-assigned unique `MITRA_COMPANION_INSTANCE_ID`
- CPU limit: `1.0`
- memory limit: `768M`
- process limit: `256`
- read-only filesystem with explicit `/data` and `/tmp` write surfaces

Before scaling beyond this envelope, rerun:

```powershell
k6 run scripts/load/k6_companion_runtime.js
pytest -q
```

## Escalation Criteria

Escalate as an operational incident when:

- `/ready` fails for more than one probe interval after startup.
- `dispatch.failed` events rise above the k6 failure budget.
- a product remains `DEGRADED` after its published health endpoint is healthy.
- telemetry stops writing JSONL records or `/metrics` stops exposing counters.
