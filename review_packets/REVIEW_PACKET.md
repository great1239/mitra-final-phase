# Review Packet - Mitra Live Runtime Sprint

## Scope

This packet covers the production-activation sprint that moves Mitra from
runtime validation into a useful companion execution layer.

Implemented runtime scope:

- persistent runtime lifecycle, health, metrics, telemetry, and attachment state;
- manifest-driven capability discovery, routing, execution, and history;
- bounded companion message layer with memory, summarization, tool selection,
  clarification, execution status, task notifications, and NDJSON streaming;
- optional vendor-neutral AI resolver fallback when deterministic selection is
  not confident;
- UniGuru and Samruddhi/trade-bot attachment through published manifests only;
- reviewable contracts, tests, and evidence artifacts.

Out of scope remains product intelligence, governance, safety policy, domain
reasoning, certification, replay, and product-specific runtime branches.

## Source Scope

The public `great1239` account was checked on 2026-07-04. Runtime-relevant
repositories reflected in this workspace are:

- Commercial-Platform-Architecture-and-Runtime-Foundation
- Companion-Runtime-Foundations
- Constitutional-Runtime-Convergence-Sprint
- Ecosystem-Runtime-Hardening-Assignment
- Governance-Drift-Replay-and-Escalation-Calibration-Sprint
- Operational-Drift-Monitoring-Governance-Reporting-Prototype
- Runtime-Evidence-Producer
- Runtime-Operations-And-Production-Readiness
- SHAKTI-TANTRA-Operationalization-Sprint
- tantra-evidence-integration

The unrelated public/fork repos `composiocode` and
`video_and_location_sharing-` were noted but not used for runtime implementation.

## Acceptance Map

| Sprint requirement | Implementation proof |
|---|---|
| Start Mitra | `mitra-companion serve`, FastAPI lifespan, Docker Compose |
| Attach products | `/api/v1/attachments`, manifest directory loading |
| Discover capabilities | `/api/v1/capabilities`, `/api/v1/intents` |
| Natural selection | `mitra_companion.interaction.NaturalIntentResolver` |
| Customer asks expressed naturally | `outcome` object on companion responses |
| Unknown/sparse BHIV products | manifest/schema/metadata-derived capability understanding |
| Execute real functions | `/api/v1/intents/dispatch`, `/api/v1/companion/messages` |
| Conversation memory | durable `companion_messages` and session context memory |
| Session continuity | durable sessions plus companion memory endpoint |
| Clarification handling | schema-required field prompts before dispatch |
| Multi-step execution status | durable `companion_tasks` records and notifications |
| Response streaming | `/api/v1/companion/messages/stream` NDJSON events |
| Runtime intelligence | ranking, recommendation, cost, latency, retry metadata |
| AI fallback | `MITRA_COMPANION_AI_RESOLVER_URL` optional resolver contract |
| Command chain | `/api/v1/runtime/chain` with `contracts/runtime-command-chain.json` |
| Health and metrics | `/health`, `/ready`, `/metrics`, `/api/v1/runtime/metrics` |
| Recovery | attachment health check and degraded-to-attached restoration |
| Evidence | `evidence/`, `review_packets/`, pytest proof |

## Verification

- Full collected suite: 75 tests.
- Full pytest run: passed.
- New focused tests: `pratham/tests/test_companion_interaction.py`.
- Static contract catalog updated and validated by existing contract tests.
