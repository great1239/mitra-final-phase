# Mitra Final Runtime Convergence

This document maps the final assignment to the implemented repository changes.

## Assignment Mapping

| Assignment phase | Repository implementation |
|---|---|
| Deterministic Replay | `mitra_companion.ecosystem.EcosystemReplayLedger` reconstructs the complete cross-owner execution from the portable package alone. It validates request/response, stage artifact, lineage, contract, reconstructed-output, and package hashes with zero database reads or live calls. |
| BHIV Runtime Convergence | `mitra_companion.ecosystem.EcosystemRuntime` executes Raj, the selected product, conditional KESHAV diagnosis, Ashmit, Bucket, Karma, PRANA, InsightFlow, replay, and Central Depository. Missing owner configuration returns 503; invalid owner contracts fail closed; there is no embedded fallback. |
| TANTRA Runtime Handover | `mitra_companion.tantra_handover.TantraHandoverAdapter` projects the verified execution into the prior four-bundle consumer contract, persists exact wire hashes, and calls only the published TANTRA gateway when configured. |
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
- `MITRA_RAJ_WORKFLOW_BASE_URL`
- `MITRA_RAJ_API_KEY`
- `MITRA_BHIV_BUCKET_BASE_URL`
- `MITRA_BHIV_KESHAV_BASE_URL`
- `MITRA_BHIV_INSIGHTFLOW_INGEST_URL`
- `MITRA_BHIV_INSIGHTFLOW_API_KEY`
- `MITRA_BHIV_KARMA_BASE_URL`
- `MITRA_BHIV_PRANA_BASE_URL`
- `MITRA_BHIV_BUCKET_PARENT_HASH`
- `MITRA_BHIV_KARMA_PREVIOUS_HASH`
- `MITRA_ECOSYSTEM_TIMEOUT_SECONDS`
- `MITRA_TANTRA_GATEWAY_URL`
- `MITRA_TANTRA_API_KEY`
- `MITRA_TANTRA_INTEGRATION_TIMEOUT_SECONDS`

`GET /api/v1/ecosystem/readiness` reports whether every owner is configured.
`GET /api/v1/ecosystem/contracts` reports the exact published contract set and
authority boundary. Controlled contract tests assert every request, response,
hash, ordering rule, strict byte check, trace bridge, failure, and recovery.

## Validation Commands

```powershell
python -m pytest pratham/tests/test_ecosystem_convergence.py -q
python -m pytest pratham/tests -q
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
