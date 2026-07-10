# Validation Report

Consolidated on July 10, 2026. This report replaces the separate
`PHASE_*_VALIDATION_REPORT.md` files and keeps the validation record focused on
runtime behavior, executable checks, and known limits. It is not a generated
evidence package.

## Overall Status

Mitra's maintained validation entry point is the current runtime plus the
review packet, not the historical per-phase reports. The runtime covers
lifecycle, sessions, context isolation, attachment, routing, transport,
product exchange, companion interaction, dispatch persistence, deterministic
reconstruction, Central Depository lineage, BHIV contracts, recovery, restart
continuity, multi-instance state, concurrency, OpenAPI, JSON Schema,
ownership, and deployment configuration.

## Phase Summary

| Area | Result | Evidence |
|---|---|---|
| Phase 1 - runtime foundation | Passed | `CompanionRuntime`, lifecycle/state catalogs, runtime interfaces, package/CLI validation |
| Phase 2 - context runtime | Passed | session/workspace/product/handoff partitions, scoped loading, restart continuity, isolation tests |
| Phase 3 - intent router | Passed | manifest-derived registration, discovery, dispatch, capability lookup, degraded-product fail-closed behavior |
| Phase 4 - product attachment | Passed | self-attachment API, schema validation, detach audit, adapter extension without runtime edits |
| Phase 5 - integration contracts | Passed | OpenAPI, integration catalog, JSON Schemas, versioned contract examples |
| Phase 6 - runtime simulation | Passed | multi-product routing, context transfer, invalid payload rejection, failure containment |
| Phase 7 - documentation package | Passed | architecture, execution flow, diagrams, onboarding, review packet, submission index |
| Final convergence sprint | Passed with external limits | deterministic reconstruction, Central Depository artifacts, BHIV contract calls, hosted dashboard/API/OpenAPI/health/metrics |

## Current Verification Commands

```powershell
python -m pytest
python scripts/production_readiness_gate.py
python scripts/validate_hosted_runtime.py
k6 run scripts/load/k6_companion_runtime.js
```

`validate_hosted_runtime.py` submits real attachment, session, and dispatch
data. It checks returned output, deterministic reconstruction, phase journals,
recovery, metrics, and telemetry. It exits nonzero on mismatch and does not
create proof documents or screenshots.

Run sustained load against a durable deployment. Vercel's ephemeral serverless
storage is not the continuity or recovery validation topology.

## Last Recorded Sprint Evidence

- Focused Samruddhi product integration tests: `4 passed`.
- Contract examples and production-mode tests: `7 passed`.
- Production readiness and handover gate: passed.
- Hosted production alias: `https://mitra-live-runtime-sprint.vercel.app`.
- Hosted deployment URL:
  `https://mitra-live-runtime-sprint-n4amutwv1-bhiv-intern.vercel.app`.
- Hosted `/health`: healthy during the last recorded validation.
- Production attachments: `samruddhi-trade-bot` and `samruddhi-uniguru`.
- Root-level phase reports were historical checkpoints and have been merged
  into this file to remove review noise.

## Known Limits

- Hosted Vercel state is ephemeral; durable recovery, failover, and sustained
  load validation belong on the Docker/Render durable-host topology.
- Trade Bot was last observed as externally degraded because its Render service
  returned `503 Service Suspended`.
- UniGuru was last observed as externally degraded because its `/health` route
  redirected or returned non-JSON.
- Hosted routing and replay require at least one real attached downstream
  product to be available; fixture attachments are not accepted as production
  proof.

## Review Entry Points

- Rebuild instructions: `docs/HANDOVER.md`.
- Central Depository transfer: `docs/CENTRAL_DEPOSITORY_HANDOVER.md`.
- Current review packet: `review_packets/REVIEW_PACKET.md`.
- Code packet: `review_packets/code_packets/README.md`.
- Testing evidence: `review_packets/testing/TESTING_EVIDENCE.md`.
