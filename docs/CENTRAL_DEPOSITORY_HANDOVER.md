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
- content hashes and dispatch-scoped lineage;
- ecosystem stage requests/responses, artifacts, and execution-scoped lineage;
- portable full-chain replay and Central Depository handover package.

The external Central Depository owns cross-system retention, acceptance,
certification, and any policy applied after receipt.

## Current Physical Backend

The current local topology configures `MITRA_CENTRAL_DEPOSITORY_BASE_URL` to the
local Bucket owner service, backed by persistent artifact and Redis volumes.
The reproducible acceptance run on 2026-07-20 appended and read back these
actual handover packages through that path:

| Product case | Execution | Depository artifact | Depository package hash |
|---|---|---|---|
| Trade Bot NVDA | `eco_1ac97452891c43bdad40b786eb5b9089` | `8243a2c25cac41caac7771bf36cc9b6448ef99d99158be0fdb2b0ce6b64717da` | `1eab86b577c535ef8ce56fc41bf8e7025e3b45417b49bc92bfa5d0b6d9240f6b` |
| UniGuru drip irrigation | `eco_07fa5401aaf94ebfb2cfd6ead3cd5424` | `9c18d4226fc8bc6ebaa03c95c017d4f5278917d5320ceace3d00ec41e2538686` | `cab6c4ecdf50f0fdc8dabc069c36079f55280a01697556e48910cde3169ce433` |
| Trade Bot typed error and KESHAV diagnosis | `eco_6e30b5bb66c549d6a691c4bc35b0582a` | `1dc3e9c905630abbf9af81325c62d143b9e5a59c2991edb636af04fe9703b7cf` | `aa9fb537c62462ecf0da3cfa28b8888a6cfe0cd18bf3ae762225fb207040dd0f` |

The exact retained replay files are independently identifiable:

| Product case | Replay package hash | Retained file SHA-256 |
|---|---|---|
| Trade Bot NVDA | `c77d72e0e1cbc6f9445807066be5472d9d433bc61614e2491f4e51583c05fb86` | `28f2c07d22e6db406ccd6559999f72e8afa6b3bf2d8667d98efd67e0d0263764` |
| UniGuru drip irrigation | `0bd258b0759bc2680d964c46ea2e6c771a19e1b17cd32cd08ec7e76586bd8583` | `6ca07901691c149640e5d25718094f53f41cc4b4078bdf0e31ae61380527ddb7` |
| Trade Bot typed error and KESHAV diagnosis | `eb73fecea94d23e15e952e094edd9b55033e8fb6915eab33796c237200fe2553` | `461858501dd89229efba11da2d1be791f9fe40d1c1905faed9299af50da79f75` |

Each Central Depository stage received HTTP 200 for latest hash, append, exact
read-back, and global replay validation. Each execution exposed eleven
content-addressed artifacts and eleven ordered lineage entries. The same run
validated its portable replay in an isolated Python process with 123/123
checks, zero database reads, and zero live service calls, then confirmed that
a changed Raj response was rejected.

This proves the handover storage protocol. It does not claim that a separate
Central Depository owner service accepted or certified the package. The
available `sl_validator_parity` repository is a language validator/compiler,
not a depository HTTP service. Replace the configured base URL when the actual
owner contract is published.

Run with `--require-independent-central-depository` in the canonical validator
when the receiving organization requires an independently hosted depository.
That mode correctly fails while Bucket and Central Depository resolve to the
same endpoint.

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

For final ecosystem acceptance:

```http
GET /api/v1/runtime/depository?subject_type=ecosystem_execution&subject_id={execution_id}&limit=500
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

For every completed ecosystem execution, transfer these three API responses:

1. `POST /api/v1/ecosystem/execute`
2. `GET /api/v1/ecosystem/executions/{execution_id}/replay`
3. `GET /api/v1/runtime/depository?subject_type=ecosystem_execution&subject_id={execution_id}`

The execution details contain every owner response. The replay package
reconstructs the complete chain without database or network access. The
depository response supplies the content-addressed stage artifacts and
lineage. A standard completed ecosystem execution has ten stage artifacts and
one replay artifact, with eleven corresponding lineage entries.

The following is the retained legacy direct-dispatch handover:

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

For an ecosystem execution, the receiving engineer must compare:

- the original request component against the submitted message and payload;
- its reconstructed request hash against `execution.request_hash`;
- selected product, capability, and intent against the capability-selection
  component;
- Raj product output and all subsequent stage responses against their
  component response hashes;
- reconstructed status, trace IDs, artifact IDs, and package hashes against
  the original execution;
- package hash and every stage artifact hash against depository lineage.

For a retained legacy direct dispatch, compare:

- submitted dispatch payload against
  `reconstructed_execution.request.payload`;
- dispatch response against the reconstructed dispatch receipt;
- selected product, capability, and intent against the reconstructed route;
- phase journal against the expected lifecycle;
- deterministic verification status and scope coverage;
- reconstruction package hash against depository lineage.

An HTTP 200 alone is not acceptance.

## Response Handling

Every BHIV module operation must produce one of:

- an accepted response;
- an explicit rejection;
- an explicit transport failure when an external endpoint is configured and
  unavailable.

The canonical ecosystem endpoint returns 503 when an owner contract is not
configured. It never creates an accepted response through an embedded adapter.

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

1. Rebuild the owner topology by following `docs/HANDOVER.md` from section 7.
2. Confirm `/health`, `/ready`, and `/api/v1/ecosystem/readiness`.
3. Run:

   ```powershell
   docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
   ```

4. Require `passed=true` for all three cases. Inspect the non-summary output
   when any assertion fails.
5. Retain each original execution response, replay response, subject-filtered
   depository response, and
   `/data/operational-acceptance-keshav-final/*.replay.json` file.
6. Verify the retained files independently:

   ```powershell
   docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py --validate-package /data/operational-acceptance-keshav-final --summary
   ```

   Require every original package to be `verified` with zero database reads
   and zero live calls. Require every altered copy to be `failed`.
7. Verify artifact hashes, lineage, clean-state reconstruction, and tamper
   rejection. Confirm counts match array lengths. The 2026-07-20 retained v2
   packages each passed 123 checks in isolated mode and rejected their altered
   copies. The two earlier v1 packages also remained valid at 112 checks each.
8. Submit the three-response handover set and exact replay package to the
   external depository.
9. Record the external acceptance or rejection in the external system.

Mitra must not claim external acceptance before step 9 succeeds.
