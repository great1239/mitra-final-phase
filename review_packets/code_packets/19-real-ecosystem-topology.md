# Real Ecosystem Topology

## File: `docker-compose.ecosystem.yml`

**Sprint change:** Added a health-gated deployment for the response-bearing
Mitra ecosystem.

**Purpose:** Runs Mitra, KESHAV, Ashmit, the Bucket owner repository, Raj,
Karma, PRANA, the InsightFlow owner registry and bridge, MongoDB, authenticated
Redis, PostgreSQL, and optional product profiles. Ashmit uses the owner Atlas
URI while Bucket keeps an independent local MongoDB URI.

**Why modified:** Configured owner slots previously had no jointly runnable
topology.

**Key implementation areas:** Dependency health gates, distinct Ashmit and
Bucket database variables, owner builds including
KESHAV's sibling repository and exact service identity, Redis AOF and artifact
volumes, loopback-only ports, container-held credentials,
required Supabase variables, optional product profiles, and generic published
origin overrides for local product health and dispatch.

**Review focus:** No product profile is required for core startup and no secret
value is embedded in the file.

**Related tests:** `integration_services/tests/test_contract_services.py`,
`pratham/tests/test_ecosystem_convergence.py`, three completed live acceptance
executions including the KESHAV error path, and Redis/Bucket restart
persistence validation.

## File: `scripts/configure_local_ecosystem.py`

**Sprint change:** Added atomic generation and key rotation for the ignored
local ecosystem environment, then added Trade Bot checkout validation.

**Purpose:** Reads authorized sibling owner configuration and creates the root
`.env` without committing credentials.

**Why modified:** Compose needed repeatable secret wiring, Atlas-backed Ashmit,
and an independently authenticated local MongoDB store for Bucket.

**Key implementation areas:** Required Ashmit, Bucket, UniGuru, and Trade Bot
checkout validation; local Mongo
URI separation, Bucket Redis secret generation, Supabase presence validation, shared
product endpoint maps, InsightFlow rotation, atomic replacement.

**Review focus:** Only variable names are printed; secret values remain in the
ignored file.

**Related tests:** Python compilation, clean configuration, secret-presence
validation, and dependency-ordered Compose startup.

## File: `deploy/local-ecosystem.env.example`

**Sprint change:** Added the non-secret local topology environment template.

**Purpose:** Documents required owner paths and variable names for handover.

**Why modified:** Incoming engineers need the configuration shape before
running the generator.

**Key implementation areas:** Owner contexts, local databases, generated keys,
Bucket Redis, UniGuru Supabase, contract endpoints.

**Review focus:** Every value must remain a placeholder.

**Related tests:** Compose variable expansion during clean startup.
