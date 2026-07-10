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

- sustained acceptance: 5 VUs, p95 `803.92 ms`, 0% failures;
- observed stress ceiling: 15 VUs, p95 `3.74 s`, 0% failures;
- 15 VUs exceeds the current `1.5 s` latency objective;
- `MITRA_COMPANION_SQLITE_SYNCHRONOUS=NORMAL` for the measured profile;
- `MITRA_COMPANION_UVICORN_WORKERS=1` per SQLite-backed container
- unique `MITRA_COMPANION_INSTANCE_ID` per process
- persistent runtime enabled
- heartbeat interval: 5 seconds
- stale peer window: 30 seconds
- CPU limit: `1.0`
- memory limit: `768M`
- process limit: `256`

For additional capacity, run multiple containers/processes with unique
runtime instance IDs and shared durable storage rather than multiple Uvicorn
workers inside one SQLite-backed container.

Before changing the envelope:

```powershell
$env:MAX_VUS="5"
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
