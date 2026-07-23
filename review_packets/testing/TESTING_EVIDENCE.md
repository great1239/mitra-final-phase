# Runtime Validation Results

Snapshot date: 2026-07-23

This report records outputs returned by running owner services. Tests are
listed separately and are not presented as production integration evidence.

## Automated Validation

| Run | Result | Scope |
| --- | --- | --- |
| Current complete regression | 161 passed on 2026-07-23 | `pratham/tests`, `contracts/integration-tests`, and `integration_services/tests` |
| Previous complete regression | 156 passed on 2026-07-20 | Same three suites before the public persistent Bucket integration |
| KESHAV and ecosystem focused regression | 29 passed | success bypass, typed product error, diagnosis, trace rejection, replay v1/v2, contracts, and operational validator |
| Previous complete repository regression | 145 passed on 2026-07-17 | `pratham/tests` and `contracts/integration-tests` before the final routing regression was added |
| Historical focused ecosystem baseline | 15 passed on 2026-07-16 | retained acceptance-gate provenance; superseded by the current focused run |
| Historical complete baseline | 144 passed on 2026-07-16 | retained acceptance-gate provenance; superseded by later complete runs |

The only warning was the installed Starlette `TestClient` deprecation notice.

Focused regression tests use controlled implementations of the published
contracts. Their portable replay check records `database_reads=0` and
`live_service_calls=0`. Those controlled tests have no production convergence claim;
the separate live executions below provide the owner-service result.

## Clean Deployment

Mitra returned `ready=true` with no pending owner modules. The running topology
contained Raj, KESHAV, Ashmit and authenticated MongoDB, Bucket and private
authenticated Redis, Karma, PRANA, the InsightFlow owner registry and
PostgreSQL bridge, UniGuru, Trade Bot, and Bucket-backed Central Depository.

UniGuru's Supabase client initialized from ignored secrets. A request from the
owner container to Supabase Auth returned HTTP 200, service `GoTrue`, with a
version present. No secret value appears in this report or a tracked image.

## Integration Validation

| Product | Execution | Owner result | Runtime result |
| --- | --- | --- | --- |
| UniGuru | `eco_07fa5401aaf94ebfb2cfd6ead3cd5424` | published response contract accepted the drip-irrigation result; KESHAV not called | `COMPLETED` |
| Trade Bot | `eco_1ac97452891c43bdad40b786eb5b9089` | returned a prediction for the requested `NVDA` symbol; KESHAV not called | `COMPLETED` |
| Trade Bot error | `eco_6e30b5bb66c549d6a691c4bc35b0582a` | real HTTP 422 preserved as `product_error`; KESHAV returned a trace-preserving resolution proposal | `COMPLETED` |

The UniGuru trace was
`4d0226817166d18f9023acf94b4bdb1e2a9e87df11c3f08df44bba5551e8ba54`.
The Trade Bot trace was
`b9701df1f6cb82e674f4d1401dfb0523610d22d73c4a014ba00b2882269ffa44`.
The KESHAV error trace was
`a5a09d63ce920ceb2c28f278f6159035c05c2d413c3e0858ab5759f6083a62b3`.
Mitra preserved each product's semantic response instead of converting a
product rejection into runtime acceptance.

Each execution recorded six dependency preflight responses. The success cases
recorded 15 owner operations; the product-error case recorded 16 because it
called KESHAV `/analyze`:

- Raj workflow execution;
- KESHAV health plus conditional dependency diagnosis;
- Ashmit evaluation;
- Bucket latest hash, append, exact read-back, and global replay;
- Karma health head and integrity append;
- PRANA strict-byte and core forwarding;
- InsightFlow execution ingest;
- Central Depository latest hash, append, exact read-back, and global replay.

Across the three executions all 64 preflight and owner operations retained a
response. Mitra-facing owner calls returned HTTP 2xx, a response SHA-256, and
accepted transport status. Raj separately preserved the product's HTTP 422 as
a typed response. Owner statuses included
Ashmit `ALLOW`, Karma `appended`, PRANA `forwarded`, InsightFlow `accepted`,
and Bucket replay `valid=true`.

## Public Bucket Storage Validation

The personal public endpoint is
[`https://pratham-bhiv-bucket.onrender.com`](https://pratham-bhiv-bucket.onrender.com).
Its free Render web service uses free Render Key Value for runtime state and
MongoDB Atlas as the authoritative append-only ledger. `/health` returned
`healthy` with both MongoDB and Redis connected.

With explicit publication approval, one minimal validation envelope was
submitted on 2026-07-23. It contains the runtime and attached-product names
only; it contains no prompt, product output, credential, or private execution
state.

| Artifact | Append and read-back |
| --- | --- |
| [`mitra-persistence-9cb0e1b3fb144a978531dc32b627a257`](https://pratham-bhiv-bucket.onrender.com/bucket/artifact/mitra-persistence-9cb0e1b3fb144a978531dc32b627a257) | POST 200 with `storage_type=append_only`; GET 200 with exact body and `chain_verified=true` |

Independent sorted-key compact-JSON SHA-256 recomputation matched server hash
`8d8bf07bd8f5aee5da2a6491cd2c747f796d5404a4b5a325ece0a151d7b62dca`.
`POST /bucket/validate-replay` returned `valid=true`, artifact count `1`, and
that hash as the chain head.

The Render service was then restarted. The post-restart health response still
reported MongoDB and Redis connected; the same artifact remained readable with
the same body and hash; replay remained valid with the same count and chain
head. The exact request, responses, and verification results are retained in
`review_packets/testing/bucket-public-storage-live-evidence.json`. This is
observed live behavior, not a simulated response or a proof generator.

The redeployed Vercel Mitra runtime then executed preflight
`eco_325bd69eeeb44eea837bff952b228553`. Its own recorded calls returned HTTP
200 and `accepted` for Bucket `/health` and the Bucket-backed Central
Depository `/bucket/latest-hash`, with the same artifact count and chain head.
The execution subsequently failed closed because Raj, Ashmit, Karma, PRANA,
and InsightFlow still lack public endpoint configuration; Bucket was not an
unhealthy module.

## Replay Validation

| Execution | Package hash | Result |
| --- | --- | --- |
| UniGuru | `0bd258b0759bc2680d964c46ea2e6c771a19e1b17cd32cd08ec7e76586bd8583` | 11 components, 123/123 checks, isolated process, zero DB/live calls, mutation rejected |
| Trade Bot | `c77d72e0e1cbc6f9445807066be5472d9d433bc61614e2491f4e51583c05fb86` | 11 components, 123/123 checks, isolated process, zero DB/live calls, mutation rejected |
| Trade Bot error and KESHAV | `eb73fecea94d23e15e952e094edd9b55033e8fb6915eab33796c237200fe2553` | 11 components, 123/123 checks, isolated process, zero DB/live calls, mutation rejected |

`scripts/validate_ecosystem_runtime.py` passed 425 assertions over the three
actual executions and persisted their exact replay packages under
`/data/operational-acceptance-keshav-final`. It did not generate narrative
evidence or screenshots.

The retained files were then re-read with:

```powershell
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py --validate-package /data/operational-acceptance-keshav-final --summary
```

All three v2 packages returned `verified`, 123/123 checks, deterministic
reconstruction, zero database reads, and zero live calls in Python isolated
mode. Their altered copies returned `failed`. Two retained pre-KESHAV v1
packages were also validated by the current reader at 112/112 checks. The
retained files were not rewritten by validation.

Windows PowerShell 5 altered high-precision market numbers during one JSON
round-trip and correctly caused 15 hash checks to fail. Native validation and
a precision-preserving Python resubmission both passed 112/112. This is a
client serialization limitation, not replay acceptance of changed data.

## Recovery Validation

Before and after restarting private Redis and Bucket, workflow artifacts
`d25a8e32b1f6313cdf41e5ab71daf7423498be60b478a03f2b4e5db80ad7b766`
and `ec8c668b4888eab37164cfb3151da402bcce79c7103b33b28f9a253c6b7c31e5`
remained readable with `chain_verified=true`. Artifact count stayed `3`,
global replay stayed valid, and last hash stayed
`004bf46f1d9bf70ac85cd37e5f6439fb8d68df342b2ec17f5cd2e80fc431f2ea`.

Checkpoint recovery remains covered by the automated suites. The live Bucket
and Redis restart preserved their durable state as recorded above.

## Failover Validation

Shared-database lease takeover remains covered by the automated suites. No
live cross-host network-partition or leader-election test was run.

## Production Validation

Docker Desktop 4.82.0, Engine 29.6.1, and Compose 5.3.0 built and ran the owner
topology. Trade Bot uses the official `xgboost-cpu==3.2.0` package to avoid an
unused GPU/NCCL runtime. Both products reported healthy and were `ATTACHED`.

After a fresh Mitra image rebuild and container recreation, the three-case
operational validator passed, `/ready` reported `READY`, recovery reported
`recovered`, and the deployment-surface validator passed all 21 requests.

Central Depository is Bucket-backed, not an independently deployed certifying
authority. Full local customer convergence is validated without claiming
external certification.

## Load Testing

No new sustained-load or long-duration result is claimed in this pass.

## Hosted Runtime Validation

The independent Vercel host still serves HTTPS dashboard and API surfaces, but
cannot resolve local Docker service names. Therefore full local convergence is
validated; public full-chain convergence and cross-host disaster recovery are
not claimed.
