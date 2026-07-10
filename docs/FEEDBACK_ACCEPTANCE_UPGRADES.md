# Mitra Feedback Acceptance Upgrades

This pass converts the received feedback into runtime-visible acceptance
surfaces while preserving the original ownership boundary. Mitra still owns
lifecycle, sessions, context, manifests, routing, transport, telemetry, and
runtime export artifacts. Governance, product logic, certification,
cross-system replay authority, and domain intelligence remain external.

## Closed Gaps

| Feedback gap | Upgrade |
| --- | --- |
| True deterministic replay missing | Every dispatch now records an immutable `mitra-deterministic-reconstruction-v1` package from durable request, route, context, manifest, phase journal, receipt, and response artifacts. `GET /api/v1/dispatches/{dispatch_id}/reconstruction` reconstructs execution from those artifacts and verifies hashes for external replay consumers. |
| Central Depository missing | Added a runtime-owned content-addressed depository export. Artifacts are keyed by canonical SHA-256 hash and linked by hash-chain lineage. `GET /api/v1/runtime/depository` exposes artifacts and lineage for external MDU/BHIV consumers. |
| Runtime provenance too weak | Dispatch proof bundles now include deterministic reconstruction verification. Reconstruction packages contain component hashes, lineage chain hashes, and replay-consumer boundaries. |
| Capability discovery primitive | Added a dynamic capability graph built from attached manifests, schemas, descriptions, metadata, and optional message terms. `GET /api/v1/runtime/capability-graph` exposes product, capability, and intent nodes. |
| Intent composition absent | Added `POST /api/v1/runtime/capability-plan`, which produces candidate single or multi-capability plans across published interfaces. Companion responses now include `capability_plan`. |
| Companion layer thin | Companion memory now carries an identity continuity profile, explicit user preferences, trust counters, client history, and a bounded relationship model. |
| BHIV convergence incomplete | Added published manifests for Bucket Insight, PRANA, Karma, SETU, KESHAV, and SARATHI as convergence consumers. The runtime command chain now names these handoff targets. |
| Scale untested | Added a 200-product simulated attachment test for capability graph and catalog generation. |

## Still Requires External Evidence

These cannot be truthfully completed inside the repository alone:

- live deployment logs from a real environment;
- exported OpenTelemetry traces from a running collector;
- screenshots from an operator using a deployed service;
- penetration or abuse testing evidence;
- throughput, latency distribution, and resource utilization from a real load
  run against deployed infrastructure;
- proof that external BHIV systems actually consumed the exported handoff
  packets in their own repositories or services.

The repository now provides the runtime mechanisms and review endpoints needed
to generate that evidence.

## Reviewer Entry Points

- `GET /api/v1/dispatches/{dispatch_id}/reconstruction`
- `GET /api/v1/runtime/depository`
- `GET /api/v1/runtime/capability-graph`
- `POST /api/v1/runtime/capability-plan`
- `POST /api/v1/companion/messages`
- `GET /api/v1/companion/sessions/{session_id}/memory`

## Test Evidence

The executable coverage added for this feedback lives in:

- `pratham/tests/test_replay_convergence_and_graph.py`
- `pratham/tests/test_companion_interaction.py`
- `contracts/integration-tests/test_contract_examples.py`
