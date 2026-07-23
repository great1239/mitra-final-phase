# TANTRA Ecosystem Convergence

This is the authoritative implementation guide for the TANTRA Ecosystem
Convergence and Production Activation sprint.

## Ownership

Mitra owns interaction, sessions, scoped context, manifest-driven capability
selection, transport orchestration, durable checkpoints, runtime telemetry,
recovery, deterministic runtime reconstruction, and immutable export.

Mitra does not implement Raj workflow logic, KESHAV dependency analysis,
Bucket truth authority, PRANA forwarding decisions, Karma integrity decisions,
InsightFlow interpretation, product business logic, governance, certification,
or Central Depository acceptance.

## Canonical Flow

```text
POST /api/v1/ecosystem/execute
  -> validate versioned request and active session boundary
  -> select one attached capability from its published manifest
  -> preflight Raj, KESHAV, Bucket, Ashmit, PRANA, and depository contracts
  -> POST Raj /api/workflow/execute (request version 1.0.0)
  -> accept only a trace-preserving success or typed product_error outcome
  -> on success, record a KESHAV skipped checkpoint without calling /analyze
  -> on product_error, POST KESHAV /analyze and validate its trace-preserving proposal
  -> POST Ashmit /api/mitra/evaluate with the execution provenance
  -> require an accepted decision and Mongo-backed artifact reference
  -> Bucket latest hash, strict artifact append/read, global replay validation
  -> POST Karma /integrity/append-bucket-artifact
  -> continue only when Karma returns status=appended
  -> POST PRANA /forward/karma-strict with the exact accepted Karma bytes
  -> verify PRANA byte-equality and SHA-256 response headers
  -> POST PRANA /forward/core and verify that trace_id was not mutated
  -> POST the canonical execution envelope to InsightFlow
  -> append the content-addressed handover to the configured external depository contract
  -> seal and validate the portable deterministic replay package
```

The assignment diagram places PRANA before Karma. The supplied owner contract
requires Karma acceptance before PRANA forwarding, so the executable order
follows that published contract. A Karma replay or append violation suppresses
all PRANA and downstream calls.

KESHAV is conditional. It diagnoses a product-owned error and proposes a
resolution signal; Mitra records and transports that proposal but does not
authorize or execute it. Raj transport, schema, contract, or trace failures
still fail closed before KESHAV because those are not valid product outcomes.
The supplied KESHAV `/analyze` wrapper internally runs its bundled TANTRA
pipeline, but exposes only the diagnosis response. Mitra therefore makes no
independent claim about hidden RAJYA, Sarathi, Core, or internal Bucket results.

## Required Configuration

The canonical endpoint is fail-closed and has no embedded fallback.

| Variable | Owner contract |
| --- | --- |
| `MITRA_RAJ_WORKFLOW_BASE_URL` | Raj `GET /healthz`, `POST /api/workflow/execute` |
| `MITRA_RAJ_API_KEY` | optional ingress credential; not required by the published v1 source contract |
| `MITRA_BHIV_ASHMIT_BASE_URL` | Ashmit `GET /health/system`, `POST /api/mitra/evaluate` |
| `MITRA_BHIV_ASHMIT_API_KEY` | required Ashmit owner-contract credential |
| `MITRA_BHIV_BUCKET_BASE_URL` | Bucket truth and validation routes |
| `MITRA_BHIV_KESHAV_BASE_URL` | KESHAV `GET /health`, conditional `POST /analyze` |
| `MITRA_BHIV_KARMA_BASE_URL` | Karma append route |
| `MITRA_BHIV_KARMA_PREVIOUS_HASH` | current Karma chain head |
| `MITRA_BHIV_PRANA_BASE_URL` | PRANA health, strict, and core routes |
| `MITRA_BHIV_INSIGHTFLOW_INGEST_URL` | absolute InsightFlow ingest URL |
| `MITRA_BHIV_INSIGHTFLOW_API_KEY` | optional InsightFlow API key |
| `MITRA_CENTRAL_DEPOSITORY_BASE_URL` | external append-only handover base URL; the updated local topology uses the Bucket owner service |
| `MITRA_ECOSYSTEM_TIMEOUT_SECONDS` | per-owner HTTP timeout |

Use `_FILE` forms or `MITRA_COMPANION_SECRETS_DIR` for credentials. Runtime
responses report only configured presence, never secret values.

Check configuration without executing:

```http
GET /api/v1/ecosystem/readiness
GET /api/v1/ecosystem/contracts
```

An incomplete configuration returns `503 ECOSYSTEM_INTEGRATION_NOT_READY` from
the execution endpoint. It is not converted into a successful local result.

## Request

```json
{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "actor_id": "operator-1",
  "workspace_id": "production",
  "product_id": "samruddhi-trade-bot",
  "capability_id": "market-prediction",
  "message": "Generate a market prediction for TCS.NS",
  "payload": {
    "symbols": ["TCS.NS"],
    "horizon": "short",
    "raj_workflow": {
      "action_type": "task",
      "title": "Run market prediction"
    }
  },
  "idempotency_key": "production:market:001"
}
```

`product_id` and `capability_id` are selectors, not runtime branches. The
selected manifest contract is sent to Raj. Mitra never calls product-private
Python code.

## Checkpoints And Recovery

The runtime persists these stages in order:

1. `capability-selection`
2. `dependency-preflight`
3. `raj-execution`
4. `keshav-diagnosis`
5. `ashmit-provenance`
6. `bucket-truth`
7. `karma-integrity`
8. `prana-forwarding`
9. `insightflow-telemetry`
10. `central-depository`

Each checkpoint contains the canonical request, actual response, hashes,
attempt count, timestamps, content-addressed artifact, and hash-chain lineage.
Every failed attempt is retained. Recovery resumes at the first incomplete
stage and does not repeat a completed owner call.

Bucket and Karma each expose a mutable chain head. Mitra therefore obtains one
crash-expiring SQLite lease around the combined Bucket/Karma mutation segment,
re-reads both heads only after acquiring it, and releases it after Karma
accepts. This prevents parallel processes from appending from the same parent.
The lease holder is unique per execution attempt, and an abandoned lease
expires after the bounded owner timeout.

Each ecosystem execution also owns one scoped `httpx.AsyncClient`. All owner
calls within that execution reuse its connection pool, while concurrent
executions have independent clients and close them deterministically.

```http
GET  /api/v1/ecosystem/executions
GET  /api/v1/ecosystem/executions/{execution_id}
POST /api/v1/ecosystem/executions/{execution_id}/recover
```

Idempotency keys are bound to the canonical request hash. Reuse with identical
content returns the original execution; reuse with different content returns a
conflict.

## Deterministic Replay

The replay package contains the original request plus every completed stage in
order. It includes request and response hashes, stage artifact hashes, lineage
IDs, parent links, chain hashes, owner contracts, reconstructed output, and a
package hash.

Validation is a pure operation over the supplied package. It performs zero
database reads and zero live service calls. It verifies:

- package, contract, component, request, and response hashes;
- exact component order and links;
- recomputed content-addressed stage artifacts;
- lineage IDs, parent hashes, sequence, and chain hashes;
- Mitra trace continuity plus recorded Mitra-to-Raj and Mitra-to-Ashmit trace bridges;
- equality of reconstructed execution and its recorded hash.

```http
GET  /api/v1/ecosystem/executions/{execution_id}/replay
POST /api/v1/ecosystem/replay/validate
```

This is runtime reconstruction. External systems still own replay authority,
acceptance, and certification.

## Attached Products And Future Intake

Production bootstrap currently contains the published UniGuru and Samruddhi
manifests under `contracts/production/`. KESHAV is integrated as a conditional
owner contract rather than a routable product. SETU, SARATHI, and future
consumers attach through a manifest or separately published owner contract.
Example manifests are not loaded by the production profile and are not
production evidence.

## Validation

Behavioral tests are in `pratham/tests/test_ecosystem_convergence.py`. They
assert the published request/response contracts, exact ordering, strict bytes,
trace identity, fail-closed behavior, recovery, idempotency, portable replay,
and mutation rejection. Tests validate Mitra behavior; the separate live pass
below validates running services.

The 2026-07-20 topology completed all three declarative acceptance cases.
UniGuru execution `eco_07fa5401aaf94ebfb2cfd6ead3cd5424` handled the
drip-irrigation request. Trade Bot execution
`eco_1ac97452891c43bdad40b786eb5b9089` returned the requested NVDA symbol.
Both recorded a KESHAV no-call checkpoint. Trade Bot error execution
`eco_6e30b5bb66c549d6a691c4bc35b0582a` supplied an empty symbol list, received
the owner's real HTTP 422 response through Raj, and invoked KESHAV. KESHAV
returned `UNBLOCK_DEPENDENCY:product-runtime-samruddhi-trade-bot` with the
original trace before the diagnosis continued through every downstream owner.

Every case recorded six accepted preflight responses. Success cases recorded
15 owner operations; the error case recorded 16 because it called
`POST /analyze`. All three eleven-component replay packages reconstructed
`COMPLETED` in an isolated Python process with 123/123 checks, zero database
reads, and zero live calls, and each rejected a changed Raj response. The
canonical validator made 425 assertions over actual outputs. Two retained
pre-KESHAV v1 packages also still passed all 112 checks. The owner Bucket runs
with authenticated Redis
AOF, MongoDB, and persistent artifacts; its artifact count, replay head, and
two workflow artifacts remained unchanged across Redis and Bucket restarts.
UniGuru's personal Supabase client initialized and GoTrue returned HTTP 200.

Central Depository remains Bucket-backed rather than an independently deployed
owner service. The runtime therefore proves export, append, exact read-back,
lineage, and replay validation, but does not claim external certification.
Exact outputs and every observed limitation are maintained in
`docs/ECOSYSTEM_CONFIGURATION_STATUS.md`.

Reproduce the result after the documented Compose rebuild:

```powershell
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
```

## Hosting

The user-assigned public host is:

```text
https://mitra-live-runtime-sprint.vercel.app
```

The main `mitra.blackholeinfiverse.com` site remains unchanged. It can call the
public runtime directly or through its proxy when required. The public runtime
stores authoritative state in managed PostgreSQL; `/tmp` is process-local
only. Raj, Karma, PRANA, and the InsightFlow registry/bridge are independently
hosted through the root Render Blueprint. Ashmit, Bucket, KESHAV, UniGuru, and
Trade Bot remain attached through their published HTTPS contracts. Vercel may
pause background compute between requests, so strict continuous scheduling
still belongs on the resident Docker/Render runtime.
