# Frontend Compatibility Connector

## File: `pratham/companion-runtime/mitra_companion/frontend_connector.py`

**Sprint change:** Added

**Purpose:** Exposes the Mitra command-center frontend's existing API shape
while routing every request into the Mitra companion runtime.

**Why modified:** The deployed frontend calls `/api/companion/chat`,
`/api/companion/greeting/{user_id}`, `/api/companion/memory/{user_id}`,
`/api/companion/capabilities`, and `/api/workflow/run`. Those routes now
translate into runtime sessions, capability analysis, dispatch, telemetry, and
replay/depository trace endpoints instead of bypassing Mitra.

**Key implementation areas:** Legacy request models; frontend-to-runtime
contract translation; session reuse by `user_id`; capability listing from
attached manifests; workflow requests routed through `companion_message`;
frontend response fields plus Mitra trace links.

**Review focus:** The adapter must remain thin, must not hardcode BHIV product
logic, must not simulate capabilities, and must preserve the runtime as the
authority for analysis, routing, dispatch, telemetry, replay, and provenance.

**Related tests:** `pratham/tests/test_frontend_connector.py`.

## File: `pratham/tests/test_frontend_connector.py`

**Sprint change:** Added

**Purpose:** Validates the command-center frontend compatibility routes against
the real runtime.

**Why modified:** Provides regression coverage that the old frontend API names
exist, return the expected frontend fields, and produce real Mitra runtime
dispatch trace links when a published capability is attached.

**Key implementation areas:** Frontend capabilities; greeting; memory; chat;
workflow; browser CORS preflight.

**Review focus:** Whether requests pass through the runtime analyzer and
dispatcher rather than using simulated frontend-only behavior.

**Related tests:** This file is the focused frontend connector regression
suite.
