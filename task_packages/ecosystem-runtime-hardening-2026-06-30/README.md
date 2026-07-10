# Mitra Companion Runtime - Phase V

Production-oriented, reusable execution layer for every future Mitra
experience:

- standalone Mitra;
- Mitra embedded in BHIV products;
- future mobile, XR, and robotics clients.

The runtime owns session continuity, context partitions and transfer, explicit
intent routing, product capability attachment, lifecycle state, versioned
integration APIs, structured telemetry, runtime metrics, attachment health
monitoring, and recovery validation. It intentionally does not implement
conversation design, governance, safety, knowledge, domain intelligence,
evidence, replay, or certification.

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

Open:

- dashboard: `http://localhost:8090/`
- API explorer: `http://localhost:8090/docs`
- health: `http://localhost:8090/health`
- metrics: `http://localhost:8090/metrics`

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
5. A dispatch loads only the context scopes declared by that capability.
6. The transport registry invokes the adapter named by the published manifest.
7. Cross-product work requires an explicit transfer. Product context is never
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

## Key documents

- [Submission Index](SUBMISSION_INDEX.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Phase 1 Runtime Design](docs/PHASE_1_COMPANION_RUNTIME_DESIGN.md)
- [Phase 2 Context Runtime](docs/PHASE_2_CONTEXT_RUNTIME.md)
- [Phase 3 Intent Router](docs/PHASE_3_INTENT_ROUTER.md)
- [Phase 4 Product Attachment Runtime](docs/PHASE_4_PRODUCT_ATTACHMENT_RUNTIME.md)
- [Phase 5 Integration Contracts](docs/PHASE_5_INTEGRATION_CONTRACTS.md)
- [Phase 6 Testing](docs/PHASE_6_TESTING.md)
- [Phase 7 Documentation](docs/PHASE_7_DOCUMENTATION.md)
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
- [Review Packet](REVIEW_PACKET.md)
- [Validation Report](VALIDATION_REPORT.md)
- [Security Boundary Re-execution](REEXECUTION_REPORT.md)
