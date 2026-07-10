# Central Depository Handover

This document defines how an incoming engineer or external depository consumer
receives real Mitra runtime artifacts. It does not create a parallel evidence
system.

## Ownership Boundary

Mitra owns creation and export of runtime facts:

- dispatch request and response;
- route, manifest, context, and phase snapshots;
- deterministic reconstruction package;
- telemetry and recovery state included by reconstruction;
- content hashes and dispatch-scoped lineage.

The external Central Depository owns cross-system retention, acceptance,
certification, and any policy applied after receipt.

## API Contract

```http
GET /api/v1/runtime/depository
```

Optional query parameters:

| Parameter | Meaning |
|---|---|
| `artifact_type` | include only this artifact type |
| `subject_type` | filter lineage, normally `dispatch` |
| `subject_id` | filter to one dispatch or other subject |
| `limit` | 1-500 records, default 100 |

For a dispatch handover:

```http
GET /api/v1/runtime/depository?subject_type=dispatch&subject_id={dispatch_id}&limit=500
```

When subject filters are present, the response includes only artifacts
referenced by that subject's returned lineage. It does not include unrelated
runtime artifacts.

Response body:

```json
{
  "schema_version": "1.0.0",
  "contract_version": "1.0.0",
  "runtime_version": "1.0.0",
  "compatibility_version": "mitra-companion-1",
  "depository": {
    "depository_type": "mitra-runtime-central-depository-export",
    "authority_boundary": "Mitra exports immutable runtime artifacts...",
    "filters": {
      "artifact_type": null,
      "subject_type": "dispatch",
      "subject_id": "dsp_example",
      "limit": 500
    },
    "artifact_count": 1,
    "lineage_count": 1,
    "artifacts": [],
    "lineage": []
  }
}
```

The arrays contain the actual records; the empty arrays above only abbreviate
the shape.

## Required Handover Set

For every dispatch, transfer these three API responses together:

1. `POST /api/v1/intents/dispatch`
2. `GET /api/v1/dispatches/{dispatch_id}/reconstruction`
3. `GET /api/v1/runtime/depository?subject_type=dispatch&subject_id={dispatch_id}`

Optionally include:

- `GET /api/v1/dispatches/{dispatch_id}/phases`
- `GET /api/v1/runtime/telemetry`
- `GET /api/v1/runtime/integrations`
- `GET /metrics`

The dispatch response is the observed execution result. Reconstruction proves
that the runtime can rebuild the recorded execution from immutable artifacts.
The depository response supplies content-addressed artifacts and lineage.

## Artifact Verification

For every item in `depository.artifacts`:

1. canonicalize the value in `artifact`;
2. serialize JSON with sorted keys, UTF-8, and compact separators;
3. calculate SHA-256 hexadecimal output;
4. compare it with `artifact_hash`.

Equivalent Python:

```python
import hashlib
import json


def sha256_json(value):
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

Reject the handover if an artifact hash does not match.

## Lineage Verification

Group lineage entries by `(subject_type, subject_id)` and sort each group by
ascending `sequence`.

For each entry:

1. sequence 1 must have `parent_chain_hash: null`;
2. every later entry must reference the preceding `chain_hash`;
3. `artifact_hash` must resolve to an artifact in the handover or an explicitly
   retained artifact already known to the receiving depository;
4. recompute `chain_hash` from:

```json
{
  "subject_type": "...",
  "subject_id": "...",
  "artifact_hash": "...",
  "parent_chain_hash": "...",
  "sequence": 1,
  "metadata": {}
}
```

Use the same canonical JSON and SHA-256 rules as artifact verification.

Reject gaps, duplicate sequence numbers, parent mismatches, missing artifacts,
or hash mismatches.

## Replay Alignment

The receiving engineer must compare:

- submitted dispatch payload against
  `reconstructed_execution.request.payload`;
- dispatch response against the reconstructed dispatch receipt;
- selected product, capability, and intent against the reconstructed route;
- phase journal against the expected lifecycle;
- deterministic verification status and scope coverage;
- reconstruction package hash against depository lineage.

An HTTP 200 alone is not acceptance.

## Response Handling

Every configured BHIV module operation must produce one of:

- an accepted response;
- an explicit rejection;
- an explicit transport failure;
- an explicit `skipped` result when the endpoint is not configured.

Karma must return `appended` before Mitra forwards the exact request bytes to
PRANA. A rejection or replay result must not be forwarded.

## Storage And Security

- Preserve the SQLite database and telemetry logs on durable storage.
- Place the API behind deployment authentication and authorization before
  exposing depository records outside a trusted environment.
- Do not log secret endpoint values.
- Do not edit stored artifacts. Add a new artifact and lineage entry instead.
- Store the exact received JSON bytes when external byte-level verification is
  required.
- Record the source runtime URL, runtime version, dispatch ID, receipt time,
  and receiving system identity outside the Mitra artifact itself.

## Operator Procedure

1. Confirm `/health` and `/ready`.
2. Submit a real dispatch.
3. Confirm the dispatch status and output values.
4. Fetch deterministic reconstruction.
5. Fetch the subject-filtered depository export.
6. Verify artifact hashes and lineage.
7. Confirm counts match array lengths.
8. Submit the three-response handover set to the external depository.
9. Record the external acceptance or rejection in the external system.

Mitra must not claim external acceptance before step 9 succeeds.
