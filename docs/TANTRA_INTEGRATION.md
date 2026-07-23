# TANTRA Handover Integration

Mitra now carries forward the useful TANTRA work from the earlier runtime
producer, operationalization, constitutional convergence, and consumer
integration sprints. The port is deliberately narrow: Mitra projects facts
from a completed dispatch into TANTRA's published four-bundle contract and
hands that package to TANTRA. It does not import downstream authority logic.

## Runtime Flow

```text
Mitra product dispatch
  -> immutable dispatch receipt and phase journal
  -> clean-state deterministic reconstruction validation
  -> evidence_bundle.json
  -> lineage_bundle.json
  -> replay_bundle.json (contains the portable reconstruction package)
  -> handover_bundle.json (contains exact wire-byte hashes)
  -> Central Depository package artifact
  -> durable outbox row committed before network I/O
  -> POST {MITRA_TANTRA_GATEWAY_URL}/api/v1/execute/evidence-package
  -> opaque gateway delivery receipt
  -> GET {MITRA_TANTRA_GATEWAY_URL}/api/v1/traces/{trace_id}
  -> scheduled trace continuity observation
  -> BHIV convergence packet.handoffs[]

TANTRA gateway
  -> downstream validation authority
  -> lineage/provenance authority
  -> convergence authority
  -> review/certification consumer
```

The gateway and its downstream systems own orchestration and decisions. Mitra
owns only runtime fact projection, transport, trace continuity checks, and
content-addressed package/receipt persistence.

## Published Contract

The outbound request contains exactly:

- `evidence_bundle`
- `lineage_bundle`
- `replay_bundle`
- `handover_bundle`
- `integration_mode: auto`
- factual request `metadata`

The three handover item hashes use the historical gateway's file representation:
sorted keys, two-space indentation, UTF-8, and one final newline. This differs
from the compact canonical JSON used for Mitra's content-addressed artifact
hash and is tested explicitly.

The source bundle uses contract `1.1.0`, schema `1.0.0`, one 64-character
lowercase hexadecimal `trace_id`, and the field set expected by the prior
Pratham consumer. Decision, authority, and governance arrays are empty because
Mitra has not made those decisions.

The replay bundle contains both the original dispatch output hash and the
clean-state reconstructed output hash. `replay_result` is `IDENTICAL` only
after `DeterministicReconstructionLedger.validate_portable_package` succeeds
without reading SQLite, attachment state, sessions, or the product runtime.

## Configuration

| Variable | Purpose |
|---|---|
| `MITRA_TANTRA_GATEWAY_URL` | Base URL for the published TANTRA HTTP gateway |
| `MITRA_TANTRA_API_KEY` | Optional `X-API-Key`; never persisted or returned |
| `MITRA_TANTRA_INTEGRATION_TIMEOUT_SECONDS` | Gateway timeout, default `15` |
| `MITRA_TANTRA_DELIVERY_LEASE_SECONDS` | Claim expiry after worker loss, default `30` |
| `MITRA_TANTRA_INITIAL_BACKOFF_SECONDS` | First retry delay, default `5` |
| `MITRA_TANTRA_MAX_BACKOFF_SECONDS` | Retry delay ceiling, default `300` |
| `MITRA_TANTRA_MAX_ATTEMPTS` | Terminal attempt limit, default `8` |
| `MITRA_TANTRA_DELIVERY_BATCH_SIZE` | Scheduled claim batch, default `20` |

All values support the existing `_FILE` and mounted secrets directory loading
patterns. `GET /api/v1/runtime/integrations` reports only whether the gateway
and key are configured.

If the URL is absent, package production remains active and the handoff is
recorded as `skipped` with `gateway-not-configured`. No approval, lineage
registration, convergence result, or review posture is simulated.

The corresponding outbox row remains `WAITING_CONFIGURATION`. When a later
runtime starts with the gateway configured, it can claim and send the original
stored request without rerunning product logic.

## Inspection

After a dispatch:

1. Read `ecosystem_convergence.handoffs[0]` in the dispatch response.
2. Fetch `/api/v1/runtime/depository?subject_type=dispatch&subject_id={id}`.
3. Locate `tantra.handover-package.v1` and `tantra.gateway-delivery.v1`.
4. Validate the embedded portable package with
   `POST /api/v1/reconstruction/validate` in a clean runtime.
5. When the gateway is configured, compare its returned `trace_id` with every
   bundle and receipt. Mitra rejects a mutated trace as a protocol failure.
6. Inspect `/api/v1/runtime/integrations/tantra/deliveries` for attempts,
   current durable state, response, and next retry time.
7. Execute `/api/v1/runtime/integrations/tantra/reconcile` to fetch accepted
   traces through the gateway's published trace endpoint and verify identity.
8. Inspect `/api/v1/runtime/continuity` for the latest scheduled reconstruction,
   lineage, dependency, trace, and delivery checks.

HTTP `400` responses are non-retryable. `408`, `425`, `429`, network failures,
timeouts, and `5xx` responses are retryable. Gateway failure does not rewrite
or roll back the already committed product result. Retryable deliveries move
to `RETRY`; accepted and non-retryable/exhausted deliveries become terminal.
Each attempt is lease-fenced so an expired worker cannot overwrite a peer's
later result.

## Port Selection

Ported:

- deterministic execution and trace identity;
- the four interoperable bundle shapes;
- exact handover item hashing;
- clean-state reconstruction attachment;
- one published handover endpoint;
- durable delivery claims, restart recovery, and bounded retry;
- published gateway health and remote trace reconciliation;
- response continuity and failure classification;
- content-addressed package and receipt lineage.

Not ported:

- generated proof reports, screenshots, committed output runs, or databases;
- simulated downstream consumers;
- local validation, lineage, convergence, or certification decisions;
- the older prefixed-ID package as a second competing runtime format;
- commercial platform, CRM, marketing, or product-specific code.

The older producer contract informed the deterministic IDs and four-bundle
structure. The later consumer contract is the single live wire format, avoiding
two overlapping package systems.

## Verification

```powershell
python -m pytest pratham/tests/test_tantra_handover.py -q
python -m pytest pratham/tests/test_runtime_coordination.py -q
python -m pytest pratham/tests/test_bhiv_integrations.py -q
python -m pytest pratham/tests/test_ownership_boundary.py -q
```

Tests cover package/schema validity, exact wire hashes, clean-state fidelity,
gateway request shape and authentication, trace mutation, retry classification,
restart recovery, lease fencing, 100-delivery contention, remote trace
reconciliation, secret redaction, authority isolation, and unchanged product
completion.
