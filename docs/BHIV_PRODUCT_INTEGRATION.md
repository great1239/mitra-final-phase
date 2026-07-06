# BHIV Product Integration

BHIV products integrate through manifests and runtime APIs only. Product code
stays in the product repo; Mitra owns attachment, session identity, scoped
context, routing, product exchange, dispatch receipts, and telemetry.

## Connect

```http
POST /api/v1/products/connect
Content-Type: application/json

{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "manifest": { "...": "product-owned manifest" }
}
```

This is the product-facing alias for attachment. It validates the manifest,
stores attachment state, and registers declared capabilities and intents.

## Share

Products share explicit payloads through the exchange mailbox:

```http
POST /api/v1/product-exchanges
Content-Type: application/json

{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "source_product_id": "source-product",
  "target_product_ids": ["target-product"],
  "exchange_type": "context",
  "classification": "internal",
  "subject": "portable customer context",
  "payload": {"customer_goal": "show my market prediction"}
}
```

Targets read:

```http
GET /api/v1/products/target-product/exchange-inbox?status=PENDING
```

Targets acknowledge:

```http
POST /api/v1/product-exchanges/{exchange_id}/ack
Content-Type: application/json

{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "product_id": "target-product",
  "status": "CONSUMED"
}
```

The runtime does not copy private product context. Only explicit exchange
payloads are shared.

## Accessible Product Fixtures

| Product | Manifest | Transport |
| --- | --- | --- |
| UniGuru | `contracts/examples/product-uniguru-runtime.json` | `POST /runtime/execute`, health `GET /health` |
| Samruddhi/trade-bot | `contracts/examples/product-trade-bot-main.json` | `POST /tools/predict`, `POST /tools/analyze`, health `GET /tools/health` |

Both use generic HTTP transport with native payload projection through
`dispatch.options.request_body`.

## Evidence

- `test_bhiv_products_attach_create_sessions_and_dispatch`
- `test_bhiv_dispatch_concurrency_metrics_and_structured_log`
- `test_runtime_analysis_matches_assignment_to_attached_product`
- `test_ai_analysis_payload_is_used_when_deterministic_payload_is_missing`
- `test_product_exchange_api_contract`
- `test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes`

No runtime source contains product-specific branches. Product-specific material
is limited to manifests and integration tests.
