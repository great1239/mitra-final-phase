# Mitra Expectation Baseline

This baseline consolidates the four Mitra-related sprint PDFs:

1. Phase IV Runtime Foundation
2. Phase V Companion Runtime Foundations
3. Ecosystem Runtime Integration and Production Hardening
4. Mitra Live Runtime Sprint / Production Activation

## Consolidated Expectations

| Expectation | Baseline from PDFs | Current runtime status |
| --- | --- | --- |
| Bounded ownership | Mitra owns runtime, execution, interaction, sessions, context, routing, attachment, and operational readiness. It must not own product intelligence, governance, certification, replay authority, or hidden BHIV architecture. | Satisfied through manifest-driven products, explicit transports, published contracts, and ownership boundary docs. |
| Persistent production runtime | Runtime must run continuously with startup manager, heartbeat, graceful restart, recovery, instance management, config loading, logs, health, metrics, Docker, and evidence. | Satisfied through startup manager, supervisor heartbeat, runtime instances, `/health`, `/ready`, `/metrics`, Docker, production config, and validation docs. |
| Companion foundations | Support standalone, embedded, mobile, XR, and robotics clients with durable sessions, resume, context partitioning, context transfer, intent routing, and product attachment. | Satisfied through session runtime, context runtime, intent router, attachment runtime, transfer API, and client-type contracts. |
| Ecosystem integration | At least three BHIV products should attach through published manifests/adapters/contracts without runtime code changes. | Satisfied through manifest examples, product integration evidence, health checks, and product exchange surfaces. |
| Live capability execution | Mitra should discover capabilities, discover intents, select naturally, execute, preserve history, expose availability, health, metadata, permissions, and lifecycle. | Mostly satisfied. Capability/intent discovery, natural selection, execution, history, health, metadata, and lifecycle are implemented. Permissions remain metadata-driven rather than a first-class policy engine. |
| Conversational companion layer | Support memory, session continuity, summarization, context preservation, tool selection, clarification, multi-step workflow surfaces, streaming, typing state, execution status, and background notifications. | Mostly satisfied. Memory, summaries, clarification, selection, streaming NDJSON, typing state, tasks, notifications, and session continuity exist. Multi-step workflow orchestration remains lightweight. |
| Runtime intelligence | Add ranking, recommendations, latency awareness, fallback routing, unavailable handling, retry strategy, cost estimation, and execution explanations without product-specific logic. | Improved in this pass. Ranking, recommendations, latency awareness, estimated cost, unavailable handling, and retry hints already existed. Fallback dispatch and execution explanations are now first-class runtime behavior. |
| Observability and reviewability | Every validation should have executable proof. Reviewers should see startup flow, routing path, response path, failure path, recovery path, JSON request/response, metrics, latency, concurrency, and failure isolation. | Improved in this pass. Dispatch phases/proofs already existed. Companion responses now include `execution_explanation`; task detail and new Prometheus counters expose companion/fallback behavior. |

## Improvements Added In This Pass

- Added automatic fallback dispatch from `companion_message` when the selected
  published capability fails at transport time and another ranked published
  capability can satisfy the same inputs.
- Added `execution_explanation` to companion responses and assistant-turn
  metadata. It records the selected candidate, resolver, confidence, runtime
  analysis status, payload keys, dispatch ID, task ID, fallback attempts, and
  reviewer focus points.
- Added `GET /api/v1/companion/tasks/{task_id}` for direct task polling.
- Added companion/fallback counters to telemetry and Prometheus output:
  `mitra_companion_messages_total`,
  `mitra_companion_messages_completed_total`,
  `mitra_companion_messages_needs_clarification_total`,
  `mitra_companion_messages_failed_total`,
  `mitra_fallback_dispatch_attempts_total`, and
  `mitra_fallback_dispatch_success_total`.
- Updated focused and broad tests to cover fallback routing, execution
  explanations, task lookup, and the current metrics contract.

## Remaining Future Work

- Promote capability permissions from manifest metadata into a first-class
  policy contract if product teams need enforceable runtime checks.
- Add explicit multi-step workflow plans that can coordinate more than one
  published capability while preserving product boundaries.
- Add richer response composition once the separate conversation/UX owner
  publishes that contract.
- Keep product-specific intelligence outside this runtime; use manifests,
  adapters, and transport contracts for all future products.
