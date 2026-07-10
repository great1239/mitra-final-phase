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

## Runtime Consumer Contracts

| Consumer | Published interaction |
|---|---|
| Ashmit | `GET /health/system` |
| Bucket | latest hash, artifact storage/read, chain validation, replay validation |
| InsightFlow | execution trace ingest |
| Karma | integrity append and bucket-artifact append |
| PRANA | strict byte forwarding and trace-preserving core forwarding |
| Central Depository | Mitra's subject-filtered runtime export API |

Karma precedes PRANA. Mitra forwards only after Karma returns `appended`.
Strict forwarding uses the exact canonical request bytes. Other independent
consumer calls are recorded with their own response, rejection, failure, or
explicit skipped result.

Inspect configured/redacted integration state with:

```http
GET /api/v1/runtime/integrations
```

## Product Manifests

| Product | Manifest | Transport |
| --- | --- | --- |
| UniGuru | `contracts/examples/product-uniguru-runtime.json`; production bootstrap `contracts/production/product-samruddhi-uniguru.json` | `POST /ask`, fallback `POST /new_rag` for UniGuru's documented safe-fallback response, health `GET /health`; dispatch uses `MITRA_PRODUCT_UNIGURU_BEARER_TOKEN` and fallback uses `MITRA_PRODUCT_UNIGURU_RAG_TOKEN` when configured |
| Samruddhi/trade-bot | `contracts/examples/product-trade-bot-main.json`; production bootstrap `contracts/production/product-samruddhi-trade-bot.json` | `POST /tools/predict`, `POST /tools/analyze`, health `GET /tools/health`; HTTP 200 payloads with `predictions[].error` are rejected as failed product execution |
| Bucket Insight | `contracts/examples/product-bucket-insight.json` | manifest contract |
| PRANA Runtime | `contracts/examples/product-prana-runtime.json` | manifest contract |
| Karma Ledger | `contracts/examples/product-karma-ledger.json` | manifest contract |
| SETU Bridge | `contracts/examples/product-setu-bridge.json` | manifest contract |
| KESHAV Knowledge | `contracts/examples/product-keshav-knowledge.json` | manifest contract |
| SARATHI Guide | `contracts/examples/product-sarathi-guide.json` | manifest contract |

These files are contract and test fixtures. Production bootstrap uses
`contracts/production`; live products should connect through
`POST /api/v1/products/connect` or publish an approved production manifest
with `metadata.production_bootstrap: true`.

Both use generic HTTP transport with native payload projection through
`dispatch.options.request_body`.

Production manifests may declare `metadata.health_contract.translator` for
non-linear product health behavior. The translator is product-neutral: it can
follow declared health redirects and normalize known text/HTML responses into
reviewable health facts before the normal JSON contract check runs. It does
not convert a suspended or failed downstream service into healthy state.

## Verification

- `pratham/tests/test_bhiv_integrations.py`
- `pratham/tests/test_bhiv_product_integration.py`
- `pratham/tests/test_replay_convergence_and_graph.py`
- `pratham/tests/test_production_hardening.py`

These tests submit data and assert requests, responses, forwarding order,
byte identity, trace identity, reconstruction, and depository lineage.

No runtime source contains product-specific branches. Product-specific material
is limited to manifests and integration tests.
