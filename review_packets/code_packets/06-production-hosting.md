# Independent Production Hosting

## File: `api/index.py`

**Sprint change:** Added

**Purpose:** Boots the FastAPI runtime in Vercel's service environment.

**Why modified:** Added an independent hosted entry point for the sprint's
canonical public runtime.

**Key implementation areas:** Monorepo package paths; production defaults;
ephemeral data paths; manifest discovery; logging; FastAPI app creation.

**Review focus:** Import portability, read-only deployment assumptions,
ephemeral-state disclosure, environment override behavior, and secret safety.

**Related tests:** `pratham/tests/test_production_readiness_gate.py`,
`scripts/validate_hosted_runtime.py`.

## File: `vercel.json`

**Sprint change:** Added

**Purpose:** Defines the Vercel service, rewrite, entry point, and runtime
environment.

**Why modified:** Configured the independently hosted Mitra deployment without
changing the existing `blackholeinfiverse.com` site. Updated production
bootstrap to use `contracts/production` instead of test/example manifests.

**Key implementation areas:** Service routing; FastAPI entry point; production
profile; temporary storage; production manifest directory; fixture-manifest
rejection; integration failure policy.

**Review focus:** Route coverage, configuration parity with `api/index.py`,
ephemeral limitations, deployment portability, and absence of embedded
credentials.

**Related tests:** `pratham/tests/test_production_readiness_gate.py::test_production_readiness_gate_script_passes`,
`scripts/validate_hosted_runtime.py`.

## File: `scripts/validate_hosted_runtime.py`

**Sprint change:** Added

**Purpose:** Sends real requests to the hosted service and validates returned
runtime outputs without creating simulated products.

**Why modified:** Added independently repeatable deployment validation for
HTTPS, dashboard, APIs, attachments, health, metrics, telemetry, and recovery;
routing and replay now run only when a real attached product is available.

**Key implementation areas:** Read probes; real attachment discovery; session
and dispatch flow; input/output reconstruction checks; proof and phase checks;
recovery; result summary.

**Review focus:** Assertions on response content, fixture rejection, clear
blocked status when no real product is attached, timeout behavior, hosted-state
assumptions, and avoidance of evidence fabrication.

**Related tests:** The script is an executable production validator; its
presence and command are checked by
`pratham/tests/test_production_readiness_gate.py`.
