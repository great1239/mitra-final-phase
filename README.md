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
`/api/workflow/run`; those routes still execute through Mitra's runtime
analysis, manifest matching, dispatch, telemetry, replay, and depository flow.

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
- Runtime instances: `GET /api/v1/runtime/instances`
- Capability graph: `GET /api/v1/runtime/capability-graph`
- Capability plan: `POST /api/v1/runtime/capability-plan`
- Runtime depository: `GET /api/v1/runtime/depository`
- Runtime integrations: `GET /api/v1/runtime/integrations`
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
```

Current coverage includes product connection, product exchanges, sessions,
context isolation, routing, dispatch, production startup/restart/recovery,
multi-instance heartbeat, source-scope reuse, phase journals, proof bundles,
deterministic reconstruction, depository lineage, capability graph planning, and
companion continuity. Acceptance is based on assertions over actual runtime
outputs. The hosted validator sends a complete session, attachment, dispatch,
reconstruction, recovery, metrics, and telemetry flow to the deployed API and
fails when returned values do not match the submitted data or contracts.

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
- [Central Depository Handover](docs/CENTRAL_DEPOSITORY_HANDOVER.md)
- [Independent Hosting](docs/INDEPENDENT_HOSTING.md)
- [Vercel Deployment](docs/VERCEL_DEPLOYMENT.md)
- [Phase 3 Production Deployment](docs/PHASE_3_PRODUCTION_DEPLOYMENT.md)
- [SLO and Capacity](docs/SLO_AND_CAPACITY.md)
- [Security Boundary Re-execution](REEXECUTION_REPORT.md)
