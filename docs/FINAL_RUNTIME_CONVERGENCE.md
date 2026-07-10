# Mitra Final Runtime Convergence

This document maps the final assignment to the implemented repository changes.

## Assignment Mapping

| Assignment phase | Repository implementation |
|---|---|
| Deterministic Replay | `mitra_companion.reconstruction.DeterministicReconstructionLedger` reconstructs dispatch execution from immutable artifacts and verifies hashes plus lineage continuity. |
| BHIV Runtime Convergence | `mitra_companion.bhiv_integrations.BHIVRuntimeIntegrator` publishes runtime evidence through Ashmit, Bucket, InsightFlow, Karma, and PRANA contracts. |
| Production Deployment | `Dockerfile`, `docker-compose.yml`, `deploy/production.env.example`, `/health`, `/ready`, `/metrics`, `/docs`, and runtime operator APIs. |
| Production Validation | Runtime tests execute multi-instance continuity, recovery, replay, concurrency, and failure paths. `scripts/load/k6_companion_runtime.js` applies sustained load and `scripts/validate_hosted_runtime.py` validates actual hosted responses. |
| Runtime outputs | The dispatch, reconstruction, telemetry, metrics, integration response, and Central Depository APIs expose the real outputs used for acceptance. |
| Documentation & Handover | `review_packets/REVIEW_PACKET.md`, this document, and `docs/CENTRAL_DEPOSITORY_HANDOVER.md`. |

## BHIV Contract Boundaries

Mitra emits runtime-owned artifacts and deterministic reconstruction. It does
not become governance, business-logic, external replay, certification, or
Central Depository acceptance authority.

Configured endpoint variables:

- `MITRA_BHIV_ASHMIT_BASE_URL`
- `MITRA_BHIV_BUCKET_BASE_URL`
- `MITRA_BHIV_INSIGHTFLOW_INGEST_URL`
- `MITRA_BHIV_KARMA_BASE_URL`
- `MITRA_BHIV_PRANA_BASE_URL`
- `MITRA_BHIV_BUCKET_PARENT_HASH`
- `MITRA_BHIV_KARMA_PREVIOUS_HASH`

Tests use contract transports to assert exact request and response behavior.
Production validation uses configured endpoints and does not substitute mocked
responses for a hosted integration.

## Validation Commands

```powershell
python -m pytest pratham/tests/test_bhiv_integrations.py pratham/tests/test_replay_convergence_and_graph.py -q
python scripts/production_readiness_gate.py
k6 run scripts/load/k6_companion_runtime.js
python scripts/validate_hosted_runtime.py
```

## Hosted Runtime Status

The canonical hosted runtime for this sprint is:

```text
https://mitra-live-runtime-sprint.vercel.app
```

The hosted validator uses this Vercel URL by default. Set
`MITRA_HOSTED_RUNTIME_URL` only when deliberately validating an alternate
deployment.
