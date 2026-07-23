# Mitra Live Runtime Sprint

Production runtime for connecting Mitra to independently owned BHIV products
through published contracts. The runtime owns session continuity, partitioned
context, manifest attachment, explicit intent routing, product exchange
mailboxes, dispatch receipts, health, recovery, telemetry, and production
operations.

It does not own product business logic, governance decisions, safety policy,
knowledge systems, certification, or downstream review systems. It does export
content-addressed runtime artifacts and deterministic dispatch reconstruction
packages for those external authorities to consume.

## Core Flow

The final strict convergence path is:

```text
User -> Mitra capability selection -> Raj -> product runtime
     -> KESHAV diagnosis only when the product returns a typed error
     -> Ashmit -> Bucket -> Karma -> PRANA -> InsightFlow
     -> deterministic reconstruction -> Central Depository
```

Run it through `POST /api/v1/ecosystem/execute`. This endpoint calls only
configured owner contracts and never substitutes an embedded adapter. See
`docs/TANTRA_ECOSYSTEM_CONVERGENCE.md` for configuration and recovery.

The complete local topology was rebuilt and validated on 2026-07-20. The
canonical three-case run completed all ten persisted stages per execution,
recorded six dependency preflights, and reconstructed each execution from
eleven immutable components with 123/123 checks passing in an isolated
process. Successful product calls recorded a no-call KESHAV checkpoint; a
real Trade Bot validation error invoked KESHAV before downstream persistence:

| Owner | Runtime access |
| --- | --- |
| Raj | healthy local published-contract service; selected and called both owner product APIs |
| KESHAV | owner repository healthy; `/analyze` was skipped for successful products and returned a trace-preserving resolution proposal for the typed Trade Bot error |
| Ashmit | owner repository healthy with authenticated local MongoDB audit persistence; both evaluations returned `ALLOW` |
| Bucket | owner repository healthy with private authenticated Redis, MongoDB, and persistent artifact storage; global replay stayed valid across Redis and Bucket restarts |
| Karma | local published-contract integrity service returned `appended` and supplied the exact canonical bytes forwarded to PRANA |
| PRANA | local published-contract forwarder proved strict byte equality, payload SHA-256 equality, and trace preservation |
| InsightFlow | owner registry and PostgreSQL persisted both execution telemetry envelopes through the bridge |
| Central Depository | local Bucket append-only contract stored, read back, and replay-validated both handover packages; no independent owner service is claimed |
| UniGuru | owner container healthy, personal Supabase client enabled, attachment `ATTACHED`; drip-irrigation execution `eco_07fa5401aaf94ebfb2cfd6ead3cd5424` completed |
| Trade Bot | owner container healthy with trained model artifacts, attachment `ATTACHED`; NVDA execution `eco_1ac97452891c43bdad40b786eb5b9089` returned the requested symbol and completed |

The product owner remains authoritative over its response. Mitra preserved
both returned product payloads without changing their semantics and verified
their response hashes in replay. Dispatch still
fails closed whenever a real attachment is unhealthy and never emulates a
product. See
`docs/ECOSYSTEM_CONFIGURATION_STATUS.md` for exact outputs, rebuild order, and
the complete error ledger.

1. A product connects with `POST /api/v1/products/connect` using a published
   manifest.
2. The runtime materializes the product's capabilities and explicit intents.
3. A client creates or resumes a session.
4. Mitra analyzes the user request, loads only required context, and routes to
   a declared intent.
5. Products share explicit payloads through `POST /api/v1/product-exchanges`;
   targets read `/api/v1/products/{product_id}/exchange-inbox` and acknowledge
   `/api/v1/product-exchanges/{exchange_id}/ack`.
6. Dispatch receipts, phase journals, and proof bundles remain available for
   downstream consumers.

## Run

```powershell
python -m pip install -e .
mitra-companion validate
mitra-companion serve --port 8090
```

Production container path:

```powershell
docker compose up -d --wait
k6 run scripts/load/k6_companion_runtime.js
```

Real local ecosystem path:

```powershell
python scripts/configure_local_ecosystem.py
# Follow the dependency-ordered startup in docs/HANDOVER.md.
docker compose -f docker-compose.ecosystem.yml ps
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
```

Independent hosted path:

```powershell
# Uses https://mitra-live-runtime-sprint.vercel.app by default.
python scripts/validate_hosted_runtime.py
```

Hosted runtime and main website connection:

```text
Runtime API/dashboard: https://mitra-live-runtime-sprint.vercel.app
Main Mitra website:    https://mitra.blackholeinfiverse.com
```

The runtime is intentionally hosted on the alternate Vercel URL above for this
submission. The main website can connect to it when required by pointing the
frontend API base or proxy at this runtime host. Compatibility routes are
available for the existing website contract under `/api/companion/*` and
`/api/workflow/run`. The website should call or proxy
`POST /api/v1/ecosystem/execute` when it requires the final strict Raj-to-
Depository chain. The current Vercel process cannot reach the local owner
containers, so the full-chain acceptance result is local Docker evidence, not
a public full-chain deployment claim. The production readiness endpoint now
fails closed when owner configuration, public endpoint portability, durable
storage, or release identity requirements are not satisfied. See
`docs/DEPLOYMENT_PARITY.md`.

Vercel upload through the assigned team:

```powershell
pnpm dlx vercel@latest deploy --prod --scope team_ciZh4E8ZRzVl7Gxnwl5y5Wbq
```

## Useful Endpoints

- Dashboard: `http://localhost:8090/`
- OpenAPI: `http://localhost:8090/docs`
- Health: `GET /health`
- Readiness: `GET /ready`
- Metrics: `GET /metrics`
- Runtime status: `GET /api/v1/runtime/status`
- Runtime startup: `GET /api/v1/runtime/startup`
- Runtime config: `GET /api/v1/runtime/config`
- Deployment parity: `GET /api/v1/runtime/deployment-parity`
- Runtime instances: `GET /api/v1/runtime/instances`
- Capability graph: `GET /api/v1/runtime/capability-graph`
- Capability plan: `POST /api/v1/runtime/capability-plan`
- Runtime depository: `GET /api/v1/runtime/depository`
- Runtime integrations: `GET /api/v1/runtime/integrations`
- Ecosystem readiness: `GET /api/v1/ecosystem/readiness`
- Ecosystem execution: `POST /api/v1/ecosystem/execute`
- Ecosystem replay: `GET /api/v1/ecosystem/executions/{execution_id}/replay`
- Offline replay validation: `POST /api/v1/ecosystem/replay/validate`
- Product connect: `POST /api/v1/products/connect`
- Product exchange: `POST /api/v1/product-exchanges`
- Intent dispatch: `POST /api/v1/intents/dispatch`
- Dispatch proof: `GET /api/v1/dispatches/{dispatch_id}/proof`
- Dispatch reconstruction: `GET /api/v1/dispatches/{dispatch_id}/reconstruction`

## Repository Map

```text
pratham/
  companion-runtime/   API, composition, lifecycle, transport, storage
  context-runtime/     scoped context loading and updates
  intent-router/       manifest-derived intent lookup
  session-runtime/     sessions and resume tokens
  attachment-runtime/  manifest validation and attachment state

contracts/
  api/                 OpenAPI contract
  schemas/             JSON Schema contracts
  examples/            attachable product manifests
```

## Verify

```powershell
pytest
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
python scripts/validate_hosted_runtime.py
python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8190 --summary
python scripts/validate_ecosystem_runtime.py --validate-package /data/operational-acceptance --summary
```

Current coverage includes product connection, product exchanges, sessions,
context isolation, routing, dispatch, production startup/restart/recovery,
multi-instance heartbeat, source-scope reuse, phase journals, proof bundles,
deterministic reconstruction, depository lineage, capability graph planning, and
companion continuity. Acceptance is based on assertions over actual runtime
outputs. The hosted validator sends a complete session, attachment, dispatch,
reconstruction, recovery, metrics, and telemetry flow to the deployed API and
fails when returned values do not match the submitted data or contracts.

`scripts/validate_ecosystem_runtime.py` is the stronger owner-topology gate. It
submits the declarative cases in `contracts/operational-acceptance.json`, checks
every returned owner receipt, verifies execution-scoped depository lineage,
replays in an isolated Python process, and confirms that a mutated recorded
response is rejected. Static readiness and hosted-surface checks do not replace
this command. The `--validate-package` form is the offline handover check: it
requires no runtime URL and proves retained packages plus tamper rejection in
an isolated Python process.

## Main Docs

- [Documentation Index](docs/DOCUMENTATION_INDEX.md)
- [Clean-Room Handover](docs/HANDOVER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Integration Guide](docs/INTEGRATION_GUIDE.md)
- [BHIV Product Integration](docs/BHIV_PRODUCT_INTEGRATION.md)
- [Operations Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [Production Hardening](docs/PRODUCTION_HARDENING.md)
- [Previous Submission Reuse](docs/PREVIOUS_SUBMISSION_REUSE.md)
- [Mitra Expectation Baseline](docs/MITRA_EXPECTATION_BASELINE.md)
- [Feedback Acceptance Upgrades](docs/FEEDBACK_ACCEPTANCE_UPGRADES.md)
- [Final Runtime Convergence](docs/FINAL_RUNTIME_CONVERGENCE.md)
- [TANTRA Ecosystem Convergence](docs/TANTRA_ECOSYSTEM_CONVERGENCE.md)
- [Ecosystem Configuration Status](docs/ECOSYSTEM_CONFIGURATION_STATUS.md)
- [Ashmit Owner Runtime](docs/ASHMIT_OWNER_RUNTIME.md)
- [Central Depository Handover](docs/CENTRAL_DEPOSITORY_HANDOVER.md)
- [Independent Hosting](docs/INDEPENDENT_HOSTING.md)
- [Vercel Deployment](docs/VERCEL_DEPLOYMENT.md)
- [Deployment Parity](docs/DEPLOYMENT_PARITY.md)
- [Phase 3 Production Deployment](docs/PHASE_3_PRODUCTION_DEPLOYMENT.md)
- [SLO and Capacity](docs/SLO_AND_CAPACITY.md)
- [Security Boundary Re-execution](REEXECUTION_REPORT.md)
