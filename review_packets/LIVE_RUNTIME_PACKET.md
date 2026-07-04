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

## Command Chain

`GET /api/v1/runtime/chain` returns the command-chain model loaded from
`contracts/runtime-command-chain.json` and enriches it with currently attached
published capabilities.

## Failure Path

Transport failures mark the attachment `DEGRADED`, persist a failed dispatch,
record a failed task, emit telemetry, and return a retry-after-health-check
strategy.

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
