# Documentation Index

This index defines the maintained documentation for the Mitra Companion
Runtime. Incoming engineers should follow the documents in the order below.

## Start Here

| Need | Authoritative document |
|---|---|
| Rebuild and hand over the runtime | `docs/HANDOVER.md` |
| Understand architecture and ownership | `docs/ARCHITECTURE.md` |
| Operate, recover, and roll back production | `docs/OPERATIONS_RUNBOOK.md` |
| Integrate a product | `docs/INTEGRATION_GUIDE.md` |
| Integrate BHIV runtime consumers | `docs/BHIV_PRODUCT_INTEGRATION.md` |
| Export artifacts to Central Depository | `docs/CENTRAL_DEPOSITORY_HANDOVER.md` |
| Deploy to the durable host | `docs/INDEPENDENT_HOSTING.md` |
| Deploy the public serverless host | `docs/VERCEL_DEPLOYMENT.md` |
| Review SLOs and capacity | `docs/SLO_AND_CAPACITY.md` |
| Review failure behavior | `docs/FAILURE_MATRIX.md` |

## Design References

- `docs/OWNERSHIP_BOUNDARY.md`
- `docs/RUNTIME_LIFECYCLE.md`
- `docs/EXECUTION_FLOW.md`
- `docs/RUNTIME_DIAGRAMS.md`
- `docs/ADAPTER_GUIDE.md`
- `docs/SECURITY_IP_BOUNDARIES.md`
- `docs/PREVIOUS_SUBMISSION_REUSE.md`
- `docs/MITRA_EXPECTATION_BASELINE.md`
- `docs/FEEDBACK_ACCEPTANCE_UPGRADES.md`
- `docs/FINAL_RUNTIME_CONVERGENCE.md`

## Historical Sprint Records

The old root-level `PHASE_*_VALIDATION_REPORT.md` files were merged into
`VALIDATION_REPORT.md` to reduce review noise. The phase design documents and
historical review packet remain traceability references, but they are not
rebuild instructions and may contain historical test counts. Current
acceptance comes from executing the commands in `docs/HANDOVER.md`.

## Machine-Readable Contracts

- OpenAPI: `contracts/api/companion-runtime.openapi.yaml`
- Integration catalog: `contracts/integration-contracts.json`
- Runtime interface catalog: `contracts/runtime-interface-catalog.json`
- Runtime state machine: `contracts/runtime-state-machine.json`
- JSON Schemas: `contracts/schemas/`
- Production bootstrap manifests: `contracts/production/`
- Test and documentation manifests: `contracts/examples/`

When prose and a machine-readable contract disagree, stop the handover and
resolve the mismatch. Do not silently choose one.
