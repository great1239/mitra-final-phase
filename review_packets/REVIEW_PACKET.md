# Review Packet - TANTRA Ecosystem Convergence

Snapshot date: 2026-07-20

## Entry Point

Start with these bounded review surfaces:

1. `pratham/companion-runtime/mitra_companion/ecosystem.py`
2. `pratham/tests/test_ecosystem_convergence.py`
3. `docs/TANTRA_ECOSYSTEM_CONVERGENCE.md`
4. `review_packets/CODE_REVIEW_PACKET/README.md`
5. `review_packets/SCREENSHOTS/README.md`

Runtime process entry point: `api/index.py` ->
`mitra_companion.api.create_app` -> `CompanionRuntime`.

Canonical assignment entry point:

```http
POST /api/v1/ecosystem/execute
```

The user-assigned independent host is
`https://mitra-live-runtime-sprint.vercel.app`. The main
`mitra.blackholeinfiverse.com` website remains unchanged and can proxy or call
this API when required.

## Runtime Architecture

Mitra owns sessions, context isolation, manifest capability selection,
transport orchestration, checkpoints, telemetry, recovery, deterministic
runtime reconstruction, and immutable export. Owner services retain workflow,
truth, intelligence, integrity, observability interpretation, product logic,
governance, acceptance, and certification authority.

The canonical runtime is implemented by:

- `PublishedEcosystemClient`: exact owner HTTP contracts, no local fallback;
- `EcosystemRuntime`: ordering, durable checkpoints, recovery, idempotency;
- `EcosystemReplayLedger`: package-only reconstruction and integrity checks;
- `RuntimeStore`: executions, stages, attempts, immutable references;
- `CentralDepository`: content-addressed artifacts and subject lineage.

## Integration Map

```text
User request
  -> Mitra session and manifest capability selection
  -> Raj POST /api/workflow/execute (1.0.0)
  -> selected product runtime
  -> KESHAV POST /analyze only for a typed product error
  -> Ashmit POST /api/mitra/evaluate with Raj provenance
  -> Bucket latest hash, strict append/read, global replay validation
  -> Karma POST /integrity/append-bucket-artifact
  -> PRANA POST /forward/karma-strict using exact Karma bytes
  -> PRANA POST /forward/core with trace preservation
  -> InsightFlow configured execution-ingest POST
  -> Mitra portable deterministic reconstruction
  -> Central Depository content-addressed export
```

Ashmit `GET /health/system`, Raj `GET /healthz`, KESHAV `GET /health`, and
PRANA `GET /health` are preflight dependencies. After Raj returns a valid
success or typed product error, Ashmit's authenticated evaluation
contract must return an accepted decision, its own trace ID, and a Mongo-backed
artifact locator. Bucket health and the Central Depository latest-hash contract
are also probed. Every configured preflight call retains its response or
transport error even when another required owner is unconfigured. Karma runs
before PRANA because that is required by the supplied published contract.
PRANA is suppressed unless Karma returns `appended`.

UniGuru and Samruddhi remain production manifest attachments. KESHAV is a
conditional owner-contract stage, not a product branch. SETU, SARATHI, and
future consumers use the same manifest or owner-contract doctrine.

## Core Execution Flow

Every execution records ten ordered stages:

1. capability selection
2. dependency preflight
3. Raj execution
4. KESHAV diagnosis or explicit no-call skip
5. Ashmit provenance
6. Bucket truth
7. Karma integrity
8. PRANA forwarding
9. InsightFlow telemetry
10. Central Depository export

Each stage stores the canonical request, actual response, request and response
hashes, attempt history, timestamps, content-addressed artifact, lineage ID,
parent chain hash, and chain hash. A failed stage stops the chain. Recovery
resumes at the failed stage without repeating completed owner work.

## Runtime Flow

The core execution flow above is the runtime flow required by the assignment.
The separate `Live Runtime Flow` section identifies which parts are currently
observable on the public and durable deployment topologies.

## API List

- `GET /api/v1/ecosystem/readiness`
- `GET /api/v1/ecosystem/contracts`
- `POST /api/v1/ecosystem/execute`
- `GET /api/v1/ecosystem/executions`
- `GET /api/v1/ecosystem/executions/{execution_id}`
- `POST /api/v1/ecosystem/executions/{execution_id}/recover`
- `GET /api/v1/ecosystem/executions/{execution_id}/replay`
- `POST /api/v1/ecosystem/replay/validate`
- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /api/v1/runtime/telemetry`
- `GET /api/v1/runtime/depository`
- `GET /docs`
- `GET /openapi.json`

The complete static API contract is
`contracts/api/companion-runtime.openapi.yaml`.

## Live Runtime Flow

The hosted dashboard and read APIs run on the assigned Vercel host. The Vercel
profile uses ephemeral `/tmp` state and disables the persistent supervisor.
It is suitable for public API access, not durable failover certification.

Live full-chain execution is accepted only when
`GET /api/v1/ecosystem/readiness` returns `ready=true` and the selected product
attachment is healthy. The local topology reports `ready=true`; UniGuru and
Trade Bot are both `ATTACHED`. Two customer executions completed all owner
stages on 2026-07-20, and one real product validation error completed the
conditional KESHAV path. Missing owner URLs, credentials, or product health still
fail closed and never become embedded acceptance. Durable long-running
validation uses Docker or Render with `/data`.

## What Changed

- Added the strict Raj-to-Central-Depository runtime path.
- Added conditional KESHAV dependency diagnosis for typed product failures,
  with an explicit no-call checkpoint for successful products.
- Preserved Raj infrastructure and contract failures as fail-closed outcomes;
  they are never mislabeled as product errors for KESHAV.
- Added response-bearing, content-addressed checkpoints and retained attempts.
- Added Raj/Mitra trace bridging without mutating either owner trace.
- Enforced Karma acceptance, PRANA byte identity, and trace preservation.
- Added fail-closed readiness and semantic owner-response validation.
- Added response-bearing read-only probes for every configured preflight
  contract before a missing-owner block is returned.
- Added checkpoint recovery and request-hash-bound idempotency.
- Serialized the shared Bucket/Karma hash-head mutation with a crash-expiring
  database lease so concurrent processes cannot append from the same parent.
- Reused one isolated HTTP connection pool per ecosystem execution and closed
  it after the execution, reducing connection churn without sharing request
  state between executions.
- Added portable full-chain replay with artifact and lineage reconstruction.
- Added ecosystem status to health, readiness, metrics, dashboard, and OpenAPI.
- Added response-bearing operator views for every stage, replay, depository,
  recovery, multi-instance state, and durable versus process-local metrics.
- Added exact contract schemas, environment variables, handover documentation,
  and controlled interoperability tests.
- Added generic published-origin endpoint overrides for local owner health and
  dispatch without product branches in runtime logic.
- Added owner Bucket with authenticated Redis AOF and persistent artifacts,
  UniGuru with ignored Supabase secrets, and CPU-only Trade Bot packaging.
- Preserved legacy companion and TANTRA handover surfaces without presenting
  them as proof that the final owner chain executed.
- Removed the legacy in-process Ashmit, Bucket, Karma, PRANA, and InsightFlow
  substitutes. Ordinary dispatch now records `not_executed` and performs zero
  owner I/O.
- Changed `/api/workflow/run` to invoke the canonical ecosystem runtime instead
  of the ordinary companion dispatch path.
- Added one canonical output-driven acceptance command covering both owner
  products, all owner responses, idempotency, telemetry, depository lineage,
  isolated replay, and recorded-response tampering.

## Replay Proof

Reviewer sequence:

```text
original execution
  -> export replay package
  -> stop original runtime
  -> start a clean runtime with an empty database
  -> validate only the exported package
  -> reconstruct the same execution
  -> verify component, request, response, artifact, lineage, contract,
     reconstructed-output, and package hashes
  -> mutate a recorded Raj response
  -> validation fails at the stage response hash
```

`EcosystemReplayLedger.validate` reports `database_reads=0` and
`live_service_calls=0`. It reconstructs runtime facts; external replay
authority and certification remain outside Mitra.

## Deployment Proof

Deployment artifacts are `Dockerfile`, `docker-compose.yml`, `render.yaml`,
`vercel.json`, `api/index.py`, and `deploy/production.env.example`.

The public deployment is independently reachable over HTTPS at the assigned
Vercel URL. The final deployment is
`D1YusdkJsCmECWD6hy3TR3wnCSg3` ([Vercel inspection](https://vercel.com/bhiv-intern/mitra-live-runtime-sprint/D1YusdkJsCmECWD6hy3TR3wnCSg3)); its immutable URL is
`https://mitra-live-runtime-sprint-1871ajpg6-bhiv-intern.vercel.app` and the
assigned alias is `https://mitra-live-runtime-sprint.vercel.app`.

Final hosted endpoint validation observed `healthy`, runtime state `READY`,
HTTP 200 from the operator surface, and ecosystem execution plus replay routes
in `/openapi.json`. This does not prove an owner-chain execution. The hosted
2026-07-15 preflight remains a historical record of missing remote owners.

The 2026-07-20 local Compose topology returns HTTP 200 from all core health
contracts. UniGuru and Trade Bot are `ATTACHED`; both completed response-bearing
Raj, product, Ashmit, Bucket, Karma, PRANA, InsightFlow, and Bucket-backed
depository calls. The error case additionally completed a real KESHAV call.
These Docker DNS services are not reachable from Vercel, so local
full-chain execution is proven while public full-chain execution is not.

## Failure Cases

| Failure | Observed runtime behavior |
| --- | --- |
| Missing owner configuration | HTTP 503, execution marked failed, no owner fallback |
| Raj health/transport failure | stop before workflow execution |
| Raj contract or trace failure | fail Raj stage; do not invoke KESHAV or Bucket |
| Typed product error | invoke KESHAV; continue only with a valid trace-preserving diagnosis |
| KESHAV rejection, transport failure, or trace mutation | fail KESHAV stage before Ashmit and Bucket |
| Ashmit rejection or invalid artifact reference | fail Ashmit stage, no Bucket call |
| Bucket append/validation rejection | stop before Karma |
| Karma replay or append violation | stop before PRANA |
| PRANA strict bytes/hash mismatch | fail PRANA stage |
| PRANA trace mutation | fail PRANA stage |
| InsightFlow rejection | retain prior stages; recovery retries InsightFlow only |
| Duplicate identical idempotency key | return original execution, no repeated owner calls |
| Duplicate changed idempotency key | HTTP 409 conflict |
| Replay component mutation | deterministic validation fails |
| Process interruption | recover from first incomplete checkpoint |

Failures are API and durable state outputs, not generated proof documents.

## Recovery Cases

- A completed stage is immutable and never rerun during recovery.
- Every failed and successful attempt is retained.
- A stale attempt cannot complete after a newer attempt owns the stage.
- A completed execution is idempotent under recovery.
- Shared runtime maintenance remains lease-fenced for multiple processes using
  one durable database.
- Vercel cannot prove durable disaster recovery because its state is ephemeral.

## Hosted URLs

- Dashboard: `https://mitra-live-runtime-sprint.vercel.app/`
- Health: `https://mitra-live-runtime-sprint.vercel.app/health`
- Readiness: `https://mitra-live-runtime-sprint.vercel.app/ready`
- Metrics: `https://mitra-live-runtime-sprint.vercel.app/metrics`
- OpenAPI: `https://mitra-live-runtime-sprint.vercel.app/docs`
- Ecosystem readiness:
  `https://mitra-live-runtime-sprint.vercel.app/api/v1/ecosystem/readiness`

## Test Commands

```powershell
python -m pip install -e ".[test]"
python -m pytest pratham/tests/test_ecosystem_convergence.py -q
python -m pytest pratham/tests contracts/integration-tests -q
python scripts/production_readiness_gate.py
docker compose up -d --wait
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
```

## Production Evidence

Observed from the 2026-07-20 rebuilt topology:

- Mitra readiness returned `ready=true` with no pending owner modules. Raj,
  KESHAV, Ashmit, Bucket, Karma, PRANA, InsightFlow, MongoDB, PostgreSQL, Redis,
  UniGuru, and Trade Bot were healthy.
- UniGuru execution `eco_07fa5401aaf94ebfb2cfd6ead3cd5424`
  completed with trace
  `4d0226817166d18f9023acf94b4bdb1e2a9e87df11c3f08df44bba5551e8ba54`
  for the drip-irrigation request.
- Trade Bot execution `eco_1ac97452891c43bdad40b786eb5b9089`
  completed with trace
  `b9701df1f6cb82e674f4d1401dfb0523610d22d73c4a014ba00b2882269ffa44`.
  The owner response contained the requested `NVDA` symbol.
- Trade Bot error execution `eco_6e30b5bb66c549d6a691c4bc35b0582a`
  preserved the owner's HTTP 422 response as `product_error`; KESHAV returned
  `UNBLOCK_DEPENDENCY:product-runtime-samruddhi-trade-bot` with the same trace.
  Mitra persisted the proposal and did not execute it.
- Every case recorded six preflight responses. Success cases recorded 15 owner
  operations and the KESHAV case recorded 16. All accepted calls retained HTTP
  status, response SHA-256, and semantic validation.
- Replay packages `c77d72e0e1cbc6f9445807066be5472d9d433bc61614e2491f4e51583c05fb86`,
  `0bd258b0759bc2680d964c46ea2e6c771a19e1b17cd32cd08ec7e76586bd8583`,
  and `eb73fecea94d23e15e952e094edd9b55033e8fb6915eab33796c237200fe2553`
  each reconstructed `COMPLETED` from eleven components with 123/123 checks,
  `deterministic=true`, `clean_state=true`, zero database reads, and zero live
  calls in an isolated process. Every altered copy was rejected.
- The canonical validator passed 425 assertions, persisted all three replay
  packages, verified eleven artifacts and lineage entries per execution, and
  observed runtime `READY` plus recovery `recovered`.
- The UniGuru Supabase client was enabled and its live GoTrue health request
  returned HTTP 200. Credentials remained in ignored files and were not
  included in images or evidence.
- After Redis and Bucket restarts, both workflow artifacts retained the same
  IDs and trace, `chain_verified=true`, artifact count `3`, valid replay, and
  unchanged last hash
  `004bf46f1d9bf70ac85cd37e5f6439fb8d68df342b2ec17f5cd2e80fc431f2ea`.
- Docker Desktop 4.82.0, Engine 29.6.1, and Compose 5.3.0 built and ran the
  updated owner topology. Trade Bot uses `xgboost-cpu==3.2.0` rather than an
  unused GPU/NCCL payload.
- The complete `pratham/tests`, `contracts/integration-tests`, and
  `integration_services/tests` run passed all 161 tests on 2026-07-23.
- With explicit publication approval, the public BHIV Bucket accepted minimal
  validation artifacts for Samruddhi UniGuru
  (`73d4ceca69b2c23b0c9d00dabbd4056185521a62df190dd34235d3a8f2794c7e`)
  and Samruddhi Trade Bot
  (`e1b403520b8078dc445ddbee9cf86e889089fc1c921fe8c09fb2e612ce1e6e5c`)
  on 2026-07-22. Both POST and exact GET read-back returned HTTP 200, both
  canonical hashes matched independently, the parent link matched, and public
  replay validation returned `valid=true` with artifact count `2`.

## Evidence References

- `pratham/tests/test_ecosystem_convergence.py`
- `review_packets/testing/TESTING_EVIDENCE.md`
- `review_packets/testing/bucket-public-storage-live-evidence.json`
- `review_packets/SCREENSHOTS/README.md`
- `review_packets/CODE_REVIEW_PACKET/README.md`
- `docs/TANTRA_ECOSYSTEM_CONVERGENCE.md`
- `contracts/runtime-command-chain.json`

## Known Limitations

- Raj, Karma, PRANA, and the InsightFlow bridge are local executable services
  built from published contracts, not the original owners' hosted deployments.
- KESHAV `/analyze` exposes only the diagnosis even though its owner wrapper
  internally runs bundled RAJYA, Sarathi, Core, and Bucket code. Those hidden
  outputs are not independently verified or claimed by Mitra.
- UniGuru's public domain exposes frontend HTML rather than its backend JSON
  contract. The validated runtime therefore maps that published origin to the
  local healthy owner service through a generic endpoint override.
- Trade Bot's public service returns HTTP 503 `Service Suspended`; the
  validated runtime similarly maps the published origin to the local healthy
  owner repository.
- Central Depository is Bucket-backed rather than an independently deployed
  owner service. Export and persistence are proven; external acceptance and
  certification are not claimed.
- The public Bucket accepted and read back two append-only artifacts on
  2026-07-22, and its global replay check was valid. Its health still reports
  Redis disconnected, so Redis-backed logs are not proven; persistence of these
  two artifacts across a future Render restart is also not yet proven. The
  owner route `/bucket/validate-chain/{artifact_id}` still reads a legacy store
  and does not find append-only artifacts.
- Ashmit now uses the owner Atlas URI. Its exact Docker egress address must
  remain in the Atlas network access list; a changing development-network IP
  will make the health gate fail before authentication.
- Ashmit does not reconnect after an initial Atlas startup refusal. Restore
  reachability and restart Ashmit; Bucket's separate local MongoDB remains
  unaffected.
- Windows PowerShell 5 changes high-precision JSON numbers during a package
  round-trip. Replay submission must use a precision-preserving JSON client;
  Python and native validation passed the retained v1 packages at 112/112 and
  the current v2 packages at 123/123 checks.
- The public Vercel process cannot reach local Docker DNS names. Equivalent
  owner services must be hosted over HTTPS before public full-chain execution.
- The public Vercel topology is ephemeral and cannot certify long-duration
  execution, durable failover, or disaster recovery.
- Cross-host clustering requires a shared transactional store or event fabric;
  SQLite leases coordinate only processes sharing one durable database.
- One ecosystem request currently selects one product capability. Multi-product
  decomposition, dependency graphs, parallel branches, and merged product
  responses are not yet implemented in the strict execution endpoint.

## Replay Validation Summary

The portable package reconstructs the selected capability, Mitra trace, Raj
trace, Raj execution, conditional KESHAV status and diagnosis, Ashmit trace
and provenance response, Bucket artifact, Karma hash, PRANA byte hash,
InsightFlow envelope hash, Central Depository package hash, and every stage
response hash. Clean-state validation succeeds without the original database
or any network service. Any changed component, request, response, artifact,
lineage link, contract set, reconstructed output, or package root fails the
appropriate check. All three current packages passed 123/123 checks in an
isolated process and reconstructed status `COMPLETED` on 2026-07-20. The same
acceptance run deliberately changed a recorded Raj response and observed a
failed replay for each package. Two retained pre-KESHAV v1 packages also passed
112/112 checks under the current replay reader.
