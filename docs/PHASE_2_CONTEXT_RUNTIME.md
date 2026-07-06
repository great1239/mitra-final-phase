# Phase 2 - Context Runtime

Phase 2 added durable context loading, updates, continuity, and product
isolation. The runtime stores opaque JSON; it does not interpret the data.

## Partitions

| Scope | Key | Purpose |
| --- | --- | --- |
| `session` | `session_id` | session continuity |
| `workspace` | `actor_id + workspace_id` | actor/workspace continuity |
| `handoff` | target `session_id` | explicit portable transfer data |
| `product` | `session_id + active_product_id` | product-private state |

Merge order is fixed:

```text
session -> workspace -> handoff -> product
```

## Operations

- `load(session_id, scopes=None)` loads selected partitions.
- `load_for_capability(session_id, scopes)` loads only manifest-declared
  dispatch scopes.
- `update(...)` supports merge/replace and optimistic `expected_revision`.
- `initialize_transfer(...)` writes caller-supplied portable context to the
  target handoff partition.

## Boundary

Product context is never copied to another product automatically. Cross-product
movement requires explicit transfer or product exchange payloads.

## Contracts

- `contracts/schemas/context-view.schema.json`
- `contracts/schemas/context-update.schema.json`
- `contracts/schemas/context-transfer.schema.json`
- `contracts/context-runtime-policy.json`
