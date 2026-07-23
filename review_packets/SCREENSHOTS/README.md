# Screenshot Evidence Index

Screenshot evidence is accepted here only when it shows the deployed Mitra
runtime or a response from the actual owner deployment. Controlled contract
servers, fixtures, generated JSON, and local owner substitutes are not
production evidence.

## Current Valid Capture

| File | Claim |
| --- | --- |
| `12-hosted-deployment.png` | the independent Vercel host returned the Mitra dashboard over HTTPS on 2026-07-15 |
| `20-keshav-product-error-diagnosis.png` | the local rebuilt owner topology recorded a real Trade Bot HTTP 422, invoked KESHAV `/analyze`, and displayed its trace-preserving proposal with timestamp and hashes on 2026-07-20 |

The hosted capture proves hosting only. The KESHAV capture proves local
owner-repository interoperability only. Neither proves a publicly hosted
complete owner chain.

## Integration Access At Last Check

| Required view | Current result |
| --- | --- |
| Raj integration | local published-contract service returned HTTP 200 and dispatched a real public Bucket artifact |
| Ashmit integration | owner repository returned HTTP 200, `ALLOW`, and a MongoDB artifact locator |
| Bucket persistence | real append, exact read-back, chain verification, and replay validation passed |
| PRANA event | local published-contract service proved byte identity and trace preservation |
| Karma event | local published-contract service appended once and rejected its duplicate as replay |
| InsightFlow telemetry | owner PostgreSQL registry returned the provenance written through the local bridge |
| Central Depository export | Bucket-backed handover artifact passed append/read/replay; no independent owner service is claimed |
| KESHAV diagnosis | owner repository `/analyze` returned a trace-preserving proposal after a real Trade Bot HTTP 422; Mitra did not authorize it |
| Replay reconstruction | three local full-chain packages passed 123 checks each in isolated mode; two retained v1 packages passed 112 checks each |
| Production metrics/traces | local runtime metrics and traces exist; no public full-chain production run is claimed |
| Failover/disaster recovery | no durable production owner-chain deployment |

The previous controlled-runtime captures were removed because they showed
contract-test outputs, including an ecosystem `READY` state, and could be
mistaken for production owner convergence. Missing screenshots remain missing
until an independently verifiable live response exists.

Local execution
`/api/v1/ecosystem/executions/eco_6e30b5bb66c549d6a691c4bc35b0582a`
contains the actual Raj product-error, KESHAV, Ashmit, Bucket, Karma, PRANA,
InsightFlow, and Central Depository responses. The KESHAV stage is captured;
the remaining required views stay explicitly missing below.

## Required Filename Status

| Required file | Status |
| --- | --- |
| `01-runtime-startup.png` | missing: fresh production capture required |
| `02-runtime-dashboard.png` | missing: fresh production capture required |
| `03-attached-products.png` | missing: fresh production capture required |
| `04-raj-integration.png` | missing: fresh local-contract capture required and must be labelled local |
| `05-ashmit-integration.png` | missing: fresh owner-repository capture required |
| `06-bucket-persistence.png` | missing: fresh public Bucket response capture required |
| `07-prana-event.png` | missing: fresh local-contract capture required and must be labelled local |
| `08-karma-event.png` | missing: fresh local-contract capture required and must be labelled local |
| `09-insightflow-telemetry.png` | missing: fresh owner-registry read-back capture required |
| `10-replay-reconstruction.png` | missing: fresh local full-chain replay capture required and must be labelled local |
| `11-central-depository-export.png` | missing: Bucket-backed storage capture required; independent owner acceptance unavailable |
| `12-hosted-deployment.png` | present: HTTPS host only |
| `13-production-metrics.png` | missing: local runtime capture required and must not be labelled public production |
| `14-opentelemetry-traces.png` | missing: local runtime capture required and must not be labelled public production |
| `15-health-endpoints.png` | missing: fresh hosted capture required |
| `16-multi-instance-runtime.png` | blocked: no durable production deployment |
| `17-failover.png` | blocked: no durable production deployment |
| `18-disaster-recovery.png` | blocked: no durable production deployment |
| `19-operator-dashboard.png` | missing: local completed-execution capture required and must be labelled local |
| `20-keshav-product-error-diagnosis.png` | present: local owner-repository interoperability; not public production |
