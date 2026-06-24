# Security Boundary Re-execution Report

Re-executed on June 23, 2026 after the adapter/port hardening request.

## Boundary audit

| Check | Result |
|---|---|
| Example or ecosystem product names in implementation code | clean |
| Product-ID conditional branches | clean |
| Hardcoded example manifest filenames in runtime code | clean |
| Obsolete example-seeding environment variable | clean |
| Concrete cross-module imports outside composition root | clean |
| Product context copied during cross-product transfer | blocked and tested |
| Unknown adapter mode | fails closed during attachment |
| Capability payload bypasses published schema | blocked and tested |

Synthetic product names remain only in test fixtures, example contracts, demo
evidence, and explanatory documentation. They are not referenced by runtime
implementation code.

## Re-executed verification

| Verification | Result |
|---|---|
| Complete pytest suite | `50 passed` |
| Published example manifests | 2 validated, 0 schema errors |
| OpenAPI contract | 3.1.0, 20 paths |
| Clean wheel/package build | passed |
| Installed package imports | all five runtime packages and public ports passed |
| Installed CLI `validate` | `valid: true` |
| Generic manifest-directory bootstrap | 2 attachments, 4 intents, healthy/READY |
| Arbitrary `queue` transport adapter | successful dispatch without runtime edits |
| Deterministic two-product demo | 2 sessions, 2 dispatches, 0 failures |
| Cross-product context isolation | verified `true` |
| Demo video full decode | passed |
| Ownership contract | exactly 9 owned and 9 excluded capabilities |
| Forbidden subsystem modules/classes/functions/imports/routes | none |
| Phase 1 interface and state catalog conformance | passed |
| Phase 2 Context Runtime policy and Context View schemas | passed |
| Actor/workspace and session/product isolation | passed |
| Selective capability context loading | passed |
| Phase 3 router policy, registration, and capability contracts | passed |
| Ambiguity, product availability, and adapter exception handling | passed |

## Remaining environment limitation

Docker Desktop's Linux engine is still not running on this host, so the
container image cannot be built or started here. The Dockerfile and Compose
profile remain present; the Python wheel, installed CLI, API bootstrap, tests,
demo, contracts, and adapter paths were independently re-executed successfully.

## Non-blocking warning

FastAPI's test client emits a Starlette deprecation warning about its current
`httpx` integration. It does not affect runtime behavior or test results.
