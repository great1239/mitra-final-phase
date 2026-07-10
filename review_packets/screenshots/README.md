# Runtime Validation Screenshots

Captured on July 11, 2026 IST / July 10, 2026 UTC from a live local
production-validation run plus the public Vercel host.

The local run used real product services, not simulated attachments:

- UniGuru: `http://127.0.0.1:8000`, `GET /health` returned `status: ok`
  with the UniGuru knowledge base loaded.
- Samruddhi Trade Bot: `http://127.0.0.1:8001`, `GET /tools/health`
  returned `status: healthy` with trained models available.
- Mitra runtime: `http://127.0.0.1:8091`, bootstrapped from local copies of
  the production Samruddhi manifests with only `base_url` redirected to the
  two live local product services.

Pretty-print evidence pages were served from `http://127.0.0.1:8093` only for
screen capture readability. The data shown on those pages is copied from live
Mitra API responses in `.codex-tmp/live-run/live_validation_outputs.json`.

| Screenshot | Source | Visible validation |
|---|---|---|
| `live-dashboard.jpg` | Local `/` | READY state, 2 attached products, 2 sessions, 2 dispatches, attached Samruddhi products |
| `runtime-startup.jpg` | Pretty `/api/v1/runtime/startup` | startup phases with UTC timestamps |
| `attached-products.jpg` | Pretty `/api/v1/attachments` + health | UniGuru and Trade Bot both `ATTACHED` and `healthy` |
| `replay-execution.jpg` | Pretty dispatch proof/reconstruction | replay `verified`, full scope coverage, both dispatches `COMPLETED` |
| `metrics.jpg` | Pretty `/metrics` | Prometheus counters and runtime metrics from the live run |
| `telemetry.jpg` | Pretty `/api/v1/runtime/telemetry` | timestamped runtime, dispatch, health, recovery, and failover events |
| `openapi.jpg` | Local `/docs` | OpenAPI 3.1 explorer and operator endpoints |
| `deployment.jpg` | Pretty `/api/v1/runtime/config` | production-local-validation config, manifest policy, data paths |
| `health.jpg` | Pretty `/health` | healthy runtime with counts and current instance |
| `recovery.jpg` | Pretty `/api/v1/runtime/recovery` | initial recovery and post-failover recovery returned `recovered` |
| `failover.jpg` | Pretty runtime instances | primary `READY`, peer `screenshot-failover-peer` marked `STOPPED` |
| `hosted-runtime.jpg` | `https://mitra-live-runtime-sprint.vercel.app/` | public HTTPS hosted runtime dashboard |
| `runtime-analysis.jpg` | Pretty `/api/v1/runtime/analysis` | capability fit matrix and recommended candidate output |
| `production-monitoring.jpg` | Pretty status/metrics/telemetry/instances | live counters, instance states, and monitoring payloads |
| `runtime-dashboard.png` | Local `/` | PNG copy of refreshed dashboard screenshot |
| `runtime-openapi.png` | Local `/docs` | PNG copy of refreshed OpenAPI screenshot |
| `runtime-intents.png` | Pretty `/api/v1/intents` | attached intent registry for UniGuru and Trade Bot |
| `runtime-health.png` | Pretty `/health` | PNG copy of refreshed runtime health evidence |

## Live Dispatches

- UniGuru dispatch: `dsp_e2b2f940229f4f1e892481a511c9375f`, status
  `COMPLETED`. Mitra used the published `/ask` route and then the configured
  `/new_rag` fallback when UniGuru returned its safe fallback response.
- Trade Bot dispatch: `dsp_39d5b705280e4bb589c62f1e2a6d08c3`, status
  `COMPLETED`. The product returned a live AAPL prediction with action
  `SHORT` and data source `REALTIME_YAHOO_FINANCE`.

## Failover Procedure

1. Start primary Mitra instance on port `8091`.
2. Start peer Mitra instance `screenshot-failover-peer` on port `8092`
   against the same runtime database.
3. Confirm both instances are registered.
4. Stop only the peer process.
5. Wait beyond the configured stale heartbeat threshold.
6. Call primary recovery and confirm the peer is marked `STOPPED`.

No database row was inserted or edited to simulate the failover result.
