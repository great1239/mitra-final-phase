# Mitra Feedback Acceptance Upgrades

This pass converts the received feedback into runtime-visible acceptance
surfaces while preserving the original ownership boundary. Mitra still owns
lifecycle, sessions, context, manifests, routing, transport, telemetry, and
runtime export artifacts. Governance, product logic, certification,
cross-system replay authority, and domain intelligence remain external.

## Closed Gaps

| Feedback gap | Upgrade |
| --- | --- |
| True deterministic replay missing | Every dispatch now records an immutable `mitra-deterministic-reconstruction-v1` package from durable lifecycle, session, route, manifest, dependency catalog, context, phase, telemetry, recovery, failure, request, receipt, and response artifacts. Clean-state validation reads no runtime database. |
| Central Depository missing | Added a runtime-owned content-addressed depository export. Artifacts are keyed by canonical SHA-256 hash and linked by hash-chain lineage. `GET /api/v1/runtime/depository` exposes artifacts and lineage for external MDU/BHIV consumers. |
| Runtime provenance too weak | Dispatch proof bundles now include deterministic reconstruction verification. Reconstruction packages contain component hashes, lineage chain hashes, and replay-consumer boundaries. |
| Capability discovery primitive | Added a dynamic capability graph built from attached manifests, schemas, descriptions, metadata, and optional message terms. `GET /api/v1/runtime/capability-graph` exposes product, capability, and intent nodes. |
| Intent composition absent | Added `POST /api/v1/runtime/capability-plan`, which produces candidate single or multi-capability plans across published interfaces. Companion responses now include `capability_plan`. |
| Companion layer thin | Companion memory now carries an identity continuity profile, explicit user preferences, trust counters, client history, and a bounded relationship model. |
| BHIV convergence incomplete | The canonical runtime uses published contracts and fails closed. Legacy local owner adapters were removed. Ashmit and Bucket are reachable; Raj, Karma, PRANA, and InsightFlow still require working owner endpoints before production convergence can be claimed. |
| Runtime coordination is single-instance | Added atomic shared-maintenance leases with fencing, heartbeat renewal, clean release, and peer takeover. Only the lease holder performs stale-peer recovery, scheduled health checks, outbox processing, and continuity scans. |
| TANTRA transport is one-shot | Added a durable outbox that persists requests before I/O, claims with expiring lease tokens, retries retryable failures with bounded backoff, survives restart, and prevents stale workers from completing reclaimed deliveries. |
| Continuous runtime monitor missing | Added scheduled continuity checks for clean-state reconstruction, lineage, dependency snapshots, trace identity, delivery state, gateway health, and accepted remote traces through the published trace API. These are operational facts, not authority decisions. |
| Dependency monitoring is point-in-time | Health responses and latency are retained as bounded observations with latest state, status changes, consecutive failures, and historical patterns. No unsupported prediction is claimed. |
| Scale untested | Added a contention test that atomically claims 100 durable deliveries across four parallel workers with no duplicate ownership, plus multi-instance takeover and restart recovery tests. |

## Still Requires External Evidence

These cannot be truthfully completed inside the repository alone:

- live deployment logs from a real environment;
- exported OpenTelemetry traces from a running collector;
- screenshots from an operator using a deployed service;
- penetration or abuse testing evidence;
- throughput, latency distribution, and resource utilization from a real load
  run against deployed infrastructure;
- production credentials and availability for every external BHIV service;
- cross-host clustering, which requires a shared production database or event
  infrastructure rather than the documented same-host SQLite topology.

The repository now provides the runtime mechanisms and review endpoints needed
to generate that evidence.

## Reviewer Entry Points

- `GET /api/v1/dispatches/{dispatch_id}/reconstruction`
- `GET /api/v1/runtime/depository`
- `GET /api/v1/runtime/capability-graph`
- `POST /api/v1/runtime/capability-plan`
- `GET /api/v1/runtime/continuity`
- `GET /api/v1/runtime/dependencies/health`
- `GET /api/v1/runtime/integrations/tantra/deliveries`
- `POST /api/v1/runtime/integrations/tantra/reconcile`
- `POST /api/v1/companion/messages`
- `GET /api/v1/companion/sessions/{session_id}/memory`

## Test Evidence

The executable coverage added for this feedback lives in:

- `pratham/tests/test_replay_convergence_and_graph.py`
- `pratham/tests/test_companion_interaction.py`
- `pratham/tests/test_runtime_coordination.py`
- `contracts/integration-tests/test_contract_examples.py`
