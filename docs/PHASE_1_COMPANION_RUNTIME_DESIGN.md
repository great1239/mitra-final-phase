# Phase 1 - Companion Runtime Design

Phase 1 defined the runtime boundary, lifecycle, state model, and public
interfaces. The current canonical overview is `docs/ARCHITECTURE.md`; this
file keeps the phase acceptance summary.

## Architecture

`CompanionRuntime` composes lifecycle, sessions, context, intent routing,
attachment, transport, and durable storage. Products are visible only through
published manifests and adapter ports.

Rules:

- no product-specific runtime branches;
- explicit registered intent IDs only;
- context is partitioned by session, workspace, handoff, and product;
- cross-product work requires transfer or product exchange;
- SQLite is the default durable store behind narrow ports.

## Lifecycle

Runtime state follows `contracts/runtime-state-machine.json`:

`INITIALIZING -> READY/DEGRADED/STOPPED -> ACTIVE/DRAINING -> STOPPED`

Transitions are validated by `ALLOWED_TRANSITIONS` and journaled in storage.
Invalid transitions fail closed.

## States

- Runtime: `INITIALIZING`, `READY`, `ACTIVE`, `DEGRADED`, `DRAINING`,
  `STOPPED`.
- Session: `ACTIVE`, `SUSPENDED`, `CLOSED`.
- Attachment: `ATTACHED`, `DEGRADED`, `DETACHED`.
- Dispatch: `ACCEPTED`, `COMPLETED`, `FAILED`.

The machine-readable source is `contracts/runtime-state-machine.json`.

## Runtime interfaces

The interface catalog is `contracts/runtime-interface-catalog.json`.

Main protocols:

- `CompanionRuntimeInterface`
- `LifecycleInterface`
- `SessionRuntimeInterface`
- `ContextRuntimeInterface`
- `ContextTransferRuntimeInterface`
- `IntentRouterInterface`
- `AttachmentRuntimeInterface`

## Phase 1 acceptance criteria

| Requirement | Evidence |
| --- | --- |
| Runtime state machine | schema and implementation transition tests |
| Runtime interfaces | protocol catalog and concrete conformance tests |
| Product-neutral architecture | ownership boundary tests |
| Contract-first integration | OpenAPI and JSON Schema catalog |
