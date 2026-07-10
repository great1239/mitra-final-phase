# BHIV Runtime Convergence

## File: `pratham/companion-runtime/mitra_companion/bhiv_integrations.py`

**Sprint change:** Added

**Purpose:** Publishes Mitra runtime outputs to Ashmit, Bucket, InsightFlow,
Karma, PRANA, and the Central Depository export through declared contracts.

**Why modified:** Completed the assigned ecosystem handoffs while preserving
Mitra's ownership boundary and the required Karma-before-PRANA ordering.

**Key implementation areas:** API call catalog; canonical JSON and SHA-256;
Karma append acceptance; strict-byte PRANA forwarding; Bucket artifact
publication; InsightFlow envelope; Ashmit health; normalized responses.

**Review focus:** Exact request bytes, trace ID preservation, replay keys,
previous/parent hash handling, forwarding suppression after Karma rejection,
timeout behavior, and response capture for every call.

**Related tests:** `pratham/tests/test_bhiv_integrations.py`.

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

**Related tests:** `pratham/tests/test_bhiv_integrations.py::test_bhiv_integration_catalog_declares_response_contracts`,
`contracts/integration-tests/test_contract_examples.py`.

## File: `pratham/tests/test_bhiv_integrations.py`

**Sprint change:** Added

**Purpose:** Exercises real integration sequencing against contract transports
and validates each captured module response.

**Why modified:** Added interoperability checks for all available assigned
modules, including strict forwarding and rejection paths.

**Key implementation areas:** API response catalog; canonical request hashes;
Karma and PRANA sequencing; Bucket and InsightFlow payloads; Ashmit health;
depository references.

**Review focus:** Byte identity assertions, rejection-path isolation, response
schema coverage, and whether mocks emulate published contracts without hiding
runtime branching.

**Related tests:** This file is the focused suite; contract examples are
validated by `contracts/integration-tests/test_contract_examples.py`.

