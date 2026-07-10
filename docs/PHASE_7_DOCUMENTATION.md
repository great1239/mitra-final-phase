# Documentation And Handover

The maintained documentation is organized around an incoming engineer rather
than sprint chronology.

## Authoritative Entry Points

| Deliverable | File |
|---|---|
| Documentation map | `docs/DOCUMENTATION_INDEX.md` |
| Clean-room rebuild and handover | `docs/HANDOVER.md` |
| Architecture and boundaries | `docs/ARCHITECTURE.md` |
| Product integration | `docs/INTEGRATION_GUIDE.md` |
| BHIV integration | `docs/BHIV_PRODUCT_INTEGRATION.md` |
| Production operations | `docs/OPERATIONS_RUNBOOK.md` |
| Central Depository transfer | `docs/CENTRAL_DEPOSITORY_HANDOVER.md` |
| Durable hosting | `docs/INDEPENDENT_HOSTING.md` |
| Public serverless hosting | `docs/VERCEL_DEPLOYMENT.md` |

## Handover Standard

An incoming engineer must be able to:

1. create a clean Python environment;
2. install the runtime and test dependencies;
3. execute the complete test suite and readiness gate;
4. start the API locally and with Docker;
5. configure manifests, storage, secrets, telemetry, and BHIV endpoints;
6. attach a product and execute a real dispatch;
7. compare submitted input with dispatch and reconstruction output;
8. recover or roll back a durable deployment;
9. export and verify a dispatch-scoped Central Depository handover.

The handover does not depend on generated proof reports. Acceptance comes from
runtime responses, immutable artifacts, tests, metrics, telemetry, and
operator execution.

## Historical Records

Phase reports and review packets remain historical sprint records. They are not
the canonical rebuild path. `docs/DOCUMENTATION_INDEX.md` identifies maintained
documentation and machine-readable contracts.
