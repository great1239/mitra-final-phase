# Runtime Lifecycle

```mermaid
stateDiagram-v2
  [*] --> INITIALIZING
  INITIALIZING --> READY: storage and interfaces ready
  INITIALIZING --> DEGRADED: startup dependency failure
  INITIALIZING --> STOPPED: startup aborted
  READY --> ACTIVE: dispatch starts
  ACTIVE --> READY: dispatch completes
  READY --> DEGRADED: product transport failure
  ACTIVE --> DEGRADED: dispatch failure
  DEGRADED --> READY: operator restores product and runtime
  DEGRADED --> ACTIVE: available product dispatch starts
  READY --> DRAINING: shutdown begins
  ACTIVE --> DRAINING: shutdown begins
  DEGRADED --> DRAINING: shutdown begins
  DRAINING --> STOPPED: clean stop
  STOPPED --> INITIALIZING: process restart
```

Every transition is appended to `runtime_transitions` with source state, target
state, reason, sequence, and UTC timestamp. Illegal transitions raise an error.
`DRAINING` may transition only to `STOPPED`.

Attachment lifecycle is independent:

```text
ATTACHED -> DEGRADED -> ATTACHED
ATTACHED -> DETACHED
DEGRADED -> DETACHED
```

A degraded product does not erase its manifest, sessions, context, or dispatch
history.

Session lifecycle:

```text
ACTIVE -> SUSPENDED -> ACTIVE
ACTIVE -> CLOSED
SUSPENDED -> CLOSED
```

Suspended sessions remain durable and resumable but cannot mutate context,
transfer, or dispatch. Closed sessions are terminal.

The normative state catalog is `contracts/runtime-state-machine.json`.
