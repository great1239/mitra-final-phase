# Mitra Runtime Handover

This is the clean-room rebuild path for the Mitra Companion Runtime. It assumes
the engineer has the repository and no prior sprint context.

## 1. Runtime Boundary

Mitra owns lifecycle, sessions, scoped context, manifest attachment,
capability discovery, routing, transport, product exchange, dispatch receipts,
telemetry, recovery, deterministic reconstruction, and runtime-owned immutable
artifact export.

Mitra does not own product business logic, governance decisions, ecosystem
certification, external replay authority, or Central Depository acceptance.

## 2. Prerequisites

Required:

- Git
- Python 3.11 or newer
- PowerShell, Git Bash, or another shell

Required for the production container:

- Docker Engine with Compose v2

Optional:

- k6 for sustained load testing
- pnpm and Vercel CLI for the public serverless deployment

## 3. Repository Layout

```text
pratham/companion-runtime/  FastAPI, composition, storage, telemetry
pratham/session-runtime/    durable sessions and resume tokens
pratham/context-runtime/    isolated context partitions and transfer
pratham/intent-router/      manifest-derived routing
pratham/attachment-runtime/ manifest validation and attachment state
contracts/                  OpenAPI, JSON Schemas, catalogs, examples,
                            production manifest directory
deploy/                     production environment and telemetry config
scripts/                    readiness, hosted validation, demo, load test
docs/                       architecture, operations, integration, handover
```

Runtime implementation must remain product-neutral. Add products through
published manifests and add protocols through transport adapters.

## 4. Clean Python Rebuild

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest
python scripts/production_readiness_gate.py
```

Expected result:

- all tests pass;
- the readiness gate reports `production_readiness_gate: passed`;
- no evidence or documentation generator is required.

Git Bash activation:

```bash
source .venv/Scripts/activate
```

## 5. Local Runtime

```powershell
$env:MITRA_COMPANION_MANIFEST_DIRECTORY="contracts\examples"
$env:MITRA_COMPANION_ENVIRONMENT="development"
$env:MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS="true"
$env:MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS="true"
$env:MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS="false"
mitra-companion validate
mitra-companion serve --port 8090
```

Check in another shell:

```powershell
curl.exe http://127.0.0.1:8090/health
curl.exe http://127.0.0.1:8090/ready
curl.exe http://127.0.0.1:8090/api/v1/runtime/status
curl.exe http://127.0.0.1:8090/api/v1/runtime/integrations
curl.exe http://127.0.0.1:8090/openapi.json
```

The dashboard is at `http://127.0.0.1:8090/` and Swagger UI is at
`http://127.0.0.1:8090/docs`.

## 6. Configuration

Start from `deploy/production.env.example`. The minimum durable configuration
is:

| Variable | Purpose |
|---|---|
| `MITRA_COMPANION_DATA_ROOT` | writable persistent root |
| `MITRA_COMPANION_DATABASE_PATH` | SQLite database |
| `MITRA_COMPANION_MANIFEST_DIRECTORY` | product manifest directory |
| `MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS` | development-only fixture opt-in |
| `MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS` | development-only simulation opt-in |
| `MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS` | development-only loopback opt-in |
| `MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS` | development-only localhost opt-in |
| `MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS` | require approved bootstrap marker |
| `MITRA_COMPANION_TELEMETRY_LOG_PATH` | structured runtime telemetry |
| `MITRA_COMPANION_LOG_PATH` | structured production log |
| `MITRA_COMPANION_INSTANCE_ID` | optional fixed instance identity |
| `MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED` | supervisor and heartbeat |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | optional trace collector |

BHIV integrations:

| Variable | Contract |
|---|---|
| `MITRA_BHIV_ASHMIT_BASE_URL` | Ashmit health contract |
| `MITRA_BHIV_BUCKET_BASE_URL` | Bucket artifact contracts |
| `MITRA_BHIV_INSIGHTFLOW_INGEST_URL` | InsightFlow trace ingest |
| `MITRA_BHIV_KARMA_BASE_URL` | Karma append contracts |
| `MITRA_BHIV_PRANA_BASE_URL` | PRANA strict/core forwarding |

Use `_FILE` variants or `MITRA_COMPANION_SECRETS_DIR` for secrets. Runtime
configuration APIs expose only redacted presence information.

## 7. Durable Docker Rebuild

```powershell
docker compose build --pull
docker compose up -d --wait
docker compose ps
docker compose logs --tail 200 companion-runtime
```

The Compose profile provides:

- a non-root, read-only runtime container;
- persistent SQLite state in `companion-runtime-data`;
- restart policy, health check, resource limits, and dropped capabilities;
- OpenTelemetry Collector wiring.

Run:

```powershell
python scripts/validate_hosted_runtime.py http://127.0.0.1:8090
k6 run scripts/load/k6_companion_runtime.js
```

The hosted validator submits real API data and fails when dispatch or replay
outputs do not match the submitted payload.

## 8. Product Integration

Production deployments load startup manifests only from `contracts/production`
by default. `contracts/examples` is reserved for tests, local demos, and
contract documentation.

1. Validate the manifest against
   `contracts/schemas/product-attachment.schema.json`.
2. Connect it with `POST /api/v1/products/connect`.
3. Create a session with `POST /api/v1/sessions`.
4. Dispatch an explicit registered intent with
   `POST /api/v1/intents/dispatch`.
5. Verify the response, dispatch phases, reconstruction, telemetry, and module
   integration responses.

No product-specific branch belongs in `CompanionRuntime` or `IntentRouter`.
See `docs/INTEGRATION_GUIDE.md`.

## 9. Deployment Choice

Use Docker or `render.yaml` when durable state, recovery, long-duration
execution, or multiple runtime instances are required.

Use `vercel.json` only for the public serverless API. Its `/tmp` database is
ephemeral and persistent supervision is disabled. Do not use a Vercel
deployment as proof of durable failover or disaster recovery.

## 10. Central Depository Handover

For each accepted dispatch:

1. retain the original dispatch response;
2. fetch `/api/v1/dispatches/{dispatch_id}/reconstruction`;
3. fetch
   `/api/v1/runtime/depository?subject_type=dispatch&subject_id={dispatch_id}`;
4. verify artifact hashes and lineage;
5. send those actual API outputs to the external Central Depository consumer.

Follow `docs/CENTRAL_DEPOSITORY_HANDOVER.md`. Do not generate a replacement
proof document or recursively embed depository snapshots.

## 11. Operational Acceptance

Before ownership transfer, verify:

- `/health` and `/ready` return HTTP 200;
- real manifests attach and declared intents are discoverable;
- a submitted payload is present in the completed dispatch response;
- deterministic reconstruction reproduces the submitted input and output;
- every required BHIV module call has a response or an explicit skipped/error
  result;
- subject-filtered depository artifacts belong to the requested lineage;
- metrics and telemetry include the dispatch;
- recovery leaves the runtime ready;
- a clean restart preserves durable sessions, attachments, and routes.

## 12. Troubleshooting

| Symptom | Check |
|---|---|
| Runtime is not ready | `/api/v1/runtime/startup`, writable data root |
| Product cannot route | attachment state, intent ID, manifest schema |
| Dispatch fails | phase journal, telemetry, product health response |
| PRANA is skipped | Karma must return `appended` first |
| Strict forwarding fails | canonical request bytes and SHA-256 headers |
| Replay is unverified | component hashes, lineage chain, missing artifacts |
| State disappears | serverless `/tmp` deployment or missing persistent volume |
| Peers become stale | unique instance IDs and heartbeat configuration |

For recovery and rollback, use `docs/OPERATIONS_RUNBOOK.md`.
