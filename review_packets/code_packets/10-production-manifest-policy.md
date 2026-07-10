# Production Manifest Policy

## File: `pratham/companion-runtime/mitra_companion/manifest_sources.py`

**Sprint change:** Modified

**Purpose:** Loads manifest files from a configured directory through the
published manifest-source port.

**Why modified:** Added explicit filtering so production bootstrap can reject
example, simulated, loopback, localhost, and unapproved manifests before they
become dashboard attachments.

**Key implementation areas:** Directory scanning; manifest validation;
production-bootstrap marker enforcement; fixture, simulation, loopback, and
localhost filters.

**Review focus:** Whether production filtering is conservative without adding
product-specific names, and whether development/test callers can still opt into
fixtures explicitly.

**Related tests:** `pratham/tests/test_production_mode.py`,
`pratham/tests/test_boundary_adapters.py`.

## File: `pratham/companion-runtime/mitra_companion/startup.py`

**Sprint change:** Modified

**Purpose:** Coordinates startup phases, manifest-source attachment, restart,
and recovery reporting.

**Why modified:** Corrected startup source reporting so `attachment_count`
records the number of attached manifests rather than the number of keys in the
`attach_many` response envelope.

**Key implementation areas:** Manifest-source phase reporting; startup status
shape; operator-visible attachment counts.

**Review focus:** Accurate startup evidence, behavior when a production
manifest directory is empty, and unchanged restart/recovery semantics.

**Related tests:** `pratham/tests/test_production_mode.py`.

## File: `pratham/tests/test_production_mode.py`

**Sprint change:** Modified

**Purpose:** Validates production configuration, operator APIs, production
logging, and manifest-policy behavior.

**Why modified:** Added regression coverage proving that `contracts/examples`
does not auto-bootstrap production attachments and that production rejects
example/simulated manifests through the attachment API.

**Key implementation areas:** Production policy setup; empty attachment list
assertion; startup source count assertion; `ATTACHMENT_INVALID` API checks.

**Review focus:** Whether the tests protect against Nova/KESHAV-style fixture
leakage into the dashboard without weakening local fixture coverage.

**Related tests:** This file is the focused production-policy regression suite.
