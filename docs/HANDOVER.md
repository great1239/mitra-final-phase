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

Completion is determined by runtime output, not by connector presence or a
diagram. Keep these three results separate:

- `python -m pytest` proves implementation behavior with controlled inputs;
- `python scripts/production_readiness_gate.py` checks repository packaging and
  reports external blockers, but is not interoperability evidence;
- `python scripts/validate_ecosystem_runtime.py` submits real product data and
  is the acceptance gate for the configured owner topology.

A configured endpoint, HTTP health response, generated report, or screenshot
does not replace a completed response-bearing ecosystem execution.

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
- the readiness gate reports `implementation_readiness: passed`; it may report
  `production_readiness_gate: blocked` when public owner endpoints or required
  screenshots are unavailable, and its `blockers` array must explain why;
- no evidence or documentation generator is required.

Git Bash activation:

```bash
source .venv/Scripts/activate
```

## 5. Core-Only Local Runtime

This path verifies the Mitra process and direct product contract surfaces. It
does not start Raj, KESHAV, Ashmit, Bucket, Karma, PRANA, InsightFlow, or either product
owner and therefore is not full interoperability evidence.

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
| `MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON` | optional published-origin to private-runtime-origin JSON map; defaults to `{}` |
| `MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS` | development-only fixture opt-in |
| `MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS` | development-only simulation opt-in |
| `MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS` | development-only loopback opt-in |
| `MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS` | development-only localhost opt-in |
| `MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS` | require approved bootstrap marker |
| `MITRA_COMPANION_TELEMETRY_LOG_PATH` | structured runtime telemetry |
| `MITRA_COMPANION_LOG_PATH` | structured production log |
| `MITRA_COMPANION_INSTANCE_ID` | optional fixed instance identity |
| `MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED` | supervisor and heartbeat |
| `MITRA_COMPANION_COORDINATION_LEASE_SECONDS` | shared-maintenance ownership expiry |
| `MITRA_COMPANION_CONTINUITY_DISPATCH_LIMIT` | dispatches checked per scheduled scan |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | optional trace collector |

BHIV integrations:

| Variable | Contract |
|---|---|
| `MITRA_RAJ_WORKFLOW_BASE_URL` | Raj `/healthz` and `/api/workflow/execute` contracts |
| `MITRA_RAJ_API_KEY` | optional Raj ingress secret |
| `MITRA_BHIV_ASHMIT_BASE_URL` | Ashmit health and provenance contracts |
| `MITRA_BHIV_ASHMIT_API_KEY` | required Ashmit owner-contract credential |
| `MITRA_BHIV_BUCKET_BASE_URL` | Bucket artifact contracts |
| `MITRA_BHIV_INSIGHTFLOW_INGEST_URL` | InsightFlow trace ingest |
| `MITRA_BHIV_INSIGHTFLOW_API_KEY` | optional InsightFlow API key |
| `MITRA_BHIV_KARMA_BASE_URL` | Karma append contracts |
| `MITRA_BHIV_PRANA_BASE_URL` | PRANA strict/core forwarding |
| `MITRA_CENTRAL_DEPOSITORY_BASE_URL` | Ashmit append-only handover contract |
| `MITRA_ECOSYSTEM_TIMEOUT_SECONDS` | owner-contract timeout |

Use `_FILE` variants or `MITRA_COMPANION_SECRETS_DIR` for secrets. Runtime
configuration APIs expose only redacted presence information.

`GET /api/v1/ecosystem/readiness` reports the canonical chain configuration.
Every required owner must be configured before
`POST /api/v1/ecosystem/execute` accepts work. Missing contracts return 503;
there is no embedded fallback on this path.

TANTRA handover:

| Variable | Contract |
|---|---|
| `MITRA_TANTRA_GATEWAY_URL` | `POST /api/v1/execute/evidence-package` |
| `MITRA_TANTRA_API_KEY` | optional `X-API-Key` secret |
| `MITRA_TANTRA_INTEGRATION_TIMEOUT_SECONDS` | outbound timeout |
| `MITRA_TANTRA_DELIVERY_LEASE_SECONDS` | outbox claim expiry |
| `MITRA_TANTRA_INITIAL_BACKOFF_SECONDS` | first retry delay |
| `MITRA_TANTRA_MAX_BACKOFF_SECONDS` | retry delay ceiling |
| `MITRA_TANTRA_MAX_ATTEMPTS` | terminal delivery limit |
| `MITRA_TANTRA_DELIVERY_BATCH_SIZE` | scheduled retry batch |

Mitra always builds and stores the four-bundle handover after verified
reconstruction. It sends the package only when the gateway URL is configured.
There are no embedded TANTRA authority decisions. See
`docs/TANTRA_INTEGRATION.md`.

The package request is committed to the durable outbox before network I/O.
Only the shared-maintenance lease holder processes retries and continuity
checks. Another instance can reclaim an expired delivery without invoking the
attached product again.

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

### Real Ecosystem Compose Topology

The separate `docker-compose.ecosystem.yml` starts the response-bearing owner
contract topology. Place these repositories beside this repository:

| Directory | Source | Required revision for the last accepted run |
|---|---|---|
| `../Ashmit-Mitra-T42` | `https://github.com/blackholeinfiverse54-creator/Mitra_T42.git` | `3b696e38adbd88b3f5343792bdba37dd88824647` |
| `../BHIV-Bucket` | `https://github.com/siddheshnarkar76/bucket.git` | `346bad0917a653074b824ba4780ce605f74e0775` |
| `../KESHAV-4` | `https://github.com/blackholeinfiverse106-creator/KESHAV-4` | `abd29012fc0cec50cf976b836f2727441f4d7d38` |
| `../uniguru_ai` | `https://github.com/VJY123VJY/uniguru_ai` | `a0740f552b33b19e1507014d63a4af6ecb61460a` |
| `../trade-bot-main` | `https://github.com/harshapawar136/trade-bot-main` | `cfa68555c2c9ca42bba419791cb50dbe0c7295eb` |

InsightFlow is built from the pinned `VJY123VJY/bhiv` revision declared in
`integration_services/insightflow-owner.Dockerfile`. Raj, Karma, and PRANA are
the supplied published-contract implementations in `integration_services/`;
no unavailable owner source is claimed for them. KESHAV runs the supplied
owner repository and is health-gated before Mitra starts.

Ashmit's ignored `../Ashmit-Mitra-T42/backend/.env` must define `API_KEY`,
`JWT_SECRET_KEY`, `MONGODB_URI`, and `DATABASE_NAME`. The topology passes the
owner Atlas URI only to Ashmit. Bucket uses a separate authenticated local
MongoDB URI, preventing either owner integration from silently changing the
other's persistence target. UniGuru's ignored
`../uniguru_ai/.env.local` must define `UNIGURU_API_TOKEN`, `SUPABASE_URL`, and
`SUPABASE_ANON_KEY`. Use only the browser-safe anonymous key. The configuration
generator writes the composed values to this repository's ignored `.env` and
prints key names only; none of the three secret files is tracked.

```powershell
python scripts/configure_local_ecosystem.py
docker compose -f docker-compose.ecosystem.yml config --quiet
docker compose -f docker-compose.ecosystem.yml up -d --wait ashmit-mongo bucket-redis insightflow-postgres
docker compose -f docker-compose.ecosystem.yml up -d --build --wait bucket
docker compose -f docker-compose.ecosystem.yml up -d --wait insightflow-registry insightflow-seed insightflow-bridge
docker compose -f docker-compose.ecosystem.yml --profile uniguru-product up -d --build --wait uniguru
docker compose -f docker-compose.ecosystem.yml --profile tradebot-product up -d --build --wait trade-bot
docker compose -f docker-compose.ecosystem.yml up -d --wait raj keshav karma prana ashmit
docker compose -f docker-compose.ecosystem.yml up -d --wait mitra
docker compose -f docker-compose.ecosystem.yml ps
```

The staged order is intentional. Ashmit and Bucket initialize their independent
database clients during owner-process startup. The local MongoDB service is a
Bucket dependency; Ashmit is health-gated on Atlas. Named volumes retain MongoDB,
Bucket Redis AOF data, Bucket artifacts, PostgreSQL, Karma, and Mitra state.

The production attachments are optional profiles so operators may run the core
chain on smaller hosts. Both owner profiles passed their health contracts on
2026-07-20. Trade Bot uses the official CPU-only XGBoost package; UniGuru reads
Supabase only from its ignored environment file. Refresh each attachment's
health endpoint after startup before accepting customer traffic.

Run the canonical interoperability acceptance from the rebuilt Mitra image:

```powershell
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
```

The command executes all three cases in `contracts/operational-acceptance.json`.
A passing result must report:

- `passed=true`, `case_count=3`, and `total_assertions=425` or more;
- Trade Bot selected for the NVDA request and UniGuru selected for the drip
  irrigation request without an explicit product ID;
- a real Trade Bot validation error reported as `product_error`, followed by
  KESHAV status `diagnosed` and a trace-preserving resolution proposal;
- ten completed stages, six preflight responses, and fifteen owner operations
  for success or sixteen when KESHAV `/analyze` is invoked;
- eleven immutable components, verified clean-state replay, zero database
  reads, zero live service calls, and rejected tampering per case;
- eleven execution-scoped depository artifacts and lineage entries per case;
- runtime `READY`, recovery `recovered`, telemetry present, and required
  metrics present.

The command exits nonzero on the first mismatched runtime output. It writes
only the three actual portable replay packages when `--package-directory` is
provided; it does not generate screenshots or narrative proof.

After stopping owner services, or on another rebuilt Mitra image containing
the same runtime version, verify the retained packages without a runtime URL:

```powershell
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py --validate-package /data/operational-acceptance-keshav-final --summary
```

This command reads each `*.replay.json` file, starts Python in isolated mode,
reconstructs the execution from the eleven immutable components, and repeats
validation after altering a recorded Raj response. A pass requires the
original package to report `status=verified`, `deterministic=true`,
`database_reads=0`, and `live_service_calls=0`; the changed package must report
`status=failed`. On 2026-07-20 all three v2 packages passed 123 checks and
their altered copies failed integrity checks. The two retained pre-KESHAV v1
packages under `/data/operational-acceptance` also passed all 112 checks, which
proves the replay reader remains backward compatible.

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
6. Submit the exported reconstruction package to
   `POST /api/v1/reconstruction/validate` from a fresh runtime when proving
   artifact-only deterministic reconstruction.
7. Inspect `ecosystem_convergence.handoffs` and the dispatch-scoped depository
   for the TANTRA package and factual delivery receipt.
8. For final ecosystem acceptance, submit the same customer request through
   `POST /api/v1/ecosystem/execute`, inspect all ten stage responses, and
   validate its portable package through
   `POST /api/v1/ecosystem/replay/validate`.

No product-specific branch belongs in `CompanionRuntime` or `IntentRouter`.
See `docs/INTEGRATION_GUIDE.md`.

## 9. Deployment Choice

Use Docker or `render.yaml` when durable state, recovery, long-duration
execution, or multiple runtime instances are required.

Use `vercel.json` only for the public serverless API. Its `/tmp` database is
ephemeral and persistent supervision is disabled. Do not use a Vercel
deployment as proof of durable failover or disaster recovery.

## 10. Central Depository Handover

For each accepted ecosystem execution:

1. retain the original execution response;
2. fetch `/api/v1/ecosystem/executions/{execution_id}/replay`;
3. fetch
   `/api/v1/runtime/depository?subject_type=ecosystem_execution&subject_id={execution_id}`;
4. verify artifact hashes and lineage;
5. send those actual API outputs to the external Central Depository consumer.

The canonical acceptance command performs steps 1-4 for both live products
and verifies append, exact read-back, replay, subject isolation, sequence
continuity, and lineage hashes. Use
`--require-independent-central-depository` when an independently hosted owner
endpoint is an acceptance requirement. That flag intentionally fails in the
current local topology because Central Depository storage is Bucket-backed.

Follow `docs/CENTRAL_DEPOSITORY_HANDOVER.md`. Do not generate a replacement
proof document or recursively embed depository snapshots.

## 11. Operational Acceptance

Before ownership transfer, verify:

- `/health` and `/ready` return HTTP 200;
- `/api/v1/runtime/deployment-parity` reports `ready=true` and the expected
  deployed commit SHA;
- real manifests attach and declared intents are discoverable;
- a submitted payload is present in the completed dispatch response;
- deterministic reconstruction reproduces the submitted input and output;
- dependency contracts and versions are present in the clean-state package;
- a clean runtime validates the exported reconstruction package without reading
  the original runtime database;
- every required ecosystem stage has an actual owner response and immutable
  artifact; controlled test adapters do not count as live production proof;
- `/api/v1/ecosystem/readiness` reports `ready=true` for live acceptance;
- the TANTRA handover has a verified package and either an accepted gateway
  response or the explicit `gateway-not-configured` state;
- accepted TANTRA traces reconcile through the published trace endpoint;
- exactly one active instance owns the shared-maintenance lease;
- `/api/v1/runtime/continuity` reports no failed local integrity checks;
- subject-filtered depository artifacts belong to the requested lineage;
- metrics and telemetry include the dispatch;
- recovery leaves the runtime ready;
- a clean restart preserves durable sessions, attachments, and routes.

Do not mark the runtime complete unless the canonical interoperability command
passes after the documented rebuild. A unit test, configured URL, dashboard,
or architecture packet cannot waive a failed live owner response.
Use `docs/DEPLOYMENT_PARITY.md` for the release gate shared by Docker, Render,
and Vercel.

## 12. Troubleshooting

| Symptom | Check |
|---|---|
| Runtime is not ready | `/api/v1/runtime/startup`, writable data root |
| Product cannot route | attachment state, intent ID, manifest schema |
| Dispatch fails | phase journal, telemetry, product health response |
| PRANA is not forwarded | Karma must return `appended` first |
| Strict forwarding fails | canonical request bytes and SHA-256 headers |
| Replay is unverified | component hashes, lineage chain, missing artifacts |
| TANTRA handover is skipped | configure `MITRA_TANTRA_GATEWAY_URL`; the package remains available in the dispatch lineage |
| TANTRA trace is rejected | compare the response trace ID with the package trace ID and inspect the delivery receipt |
| TANTRA delivery remains queued | inspect `/api/v1/runtime/integrations/tantra/deliveries`, next retry time, lease owner, and gateway health |
| Accepted trace later disappears | run `/api/v1/runtime/integrations/tantra/reconcile` and inspect the retained dependency observation |
| State disappears | serverless `/tmp` deployment or missing persistent volume |
| Peers become stale | unique instance IDs, heartbeat configuration, and shared-maintenance lease ownership |

For recovery and rollback, use `docs/OPERATIONS_RUNBOOK.md`.
