# BHIV Product Integration

The Mitra Companion Runtime integrates the selected BHIV products through
published contracts only. Product-specific behavior remains in the product
folders; the runtime owns attachment, session identity, context isolation,
deterministic intent routing, transport invocation, metrics, and operational
telemetry.

## Required Runtime Files

| Concern | File | Responsibility |
| --- | --- | --- |
| Public interfaces | `pratham/companion-runtime/mitra_companion/interfaces.py` | Defines the attachment, session, context, router, transfer, and top-level runtime protocols. |
| Adapter ports | `pratham/companion-runtime/mitra_companion/ports.py` | Defines `TransportAdapter` and `ManifestSourceAdapter` so products attach without runtime branches. |
| HTTP and loopback adapters | `pratham/companion-runtime/mitra_companion/transport.py` | Selects transport by manifest `dispatch.mode`; supports native HTTP payload projection through `dispatch.options.request_body`. |
| Runtime telemetry | `pratham/companion-runtime/mitra_companion/telemetry.py` | Emits structured JSONL events and in-process metrics without product branches. |
| Manifest source adapter | `pratham/companion-runtime/mitra_companion/manifest_sources.py` | Loads published product manifests from `MITRA_COMPANION_MANIFEST_DIRECTORY`. |
| HTTP routing | `pratham/companion-runtime/mitra_companion/api.py` | Exposes attachment, session creation, context loading, intent discovery, dispatch, metrics, telemetry, and attachment health routes. |
| Runtime orchestration | `pratham/companion-runtime/mitra_companion/runtime.py` | Composes lifecycle, sessions, context, attachments, router, dispatch, health checks, recovery, and telemetry. |
| Attachment runtime | `pratham/attachment-runtime/mitra_attachment/runtime.py` | Validates and stores product manifests. |
| Session runtime | `pratham/session-runtime/mitra_session/runtime.py` | Creates durable product-scoped sessions. |
| Intent router | `pratham/intent-router/mitra_intent/runtime.py` | Resolves deterministic product/capability/intent routes from attached manifests. |

## BHIV Product Manifests

| Product | Manifest | Product route |
| --- | --- | --- |
| UniGuru AI | `contracts/examples/product-uniguru-runtime.json` | `POST /runtime/execute` in `uniguru_ai/uniguru_v2-main-main/backend/service/uniguru_runtime_api.py`; health from `GET /health` in `uniguru_ai/backend/service/api.py` |
| Trade Bot Main | `contracts/examples/product-trade-bot-main.json` | `POST /tools/predict` and `POST /tools/analyze` in `trade-bot-main/backend/api_server.py` |

Both manifests use the generic `http` transport with
`options.request_body` set to `payload`. This lets the runtime send native
product request bodies while preserving Companion headers for session,
correlation, and contract version.

## Operational Behavior

| Capability | Evidence |
| --- | --- |
| Product attachment | `test_bhiv_products_attach_create_sessions_and_dispatch` attaches UniGuru AI and Trade Bot Main from manifests. |
| Session creation | The focused BHIV test creates one product-scoped session per product. |
| Context loading and deterministic routing | Dispatch uses the intent registry derived from each manifest and loads only the capability-declared context scopes. |
| Native product dispatch | UniGuru AI receives `POST /runtime/execute`; Trade Bot Main receives `POST /tools/predict`. |
| Health monitoring | UniGuru AI publishes `GET /health`; Trade Bot Main publishes `GET /tools/health`; both are checked through the generic attachment health monitor. |
| Metrics and telemetry | `test_bhiv_dispatch_concurrency_metrics_and_structured_log` verifies dispatch counters, per-product latency metrics, and JSONL structured events. |
| Restart validation | `test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes` proves attachments, sessions, and routing survive runtime recreation. |
| Recovery validation | `test_attachment_health_monitoring_and_recovery_validation` simulates HTTP failure, degradation, health recovery, and resumed dispatch. |

## Runtime Modification Boundary

No runtime source contains UniGuru or Trade Bot specific branches. The only
product-specific files are the two manifests under `contracts/examples/` and
the focused integration tests that prove the manifests can drive the generic
runtime.
