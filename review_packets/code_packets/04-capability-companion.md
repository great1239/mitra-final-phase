# Capability Planning And Companion Continuity

## File: `pratham/companion-runtime/mitra_companion/capability_graph.py`

**Sprint change:** Added

**Purpose:** Builds dynamic product, capability, and intent graphs from
published manifests and composes candidate multi-system execution plans.

**Why modified:** Upgraded primitive registered-capability lookup and added the
missing intent-composition layer identified in prior feedback.

**Key implementation areas:** Manifest tokenization; schema field matching;
graph nodes and edges; message relevance; input/output composition edges;
bounded plan ranking.

**Review focus:** Determinism, false-positive composition, schema
compatibility, ranking stability, graph growth, and the lack of hardcoded
product knowledge.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py::test_capability_graph_and_plan_cover_bhiv_convergence_products`,
`pratham/tests/test_replay_convergence_and_graph.py::test_scale_catalog_handles_200_simulated_products`.

## File: `contracts/runtime-command-chain.json`

**Sprint change:** Modified

**Purpose:** Defines the manifest-first runtime workflow and its BHIV handoff
targets as data.

**Why modified:** Extended the command chain with capability planning,
deterministic reconstruction, convergence consumers, and explicit ownership
boundaries.

**Key implementation areas:** Stage ordering; required inputs and outputs;
consumer handoffs; failure policy; versioned runtime flow.

**Review focus:** Consistency with `CompanionRuntime`, absence of implicit
product branches, serial versus parallel handoff semantics, and complete
failure outputs.

**Related tests:** `pratham/tests/test_companion_interaction.py`,
`pratham/tests/test_bhiv_integrations.py`.

## File: `pratham/tests/test_companion_interaction.py`

**Sprint change:** Modified

**Purpose:** Verifies companion selection, execution, clarification, fallback,
memory, tasks, and API behavior.

**Why modified:** Expanded executable coverage for sparse BHIV capability
understanding, AI-assisted payload analysis, and fallback through published
capabilities.

**Key implementation areas:** Natural intent selection; schema payload
inference; clarification; fallback routing; memory persistence; streaming and
task APIs.

**Review focus:** Deterministic fallback, ambiguous requests, missing required
fields, product neutrality, trust updates, and successful versus failed task
state.

**Related tests:** This file is the focused suite; continuity assertions also
live in `pratham/tests/test_replay_convergence_and_graph.py`.

