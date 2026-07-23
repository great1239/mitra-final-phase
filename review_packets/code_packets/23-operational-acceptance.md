# Operational Acceptance

## File: `scripts/validate_ecosystem_runtime.py`

**Sprint change:** Added

**Purpose:** Executes submitted customer requests through the complete live
owner topology and decides acceptance from returned data.

**Why modified:** Configuration, architecture, screenshots, and controlled
tests do not prove owner interoperability or deterministic replay.

**Key implementation areas:** Two-product execution; exact stage order;
preflight and owner response validation; idempotency; telemetry and metrics;
execution-scoped depository lineage; API replay; isolated-process replay;
recorded-response mutation rejection; optional exact package persistence;
standalone file-or-directory replay verification without owner services.

**Review focus:** No simulated owner result, no narrative evidence generation,
nonzero exit on mismatch, precision-preserving replay, and honest Central
Depository boundary reporting.

**Related tests:** `pratham/tests/test_operational_validators.py` and the
2026-07-20 live two-product run.

## File: `contracts/operational-acceptance.json`

**Sprint change:** Added

**Purpose:** Declares stable real-product inputs and expected manifest-derived
selection without product branches in the validator.

**Why modified:** Repeatable validation needs known customer inputs and output
invariants while allowing future products to add data instead of code.

**Key implementation areas:** NVDA prediction case; drip-irrigation learning
case; expected product, capability, intent, and response paths.

**Review focus:** Native product payloads, no credentials, no mock responses,
and agreement with production manifests.

**Related tests:**
`test_operational_cases_cover_both_real_product_owners`.

## File: `pratham/tests/test_operational_validators.py`

**Sprint change:** Added

**Purpose:** Locks validator payload generation, declarative case coverage,
operation receipt handling, and non-destructive tamper construction.

**Why modified:** The previous hosted validator generated an empty required
symbol list and could not pass its documented clean-room command.

**Key implementation areas:** Recursive schema samples; both owner cases;
operation de-duplication; deep-copy mutation; retained-package discovery.

**Review focus:** Validator regressions should fail before a lengthy live run.

**Related tests:** This file is the focused validator regression suite.
