# Execution Flow

## Intent dispatch

```mermaid
sequenceDiagram
  participant C as Client
  participant API as Companion API
  participant S as Session Runtime
  participant X as Context Runtime
  participant R as Intent Router
  participant A as Attachment Runtime
  participant T as Product Transport
  participant P as Product

  C->>API: POST /api/v1/intents/dispatch
  API->>S: Load session
  S-->>API: Active workspace and product
  API->>R: Route explicit intent/product/capability
  R->>A: Materialize attached manifest registrations
  A-->>R: Product, capability, scopes, schema, transport
  R->>R: Fail closed on missing/ambiguous/unavailable route
  API->>X: Load isolated context
  X-->>API: Declared partitions only
  API->>T: Versioned dispatch envelope
  T->>P: HTTP or loopback test transport
  P-->>T: JSON response
  T-->>API: Dispatch result
  API-->>C: Route plus durable receipt
```

The router never infers an intent from free text. The caller or a separately
owned conversation/intelligence component supplies the registered `intent_id`.

## Context transfer

```mermaid
sequenceDiagram
  participant C as Client
  participant S as Session Runtime
  participant X as Context Runtime
  participant DB as Durable Store

  C->>S: Transfer source session to target product/workspace
  S->>DB: Create child session
  S->>DB: Record transfer receipt
  C->>X: Supply portable_context
  X->>DB: Write target handoff partition
  X->>DB: Load target product partition
  DB-->>X: Empty or existing target-only context
  X-->>C: New resume token and isolated merged context
```

## Failure behavior

- unknown or ambiguous intent: fail closed before transport;
- unknown capability: fail with `404` before transport;
- cross-product dispatch without transfer: conflict;
- stale context revision: conflict with current revision preserved;
- incompatible attachment contract: reject before registration;
- HTTP timeout/non-2xx/non-JSON: dispatch fails, product becomes degraded, and
  the lifecycle enters `DEGRADED`;
- unexpected adapter exception: normalize to transport failure and persist a
  failed dispatch receipt;
- runtime shutdown: stop accepting work, record `DRAINING`, then `STOPPED`.
