# Code Review Packet

Maximum review surface: five primary files.

## 1. `pratham/companion-runtime/mitra_companion/interaction.py`

Purpose: generic companion interaction intelligence over published manifests.

Why changed: adds natural capability selection, recommendations, schema-driven
payload inference, clarification prompts, cost/latency/retry metadata, memory
summarization, customer outcome extraction, sparse capability understanding,
and optional AI resolver fallback.

Integration points: `CompanionRuntime.companion_message`, manifest intent
registrations, runtime metrics, and optional `MITRA_COMPANION_AI_RESOLVER_URL`.

Reviewer focus: ranking thresholds, ambiguity behavior, required-field
inference, sparse-manifest routing, and ensuring no product-specific branches
exist.

## 2. `pratham/companion-runtime/mitra_companion/runtime.py`

Purpose: orchestrates companion turns end to end.

Why changed: creates/resumes sessions, records user/assistant turns, selects
capabilities, asks for clarification, dispatches selected intents, records
execution tasks, updates memory, exposes the runtime command chain from a
contract file, and emits telemetry.

Integration points: session runtime, context runtime, intent router, attachment
runtime, transport registry, telemetry, and durable store.

Reviewer focus: failure handling, memory persistence, dispatch boundaries, and
cross-product behavior.

## 3. `pratham/companion-runtime/mitra_companion/store.py`

Purpose: durable state for companion messages and execution tasks.

Why changed: adds `companion_messages` and `companion_tasks` tables plus list,
read, create, and update helpers.

Integration points: SQLite runtime database, session foreign keys, dashboard
and memory/task APIs.

Reviewer focus: migration safety on existing databases, JSON encoding, ordering,
and no changes to existing `counts()` contract.

## 4. `pratham/companion-runtime/mitra_companion/api.py`

Purpose: exposes companion interaction APIs.

Why changed: adds message, stream, memory, and task endpoints while preserving
existing versioned contracts.

Integration points: FastAPI, OpenAPI contract, runtime lifecycle, and error
handler.

Reviewer focus: stream error semantics, versioned responses, and endpoint
compatibility.

## 5. `pratham/tests/test_companion_interaction.py`

Purpose: executable proof of the new live companion path.

Why changed: verifies natural selection, schema-driven symbol extraction,
dispatch, memory persistence, task completion, and clarification handling.

Integration points: Samruddhi manifest, mocked HTTP transport, session/context
runtime, and companion memory API.

Reviewer focus: coverage of both successful execution and missing-field
clarification.
