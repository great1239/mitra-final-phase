# Change Packet

## Runtime

- Added companion message orchestration to `CompanionRuntime`.
- Added durable companion messages and execution tasks.
- Added generic interaction resolver and schema payload builder.
- Added product-neutral customer outcome extraction.
- Added runtime command-chain loading from `contracts/runtime-command-chain.json`.
- Added manifest/schema-derived sparse capability understanding.
- Added optional AI resolver settings:
  - `MITRA_COMPANION_AI_RESOLVER_URL`
  - `MITRA_COMPANION_AI_RESOLVER_TIMEOUT_SECONDS`
  - `MITRA_COMPANION_DETERMINISTIC_INTENT_THRESHOLD`

## API

- Added `POST /api/v1/companion/messages`.
- Added `POST /api/v1/companion/messages/stream`.
- Added `GET /api/v1/companion/sessions/{session_id}/memory`.
- Added `GET /api/v1/companion/tasks`.
- Added `GET /api/v1/runtime/chain`.

## Contracts

- Added `contracts/schemas/companion-message.schema.json`.
- Added `contracts/runtime-command-chain.json`.
- Updated `contracts/api/companion-runtime.openapi.yaml`.
- Updated `contracts/integration-contracts.json`.

## Tests

- Added focused companion interaction tests.
- Full collected test count is now 75.

## Review Packets

- Added sprint-required `review_packets/` with review, code review,
  architecture, test, change, live runtime, and screenshot index files.
