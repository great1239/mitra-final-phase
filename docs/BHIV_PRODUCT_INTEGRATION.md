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
| Raj | `GET /healthz`, `POST /api/workflow/execute` version `1.0.0` |
| Ashmit | `GET /health/system` |
| Bucket | owner repository on the local topology; latest hash, strict artifact storage/read, global replay validation; authenticated Redis and artifact volumes are persistent |
| InsightFlow | execution trace ingest |
| Karma | integrity append and bucket-artifact append |
| PRANA | strict byte forwarding and trace-preserving core forwarding |
| Central Depository | configured external append-only contract through the local Bucket owner service; append, exact read-back, global replay, and restart persistence passed |
| TANTRA | four-bundle handover through `POST /api/v1/execute/evidence-package` |

The canonical chain starts at `POST /api/v1/ecosystem/execute`. Karma precedes
PRANA because the supplied published contract allows forwarding only after
Karma returns `appended`. Strict forwarding uses the exact canonical request
bytes. Every owner call records its actual response, rejection, or transport
failure. Missing owner configuration fails closed; it is never converted into
embedded acceptance.

TANTRA is an external-only coordinator. Mitra creates its interoperable package
from the verified dispatch reconstruction and records the result under
`ecosystem_convergence.handoffs`; it does not embed or call the coordinator's
downstream authority systems directly.

Inspect configured/redacted integration state and contracts with:

```http
GET /api/v1/ecosystem/readiness
GET /api/v1/ecosystem/contracts
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
| KESHAV legacy example | `contracts/examples/product-keshav-knowledge.json` | test fixture only; current integration uses conditional owner `POST /analyze` |
| SARATHI Guide | `contracts/examples/product-sarathi-guide.json` | manifest contract |

These files are contract and test fixtures. Production bootstrap uses
`contracts/production`; live products should connect through
`POST /api/v1/products/connect` or publish an approved production manifest
with `metadata.production_bootstrap: true`.

Both use generic HTTP transport with native payload projection through
`dispatch.options.request_body`.

On 2026-07-20 both production attachments were live rather than manifest-only.
UniGuru execution `eco_07fa5401aaf94ebfb2cfd6ead3cd5424` completed the
drip-irrigation request, and Trade Bot execution
`eco_1ac97452891c43bdad40b786eb5b9089` returned the requested NVDA symbol.
Both recorded a KESHAV no-call checkpoint. A third execution,
`eco_6e30b5bb66c549d6a691c4bc35b0582a`, preserved Trade Bot's real HTTP 422 as
a typed product error and received a trace-preserving KESHAV proposal before
completing the downstream chain. Every package passed 123 clean-state replay
checks and rejected mutation.

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
- `pratham/tests/test_tantra_handover.py`
- `pratham/tests/test_ecosystem_convergence.py`

These tests submit data and assert requests, responses, forwarding order,
byte identity, trace identity, reconstruction, and depository lineage.

No runtime source contains product-specific branches. Product-specific material
is limited to manifests and integration tests.
