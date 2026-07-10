# Deterministic Replay And Depository

## File: `pratham/companion-runtime/mitra_companion/reconstruction.py`

**Sprint change:** Added

**Purpose:** Reconstructs complete dispatch execution solely from immutable,
content-addressed runtime artifacts.

**Why modified:** Replaced dispatch-history proof with deterministic
reconstruction covering lifecycle, sessions, routing, attachments, context,
dispatch, telemetry, recovery, and failures.

**Key implementation areas:** Component snapshot recording; package hashing;
artifact-only loading; scope coverage; hash verification; lineage verification;
execution reconstruction.

**Review focus:** Whether mutable runtime state can influence replay, canonical
hash stability, missing-artifact behavior, chain validation, and fidelity of
the reconstructed request and response.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py::test_dispatch_records_verified_reconstruction_and_depository`.

## File: `pratham/companion-runtime/mitra_companion/depository.py`

**Sprint change:** Added

**Purpose:** Stores runtime-owned artifacts by canonical SHA-256 hash and
records immutable lineage references.

**Why modified:** Added the runtime export boundary required for independent
artifact verification and Central Depository handover without claiming
external depository authority.

**Key implementation areas:** Canonical artifact storage; metadata persistence;
parent-chain hashing; lineage reads; filtered artifact access; bounded
snapshots.

**Review focus:** Content-address stability, duplicate insertion behavior,
parent hash continuity, subject isolation, and authority-boundary wording.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py`,
`pratham/tests/test_bhiv_integrations.py`.

## File: `pratham/tests/test_replay_convergence_and_graph.py`

**Sprint change:** Added

**Purpose:** Executes acceptance coverage for replay fidelity, depository
exports, capability composition, companion continuity, and scale.

**Why modified:** Added executable checks for the principal gaps identified in
the prior sprint feedback.

**Key implementation areas:** Clean artifact reconstruction; schema validation;
lineage continuity; 200-product catalog scale; graph planning; identity,
preference, and trust continuity.

**Review focus:** Strength of assertions, clean-state independence, negative
coverage, fixture realism, and whether tests verify outputs rather than merely
the presence of APIs.

**Related tests:** This file is the focused test suite; it is complemented by
`pratham/tests/test_bhiv_integrations.py` and
`pratham/tests/test_dispatch_and_failures.py`.

