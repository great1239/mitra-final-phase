# Change Packet

## Runtime

- Added companion message orchestration to `CompanionRuntime`.
- Added durable companion messages and execution tasks.
- Added generic interaction resolver and schema payload builder.
- Added product-neutral customer outcome extraction.
- Added runtime command-chain loading from `contracts/runtime-command-chain.json`.
- Added manifest/schema-derived sparse capability understanding.
- Added deterministic dispatch reconstruction packages backed by immutable
  depository artifacts and hash-chain lineage.
- Added dynamic capability graph and candidate multi-capability planning.
- Added companion identity continuity, preference, trust, and bounded
  relationship profile memory.
- Added BHIV convergence consumer manifests for Bucket Insight, PRANA, Karma,
  SETU, KESHAV, and SARATHI.
- Added optional AI resolver settings:
  - `MITRA_COMPANION_AI_RESOLVER_URL`
  - `MITRA_COMPANION_AI_RESOLVER_TIMEOUT_SECONDS`
  - `MITRA_COMPANION_DETERMINISTIC_INTENT_THRESHOLD`

## API

- Added `POST /api/v1/companion/messages`.
- Added `POST /api/v1/companion/messages/stream`.
- Added `GET /api/v1/companion/sessions/{session_id}/memory`.
- Added `GET /api/v1/companion/tasks`.
- Added `GET /api/v1/companion/tasks/{task_id}`.
- Added `GET /api/v1/runtime/chain`.
- Added `GET /api/v1/runtime/capability-graph`.
- Added `POST /api/v1/runtime/capability-plan`.
- Added `GET /api/v1/runtime/depository`.
- Added `GET /api/v1/dispatches/{dispatch_id}/reconstruction`.
- Added companion execution explanations, fallback dispatch attempts, and
  companion/fallback Prometheus counters.

## Contracts

- Added `contracts/schemas/companion-message.schema.json`.
- Added `contracts/runtime-command-chain.json`.
- Updated `contracts/api/companion-runtime.openapi.yaml`.
- Updated `contracts/integration-contracts.json`.
- Updated `contracts/runtime-command-chain.json` with BHIV convergence
  consumers.

## Tests

- Added focused companion interaction, reconstruction, convergence, graph, and
  scale tests.
- Full collected test count is now 104 across runtime and contract tests.

## Review Packets

- Added sprint-required `review_packets/` with review, code review,
  architecture, test, change, live runtime, and screenshot index files.
