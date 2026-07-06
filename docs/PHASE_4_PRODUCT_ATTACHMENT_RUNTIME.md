# Phase 4 - Product Attachment Runtime

Phase 4 added manifest validation, attachment state, and adapter-driven product
registration.

## Attach

Products attach with `POST /api/v1/attachments` or connect with
`POST /api/v1/products/connect`. Both use the same manifest contract.

The attachment runtime validates:

- contract version;
- unique capability IDs;
- unique intent IDs within each capability;
- unique context scopes;
- valid JSON Schemas for intent payloads;
- transport target compatibility.

## States

| State | Meaning |
| --- | --- |
| `ATTACHED` | discoverable and routable |
| `DEGRADED` | discoverable, not routable |
| `DETACHED` | hidden from default listings and not routable |

## Extension

New products publish manifests. New transport modes register adapters. The
runtime does not add product-specific source branches.

## Contracts

- `contracts/schemas/product-attachment.schema.json`
- `contracts/schemas/attachment-record.schema.json`
- `contracts/product-attachment-runtime-policy.json`
