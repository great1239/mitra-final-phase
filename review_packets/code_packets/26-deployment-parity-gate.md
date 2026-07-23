# Deployment Parity Gate

## File: `pratham/companion-runtime/mitra_companion/deployment.py`

**Sprint change:** Added the fail-closed deployment parity evaluator.

**Purpose:** Converts owner configuration, endpoint portability, manifest
policy, durable storage, and release identity into one redacted runtime gate.

**Why modified:** A running local topology and a reachable hosted dashboard
were previously able to look equivalent even when the host lacked owner
services or durable runtime state.

**Key implementation areas:** Required owner settings, public HTTPS validation,
durable storage validation, issue codes, and release revision reporting.

**Review focus:** No credential value is returned; Docker-internal endpoints
remain valid only when public endpoint enforcement is disabled.

**Related tests:** Strict rejection and acceptance paths in
`pratham/tests/test_production_mode.py`; complete runtime regression suite.
