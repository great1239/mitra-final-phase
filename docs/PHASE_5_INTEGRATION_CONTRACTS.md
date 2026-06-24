# Phase 5 - Integration Contracts

Phase 5 publishes the runtime integration surface as versioned contracts rather
than implementation knowledge. External products depend on these files and
interfaces, not hidden BHIV architecture.

## Stable API surface

The HTTP surface is published in
`contracts/api/companion-runtime.openapi.yaml` as OpenAPI `3.1.0`.

Mutation requests include the four compatibility fields:

- `schema_version`;
- `contract_version`;
- `runtime_version`;
- `compatibility_version`.

The runtime accepts contract `1.0.0` with compatibility
`mitra-companion-1`. Incompatible versions fail before mutating state.

## Contract catalog

`contracts/integration-contracts.json` is the machine-readable catalog for
integrators. It points to:

- the OpenAPI file and all published paths;
- request, response, record, and policy JSON Schemas;
- adapter port names;
- manifest and HTTP examples.

## JSON Schemas

Published schemas live under `contracts/schemas/` and use JSON Schema
2020-12. They cover:

- product attachment manifests and attachment records;
- session creation;
- context update, view, transfer, and context policy;
- intent dispatch, intent registration, capability view, and router policy;
- runtime interface catalog and state machine;
- ownership boundary and integration contract catalog;
- error responses.

## Integration examples

| Example | Purpose |
|---|---|
| `contracts/examples/product-atlas.json` | workspace-oriented product manifest |
| `contracts/examples/product-nova.json` | operations-oriented product manifest |
| `contracts/examples/product-echo.json` | minimal self-attachment product |
| `contracts/examples/embedded-flow.http` | session/context/dispatch flow |
| `contracts/examples/product-self-attach.http` | manifest self-attachment flow |

## Compatibility policy

Non-breaking changes may add optional response fields, new adapter modes, or new
manifest examples. Removing fields, renaming fields, changing semantics, or
adding required fields requires a new major `contract_version`.

