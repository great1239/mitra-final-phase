# Architectural Change Summary

## Before

The repository had manifest routing, direct product dispatch, dispatch
reconstruction, a generic BHIV publication helper, and TANTRA handover. Those
surfaces established boundaries but could not prove that the final required
owner chain executed. Historical fallback adapters also made configuration
readiness easy to confuse with live convergence.

## After

The final assignment now has one explicit strict path. It selects a capability
from manifests, invokes Raj and the product, conditionally requests a KESHAV
diagnosis for a typed product error, records Ashmit provenance, persists and
validates Bucket truth, gates PRANA on Karma acceptance, emits InsightFlow
telemetry, exports a Central Depository package, and seals a portable replay.
Every stage has durable input, actual output, attempts, hashes, artifacts, and
lineage.

Recovery resumes from checkpoints. Idempotency prevents duplicate owner work.
Replay validates from a package alone. Missing configuration and owner failure
remain visible failures. The legacy companion path is preserved for backward
compatibility, but its convergence exporter performs zero owner I/O and reports
`not_executed`. The website's `/api/workflow/run` route enters the strict path.

Concurrent Bucket and Karma mutation is fenced by a shared transactional
lease, including across processes using the same database. Owner HTTP calls
reuse a per-execution connection pool, so efficiency does not require shared
request state or a global client lifecycle.

The 2026-07-20 local topology has response-bearing Raj, KESHAV, Ashmit, Bucket, Karma,
PRANA, InsightFlow, UniGuru, and Trade Bot paths. Both production attachments
are healthy and completed real customer executions with clean-state replay.
Raj, Karma, PRANA, and the InsightFlow bridge are contract-faithful local
services rather than the owners' hosted deployments. Central Depository is
Bucket-backed rather than an independent owner service, so external
certification remains unclaimed.

## Boundary Result

No product branch, Raj workflow code, KESHAV analysis or resolution authority,
Bucket authority logic, Karma decision,
PRANA intelligence, InsightFlow interpretation, governance, or certification
logic was added to Mitra.
