# Live Configuration Validation

## File: `integration_services/tests/test_contract_services.py`

**Sprint change:** Added focused contract behavior tests for the executable
integration services.

**Purpose:** Verifies Karma replay behavior, PRANA byte identity, generic Raj
dispatch, and InsightFlow registry adaptation.

**Why modified:** Configuration alone cannot establish that calls produce the
required responses.

**Key implementation areas:** Negative parents, duplicate IDs, raw bytes,
trace identity, response schemas, provenance calls.

**Review focus:** Controlled transports remain regression tests and are not
labelled as live owner evidence.

**Related tests:** This file is the four-test contract-service suite.

## File: `docs/ECOSYSTEM_CONFIGURATION_STATUS.md`

**Sprint change:** Added one maintained live-state and pitfall ledger, updated
with the 2026-07-20 canonical acceptance run.

**Purpose:** Records exact running-service outputs, resolved and remaining
pitfalls, Docker recovery, and rebuild order.

**Why modified:** Earlier review documents still described newly configured
core modules as unavailable.

**Key implementation areas:** Module classification, current execution IDs and
hashes, 266 live assertions, isolated replay, per-call response audit, restart
persistence, failure ledger, public-host boundary.

**Review focus:** Partial and local contract services must not be described as
original hosted owner deployments.

**Related tests:** Live HTTP, protected read-back, and Compose health checks in
the document.

## File: `docs/TANTRA_ECOSYSTEM_CONVERGENCE.md`

**Sprint change:** Updated convergence acceptance to the response-bearing
local topology.

**Purpose:** Keeps the canonical flow and current operational boundary in one
implementation guide.

**Why modified:** The previous validation section reported Raj, Karma, PRANA,
and InsightFlow as unavailable.

**Key implementation areas:** Two completed product workflows, product health
gate, clean-state replay, Bucket-backed depository boundary, hosted
reachability.

**Review focus:** Core readiness and completed customer execution remain
separate claims.

**Related tests:** `pratham/tests/test_ecosystem_convergence.py` and the live
status ledger.
