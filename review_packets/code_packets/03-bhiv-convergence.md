# BHIV Runtime Convergence

## File: `pratham/companion-runtime/mitra_companion/bhiv_integrations.py`

**Sprint change:** Replaced legacy executor with a non-executing compatibility recorder

**Purpose:** Preserves the ordinary dispatch response shape while directing all
owner execution to `EcosystemRuntime`. It never calls or emulates an owner.

**Why modified:** The previous implementation duplicated the canonical chain
and could produce local owner successes. That path conflicted with the required
no-mock, owner-contract-only workflow.

**Key implementation areas:** canonical endpoint declaration; redacted
configuration status; zero-I/O `not_executed` results; immutable compatibility
record and lineage.

**Review focus:** Confirm no HTTP method is reachable from this compatibility
class, no embedded owner implementation remains, and ordinary dispatch points
reviewers to `/api/v1/ecosystem/execute`.

**Related tests:** `pratham/tests/test_bhiv_integrations.py`,
`pratham/tests/test_tantra_handover.py`.

## File: `contracts/integration-contracts.json`

**Sprint change:** Modified

**Purpose:** Declares the published cross-module operations, request/response
contracts, compatibility versions, and ownership constraints.

**Why modified:** Added convergence and depository operations plus explicit
response shapes so integrations remain contract-driven rather than encoded as
runtime product branches.

**Key implementation areas:** Operation catalog; request and response schemas;
integration ownership; source-scope entries; contract versioning.

**Review focus:** Agreement with the implementation and OpenAPI, required
response fields, version consistency, and whether external authority remains
outside Mitra.

**Related tests:** `pratham/tests/test_bhiv_integrations.py::test_legacy_exporter_declares_canonical_owner_workflow`,
`contracts/integration-tests/test_contract_examples.py`.

## File: `pratham/tests/test_bhiv_integrations.py`

**Sprint change:** Added

**Purpose:** Proves the compatibility exporter performs zero owner I/O and that
ordinary dispatch cannot be mistaken for ecosystem convergence.

**Why modified:** Removed tests whose expected result was a successful embedded
owner flow. Canonical sequencing is tested in `test_ecosystem_convergence.py`.

**Key implementation areas:** API catalog; canonical-only readiness; zero HTTP
calls even when endpoint settings are populated; `not_executed` response shape.

**Review focus:** Absence of local owner behavior and separation between product
dispatch and canonical ecosystem execution.

**Related tests:** This file is the focused suite; contract examples are
validated by `contracts/integration-tests/test_contract_examples.py`.
