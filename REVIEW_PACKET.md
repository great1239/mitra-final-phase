# Review Packet - Mitra Companion Runtime Phase V

## Scope

This repository implements Pratham's bounded ownership:

- Companion Runtime;
- Session Runtime;
- Context Runtime and transfer;
- Intent Router;
- Capability/Product Attachment Runtime;
- lifecycle, state, versioned APIs, schemas, tests, and documentation.

It does not implement conversation design, governance, safety, knowledge,
project/domain intelligence, evidence, replay, or certification.

## Canonical flow

```text
Client
  -> durable session
  -> isolated context load
  -> explicit registered intent
  -> capability lookup
  -> product route
  -> registered transport adapter
  -> durable dispatch receipt
```

Cross-product work uses:

```text
source session
  -> new target session
  -> caller-supplied portable handoff context
  -> empty or target-owned product context
```

## Acceptance mapping

| Requirement | Proof |
|---|---|
| Working Companion Runtime | FastAPI application and `CompanionRuntime` composition root |
| Runtime lifecycle/state | durable transition journal and lifecycle API |
| Context loading/updates | four context partitions with optimistic revisions |
| Session continuity | durable sessions and hashed resume tokens |
| Workspace continuity | actor/workspace partition shared across sessions and client types |
| Product context isolation | session/product partition plus transfer exclusion |
| Intent registration/discovery | manifest-derived records and filtered `/api/v1/intents` |
| Intent dispatch/capability lookup/product routing | exact capability APIs, explicit router, durable dispatch |
| Products attach without runtime modification | manifest examples attach through the same API |
| Product self-attachment | `product-echo.json` attaches through `POST /api/v1/attachments` |
| Stable/versioned APIs | OpenAPI 3.1 and version fields on mutations |
| JSON schemas | published JSON Schema 2020-12 contracts for runtime inputs, views, records, catalogs, and policies |
| Multiple products | Atlas and Nova integration test/demo |
| Context transfer validation | source product context excluded; portable handoff context included |
| Attachment validation | duplicate capability/context/intent and invalid schema checks fail closed |
| Failure handling | contract, revision, route, isolation, and transport failure tests |
| Architecture/execution/runtime diagrams | Mermaid diagrams under `docs/` |
| Developer onboarding | `docs/DEVELOPER_ONBOARDING.md` |
| Runtime screenshots/video | artifacts under `evidence/` |

## Verification

- Automated suite: `59 passed`
- Two products attached through published manifests
- Two sessions spanning an explicit cross-product transfer
- Two successful routed dispatches
- Product context isolation verified
- Remote transport failure persisted and degraded safely
- Runtime implementation contains no example or ecosystem product names
- Arbitrary transport mode proven through a custom adapter without runtime edits
- Cross-module concrete imports restricted to the composition root
- Ownership allowlist and forbidden-subsystem API/symbol/import scans passed
- Machine-readable ownership contract: exactly 9 owned and 9 excluded capabilities
- Phase 1 interface/state catalogs validated with zero errors
- Seven runtime-checkable public interfaces conform to concrete components
- Phase 2 policy and Context View contracts validate with zero errors
- Selective context loading and capability-scoped least-privilege loading passed
- Actor/workspace and session/product isolation tests passed
- Phase 3 policy, registration, and capability contracts validate
- Ambiguous intent, degraded product, and adapter exception paths fail closed
- Intent registrations survive restart through durable manifests
- Phase 4 Product Attachment Runtime policy and attachment record contracts validate
- Product self-attachment, detach audit, and arbitrary transport adapter tests passed
- Phase 5 integration contract catalog validates and references all published files
- Phase 6 runtime simulation validates multi-product attachment, transfer, routing, validation, and failure containment
- Phase 7 documentation/review package updated with architecture, execution flow, runtime diagrams, onboarding, and review packet

## Key files

- `pratham/companion-runtime/mitra_companion/runtime.py`
- `pratham/context-runtime/mitra_context/runtime.py`
- `pratham/intent-router/mitra_intent/runtime.py`
- `pratham/session-runtime/mitra_session/runtime.py`
- `pratham/attachment-runtime/mitra_attachment/runtime.py`
- `contracts/api/companion-runtime.openapi.yaml`
- `contracts/schemas/product-attachment.schema.json`
- `contracts/context-runtime-policy.json`
- `contracts/schemas/context-view.schema.json`
- `contracts/intent-router-policy.json`
- `contracts/schemas/intent-registration.schema.json`
- `contracts/schemas/capability-view.schema.json`
- `contracts/product-attachment-runtime-policy.json`
- `contracts/schemas/attachment-record.schema.json`
- `contracts/integration-contracts.json`
- `contracts/integration-tests/test_contract_examples.py`
- `pratham/tests/test_phase4_product_attachment_runtime.py`
- `pratham/tests/test_phase5_integration_contracts.py`
- `pratham/tests/test_phase6_runtime_simulation.py`
- `evidence/demo-transcript.json`
