# Mitra Live Runtime Sprint

Production activation layer for Mitra's companion runtime, built on the Phase V
foundations but scoped as its own sprint. It lets Mitra understand a customer
request, inspect attached BHIV product manifests, compare user expectation
against product capability, and route only through published runtime contracts.

The runtime supports:

- standalone Mitra;
- Mitra embedded in BHIV products;
- future mobile, XR, and robotics clients.

The runtime owns session continuity, context partitions and transfer, explicit
intent routing, product capability attachment, bounded companion interaction,
lifecycle state, versioned integration APIs, structured telemetry, runtime
metrics, attachment health monitoring, recovery validation, and runtime
analysis for assignment-to-product matching. It runs as a persistent service
process by default: a startup manager loads production configuration, starts
the runtime, loads manifest sources, verifies the persistent supervisor, and
keeps the instance alive for repeated work. Each live runtime instance keeps
heartbeating, marks stale peer instances, recovers interrupted companion tasks
after restart, and runs periodic attachment maintenance instead of behaving as
a one-shot invocation.
It also imports useful generic systems from earlier submissions: manifest-backed
capability catalogs, public contract summaries, semantic-version dependency
reports, source-scope catalogs, seven-phase dispatch checkpoints, and portable
dispatch proof bundles. It
intentionally does not implement product conversation design, governance,
safety, knowledge, domain intelligence, evidence, replay, certification, or
product-specific business logic.

All external integration occurs through published manifest-source and transport
adapter ports. Runtime implementation code contains no product identities.

## Repository ownership

```text
pratham/
  companion-runtime/   composition, API, lifecycle, persistence, transport
  context-runtime/     context loading, updates, isolation, transfer
  intent-router/       registration discovery, lookup, explicit routing
  session-runtime/     durable sessions and resume tokens
  attachment-runtime/  manifest validation and product lifecycle

contracts/
  schemas/             JSON Schema 2020-12 contracts
  api/                 OpenAPI 3.1 contract
  examples/            independently attachable product manifests and flows
  integration-tests/   shared contract and multi-product tests
```

No other developer implementation folder is created or modified.

## Start

```powershell
python -m pip install -e .
mitra-companion validate
mitra-companion serve --port 8090
```

Production container path:

```powershell
docker compose up -d --wait
k6 run scripts/load/k6_companion_runtime.js
```

Open:

- dashboard: `http://localhost:8090/`
- API explorer: `http://localhost:8090/docs`
- health: `http://localhost:8090/health`
- metrics: `http://localhost:8090/metrics`
- runtime analysis: `POST http://localhost:8090/api/v1/runtime/analysis`
- runtime startup: `GET http://localhost:8090/api/v1/runtime/startup`
- graceful restart: `POST http://localhost:8090/api/v1/runtime/restart`
- recovery pass: `POST http://localhost:8090/api/v1/runtime/recovery`
- redacted config: `GET http://localhost:8090/api/v1/runtime/config`
- redacted secrets: `GET http://localhost:8090/api/v1/runtime/secrets`
- source scope: `GET http://localhost:8090/api/v1/runtime/source-scope`
- capability catalog: `GET http://localhost:8090/api/v1/runtime/capability-catalog`
- runtime instances: `GET http://localhost:8090/api/v1/runtime/instances`
- OpenTelemetry Collector Prometheus exporter: `http://localhost:8889/metrics`

Load any directory of published attachment manifests:

```powershell
$env:MITRA_COMPANION_MANIFEST_DIRECTORY="contracts\examples"
mitra-companion serve --port 8090
```

## Runtime behavior

1. A client creates a durable session for one client type and workspace.
2. Context is stored in session, actor/workspace, session/product, and handoff
   partitions.
3. The active product submits a versioned capability manifest.
4. The router materializes deterministic registrations and discovers only
   explicit registered intent IDs.
5. A runtime analysis pass builds an assignment profile, user expectation,
   attached-product profiles, communication/adapter hints, and a fit matrix
   across all discovered capabilities.
6. A companion message can rank published capabilities, ask clarifying
   questions for missing schema fields, preserve memory, and dispatch only
   selected registered intents. When deterministic matching, payload inference,
   or dispatch readiness is weak, ambiguous, or incomplete, the analyzer and
   resolver automatically call configured AI endpoints before asking the user.
7. Each companion response includes a product-neutral `outcome` describing what
   the customer appears to want, plus manifest/schema-derived capability
   understanding so sparse BHIV products can still be routed without runtime
   product branches.
8. The runtime command chain is published through
   `GET /api/v1/runtime/chain` and loaded from
   `contracts/runtime-command-chain.json`.
9. The previous-submission source scope is published through
   `GET /api/v1/runtime/source-scope` and loaded from
   `contracts/source-scope-catalog.json`.
10. The startup manager records production configuration, process startup,
   manifest-source loading, and persistent-supervisor checks.
11. The persistent supervisor refreshes the current runtime heartbeat, removes
   stale peer instances from the active set, recovers interrupted tasks, and
   triggers periodic attachment health maintenance.
12. Production configuration can load from an env file; AI and observability
   endpoints can be supplied by mounted secret files and are only exposed as
   redacted metadata through runtime APIs.
13. The capability catalog validates manifest-declared product/capability
   dependencies and summarizes contract registrations without product branches.
14. A dispatch loads only the context scopes declared by that capability.
15. The transport registry invokes the adapter named by the published manifest.
16. Dispatch phases are checkpointed as a seven-step product-neutral journal:
   request accepted, route selected, payload validated, context loaded,
   transport dispatched, receipt persisted, and terminal completion/failure.
17. Each durable dispatch receipt can produce a portable proof bundle at
   `GET /api/v1/dispatches/{dispatch_id}/proof`.
18. Cross-product work requires an explicit transfer. Product context is never
   copied into the target product; only caller-supplied portable context enters
   the handoff partition.

## Verify

```powershell
pytest
python scripts/run_demo.py
```

The suite covers lifecycle, durable session resume, context revision conflicts,
workspace continuity, product isolation, product self-attachment, multiple
attached products, discovery, routing, dispatch, contract validation,
cross-product transfer, attachment validation, transport failure containment,
BHIV product integration, structured telemetry, metrics, health checks,
recovery validation, restart validation, and concurrency validation.
The live companion suite also covers natural selection, schema-driven payload
inference, clarification handling, execution tasks, memory persistence, and
contracted streaming surfaces. The runtime analysis suite covers assignment
profiling, product profiling, communication hints, fit-matrix scoring,
automatic AI payload repair, and the standalone analysis API. Persistent
runtime coverage verifies the supervisor heartbeat, stale peer cleanup, and
interrupted task recovery after restart. Production-mode coverage verifies
env-file configuration loading, secret-file redaction, startup-manager reports,
operator restart/recovery endpoints, runtime instance reconciliation, and JSONL
process logging. Reuse coverage verifies manifest dependency validation,
source-scope catalog exposure, dispatch checkpoint phases, and proof-bundle
hashing.

## Key documents

- [Submission Index](SUBMISSION_INDEX.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Phase 1 Runtime Design](docs/PHASE_1_COMPANION_RUNTIME_DESIGN.md)
- [Phase 1 Validation Report](PHASE_1_VALIDATION_REPORT.md)
- [Phase 2 Context Runtime](docs/PHASE_2_CONTEXT_RUNTIME.md)
- [Phase 2 Validation Report](PHASE_2_VALIDATION_REPORT.md)
- [Phase 3 Intent Router](docs/PHASE_3_INTENT_ROUTER.md)
- [Phase 3 Validation Report](PHASE_3_VALIDATION_REPORT.md)
- [Phase 4 Product Attachment Runtime](docs/PHASE_4_PRODUCT_ATTACHMENT_RUNTIME.md)
- [Phase 4 Validation Report](PHASE_4_VALIDATION_REPORT.md)
- [Phase 5 Integration Contracts](docs/PHASE_5_INTEGRATION_CONTRACTS.md)
- [Phase 5 Validation Report](PHASE_5_VALIDATION_REPORT.md)
- [Phase 6 Testing](docs/PHASE_6_TESTING.md)
- [Phase 6 Validation Report](PHASE_6_VALIDATION_REPORT.md)
- [Phase 7 Documentation](docs/PHASE_7_DOCUMENTATION.md)
- [Phase 7 Validation Report](PHASE_7_VALIDATION_REPORT.md)
- [Execution Flow](docs/EXECUTION_FLOW.md)
- [Runtime Diagrams](docs/RUNTIME_DIAGRAMS.md)
- [Runtime Lifecycle](docs/RUNTIME_LIFECYCLE.md)
- [Integration Guide](docs/INTEGRATION_GUIDE.md)
- [Developer Onboarding](docs/DEVELOPER_ONBOARDING.md)
- [Failure Matrix](docs/FAILURE_MATRIX.md)
- [Security and IP Boundaries](docs/SECURITY_IP_BOUNDARIES.md)
- [Pratham Ownership Boundary](docs/OWNERSHIP_BOUNDARY.md)
- [Adapter Guide](docs/ADAPTER_GUIDE.md)
- [BHIV Product Integration](docs/BHIV_PRODUCT_INTEGRATION.md)
- [Production Hardening](docs/PRODUCTION_HARDENING.md)
- [Production Tactics Compliance](docs/PRODUCTION_TACTICS.md)
- [Production Readiness Gate](docs/PRODUCTION_READINESS.md)
- [Operations Runbook](docs/OPERATIONS_RUNBOOK.md)
- [SLO and Capacity Targets](docs/SLO_AND_CAPACITY.md)
- [Previous Submission Reuse](docs/PREVIOUS_SUBMISSION_REUSE.md)
- [Review Packet](REVIEW_PACKET.md)
- [Validation Report](VALIDATION_REPORT.md)
- [Security Boundary Re-execution](REEXECUTION_REPORT.md)
