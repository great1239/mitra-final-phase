# Submission Index

| Assignment deliverable | Implementation / artifact |
|---|---|
| Working Companion Runtime | `pratham/companion-runtime/mitra_companion/` |
| Runtime lifecycle and state | `lifecycle.py`, `/api/v1/runtime/lifecycle`, `docs/RUNTIME_LIFECYCLE.md` |
| Session Runtime | `pratham/session-runtime/mitra_session/` |
| Context Runtime | `pratham/context-runtime/mitra_context/` |
| Intent Router | `pratham/intent-router/mitra_intent/` |
| Attachment Runtime | `pratham/attachment-runtime/mitra_attachment/` |
| Product attachment without runtime modification | `POST /api/v1/products/connect`; production bootstrap directory `contracts/production/` |
| Product attachment contract examples | `contracts/examples/product-atlas.json`, `product-nova.json` |
| Versioned contracts | `contracts/schemas/`, `contracts/api/companion-runtime.openapi.yaml` |
| Integration APIs | FastAPI endpoints under `/api/v1` |
| Architecture diagrams | `docs/ARCHITECTURE.md` |
| Phase 1 architecture/lifecycle/state/interfaces | `docs/PHASE_1_COMPANION_RUNTIME_DESIGN.md` |
| Phase 1 validation report | `PHASE_1_VALIDATION_REPORT.md` |
| Phase 2 Context Runtime design | `docs/PHASE_2_CONTEXT_RUNTIME.md` |
| Phase 2 validation report | `PHASE_2_VALIDATION_REPORT.md` |
| Context Runtime policy | `contracts/context-runtime-policy.json` |
| Context View schema | `contracts/schemas/context-view.schema.json` |
| Phase 3 Intent Router design | `docs/PHASE_3_INTENT_ROUTER.md` |
| Phase 3 validation report | `PHASE_3_VALIDATION_REPORT.md` |
| Intent Router policy | `contracts/intent-router-policy.json` |
| Intent registration schema | `contracts/schemas/intent-registration.schema.json` |
| Capability view schema | `contracts/schemas/capability-view.schema.json` |
| Phase 4 Product Attachment Runtime design | `docs/PHASE_4_PRODUCT_ATTACHMENT_RUNTIME.md` |
| Phase 4 validation report | `PHASE_4_VALIDATION_REPORT.md` |
| Product Attachment Runtime policy | `contracts/product-attachment-runtime-policy.json` |
| Attachment record schema | `contracts/schemas/attachment-record.schema.json` |
| Product self-attachment example | `contracts/examples/product-self-attach.http`, `contracts/examples/product-echo.json` |
| Phase 5 Integration Contracts design | `docs/PHASE_5_INTEGRATION_CONTRACTS.md` |
| Phase 5 validation report | `PHASE_5_VALIDATION_REPORT.md` |
| Integration contract catalog | `contracts/integration-contracts.json` |
| Integration contract schema | `contracts/schemas/integration-contracts.schema.json` |
| Phase 6 Testing design | `docs/PHASE_6_TESTING.md` |
| Phase 6 validation report | `PHASE_6_VALIDATION_REPORT.md` |
| Runtime simulation tests | `pratham/tests/test_phase6_runtime_simulation.py` |
| Phase 7 Documentation package | `docs/PHASE_7_DOCUMENTATION.md` |
| Phase 7 validation report | `PHASE_7_VALIDATION_REPORT.md` |
| Runtime interface catalog | `contracts/runtime-interface-catalog.json` |
| Runtime state machine | `contracts/runtime-state-machine.json` |
| Execution diagrams | `docs/EXECUTION_FLOW.md` |
| Runtime diagrams | `docs/RUNTIME_DIAGRAMS.md` |
| Unit tests | `pratham/tests/` |
| Integration tests | `contracts/integration-tests/` |
| Failure tests | `pratham/tests/test_dispatch_and_failures.py`, `docs/FAILURE_MATRIX.md` |
| Developer onboarding | `docs/DEVELOPER_ONBOARDING.md` |
| Documentation index | `docs/DOCUMENTATION_INDEX.md` |
| Clean-room rebuild and handover | `docs/HANDOVER.md` |
| Central Depository handover | `docs/CENTRAL_DEPOSITORY_HANDOVER.md` |
| Deterministic reconstruction | `mitra_companion/reconstruction.py`, `/api/v1/dispatches/{dispatch_id}/reconstruction` |
| Runtime artifact export | `mitra_companion/depository.py`, `/api/v1/runtime/depository` |
| BHIV convergence | `mitra_companion/bhiv_integrations.py`, `/api/v1/runtime/integrations` |
| Security/IP boundaries | `docs/SECURITY_IP_BOUNDARIES.md` |
| Ownership allowlist/denylist | `docs/OWNERSHIP_BOUNDARY.md` |
| Machine-readable ownership contract | `contracts/ownership-boundary.json` |
| Adapter extension guide | `docs/ADAPTER_GUIDE.md` |
| Mandatory bounded code packet | `review_packets/code_packets/README.md` |
| Executed testing evidence | `review_packets/testing/TESTING_EVIDENCE.md` |
| Review packet | `review_packets/REVIEW_PACKET.md` |
| Validation report | `VALIDATION_REPORT.md` |
| Security boundary re-execution | `REEXECUTION_REPORT.md` |
| Runtime screenshots | `evidence/runtime-dashboard.png`, `evidence/runtime-openapi.png` |
| Demo video | `evidence/mitra-companion-runtime-demo.mp4` |

The runtime composes published interfaces only. No source from SHAKTI,
Parikshak, governance, external evidence/replay authorities, or certification
engines is imported into the implementation.
