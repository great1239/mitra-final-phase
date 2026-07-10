# Documentation And Handover

## File: `docs/HANDOVER.md`

**Sprint change:** Added

**Purpose:** Gives incoming engineers a clean-room rebuild, validation,
deployment, and operations path.

**Why modified:** Completed Phase 6 so the runtime can be rebuilt from
repository documentation alone.

**Key implementation areas:** Prerequisites; exact install and test commands;
local and container startup; configuration; hosted validation; troubleshooting;
acceptance checklist.

**Review focus:** Command reproducibility, missing assumptions, Windows and
container portability, version pinning, and truthful hosted limitations.

**Related tests:** `pratham/tests/test_production_readiness_gate.py::test_documentation_handover_contains_clean_rebuild_and_depository_protocol`.

## File: `docs/CENTRAL_DEPOSITORY_HANDOVER.md`

**Sprint change:** Added

**Purpose:** Defines how an external Central Depository consumer retrieves and
independently verifies Mitra artifacts and lineage.

**Why modified:** Added the required handover protocol while preserving the
external system's authority over acceptance and certification.

**Key implementation areas:** Export filters; canonical JSON; artifact hash
verification; lineage chain verification; failure handling; authority
boundary.

**Review focus:** Reproducibility of hashes, subject filtering, chain order,
consumer responsibilities, and whether HTTP success is kept separate from
artifact acceptance.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py`,
`pratham/tests/test_production_readiness_gate.py`.

## File: `review_packets/REVIEW_PACKET.md`

**Sprint change:** Modified

**Purpose:** Provides the mandatory reviewer entry point for execution flow,
production evidence, failure cases, limitations, and replay validation.

**Why modified:** Replaced stale sprint claims with the implemented final
runtime convergence flow and independently inspectable outputs.

**Key implementation areas:** Entry point; core and live flow; change summary;
failure cases; production evidence; known limitations; replay summary;
screenshot and code-packet links.

**Review focus:** Traceability from claims to runtime endpoints and tests,
clear separation of local versus hosted evidence, and disclosure of external
integration limitations.

**Related tests:** `pratham/tests/test_production_readiness_gate.py`.

