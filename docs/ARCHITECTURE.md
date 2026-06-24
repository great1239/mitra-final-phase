# Companion Runtime Architecture

## Boundary

Mitra Phase V is a universal companion execution layer, not an intelligence
owner. Products attach through manifests and retain their own business logic.
The runtime moves typed requests and bounded context; it does not decide what a
domain action means or whether it is permitted.

```mermaid
flowchart LR
  Client["Standalone / Embedded / Mobile / XR / Robotics Client"]
  API["Versioned Companion API"]
  Session["Session Runtime"]
  Context["Context Runtime"]
  Router["Intent Router"]
  Attach["Attachment Runtime"]
  Ports["Published Adapter Ports"]
  Transport["Transport Adapter Registry"]
  Sources["Manifest Source Adapters"]
  ProductA["Attached Product A"]
  ProductB["Attached Product B"]

  Client --> API
  API --> Session
  Session --> Context
  API --> Router
  Sources --> Attach
  Attach --> Router
  Context --> Router
  Router --> Ports
  Ports --> Transport
  Transport --> ProductA
  Transport --> ProductB
```

## Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| Companion Runtime | composition, API, durable store, lifecycle, dispatch receipts | product behavior |
| Session Runtime | session identity, resume token validation, client/workspace binding | conversation content |
| Context Runtime | partition loading, revisions, merge order, transfer handoff | knowledge retrieval or inference |
| Intent Router | manifest-derived registration, discovery, capability lookup, explicit product/route selection | natural-language understanding |
| Attachment Runtime | manifest validation, attach/degrade/detach state | capability implementation |
| Adapter ports | manifest discovery and transport interfaces | hidden product implementation |
| Transport registry | adapter lookup by published mode | product-specific routing branches |

## Durable state

SQLite uses WAL mode, full synchronous writes, foreign keys, and explicit
transactions for context revisions. It stores:

- lifecycle transitions;
- sessions and hashed resume tokens;
- session/workspace/product/handoff context partitions;
- product attachment manifests and state;
- dispatch request/response receipts;
- context transfer receipts.

## Context isolation

```mermaid
flowchart TB
  S["Session Context"]
  W["Workspace Context"]
  H["Portable Handoff Context"]
  PA["Product A Context"]
  PB["Product B Context"]
  MA["Merged Context for Product A"]
  MB["Merged Context for Product B"]

  S --> MA
  W --> MA
  H --> MA
  PA --> MA

  S --> MB
  W --> MB
  H --> MB
  PB --> MB

  PA -. never copied .-> PB
```

The precedence order is session, workspace, handoff, then active product.
Workspace partitions are keyed by actor plus workspace, while product
partitions are keyed by session plus active product. A cross-product transfer
creates a new session and only writes caller-supplied portable context to its
handoff partition. Source product context is excluded.

Dispatch uses the Context Runtime's capability-scoped loading interface. It
loads only the partition identifiers published by the selected capability.

The Intent Router derives registration records from durable attachment
manifests rather than maintaining a second mutable capability source.

## Source alignment

- Phase IV Runtime Operations informed durable lifecycle, SQLite journaling,
  health, and versioned API patterns.
- Commercial Platform Architecture informed manifest-first attachment,
  capability identity, compatibility, health, and independent ownership.
- SHAKTI, TANTRA, Evidence, and Parikshak repositories were treated as external
  authorities. Their governance, evidence, replay, and readiness logic was not
  copied or reimplemented.

The runtime has no hardcoded product identifiers. Synthetic examples live only
under `contracts/examples` and tests.

The exact implementation ownership allowlist is defined in
`docs/OWNERSHIP_BOUNDARY.md`.
