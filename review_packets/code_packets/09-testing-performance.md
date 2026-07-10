# Testing And Performance

## File: `scripts/load/k6_companion_runtime.js`

**Sprint change:** Modified

**Purpose:** Applies sustained HTTP load to real Mitra session and dispatch
paths with response, receipt, and input/output equality checks.

**Why modified:** Added a self-contained runtime profile that does not depend
on unavailable product processes, retained the BHIV profile, and made the
virtual-user ceiling configurable for capacity testing.

**Key implementation areas:** Runtime versus BHIV profiles; manifest
attachment; session setup; ramping VUs; dispatch output validation; error,
latency, and check thresholds.

**Review focus:** Whether checks validate response content, threshold
integrity, profile isolation, VU parameter handling, and parity between load
payloads and published schemas.

**Related tests:** `pratham/tests/test_production_hardening.py::test_production_tactics_are_deployed_as_first_class_artifacts`.

## File: `pratham/tests/test_production_hardening.py`

**Sprint change:** Modified

**Purpose:** Exercises recovery, restart continuity, concurrency,
multi-instance failover, stale-peer handling, observability, and production
deployment controls.

**Why modified:** Extended production assertions for the runtime load profile,
capacity control, and content-equality checks used by the executed k6 run.

**Key implementation areas:** Thirty-dispatch concurrency; two-instance shared
state; failover; stale-peer reconciliation; interrupted-task recovery;
observability; operational artifact checks.

**Review focus:** Assertion strength, realistic failure transitions, shared
database isolation, concurrency determinism, and whether deployment checks
match the executed production profile.

**Related tests:** This file is the focused production-hardening suite; final
execution results are recorded in
`review_packets/testing/TESTING_EVIDENCE.md`.

