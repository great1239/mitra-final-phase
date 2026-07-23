# Implementation Areas

Each area names at most three critical files.

## Strict Execution

- Path: `pratham/companion-runtime/mitra_companion/ecosystem.py`
  Purpose: exact owner calls and ordered stage execution.
  Why modified: the assignment requires operational convergence, not placeholders.
  Key areas: `PublishedEcosystemClient`, `execution_scope`,
  `dependency_preflight`, `_run_integrity_chain`, `_run_stage`.
  Review focus: ordering, semantic acceptance, connection reuse, transactional
  Bucket/Karma serialization, response-bearing partial preflight, no embedded
  fallback.
  Related tests: `test_strict_ecosystem_flow_records_every_owner_response`,
  `test_karma_rejection_stops_prana_and_downstream`,
  `test_concurrent_executions_serialize_bucket_and_karma_heads`, and
  `test_partially_configured_ecosystem_probes_available_owners_then_blocks`.
- Path: `pratham/companion-runtime/mitra_companion/runtime.py`
  Purpose: session boundary and manifest-derived capability contract.
  Why modified: connect existing Mitra architecture to the strict path.
  Key areas: `execute_ecosystem`, `_session_for_ecosystem_request`.
  Review focus: no product branch, unique selection, context isolation.
  Related tests: full convergence suite.
- Path: `pratham/companion-runtime/mitra_companion/store.py`
  Purpose: durable execution, stage, and attempt state.
  Why modified: recovery and idempotency require transactional checkpoints.
  Key areas: ecosystem create/begin/complete/fail/link methods and runtime
  lease transactions.
  Review focus: immutability, stale attempts, request-hash conflicts, lease
  expiry and exclusive ownership.
  Related tests: recovery and idempotency cases.

## Replay And Recovery

- Path: `pratham/companion-runtime/mitra_companion/ecosystem.py`
  Purpose: seal and validate portable replay; resume incomplete stages.
  Why modified: metadata history is not deterministic reconstruction.
  Key areas: `EcosystemReplayLedger`, `recover`, `_stages_with_lineage`.
  Review focus: zero-state validation and lineage recomputation.
  Related tests: clean-state, mutation, recovery tests.
- Path: `pratham/companion-runtime/mitra_companion/store.py`
  Purpose: retain every stage attempt and replay package.
  Why modified: failed attempts and completed stages must survive restart.
  Key areas: attempt table and completed-stage guards.
  Review focus: transaction boundaries and immutable responses.
  Related tests: `test_recovery_resumes_at_failed_stage_without_repeating_owners`.
- Path: `pratham/tests/test_ecosystem_convergence.py`
  Purpose: assert replay and recovery behavior from submitted data.
  Why modified: acceptance must inspect outputs, not generate proof documents.
  Key areas: empty runtime replay and changed-response rejection.
  Review focus: original versus reconstructed equality.
  Related tests: file itself.

## API And Contracts

- Path: `pratham/companion-runtime/mitra_companion/api.py`
  Purpose: public execution, recovery, replay, and operator endpoints.
  Why modified: the complete flow must be callable and observable.
  Key areas: `/api/v1/ecosystem/*`, dashboard, readiness.
  Review focus: status codes and response exposure.
  Related tests: API/OpenAPI convergence test.
- Path: `pratham/companion-runtime/mitra_companion/contracts.py`
  Purpose: versioned Pydantic mutation contracts.
  Why modified: ecosystem requests need explicit identity and idempotency.
  Key areas: `EcosystemExecutionRequest`, replay validation request.
  Review focus: bounds and extra-field rejection.
  Related tests: API model validation.
- Path: `contracts/api/companion-runtime.openapi.yaml`
  Purpose: static public API handover.
  Why modified: incoming engineers must rebuild without code search.
  Key areas: ecosystem paths, assigned host, execution ID parameter.
  Review focus: parity with FastAPI OpenAPI.
  Related tests: OpenAPI route assertion.

## Frontend And Legacy Isolation

- Path: `pratham/companion-runtime/mitra_companion/frontend_connector.py`
  Purpose: adapt the existing website request into canonical ecosystem input.
  Why modified: workflow requests previously used ordinary product dispatch.
  Key areas: `frontend_workflow`, `_workflow_payload`.
  Review focus: explicit Raj action translation and canonical target.
  Related tests: `test_frontend_workflow_uses_canonical_ecosystem_and_fails_closed`.
- Path: `pratham/companion-runtime/mitra_companion/bhiv_integrations.py`
  Purpose: preserve compatibility metadata without owner execution.
  Why modified: remove the duplicate embedded owner path.
  Key areas: `status`, `publish_dispatch`.
  Review focus: zero HTTP calls and factual `not_executed` results.
  Related tests: `test_legacy_exporter_performs_zero_http_calls_when_configured`.
- Path: `pratham/tests/test_bhiv_integrations.py`
  Purpose: lock the no-substitution boundary.
  Why modified: prior tests required local owner success.
  Key areas: ordinary dispatch and configured-endpoint zero-I/O tests.
  Review focus: separation from `EcosystemRuntime`.
  Related tests: file itself.

## Deployment

- Path: `pratham/companion-runtime/mitra_companion/config.py`
  Purpose: environment and mounted-secret configuration.
  Why modified: owner contracts must be supplied without committed secrets.
  Key areas: endpoint loading, redacted summaries, readiness flags.
  Review focus: no secret disclosure.
  Related tests: status and convergence configuration cases.
- Path: `docker-compose.yml`
  Purpose: durable local/hosted topology with owner contract injection.
  Why modified: production execution needs all owner variables.
  Key areas: environment pass-through and persistent `/data`.
  Review focus: secure defaults and exact variable names.
  Related tests: `docker compose config`, health validation.
- Path: `render.yaml`
  Purpose: durable independent deployment profile.
  Why modified: reject example manifests and request owner secrets externally.
  Key areas: production manifest policy and `sync:false` values.
  Review focus: no placeholder URLs or secrets.
  Related tests: deployment configuration validation.

## Operational Acceptance

- Path: `scripts/validate_ecosystem_runtime.py`
  Purpose: execute and verify the complete response-bearing owner chain.
  Why modified: live interoperability must be judged from submitted inputs and
  returned outputs rather than configuration or generated evidence.
  Key areas: declarative cases, 15 owner receipts, clean-process replay,
  tamper rejection, depository lineage, telemetry, metrics, recovery.
  Review focus: fail behavior, output assertions, no simulation, and no
  external acceptance overclaim.
  Related tests: `pratham/tests/test_operational_validators.py` and the live
  two-product acceptance run.
- Path: `contracts/operational-acceptance.json`
  Purpose: hold stable native product requests and selection expectations.
  Why modified: new acceptance inputs should be data rather than validator
  branches.
  Key areas: Trade Bot NVDA and UniGuru drip-irrigation cases.
  Review focus: production-manifest parity and absence of credentials.
  Related tests: operational case coverage test.
- Path: `pratham/tests/test_operational_validators.py`
  Purpose: detect validator defects before owner services are started.
  Why modified: the previous validator emitted an invalid empty required array.
  Key areas: schema samples, case coverage, operation de-duplication, tamper
  copy isolation.
  Review focus: focused regression value.
  Related tests: file itself.

## Clean Rebuild

- Path: `Dockerfile`
  Purpose: create the production runtime and package operational tools.
  Why modified: script changes should not reinstall all Python dependencies.
  Key areas: layer order and non-root script ownership.
  Review focus: image parity and cached rebuild behavior.
  Related tests: fresh image build and Compose healthcheck.
- Path: `scripts/configure_local_ecosystem.py`
  Purpose: create ignored local topology configuration from explicit inputs.
  Why modified: a missing Trade Bot checkout previously failed only during a
  later Compose build.
  Key areas: four sibling owner prerequisites and atomic secret-file output.
  Review focus: early errors and no secret disclosure.
  Related tests: compilation and clean topology configuration.
- Path: `docs/HANDOVER.md`
  Purpose: let a new engineer rebuild, validate, replay, deploy, and operate.
  Why modified: static readiness had been described as completion and the live
  owner command was missing.
  Key areas: pinned sources, secrets, startup order, acceptance outputs,
  depository transfer, public-host boundary.
  Review focus: undocumented assumptions and copy/paste reproducibility.
  Related tests: production readiness handover assertions.
