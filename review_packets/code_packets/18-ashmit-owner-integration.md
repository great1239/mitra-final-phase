# Owner Execution And Provenance

## File: `pratham/companion-runtime/mitra_companion/ecosystem.py`

**Sprint change:** Added response-bearing Ashmit provenance and conditional
KESHAV diagnosis stages, then versioned ecosystem replay.

**Purpose:** Coordinates owner calls after Raj, records KESHAV's product-error
proposal when required, and records Ashmit's independent trace plus Mongo
artifact reference.

**Why modified:** Ashmit was previously only a health probe, and product-owned
errors had no published path to KESHAV dependency diagnosis.

**Key implementation areas:** typed Raj outcome validation; conditional KESHAV
request and success skip; proposal/trace validation; authenticated Ashmit
request; immutable checkpoints; Bucket and InsightFlow propagation; replay v2
with v1 compatibility.

**Review focus:** No imported owner logic or proposal execution, fail-closed
infrastructure errors, trace separation, recorded HTTP responses, and recovery
without duplicate owner calls.

**Related tests:** `test_product_error_invokes_keshav_then_persists_diagnosis`,
`test_keshav_trace_mutation_stops_before_truth_storage`, and
`test_replay_accepts_pre_keshav_v1_package`.

## File: `pratham/tests/test_ecosystem_convergence.py`

**Sprint change:** Added Ashmit request, response, rejection, and recovery cases

**Purpose:** Verifies the complete checkpointed owner sequence through
controlled published contracts.

**Why modified:** The previous suite asserted Ashmit health only and could not
detect that execution data was never submitted to the owner.

**Key implementation areas:** exact request headers and body; accepted Mongo
locator; downstream suppression on rejection; idempotent recovery.

**Review focus:** Every owner call has a response, completed stages are not
repeated, and replay includes the new response without live service access.

**Related tests:** This file is the focused ecosystem suite.
