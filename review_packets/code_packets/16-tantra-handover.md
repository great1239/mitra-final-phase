# TANTRA Handover Port

This packet covers the selective port from the earlier runtime producer,
operationalization, constitutional convergence, and TANTRA consumer sprints.
It excludes generated reports, committed outputs, simulated consumers, and
downstream authority implementations.

## File: `pratham/companion-runtime/mitra_companion/tantra_handover.py`

**Sprint change:** Added

**Purpose:** Build, validate, persist, and durably deliver one deterministic
four-bundle handover from an actual completed Mitra dispatch.

**Why modified:** The previous Mitra runtime exposed reconstruction and BHIV
outputs but did not project them into the published TANTRA package expected by
the historical gateway.

**Key implementation areas:** 64-hex trace derivation; clean-state package
validation; original/reconstructed output equality; newline-sensitive wire
hashes; content-addressed package and delivery receipts; persist-before-send
outbox; lease-fenced claims; retry/backoff; gateway health; remote trace
reconciliation.

**Review focus:** No downstream decision is synthesized, no API key is
persisted, only published TANTRA endpoints are called, stale workers cannot
overwrite reclaimed deliveries, and gateway failure cannot change the
committed product result.

**Related tests:** `pratham/tests/test_tantra_handover.py` and
`pratham/tests/test_runtime_coordination.py`.

## File: `contracts/schemas/tantra-handover.schema.json`

**Sprint change:** Added

**Purpose:** Publish the machine-readable package contract shared with the
external coordinator.

**Why modified:** The handover needs an independently reviewable shape rather
than implementation-only dictionaries.

**Key implementation areas:** Four required bundles; trace/execution
continuity; source field set; portable package reference; handover manifest.

**Review focus:** Contract `1.1.0`, schema `1.0.0`, 64-hex trace, required
source arrays, and exact package type.

**Related tests:**
`test_handover_is_real_package_projection_without_local_authority`.

## File: `pratham/tests/test_tantra_handover.py`

**Sprint change:** Added

**Purpose:** Execute the port with real Mitra dispatch data and controlled HTTP
responses.

**Why modified:** Architecture or generated proof is not interoperability
evidence; assertions must inspect the produced package and actual call.

**Key implementation areas:** JSON Schema validation; wire hashes; clean-state
fidelity; exact method/path/header/body; 4xx/429/5xx behavior; trace mutation;
secret redaction; product failure isolation; durable outbox state assertions.

**Review focus:** Tests use the runtime's actual dispatch and immutable
artifacts, not fabricated package fixtures.

**Related tests:** This file is the acceptance suite for this area.
