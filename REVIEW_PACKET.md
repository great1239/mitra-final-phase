# Review Packet - Mitra Companion Runtime Phase V

## Scope

This repository implements Pratham's bounded ownership:

- Companion Runtime;
- Session Runtime;
- Context Runtime and transfer;
- Intent Router;
- Capability/Product Attachment Runtime;
- lifecycle, state, versioned APIs, schemas, tests, and documentation.
- bounded companion interaction: natural tool selection, memory,
  clarification, status notifications, streaming, and execution receipts.

It does not implement product conversation design, governance, safety,
knowledge, project/domain intelligence, evidence, replay, certification, or
product-specific business logic.

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
| Conversational companion layer | `/api/v1/companion/messages`, memory, clarification, task notifications, streaming |
| Customer outcome extraction | Product-neutral `outcome` response derived from user message, memory, symbols, and constraints |
| Assignment analysis | `/api/v1/runtime/analysis` profiles assignment text, user expectation, linked products, communication hints, and capability fit before dispatch |
| Unknown BHIV capability understanding | Manifest/schema/metadata-derived capability understanding with sparse-manifest test coverage |
| Command-chain understanding | `/api/v1/runtime/chain` loads `contracts/runtime-command-chain.json` without hardcoded runtime product names |
| Runtime intelligence | capability ranking, fit matrix, recommendations, cost/latency metadata, retry strategy, and automatic AI fallback when deterministic matching or payload inference is incomplete |
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
| Real BHIV product attachment/session/dispatch | UniGuru backward integration and Samruddhi forward integration manifests plus focused integration test |
| Production deployment tactics | FastAPI/Uvicorn workers, Docker Compose, readiness healthcheck, OpenTelemetry Collector, Prometheus endpoint, and k6 profile |
| Production observability | structured telemetry, JSON metrics, Prometheus metrics, OpenTelemetry spans, attachment health checks |
| Production readiness gate | non-root container, read-only service filesystem, restart policy, resource bounds, runbook, SLOs, and automated readiness gate |
| Production resilience | simulated degradation, recovery validation, restart validation, concurrency/load validation |

## Verification

- Automated suite: `78 passed`
- Companion interaction and runtime analysis tests: `7 passed`
- Focused BHIV, hardening, contract, and production-readiness suite: `15 passed`
- Two products attached through published manifests
- Two accessible BHIV products attach through published manifests: UniGuru in `uniguru_ai` and Samruddhi in `trade-bot-main`
- Two sessions spanning an explicit cross-product transfer
- BHIV product-scoped sessions created for UniGuru and Samruddhi
- Two successful routed dispatches
- BHIV intent dispatch verified for `uniguru.execute-query` and `tradebot.predict`
- BHIV attachment health verified through UniGuru `GET /health` and Samruddhi `GET /tools/health`
- Product context isolation verified
- Remote transport failure persisted and degraded safely
- Runtime implementation contains no example or ecosystem product names
- Runtime implementation contains no BHIV product-specific branches; native product payloads are selected by manifest transport options
- Runtime analysis verifies assignment-to-product fit without dispatch and is included in companion message responses
- Structured telemetry emits `dispatch.completed`, `dispatch.failed`, `attachment.health_checked`, and `attachment.recovery_validated` events
- Structured logs include timestamp, service, environment, severity, event type, product, dispatch, latency, health, and recovery fields
- Runtime metrics expose dispatch counters, per-product latency, health checks, and recovery counters through `/api/v1/runtime/metrics` and `/metrics`
- OpenTelemetry instrumentation is wired through FastAPI, runtime dispatch spans, attachment-health spans, and the OTLP collector in Docker Compose
- Production k6 load profile runs UniGuru and Samruddhi attachment, session creation, context loading, routing, dispatch, and threshold validation
- Production-readiness gate passes and verifies non-root container execution, healthchecks, restart policy, restricted writable surfaces, resource limits, log rotation, runbook, SLOs, and required evidence files
- Multi-instance validation proves one runtime instance can consume attachments and sessions created by another instance, and the survivor continues dispatching after the first instance stops
- Attachment health monitoring validates published product health endpoints and restores degraded products after healthy checks
- Restart validation proves BHIV attachments, sessions, and routing survive runtime recreation
- Concurrency validation completes 30 concurrent BHIV dispatches with metrics and JSONL telemetry
- Clarified assignment scope uses two independent real BHIV products, UniGuru and Samruddhi/trade-bot; both consume the runtime through published contracts only with no runtime product branch
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
- `pratham/companion-runtime/mitra_companion/analysis.py`
- `pratham/context-runtime/mitra_context/runtime.py`
- `pratham/intent-router/mitra_intent/runtime.py`
- `pratham/session-runtime/mitra_session/runtime.py`
- `pratham/attachment-runtime/mitra_attachment/runtime.py`
- `contracts/api/companion-runtime.openapi.yaml`
- `contracts/schemas/product-attachment.schema.json`
- `contracts/schemas/runtime-analysis.schema.json`
- `contracts/context-runtime-policy.json`
- `contracts/schemas/context-view.schema.json`
- `contracts/intent-router-policy.json`
- `contracts/schemas/intent-registration.schema.json`
- `contracts/schemas/capability-view.schema.json`
- `contracts/product-attachment-runtime-policy.json`
- `contracts/schemas/attachment-record.schema.json`
- `contracts/integration-contracts.json`
- `contracts/integration-tests/test_contract_examples.py`
- `contracts/examples/product-uniguru-runtime.json`
- `contracts/examples/product-trade-bot-main.json`
- `docs/BHIV_PRODUCT_INTEGRATION.md`
- `docs/PRODUCTION_HARDENING.md`
- `docs/PRODUCTION_TACTICS.md`
- `docs/PRODUCTION_READINESS.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/SLO_AND_CAPACITY.md`
- `pratham/companion-runtime/mitra_companion/telemetry.py`
- `pratham/companion-runtime/mitra_companion/observability.py`
- `deploy/otel-collector-config.yaml`
- `deploy/production.env.example`
- `scripts/production_readiness_gate.py`
- `scripts/load/k6_companion_runtime.js`
- `pratham/tests/test_bhiv_product_integration.py`
- `pratham/tests/test_runtime_analysis.py`
- `pratham/tests/test_production_hardening.py`
- `pratham/tests/test_production_readiness_gate.py`
- `pratham/tests/test_phase4_product_attachment_runtime.py`
- `pratham/tests/test_phase5_integration_contracts.py`
- `pratham/tests/test_phase6_runtime_simulation.py`
- `evidence/demo-transcript.json`
