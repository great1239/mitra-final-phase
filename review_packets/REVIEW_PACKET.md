# Review Packet - Mitra Final Runtime Convergence

## Entry Point

Large-repository review starts with the bounded
[`code_packets/`](code_packets/README.md) surface. It contains only critical
files changed during this sprint and limits each implementation area to three
files.

Start with:

1. `docs/HANDOVER.md` for clean-room rebuild and operation.
2. `docs/ARCHITECTURE.md` for ownership and component boundaries.
3. `docs/CENTRAL_DEPOSITORY_HANDOVER.md` for artifact transfer.
4. `pratham/tests/test_bhiv_integrations.py` for module interoperability.
5. `pratham/tests/test_replay_convergence_and_graph.py` for reconstruction and
   lineage.

Primary commands:

```powershell
python -m pip install -e ".[test]"
python -m pytest
python scripts/production_readiness_gate.py
python scripts/validate_hosted_runtime.py
```

Primary implementation:

- `pratham/companion-runtime/mitra_companion/runtime.py`
- `pratham/companion-runtime/mitra_companion/reconstruction.py`
- `pratham/companion-runtime/mitra_companion/depository.py`
- `pratham/companion-runtime/mitra_companion/bhiv_integrations.py`
- `pratham/companion-runtime/mitra_companion/frontend_connector.py`
- `contracts/api/companion-runtime.openapi.yaml`

## Core Execution Flow

```text
client input
  -> version and payload validation
  -> durable session lookup
  -> declared context-scope merge
  -> manifest-derived route selection
  -> product transport dispatch
  -> response-schema validation
  -> durable dispatch receipt and seven-phase journal
  -> immutable deterministic reconstruction
  -> dispatch-scoped depository artifacts and lineage
  -> BHIV contract publication with an explicit response per operation
```

Karma and PRANA are ordered: Karma must return `appended` before PRANA receives
the exact canonical request bytes. Bucket, InsightFlow, Ashmit, and the runtime
Central Depository export use their published contracts and record accepted,
rejected, failed, or explicitly skipped results.

Mitra owns runtime execution facts and deterministic reconstruction. It does
not own product business logic, governance, external replay/evidence authority,
certification, or Central Depository acceptance.

## Live Runtime Flow

Public host:

```text
https://mitra-live-runtime-sprint.vercel.app
```

Review endpoints:

- `GET /`
- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /docs`
- `GET /openapi.json`
- `GET /api/v1/runtime/status`
- `GET /api/v1/runtime/integrations`
- `POST /api/v1/products/connect`
- `POST /api/v1/sessions`
- `POST /api/v1/intents/dispatch`
- `GET /api/v1/dispatches/{dispatch_id}/reconstruction`
- `GET /api/v1/runtime/depository?subject_type=dispatch&subject_id={dispatch_id}`

`scripts/validate_hosted_runtime.py` probes the live read surfaces and performs
the dispatch/replay flow only when a real, already attached product target is
available. It ignores example, simulated, loopback, and localhost manifests
instead of creating fixture data.

The Vercel host uses ephemeral `/tmp` state and persistent supervision is
disabled. Docker or Render with durable `/data` is the production topology for
continuity, failover, recovery, and long-duration validation.

## What Changed

- Added true artifact-based deterministic reconstruction covering lifecycle,
  sessions, routing, attachments, context, dispatch, telemetry, recovery, and
  failures.
- Added content-addressed runtime artifacts and hash-chain lineage.
- Added subject-scoped Central Depository exports so one dispatch cannot leak
  unrelated artifacts.
- Added contract-first integration for Ashmit, Bucket, InsightFlow, Karma, and
  PRANA.
- Enforced Karma-before-PRANA forwarding, canonical JSON SHA-256 truth, strict
  byte identity, and trace preservation.
- Added capability graph planning and contract manifests for Bucket, PRANA,
  Karma, SETU, KESHAV, and SARATHI as test/documentation surfaces.
- Added production manifest policy: hosted and container profiles bootstrap
  only from `contracts/production` and reject example, simulated, loopback, and
  localhost manifests by default.
- Added command-center frontend compatibility routes for `/api/companion/*` and
  `/api/workflow/run`; these translate requests into Mitra sessions,
  capability analysis, dispatch, telemetry, replay, and Central Depository
  trace surfaces.
- Added persistent runtime supervision, heartbeat, stale-peer reconciliation,
  interrupted-task recovery, metrics, telemetry, and operator APIs.
- Removed phase-specific evidence generators and recursively nested depository
  snapshots.
- Added a clean-room rebuild guide, documentation index, Central Depository
  protocol, and machine-readable depository export schema.

## Failure Cases

| Failure | Runtime behavior | Reviewer surface |
|---|---|---|
| Invalid input schema | Reject before transport | HTTP 422 / routing error |
| Ambiguous or missing route | Fail closed | intent dispatch response |
| Product transport failure | Persist failed receipt and failed phases; degrade only that attachment | dispatch, phases, telemetry |
| Invalid product response | Normalize as transport failure | failed dispatch reconstruction |
| Missing BHIV endpoint | Record explicit `skipped` result | convergence response |
| Karma replay or append violation | Do not forward to PRANA | Karma and PRANA operation results |
| PRANA byte mismatch | Record strict forwarding failure | integration response |
| PRANA trace mutation | Record core forwarding failure | integration response |
| Stale runtime instance | Mark stale and reconcile interrupted work | instance and recovery APIs |
| Missing or changed replay artifact | Reconstruction verification fails | reconstruction endpoint |
| Depository hash/lineage mismatch | Receiving system rejects handover | depository export verification |

Failures are runtime outputs. They are not converted into generated proof
documents.

## Production Evidence

Evidence means observed system behavior:

The executed acceptance results are in
[`testing/TESTING_EVIDENCE.md`](testing/TESTING_EVIDENCE.md). The packet
retains passing, failed, and blocked observations rather than converting them
into certification claims.

- `POST /api/v1/intents/dispatch` returns the actual product response.
- `GET /api/v1/dispatches/{dispatch_id}/phases` returns execution phases.
- `GET /api/v1/dispatches/{dispatch_id}/reconstruction` reconstructs execution
  from immutable artifacts.
- `GET /api/v1/runtime/depository` returns content-addressed artifacts and
  lineage.
- `GET /api/v1/runtime/integrations` exposes contract surfaces and redacted
  configuration.
- `GET /api/v1/runtime/telemetry` and `GET /metrics` expose runtime outcomes.

Verified on the current source:

- complete test suite: 104 passed;
- production readiness and handover gate: passed;
- fresh virtual-environment install with `.[test]`: passed;
- `mitra-companion validate` from that clean environment: `valid: true`;
- Docker Desktop repaired; Compose config validated; image built; Compose stack
  recreated healthy on port `8090`; container `mitra-companion validate`
  returned `valid: true`;
- hosted redeploy: production config points to `/contracts/production`,
  strict manifest policy is active, startup loaded zero bootstrap manifests,
  and `/api/v1/attachments` returned `[]`;
- OpenAPI YAML and JSON contracts: parsed successfully;
- repository Markdown links: all resolved.

Screenshots and reports are optional review aids. They are not substitutes for
the API responses and assertions above. Mandatory visual coverage is indexed
under `review_packets/screenshots/README.md`.

## Known Limitations

- The current public Vercel topology is ephemeral and cannot demonstrate
  durable multi-instance recovery.
- Docker Compose now validates and runs locally; the profile uses one Uvicorn
  worker per SQLite-backed container.
- Contract tests use controlled transports and do not claim that every external
  BHIV deployment was live during the run.
- Real downstream coverage depends on configured endpoint credentials and
  availability.
- Hosted routing and replay evidence now requires a real attached product;
  fixture-created Echo/Nova/KESHAV-style attachments are not accepted as
  production proof.
- Security coverage includes configuration hardening and negative-path tests,
  not penetration or abuse testing.
- SQLite supports the documented single-durable-host topology; cross-host
  scaling requires a different storage adapter.
- Current local changes must be deployed before the public host reflects this
  exact source revision.

## Replay Validation Summary

`DeterministicReconstructionLedger` records immutable components for:

- lifecycle;
- sessions;
- routing;
- attachments and selected manifest;
- scoped context;
- request, response, receipt, and seven dispatch phases;
- telemetry;
- recovery and runtime instances;
- failure state.

Verification recomputes canonical JSON SHA-256 hashes, checks the package root,
checks every component hash, validates scope coverage, and verifies lineage
continuity. The reconstructed request payload and dispatch response are compared
with the original execution.

Primary API:

```http
GET /api/v1/dispatches/{dispatch_id}/reconstruction
```

Depository companion export:

```http
GET /api/v1/runtime/depository?subject_type=dispatch&subject_id={dispatch_id}
```

Replay reconstructs the recorded execution without invoking downstream product
side effects again. External systems remain responsible for replay authority,
acceptance, and certification.
