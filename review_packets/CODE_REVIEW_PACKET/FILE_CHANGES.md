# Sprint File Changes

## New Files

| Path | Purpose |
| --- | --- |
| `pratham/companion-runtime/mitra_companion/ecosystem.py` | strict execution, recovery, owner contracts, replay |
| `pratham/tests/test_ecosystem_convergence.py` | behavioral interoperability and replay validation |
| `contracts/schemas/ecosystem-execution.schema.json` | public execution request contract |
| `contracts/schemas/ecosystem-replay-validation.schema.json` | portable replay validation contract |
| `docs/TANTRA_ECOSYSTEM_CONVERGENCE.md` | authoritative rebuild and operation guide |
| `review_packets/CODE_REVIEW_PACKET/*` | bounded code review surface |
| `review_packets/SCREENSHOTS/README.md` | mandatory visual evidence index |
| `scripts/validate_ecosystem_runtime.py` | output-driven live interoperability and replay acceptance |
| `contracts/operational-acceptance.json` | declarative real-product acceptance inputs |
| `pratham/tests/test_operational_validators.py` | validator regression coverage |

## Modified Files

| Path | Why modified |
| --- | --- |
| `pratham/companion-runtime/mitra_companion/runtime.py` | compose strict runtime and select manifest capability |
| `pratham/companion-runtime/mitra_companion/store.py` | persist executions, stages, attempts, replay package |
| `pratham/companion-runtime/mitra_companion/api.py` | expose execution, recovery, replay, readiness, dashboard |
| `pratham/companion-runtime/mitra_companion/config.py` | load and redact owner endpoint credentials |
| `pratham/companion-runtime/mitra_companion/bhiv_integrations.py` | remove duplicate local owner implementations and retain a zero-I/O compatibility record |
| `pratham/companion-runtime/mitra_companion/frontend_connector.py` | route `/api/workflow/run` into canonical ecosystem execution |
| `pratham/companion-runtime/mitra_companion/contracts.py` | add versioned ecosystem requests |
| `pratham/companion-runtime/mitra_companion/errors.py` | add factual 502 and 503 error contracts |
| `contracts/api/companion-runtime.openapi.yaml` | publish the operator API and assigned host |
| `contracts/integration-contracts.json` | register new routes, schemas, and adapter |
| `contracts/runtime-command-chain.json` | record Raj and executable contract order |
| `contracts/source-scope-catalog.json` | map reused and externalized sprint systems |
| `.env.example` | expose owner configuration names |
| `deploy/production.env.example` | document production secret wiring |
| `api/index.py` | enforce production-only manifest bootstrap |
| `docker-compose.yml` | pass owner contracts into durable deployment |
| `render.yaml` | use production manifests and external secret inputs |
| `vercel.json` | configure ecosystem timeout on public host |
| `README.md` | identify strict entry point and assigned host |
| `docs/ARCHITECTURE.md` | replace placeholder integration with executable chain |
| `docs/BHIV_PRODUCT_INTEGRATION.md` | document exact owner contracts and fail-closed behavior |
| `docs/FINAL_RUNTIME_CONVERGENCE.md` | remove embedded-adapter acceptance claims |
| `docs/HANDOVER.md` | add clean rebuild, configuration, replay, acceptance |
| `docs/INDEPENDENT_HOSTING.md` | distinguish frontend compatibility from strict flow |
| `docs/DOCUMENTATION_INDEX.md` | link authoritative convergence guide |
| `pratham/tests/test_companion_interaction.py` | include Raj in expected chain |
| `pratham/tests/test_bhiv_integrations.py` | assert zero owner I/O outside the canonical path |
| `pratham/tests/test_frontend_connector.py` | assert frontend workflow fail-closed behavior |
| `pratham/tests/test_ownership_boundary.py` | allow owned runtime reconstruction while forbidding external authority |
| `pratham/tests/test_production_readiness_gate.py` | require current executed evidence rather than stale pending claims |
| `scripts/load/k6_companion_runtime.js` | add the strict ecosystem profile and configurable stage durations |
| `review_packets/REVIEW_PACKET.md` | replace historical claims with current factual packet |
| `Dockerfile` | cache runtime dependencies independently from validator edits |
| `scripts/validate_hosted_runtime.py` | generate valid nested payloads, allow loopback HTTP, and wait for real products |
| `scripts/configure_local_ecosystem.py` | require every sibling owner checkout used by Compose |
| `scripts/production_readiness_gate.py` | require the operational acceptance surface |
| `docs/CENTRAL_DEPOSITORY_HANDOVER.md` | make rebuild, replay, and transfer executable from current runtime outputs |

## Deleted Files

Controlled-runtime screenshots were deleted from
`review_packets/SCREENSHOTS/`. They showed contract-test outputs and could not
serve as production owner evidence. No owner repository code was deleted.
