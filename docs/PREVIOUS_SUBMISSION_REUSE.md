# Previous Submission Reuse

Only generic runtime infrastructure was reused. Product logic and downstream
authority systems remain external.

| Reused pattern | Runtime implementation | Boundary |
| --- | --- | --- |
| Phase IV durable execution checkpoints | dispatch phase table and `/api/v1/dispatches/{dispatch_id}/phases` | Mitra records routing progress only. |
| Phase IV dependency/runtime registry | `/api/v1/runtime/capability-catalog` | Manifest-derived only. |
| Commercial Foundation manifest module catalog | `CapabilityDependencyRegistry` | Product manifests remain source of truth. |
| Commercial Foundation semantic version dependency validation | dependency checks in capability catalog | Report missing/incompatible dependencies. |
| Commercial Foundation public contract registry | manifest metadata summaries | Runtime does not invent product contracts. |
| Runtime proof-bundle producer | `/api/v1/dispatches/{dispatch_id}/proof` | Downstream systems decide how to use proof. |
| Operational gateway negative-path discipline | failed dispatch phases and receipts | Failure stays scoped to affected attachment. |
| Source scope and prior-submission feature catalog | `contracts/source-scope-catalog.json` and `/api/v1/runtime/source-scope` | Documents what was imported or externalized. |
| Product exchange mailbox | product exchange envelope, inbox, and receipt APIs | Shares explicit payloads only. |
| TANTRA evidence consumer gateway | `TantraHandoverAdapter`, four deterministic bundles, exact wire hashes, one published gateway POST | TANTRA and downstream systems retain orchestration and decision authority. |

## Externalized

- governance decision engines;
- downstream proof consumers;
- constitutional or readiness classifiers;
- product-specific commercial, education, or market logic;
- external lineage, convergence, and certification authorities.

## Verification

Tests cover source-scope exposure, dispatch phases, proof hashes, manifest
dependency validation, product exchange, TANTRA handover interoperability, and
boundary scans. See `docs/TANTRA_INTEGRATION.md` for the inclusion/exclusion
audit.
