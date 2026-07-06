# Previous Submission Reuse

This sprint imports useful generic systems from earlier submissions without
moving downstream authority or product-specific business logic into Mitra.

| Prior submission pattern | Mitra runtime implementation | Boundary rule |
| --- | --- | --- |
| Phase IV durable execution checkpoints | `dispatch_phases` storage, `CompanionRuntime.dispatch_phases`, and `GET /api/v1/dispatches/{dispatch_id}/phases` record seven Mitra-owned phases: request accepted, route selected, payload validated, context loaded, transport dispatched, receipt persisted, and terminal completion/failure. | Mitra records how it routed; products still own their response. |
| Phase IV dependency/runtime registry | `GET /api/v1/runtime/capability-catalog` summarizes attached product manifests, contracts, capabilities, dispatch modes, and compatibility. | Registry is manifest-derived only. |
| Commercial Foundation manifest module catalog | `CapabilityDependencyRegistry` builds a product/capability catalog from published manifests and metadata declarations. | No product branch is added to runtime code. |
| Commercial Foundation semantic version dependency validation | Manifest metadata can declare `dependencies` or `requires`; the catalog validates product and capability dependencies against attached manifests. | Missing or incompatible dependencies are reported, not silently patched. |
| Commercial Foundation public contract registry | Manifest metadata can declare `public_contracts` for APIs, events, permissions, UI routes, and UI slots; the runtime catalog summarizes publishers, consumers, permissions, and conflicts. | Mitra reports registrations; product manifests remain the source of truth. |
| Runtime proof-bundle producer | `GET /api/v1/dispatches/{dispatch_id}/proof` returns canonical request/response hashes, phase journal, lineage nodes, reconstruction hints, and handover steps. | Mitra emits dispatch proof; external systems decide any downstream validation. |
| Operational gateway negative-path discipline | Failed product transport records failed dispatch phases and a durable failed dispatch receipt. | Failures stay contained to the affected attachment and dispatch. |
| Source scope and prior-submission feature catalog | `contracts/source-scope-catalog.json`, `SourceScopeRegistry`, and `GET /api/v1/runtime/source-scope` expose which useful systems were imported, adapted, or left external. | Mitra can understand previous submissions without absorbing downstream authority or product logic. |
| Persistent service operations | `RuntimeStartupManager`, redacted production config/secrets summaries, process-level JSONL logs, restart/recovery endpoints, and runtime instance reconciliation convert prior validation loops into service operations. | Operations remain Mitra-owned and product-neutral. |

## Not Copied Into Mitra

These systems remain external and are only reachable through published product
manifests, adapters, or later consumers:

- governance decision engines;
- downstream proof consumers;
- constitutional or production-readiness classifiers;
- product-specific commercial, education, or market intelligence logic;
- external lineage, convergence, or certification authorities.

## Verification

Runtime coverage now includes:

- source-scope catalog validation and API exposure;
- runtime status and analysis hints for imported prior-submission systems;
- dispatch phase journal creation for successful and failed dispatches;
- dispatch proof bundle hashes and lineage nodes;
- manifest dependency validation through the capability catalog;
- public API/event/permission/UI summaries through manifest metadata;
- startup manager, production configuration, secrets, and process-log coverage;
- API exposure for catalog, phases, and proof bundle;
- existing boundary scans proving no product-specific branches were added.
