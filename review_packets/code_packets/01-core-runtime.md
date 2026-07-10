# Core Runtime Orchestration

## File: `pratham/companion-runtime/mitra_companion/runtime.py`

**Sprint change:** Modified

**Purpose:** Owns Mitra lifecycle, attachment, session, routing, dispatch,
recovery, companion, reconstruction, and ecosystem handoff orchestration.

**Why modified:** Connected deterministic reconstruction, Central Depository
artifacts, BHIV publication, capability planning, companion continuity, and
multi-instance recovery to the live dispatch path. Added production attachment
policy enforcement so example, simulated, loopback, and localhost manifests are
not accepted by default in production.

**Key implementation areas:** Runtime startup and supervisor; dispatch phase
journal; reconstruction recording; BHIV convergence publication; capability
graph and plan; companion memory; subject-filtered depository export;
attachment policy validation.

**Review focus:** Transaction and failure boundaries, ordering of immutable
artifact creation versus external publication, fail-closed integration
behavior, production rejection of fixture manifests, and the absence of
product-specific branching.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py`,
`pratham/tests/test_bhiv_integrations.py`,
`pratham/tests/test_companion_interaction.py`.

## File: `pratham/companion-runtime/mitra_companion/store.py`

**Sprint change:** Modified

**Purpose:** Provides durable SQLite state for runtime instances, dispatch
phases, artifacts, lineage, messages, tasks, and operational recovery.

**Why modified:** Added the persistence primitives required for immutable
reconstruction, content-addressed artifacts, hash-chain lineage, companion
continuity, and stale-instance reconciliation.

**Key implementation areas:** Schema migrations; artifact and lineage tables;
runtime heartbeat state; dispatch phase persistence; companion message and task
records.

**Review focus:** Migration safety, transaction boundaries, deterministic
ordering, JSON serialization, lineage sequence integrity, and concurrent
instance access.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py`,
`pratham/tests/test_production_hardening.py`,
`pratham/tests/test_companion_interaction.py`.

## File: `pratham/companion-runtime/mitra_companion/api.py`

**Sprint change:** Modified

**Purpose:** Exposes the versioned runtime, operator, companion, replay,
depository, integration, and observability APIs.

**Why modified:** Added the final convergence endpoints and dashboard surfaces
for capability planning, runtime analysis, deterministic reconstruction,
Central Depository export, recovery, integrations, metrics, telemetry, and
strict directory-manifest bootstrap policy.

**Key implementation areas:** Runtime operator routes; dispatch reconstruction;
depository filters; companion APIs; dashboard status; versioned response
envelopes; filtered production manifest source wiring.

**Review focus:** Contract compatibility, status and error semantics, bounded
query parameters, response completeness, and whether every published call has
an explicit response.

**Related tests:** `pratham/tests/test_companion_interaction.py`,
`pratham/tests/test_dispatch_and_failures.py`,
`pratham/tests/test_replay_convergence_and_graph.py`.
