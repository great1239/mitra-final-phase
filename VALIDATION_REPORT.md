# Validation Report

This file records the current repository-level verification entry points. It
is not a generated evidence package.

## Automated Verification

```powershell
python -m pytest
python scripts/production_readiness_gate.py
```

The suite covers lifecycle, sessions, context isolation, attachment, routing,
transport, product exchange, companion interaction, dispatch persistence,
deterministic reconstruction, Central Depository lineage, BHIV contracts,
recovery, restart continuity, multi-instance state, concurrency, OpenAPI, JSON
Schema, ownership, and deployment configuration.

## Hosted Verification

```powershell
python scripts/validate_hosted_runtime.py
```

The validator submits real attachment, session, and dispatch data. It checks
the returned output, deterministic reconstruction, phase journal, recovery,
metrics, and telemetry. It exits nonzero on mismatch and does not create proof
documents or screenshots.

## Sustained Load

```powershell
k6 run scripts/load/k6_companion_runtime.js
```

Run sustained load against a durable deployment. Vercel's ephemeral serverless
storage is not the continuity or recovery validation topology.

## Handover

Rebuild instructions: `docs/HANDOVER.md`.

Central Depository transfer: `docs/CENTRAL_DEPOSITORY_HANDOVER.md`.
