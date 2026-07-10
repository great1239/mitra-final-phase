# Production Operations And Observability

## File: `pratham/companion-runtime/mitra_companion/config.py`

**Sprint change:** Modified

**Purpose:** Loads typed runtime, deployment, persistence, integration, and
companion settings from the environment.

**Why modified:** Added the final convergence endpoints, hashes, failure
policy, production profiles, instance controls, and companion analysis
configuration. Added manifest policy settings that default production away from
examples, simulations, loopback dispatch, and localhost product URLs.

**Key implementation areas:** Environment parsing; manifest policy defaults;
BHIV URLs; Karma and Bucket hash state; fail-closed mode; runtime instance
identity; production paths; secret redaction.

**Review focus:** Secure defaults, fixture-manifest rejection, boolean and
timeout parsing, environment precedence, accidental secret exposure, and
behavior when integrations are partially configured.

**Related tests:** `pratham/tests/test_bhiv_integrations.py`,
`pratham/tests/test_production_readiness_gate.py`,
`pratham/tests/test_production_hardening.py`.

## File: `pratham/companion-runtime/mitra_companion/telemetry.py`

**Sprint change:** Modified

**Purpose:** Records bounded runtime events and exposes operational counters,
latencies, recovery validation, and Prometheus metrics.

**Why modified:** Added observability for companion decisions, integration
handoffs, replay, recovery, and production monitoring.

**Key implementation areas:** Event recording; metrics snapshot; dispatch
latency; fallback counters; reconstruction events; recovery metrics;
Prometheus rendering.

**Review focus:** Counter correctness, cardinality, timestamp consistency,
thread safety, sensitive payload handling, and metric behavior after failures.

**Related tests:** `pratham/tests/test_companion_interaction.py`,
`pratham/tests/test_dispatch_and_failures.py`,
`pratham/tests/test_production_hardening.py`.

## File: `scripts/production_readiness_gate.py`

**Sprint change:** Modified

**Purpose:** Fails review when required implementation, deployment, handover,
screenshot, or code-packet surfaces are absent or malformed.

**Why modified:** Consolidated production acceptance into one operational gate
and added mandatory bounded code-packet validation.

**Key implementation areas:** Required runtime markers; deployment controls;
handover checks; JPEG validation; code-packet structure and review limits;
machine-readable result.

**Review focus:** False positives, brittle string checks, deterministic output,
packet parser boundaries, and whether the gate verifies required artifacts
without pretending to certify external production behavior.

**Related tests:** `pratham/tests/test_production_readiness_gate.py`.
