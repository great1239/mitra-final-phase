# Runtime Validation Screenshots

Captured on 2026-07-09 from local and hosted runtime surfaces. The local
capture used `http://127.0.0.1:8091` with a fixture manifest profile, one
session, dispatches, persistent supervision, and a real two-process failover
exercise. Fixture manifests are not production integrations and are no longer
loaded by production bootstrap.

These images are review aids. The API responses, tests, metrics, telemetry,
reconstruction, and depository artifacts remain the underlying validation
outputs.

| Screenshot | Source | Visible validation |
|---|---|---|
| `live-dashboard.jpg` | Local `/` | READY state, counts, supervisor, UTC snapshot |
| `runtime-startup.jpg` | Local dashboard startup section | startup phases and `completed_at` timestamps |
| `attached-products.jpg` | Local dashboard attachment table | fixture-profile attachment table and capability/intent counts |
| `replay-execution.jpg` | Swagger reconstruction request | dispatch ID, HTTP 200, `verified`, package hash, lineage |
| `metrics.jpg` | Local `/metrics` | Prometheus dispatch, latency, recovery, and health counters |
| `telemetry.jpg` | Local telemetry API | timestamped health, dispatch, reconstruction, and convergence events |
| `openapi.jpg` | Local `/docs` | OpenAPI 3.1 explorer and operator endpoints |
| `deployment.jpg` | Local runtime config API | production profile, data paths, supervisor, integrations, redaction |
| `health.jpg` | Local `/health` | healthy runtime with current instance and heartbeat |
| `recovery.jpg` | Swagger recovery request | HTTP 200, `recovered`, completion and heartbeat timestamps |
| `failover.jpg` | Local runtime instances API | primary READY and terminated peer STOPPED with timestamps |
| `hosted-runtime.jpg` | `https://mitra-live-runtime-sprint.vercel.app/` | public HTTPS runtime and READY dashboard |
| `runtime-analysis.jpg` | Swagger runtime analysis request | timestamped request, HTTP 200, deterministic matched response |
| `production-monitoring.jpg` | Local dashboard monitoring section | completed dispatches, peer states, heartbeats, startup timeline |

## Failover Procedure

1. Start primary instance `screenshot-primary` on port 8091.
2. Start peer `screenshot-failover-peer` on port 8092 against the same database.
3. Confirm both instances are registered.
4. Force-stop the peer process.
5. Wait beyond the configured stale heartbeat threshold.
6. Query the primary instance and confirm the peer is marked `STOPPED`.

No database row was inserted or edited to simulate this result.

## Timestamp Notes

Runtime screenshots show UTC timestamps where the runtime contract emits them:
dashboard snapshot, startup phases, replay lineage, telemetry events, runtime
heartbeats, recovery completion, failover stop time, and runtime-analysis
request time.

Prometheus exposition, OpenAPI, attachment catalog, deployment configuration,
and the currently deployed hosted dashboard do not emit observation timestamps.
Their capture date and source are recorded in this index.
