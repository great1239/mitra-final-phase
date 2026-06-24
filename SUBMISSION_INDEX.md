# Submission Index

| Assignment deliverable | Implementation / artifact |
|---|---|
| Working Companion Runtime | `pratham/companion-runtime/mitra_companion/` |
| Runtime lifecycle and state | `lifecycle.py`, `/api/v1/runtime/lifecycle`, `docs/RUNTIME_LIFECYCLE.md` |
| Session Runtime | `pratham/session-runtime/mitra_session/` |
| Context Runtime | `pratham/context-runtime/mitra_context/` |
| Intent Router | `pratham/intent-router/mitra_intent/` |
| Attachment Runtime | `pratham/attachment-runtime/mitra_attachment/` |
| Product attachment without runtime modification | `contracts/examples/product-atlas.json`, `product-nova.json` |
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
| Runtime interface catalog | `contracts/runtime-interface-catalog.json` |
| Runtime state machine | `contracts/runtime-state-machine.json` |
| Execution diagrams | `docs/EXECUTION_FLOW.md` |
| Unit tests | `pratham/tests/` |
| Integration tests | `contracts/integration-tests/` |
| Failure tests | `pratham/tests/test_dispatch_and_failures.py`, `docs/FAILURE_MATRIX.md` |
| Developer onboarding | `docs/DEVELOPER_ONBOARDING.md` |
| Security/IP boundaries | `docs/SECURITY_IP_BOUNDARIES.md` |
| Ownership allowlist/denylist | `docs/OWNERSHIP_BOUNDARY.md` |
| Machine-readable ownership contract | `contracts/ownership-boundary.json` |
| Adapter extension guide | `docs/ADAPTER_GUIDE.md` |
| Review packet | `REVIEW_PACKET.md` |
| Validation report | `VALIDATION_REPORT.md` |
| Security boundary re-execution | `REEXECUTION_REPORT.md` |
| Runtime screenshots | `evidence/runtime-dashboard.png`, `evidence/runtime-openapi.png` |
| Demo video | `evidence/mitra-companion-runtime-demo.mp4` |

The runtime composes published interfaces only. No source from SHAKTI,
Parikshak, governance, evidence, replay, or certification engines is imported
into the implementation.
