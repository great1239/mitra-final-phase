# Runtime Diagrams

This page collects the main runtime diagrams in one place for review.

## Capability attachment

```mermaid
flowchart LR
  Manifest["Published product manifest"]
  AttachAPI["Attachment API"]
  AttachmentRuntime["Product Attachment Runtime"]
  Store["Durable attachment store"]
  Router["Intent Router"]
  Registry["Materialized registrations"]

  Manifest --> AttachAPI
  AttachAPI --> AttachmentRuntime
  AttachmentRuntime --> Store
  Store --> Router
  Router --> Registry
```

## Dispatch path

```mermaid
flowchart LR
  Client["Client"]
  Session["Session Runtime"]
  Router["Intent Router"]
  Context["Context Runtime"]
  Transport["Transport Adapter"]
  Product["Attached Product"]
  Receipt["Durable dispatch receipt"]

  Client --> Session
  Session --> Router
  Router --> Context
  Context --> Transport
  Transport --> Product
  Product --> Receipt
```

## Context partitions

```mermaid
flowchart TB
  Session["session partition"]
  Workspace["actor/workspace partition"]
  Handoff["handoff partition"]
  ProductA["session/product A partition"]
  ProductB["session/product B partition"]
  ViewA["capability-scoped view for product A"]
  ViewB["capability-scoped view for product B"]

  Session --> ViewA
  Workspace --> ViewA
  Handoff --> ViewA
  ProductA --> ViewA

  Session --> ViewB
  Workspace --> ViewB
  Handoff --> ViewB
  ProductB --> ViewB

  ProductA -. not transferred .-> ProductB
```

## Lifecycle and failure containment

```mermaid
stateDiagram-v2
  [*] --> STOPPED
  STOPPED --> INITIALIZING
  INITIALIZING --> READY
  READY --> ACTIVE
  ACTIVE --> READY
  READY --> DEGRADED
  ACTIVE --> DEGRADED
  DEGRADED --> READY
  READY --> DRAINING
  DEGRADED --> DRAINING
  DRAINING --> STOPPED
```

Transport failures degrade the affected attachment and runtime state. Healthy
attachments remain attached and can still be routed when explicitly selected.

