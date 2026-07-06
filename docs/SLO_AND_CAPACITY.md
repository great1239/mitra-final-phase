# SLO And Capacity Targets

Small validation targets are used here because product fixtures run locally.
The same signals apply to larger deployments.

## Service Objectives

| Signal | Target | Evidence |
| --- | --- | --- |
| Readiness | `/ready` returns 200 while accepting work | Compose healthcheck |
| Dispatch success | at least 98% successful k6 checks | k6 `checks: rate>0.98` |
| Dispatch latency | p95 under 1500 ms in k6 profile | k6 threshold |
| Attachment recovery | degraded product returns to `ATTACHED` after healthy check | recovery test |
| Restart recovery | attachments, sessions, and routes survive restart | restart test |
| Multi-instance continuity | one instance can consume state created by another | multi-instance test |
| Persistent heartbeat freshness | live process refreshes heartbeat without traffic | supervisor test |
| Stale peer convergence | expired peers are removed from active set | stale-peer test |
| Product exchange delivery | target inbox receives and records exchange receipt | product-exchange tests |

## Capacity Envelope

- `MITRA_COMPANION_UVICORN_WORKERS=2`
- unique `MITRA_COMPANION_INSTANCE_ID` per process
- persistent runtime enabled
- heartbeat interval: 5 seconds
- stale peer window: 30 seconds
- CPU limit: `1.0`
- memory limit: `768M`
- process limit: `256`

Before changing the envelope:

```powershell
k6 run scripts/load/k6_companion_runtime.js
pytest -q
```

## Escalate When

- `/ready` fails longer than one probe interval;
- runtime startup lacks `runtime_process_started`;
- heartbeat is stale for two intervals;
- dispatch failures exceed the budget;
- product remains `DEGRADED` after its health endpoint is healthy;
- logs or `/metrics` stop updating.
