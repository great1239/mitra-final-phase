# Execution Flow

## Dispatch

```mermaid
sequenceDiagram
  participant C as Client
  participant API as Companion API
  participant S as Session Runtime
  participant X as Context Runtime
  participant R as Intent Router
  participant T as Transport Adapter
  participant P as Product

  C->>API: POST /api/v1/intents/dispatch
  API->>S: Load session
  API->>R: Resolve explicit intent/product/capability
  API->>X: Load declared context scopes only
  API->>T: Send versioned dispatch envelope
  T->>P: Product-owned endpoint
  P-->>API: Product response
  API-->>C: Route plus durable receipt
```

## Product Connect

```mermaid
sequenceDiagram
  participant P as Product
  participant API as Companion API
  participant A as Attachment Runtime
  participant R as Intent Router

  P->>API: POST /api/v1/products/connect
  API->>A: Validate and store manifest
  A-->>API: Attachment record
  API->>R: Register declared intents
  API-->>P: Versioned connection response
```

## Product Exchange

```mermaid
sequenceDiagram
  participant A as Source Product
  participant API as Companion API
  participant DB as Runtime Store
  participant B as Target Product

  A->>API: POST /api/v1/product-exchanges
  API->>DB: Store envelope and target rows
  B->>API: GET /api/v1/products/{product_id}/exchange-inbox
  API-->>B: Pending explicit payloads
  B->>API: POST /api/v1/product-exchanges/{exchange_id}/ack
  API->>DB: Store receipt state
```

## Transfer

`/api/v1/sessions/{session_id}/transfer` creates a target session and writes
only caller-supplied `portable_context` to the target handoff partition.

## Failure Rules

- unknown or ambiguous intent: fail before transport;
- cross-product dispatch without transfer: conflict;
- stale context revision: conflict;
- invalid manifest: reject before registration;
- transport failure: persist failed dispatch and degrade only that attachment;
- shutdown: stop accepting work, drain, then stop.
