# Clean Rebuild Efficiency

## File: `Dockerfile`

**Sprint change:** Modified

**Purpose:** Builds the production Mitra image and includes its operational
commands.

**Why modified:** Validator-only edits previously invalidated the dependency
installation layer and made every acceptance iteration reinstall the full
runtime.

**Key implementation areas:** Runtime installation before script copy;
read-only script ownership for the non-root runtime user.

**Review focus:** Installed package parity, final image contents, non-root
execution, and Docker cache behavior.

**Related tests:** Fresh image build, Compose healthcheck, hosted-surface
validation, and two-product operational acceptance.

## File: `README.md`

**Sprint change:** Modified

**Purpose:** Directs reviewers and incoming engineers to the authoritative
runtime and validation entry points.

**Why modified:** The previous quick-start stopped after configuration and did
not execute the complete owner chain.

**Key implementation areas:** Current execution IDs; canonical acceptance
command; public versus local boundary; replay behavior.

**Review focus:** Commands must agree with `docs/HANDOVER.md`, and no public
full-chain claim may be inferred from the Vercel surface alone.

**Related tests:** `pratham/tests/test_production_readiness_gate.py` and the
2026-07-20 live acceptance run.
