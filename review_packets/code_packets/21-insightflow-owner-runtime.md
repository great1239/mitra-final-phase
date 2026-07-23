# InsightFlow Owner Runtime

## File: `integration_services/insightflow-owner.Dockerfile`

**Sprint change:** Added a pinned build of the `VJY123VJY/bhiv` owner registry.

**Purpose:** Runs the real owner dataset/provenance API with PostgreSQL.

**Why modified:** InsightFlow required owner code rather than an in-process
stand-in.

**Key implementation areas:** Pinned commit, sparse checkout, migrations,
production logging mode.

**Review focus:** The owner application is copied unchanged from the pinned
repository revision.

**Related tests:** Registry health and protected provenance read-back.

## File: `integration_services/insightflow_bridge.py`

**Sprint change:** Added a transport adapter from PRANA/Mitra envelopes to the
owner registry contracts.

**Purpose:** Registers one canonical dataset and stores trace-bearing
provenance through owner APIs.

**Why modified:** The registry does not publish PRANA ingress routes.

**Key implementation areas:** Dataset lookup/registration, payload SHA-256,
trace retention, protected owner calls.

**Review focus:** The adapter transports facts and does not interpret or score
telemetry.

**Related tests:**
`test_insightflow_bridge_registers_dataset_and_provenance`.

## File: `integration_services/seed_insightflow_key.py`

**Sprint change:** Added idempotent owner API-key seeding.

**Purpose:** Makes authenticated local registry calls possible without logging
the plaintext key.

**Why modified:** Owner dataset and provenance endpoints require a stored key
hash.

**Key implementation areas:** Database seed, key hashing, idempotency,
production-safe output.

**Review focus:** No plaintext credential may reach logs or tracked files.

**Related tests:** One-shot seed exits zero and authenticated owner calls pass.
