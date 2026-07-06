# Product Integration Guide

## 1. Publish A Manifest

Declare product ID, version, attachment mode, capabilities, explicit intents,
input schemas, context scopes, and transport targets. Validate against
`contracts/schemas/product-attachment.schema.json`.

## 2. Connect

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

`POST /api/v1/attachments` is the same contract under the older attachment
name. Identical manifests are idempotent; changed active manifests return
`409`.

## 3. Use Sessions And Context

Create sessions with `POST /api/v1/sessions`. Use context scopes narrowly:

- `session`: session continuity;
- `workspace`: actor/workspace state;
- `product`: product-private state;
- `handoff`: caller-supplied portable transfer context.

Use `expected_revision` when updating context.

## 4. Dispatch

Call `POST /api/v1/intents/dispatch` with an explicit `intent_id`. Include
`product_id` or `capability_id` when needed to avoid ambiguity. The runtime
loads only the capability-declared context scopes and calls the manifest
transport adapter.

## 5. Share With Another Product

Use `/api/v1/product-exchanges` for explicit context, event, artifact, status,
or handoff payloads.

Targets read `/api/v1/products/{product_id}/exchange-inbox` and record receipt,
consumption, or rejection with `/api/v1/product-exchanges/{exchange_id}/ack`.
Product-private context is not copied unless it is explicitly placed in the
exchange payload.

## 6. Transfer

Use `/api/v1/sessions/{session_id}/transfer` to create a target session and
write minimal `portable_context` into the target handoff partition.

## Compatibility

This release accepts contract `1.0.0` and compatibility
`mitra-companion-1`. Optional fields are minor-compatible; renamed, removed, or
new required fields need a new major contract.

Machine-readable catalog: `contracts/integration-contracts.json`.
