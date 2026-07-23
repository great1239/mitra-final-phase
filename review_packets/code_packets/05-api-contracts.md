# Published API And Contract Surface

## File: `contracts/api/companion-runtime.openapi.yaml`

**Sprint change:** Modified

**Purpose:** Publishes the versioned HTTP contract used by runtime consumers
and the OpenAPI dashboard.

**Why modified:** Added final convergence, depository, reconstruction
validation, capability, companion, recovery, telemetry, and integration
endpoints.

**Key implementation areas:** Paths and operations; request envelopes;
`POST /api/v1/reconstruction/validate`; response schemas; status codes;
operator APIs; compatibility metadata.

**Review focus:** Parity with FastAPI routes, explicit success and failure
responses, stable version fields, filter limits, and schema references.

**Related tests:** `contracts/integration-tests/test_contract_examples.py`,
`pratham/tests/test_companion_interaction.py`,
`pratham/tests/test_replay_convergence_and_graph.py`.

## File: `contracts/schemas/runtime-depository-export.schema.json`

**Sprint change:** Added

**Purpose:** Defines the machine-verifiable response for runtime artifact and
lineage export.

**Why modified:** Made Central Depository handover independently validatable
instead of relying on prose or an HTTP 200 response.

**Key implementation areas:** Export envelope; subject filters; artifact hash
format; lineage parent and chain hashes; counts; bounded limits.

**Review focus:** Closed versus extensible objects, nullability, SHA-256
patterns, count semantics, and alignment with the runtime export.

**Related tests:** `pratham/tests/test_replay_convergence_and_graph.py::test_dispatch_records_verified_reconstruction_and_depository`.

## File: `contracts/integration-tests/test_contract_examples.py`

**Sprint change:** Modified

**Purpose:** Validates example manifests against published schemas and
exercises cross-product context transfer and dispatch.

**Why modified:** Extended contract checks to require declared response
schemas for the larger manifest-first ecosystem.

**Key implementation areas:** JSON Schema validation; manifest discovery;
response schema requirements; context transfer; multi-product dispatch.

**Review focus:** Example-to-schema parity, accidental fixture exceptions,
response-contract enforcement, and isolation across products.

**Related tests:** This file is the contract test suite; runtime response
behavior is covered by `pratham/tests/test_dispatch_and_failures.py`.
