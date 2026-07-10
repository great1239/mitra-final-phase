# Live Runtime Packet

## Startup Flow

1. `mitra-companion serve --port 8090`
2. Runtime settings load production env, data root, database, manifest
   directory, telemetry, OpenTelemetry, and optional AI resolver config.
3. FastAPI lifespan calls `CompanionRuntime.start()`.
4. Runtime registers an instance row and heartbeat.
5. Directory manifests attach through the manifest-source adapter.
6. `/ready`, `/health`, `/metrics`, and `/` become available.

## Capability Discovery

- `GET /api/v1/capabilities`
- `GET /api/v1/intents`
- `GET /api/v1/products/{product_id}/intent-registrations`
- `GET /api/v1/runtime/capability-graph`
- `POST /api/v1/runtime/capability-plan`

## Intent Routing

Natural user messages enter `POST /api/v1/companion/messages`. The resolver
ranks manifest-published candidates using the extracted customer outcome,
schema fields, published metadata, memory, availability, and observed latency.
Clear selections dispatch. Ambiguous or missing-schema-field turns return
`NEEDS_CLARIFICATION`.

## Execution Path

```json
{
  "message": "Show my market prediction for RELIANCE.NS",
  "actor_id": "market-user",
  "workspace_id": "market-workspace"
}
```

The runtime selects `trade-bot-main / market-prediction / tradebot.predict`,
builds:

```json
{"symbols": ["RELIANCE.NS"]}
```

Then it dispatches through the manifest-declared transport.

## Response Path

The response contains:

- companion status;
- assistant message;
- extracted customer outcome;
- memory summary and slots;
- selection, recommendations, cost, latency, retry metadata;
- manifest/schema-derived capability understanding;
- payload;
- dispatch receipt;
- task notification.
- execution explanation with selected candidate, resolver, confidence,
  runtime-analysis summary, payload keys, dispatch ID, task ID, fallback
  attempts, and reviewer focus.
- capability graph plan;
- companion identity continuity, preferences, trust posture, and relationship
  profile.

## Reconstruction And Depository

Every terminal dispatch writes immutable content-addressed artifacts for the
request, route, manifest, context, phase journal, receipt, and response.
`GET /api/v1/dispatches/{dispatch_id}/reconstruction` rebuilds the execution
from those artifacts and verifies hashes. `GET /api/v1/runtime/depository`
exposes artifact hashes and lineage chain entries for external MDU, evidence,
or replay consumers.

## Command Chain

`GET /api/v1/runtime/chain` returns the command-chain model loaded from
`contracts/runtime-command-chain.json` and enriches it with currently attached
published capabilities, including Bucket Insight, PRANA, Karma, SETU, KESHAV,
and SARATHI convergence consumer manifests.

## Failure Path

Transport failures mark the attachment `DEGRADED`, persist a failed dispatch,
emit telemetry, and then attempt fallback dispatch through the next suitable
ranked published capability when the same inputs can be satisfied safely. If no
fallback is viable, the runtime records a failed task and returns a retry-after-
health-check strategy.

## Recovery Path

`POST /api/v1/attachments/{product_id}/health` checks the product-published
health endpoint. A healthy degraded product is reattached through the same
manifest, with recovery telemetry emitted.

## Streaming

`POST /api/v1/companion/messages/stream` emits NDJSON:

- typing started;
- execution status;
- final message;
- typing stopped.

Clients can poll `GET /api/v1/companion/tasks/{task_id}` for a single execution
task. Companion and fallback behavior is also exposed through Prometheus
counters under `/metrics`.
