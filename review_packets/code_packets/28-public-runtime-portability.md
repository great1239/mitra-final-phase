# Public Runtime Portability

## File: `render.yaml`

**Sprint change:** Added the independently hosted public module Blueprint.

**Purpose:** Declares Raj, Karma, PRANA, and the two-service InsightFlow
topology as reproducible public services.

**Why modified:** The public Mitra host cannot converge with Docker-only module
URLs, and Karma plus InsightFlow require durable network storage.

**Key implementation areas:** Five free web services, service-to-service
secret references, managed database inputs, public health checks, and pinned
owner InsightFlow source.

**Review focus:** No localhost routes or credential values are committed, and
every dependency reference resolves to a published HTTPS contract.

**Related tests:** `pratham/tests/test_production_readiness_gate.py` and hosted
health/contract validation.

## File: `integration_services/start_insightflow.sh`

**Sprint change:** Added one portable owner-registry startup entrypoint.

**Purpose:** Runs InsightFlow migrations, seeds the Mitra API key, and starts
the owner FastAPI registry.

**Why modified:** Render treated a quoted multi-command override as one
executable name; local Docker and Render needed the same unambiguous boot path.

**Key implementation areas:** Fail-fast shell mode, Alembic migration, API-key
seeding, `exec` handoff, and platform `PORT` support.

**Review focus:** The script changes startup only; it does not alter owner
InsightFlow behavior or schemas.

**Related tests:** Local image build and shell validation; hosted registry and
bridge `/health`.

## File: `pratham/tests/test_postgres_runtime_store.py`

**Sprint change:** Added cross-instance PostgreSQL persistence coverage.

**Purpose:** Proves that sessions, context, immutable artifacts, lineage, and
runtime leases survive complete store recreation.

**Why modified:** A schema-compatible adapter alone is not evidence that state
persists across a cold start.

**Key implementation areas:** Isolated schema, first-store writes, second-store
read-back, advisory-lock lease path, and guaranteed schema cleanup.

**Review focus:** The second store receives no in-memory state from the first;
all assertions are backed by PostgreSQL reads.

**Related tests:** Runs in CI through `MITRA_TEST_POSTGRES_URL`; the complete
SQLite regression suite remains unchanged.
