# Product Integration Guide

## 1. Publish a manifest

A product declares stable identity, version, attachment mode, capabilities,
context scopes, explicit intents, input schemas, and transport targets. Start
from `contracts/examples/product-atlas.json`,
`contracts/examples/product-nova.json`, or the minimal
`contracts/examples/product-echo.json`, then validate against
`contracts/schemas/product-attachment.schema.json`.

The manifest requests routing metadata only. It cannot grant authority or add
hidden runtime code.

## 2. Connect Or Attach

```http
POST /api/v1/products/connect
Content-Type: application/json

{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "manifest": { "...": "published product manifest" }
}
```

`POST /api/v1/products/connect` and `POST /api/v1/attachments` use the same
manifest contract. Registration is idempotent for an identical active manifest.
A different manifest under the same product ID returns `409`.

Detached records are omitted from the default list. Use
`GET /api/v1/attachments?include_detached=true` when an integration console
needs audit visibility.

## 3. Create or resume a session

The client type is one of `standalone`, `embedded`, `mobile`, `xr`, or
`robotics`. The create response contains a one-time opaque resume token. Only
its SHA-256 digest is stored.

## 4. Write context

Use the narrowest scope:

- `session`: companion continuity across the session;
- `workspace`: actor-scoped workspace state that continues across sessions and
  client types when both actor and workspace IDs match;
- `product`: product-private state for the active product;
- `handoff`: explicit portable context supplied during transfer.

Pass `expected_revision` to prevent lost updates.

Load all context with `GET /sessions/{id}/context`, or repeat the `scope` query
parameter to request only selected partitions, for example
`?scope=session&scope=workspace`.

## 5. Dispatch

Submit an explicit `intent_id`. The runtime validates the active product,
looks up the declared capability, filters context to declared scopes, invokes
the generic transport, and persists a receipt.

Inspect exact manifest registrations through
`/products/{product_id}/intent-registrations`. Use `/capabilities` or the exact
product capability endpoint for lookup. When an intent ID exists under more
than one capability, dispatch must include `capability_id`.

The transport `mode` is an adapter key, not a product classification. HTTP
relative endpoints are resolved against `base_url`; other protocols define
their target rules in their adapters. Adapters return a JSON object.

## 6. Share With Another Product

Use `/api/v1/product-exchanges` when one attached product needs to share a
specific context, event, artifact, status, or handoff payload with another
attached product.

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
  "subject": "portable customer context",
  "payload": {"customer_goal": "show my market prediction"}
}
```

Targets fetch their inbox with
`GET /api/v1/products/{product_id}/exchange-inbox` and acknowledge with
`POST /api/v1/product-exchanges/{exchange_id}/ack`. The runtime stores only
the explicit exchange payload and acknowledgement state; product-private
context is not copied.

## 7. Transfer

Cross-product calls are blocked. Use `/sessions/{id}/transfer` to create a
target session and supply a minimal `portable_context`. Product-private context
from the source is never copied.

## Compatibility

This release accepts contract `1.0.0` and compatibility
`mitra-companion-1`. Adding optional fields is a minor-compatible change.
Renaming/removing fields, changing meaning, or adding required fields requires
a new major contract.

The machine-readable integration catalog is
`contracts/integration-contracts.json`.
