# Docker Deployment Repair

## File: `docker-compose.yml`

**Sprint change:** Modified

**Purpose:** Defines the durable local production deployment for the Mitra
runtime and OpenTelemetry collector.

**Why modified:** Repaired Docker Compose v5 validation by replacing
conflicting top-level `pids_limit` settings with
`deploy.resources.limits.pids`, and changed the SQLite-backed runtime profile
to one Uvicorn worker per container.

**Key implementation areas:** Production manifest directory; strict manifest
policy; resource limits; process limits; single-worker runtime; healthcheck;
read-only container controls.

**Review focus:** Compose v5 compatibility, healthcheck reliability, resource
limit preservation, and alignment with the SQLite durability topology.

**Related tests:** `pratham/tests/test_production_readiness_gate.py`,
`scripts/production_readiness_gate.py`, Docker Compose validation.

## File: `deploy/production.env.example`

**Sprint change:** Modified

**Purpose:** Documents production environment values for durable deployments.

**Why modified:** Matched the repaired Docker profile by using one Uvicorn
worker for SQLite-backed containers while retaining strict production manifest
policy and WAL-friendly SQLite settings.

**Key implementation areas:** Worker count; manifest directory; manifest
policy flags; SQLite synchronous mode; production logging; telemetry
configuration.

**Review focus:** Operator copy/paste safety, parity with Compose, and whether
defaults avoid simulated/example startup attachments.

**Related tests:** `pratham/tests/test_production_readiness_gate.py`.

## File: `pratham/tests/test_production_readiness_gate.py`

**Sprint change:** Modified

**Purpose:** Verifies production deployment, documentation, code-packet, and
testing-evidence gates.

**Why modified:** Updated assertions to require Compose-compatible `pids`
limits, the one-worker Docker profile, and the repaired Docker evidence in the
testing packet.

**Key implementation areas:** Compose hardening assertions; production env
assertions; testing evidence markers; readiness-gate command execution.

**Review focus:** Whether the test prevents regression to the broken
`pids_limit` Compose profile and stale Docker-blocked evidence.

**Related tests:** This file is the focused readiness-gate suite.
