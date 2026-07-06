# Validation Report

Validated on July 6, 2026.

## Automated verification

| Check | Result |
|---|---|
| Last full unit, API, integration, contract, failure, adapter, ownership, production hardening, production readiness, persistent multi-instance runtime, runtime analysis, and Phase 1-7 conformance test run | `81 passed` |
| Current previous-submission reuse extension static validation | `py_compile` passed for changed runtime/test modules; `git diff --check` passed |
| Example manifests against JSON Schema 2020-12 | passed |
| Two-product runtime simulation | passed |
| Cross-product context isolation | passed |
| Loopback capability dispatch | 2 completed |
| Remote HTTP failure handling | failed receipt persisted; product/runtime degraded |
| Custom transport adapter | passed without runtime/router changes |
| Generic manifest source | arbitrary filenames discovered and attached |
| Hardcoded product-name boundary scan | passed |
| Concrete cross-module coupling scan | passed |
| Ownership contract schema | 9 owned, 9 excluded, 0 errors |
| Forbidden subsystem symbol/import/API scan | passed |
| Phase 1 runtime interface catalog | 7 interfaces, 0 schema errors |
| Phase 1 runtime state machine | 6 runtime states, 14 transitions, 0 schema errors |
| OpenAPI surface | 34 published paths |
| Durable session resume after runtime recreation | passed |
| Durable session and context continuity after runtime recreation | passed |
| Actor-scoped workspace isolation | passed |
| Session/product context isolation | passed |
| Selective capability context loading | passed |
| Deterministic intent registration/discovery | passed |
| Runtime analysis assignment profile, product profile, protocol hints, and fit matrix | passed |
| Automatic AI payload fallback after deterministic schema inference gap | passed |
| Persistent runtime supervisor heartbeat | passed |
| Stale runtime peer cleanup | passed |
| Interrupted companion task recovery after restart | passed |
| Previous submission reuse: seven-phase dispatch journal, capability catalog, public contract summary, and proof bundle | static validation passed; focused pytest blocked by environment approval usage limit |
| Exact capability lookup | passed |
| Ambiguous intent fail-closed routing | passed |
| Unexpected adapter exception normalization | passed |
| Phase 4 Product Attachment Runtime policy and attachment record contracts validate | passed |
| Product self-attachment through published API | passed |
| Detached attachment audit listing | passed |
| Arbitrary transport adapter without runtime code change | passed |
| Phase 5 integration contract catalog | passed |
| Phase 6 multi-product runtime simulation | passed |
| Phase 6 transfer, routing, attachment validation, and failure containment | passed |
| Phase 7 documentation and review package | completed |
| OpenTelemetry instrumentation and collector configuration | passed |
| Prometheus runtime metrics and collector exporter configuration | passed |
| k6 production load profile artifact | passed |
| Structured JSONL telemetry with service/environment fields | passed |
| Production readiness gate | passed |
| Non-root/read-only/restart/resource-bounded container posture | passed |
| Multi-instance runtime continuity | passed |
| Python wheel build and isolated install | passed |
| All five implementation packages import from built artifact | passed |
| OpenAPI YAML parse | OpenAPI `3.1.0`, 34 paths |
| Demo video decode | H.264 MP4, 1440x1080, 30 fps, 17 seconds |

## Live evidence

The runtime was started at `http://127.0.0.1:8090` against the persisted demo
database. Live checks returned:

- runtime state: `READY`;
- attached products: `2`;
- durable sessions: `2`;
- completed dispatches: `2`;
- failed dispatches: `0`;
- product isolation verified: `true`.

Screenshots and the video are under `evidence/`.

## Container note

The Dockerfile and Compose profile are included. A Docker build was attempted,
but Docker Desktop's Linux engine was not running on the validation host, so
container execution could not be exercised in this pass. The Python wheel and
production CLI entry point were independently built and installed
successfully.
