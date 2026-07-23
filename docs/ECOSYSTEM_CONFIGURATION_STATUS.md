# Ecosystem Configuration Status

Last completed live validation: 2026-07-23

This is the current factual configuration ledger for the Mitra ecosystem. It
records responses produced by running services. It does not treat a manifest,
test double, generated report, or configured URL as proof of integration.

## Live Runtime Topology

| Component | Address | State | Live validation |
| --- | --- | --- | --- |
| Mitra | `http://127.0.0.1:8190` | Operational | `/health` and `/ready` returned HTTP 200 |
| Raj | `http://127.0.0.1:8120` | Operational contract service | `/healthz` returned 200; manifest-selected calls to local UniGuru and Trade Bot returned 200 |
| Ashmit | `http://127.0.0.1:8110` | Operational owner repository | Atlas ping/write/read/cleanup passed; `/health/system` returned 200 with Mongo connected and audit active; `/api/mitra/evaluate` returned an Atlas-backed decision |
| Bucket MongoDB | `127.0.0.1:8111` | Operational | Authenticated MongoDB 7 container and durable named volume, isolated from Ashmit's Atlas connection |
| Bucket owner repository | `http://127.0.0.1:8125` | Operational owner repository | Mongo and private authenticated Redis connected; strict append/read and global replay passed; artifacts and replay head survived Redis and Bucket restarts |
| Bucket public deployment | `https://pratham-bhiv-bucket.onrender.com` | Operational on a free Render web service | `/health` reported MongoDB and Redis connected; append, exact read-back, canonical SHA-256 verification, global replay, restart, and post-restart read-back passed on 2026-07-23 |
| Karma | `http://127.0.0.1:8121` | Operational contract service | New append returned `appended`; duplicate returned `replay_detected` |
| PRANA | `http://127.0.0.1:8122` | Operational contract service | Strict bytes and SHA-256 headers matched; core forwarding preserved `trace_id` |
| KESHAV | `http://127.0.0.1:8126` | Operational owner repository | `/health` identified `KESHAV`; successful products caused no `/analyze` call, while the typed Trade Bot error returned a trace-preserving diagnosis and resolution proposal |
| InsightFlow registry | `http://127.0.0.1:8123` | Operational owner repository | PostgreSQL-backed registry accepted the completed execution envelopes |
| InsightFlow bridge | `http://127.0.0.1:8124` | Operational adapter | Both trace-preserving execution telemetry calls returned `accepted` |
| Central Depository storage | local Bucket contract | Operational storage path, not an independent owner service | Both handover packages were appended, read back with `chain_verified=true`, and included in valid global replay |
| UniGuru | `http://127.0.0.1:8131` | Operational owner product, `ATTACHED` | `/health` and `/ready` passed; Supabase client enabled and GoTrue returned HTTP 200; full ecosystem execution completed |
| Trade Bot | `http://127.0.0.1:8130` | Operational owner product, `ATTACHED` | `/tools/health` returned `healthy`; the requested NVDA symbol was returned and the full ecosystem execution completed |

Raj, Karma, PRANA, and the InsightFlow bridge are executable local services
implemented from the supplied published contracts. They are not presented as
the original owners' hosted deployments. Ashmit and the InsightFlow registry
run code from their owner repositories. Bucket, KESHAV, UniGuru, and Trade Bot
also run from their owner repositories. The public Bucket result is a narrow
live storage validation; it is not used by the validated local full-chain path
and does not prove public full-chain convergence.

## Recorded Outputs

- UniGuru execution `eco_07fa5401aaf94ebfb2cfd6ead3cd5424`, trace
  `4d0226817166d18f9023acf94b4bdb1e2a9e87df11c3f08df44bba5551e8ba54`,
  selected `samruddhi.uniguru.ask` for the drip-irrigation request and completed
  all ten stages with KESHAV skipped.
- Trade Bot execution `eco_1ac97452891c43bdad40b786eb5b9089`, trace
  `b9701df1f6cb82e674f4d1401dfb0523610d22d73c4a014ba00b2882269ffa44`,
  selected `samruddhi.tradebot.predict`, returned the requested `NVDA` symbol,
  and completed all ten stages with KESHAV skipped.
- Trade Bot error execution `eco_6e30b5bb66c549d6a691c4bc35b0582a`, trace
  `a5a09d63ce920ceb2c28f278f6159035c05c2d413c3e0858ab5759f6083a62b3`,
  sent an empty `symbols` list. The owner returned HTTP 422, Raj preserved it as
  `product_error`, and KESHAV returned
  `UNBLOCK_DEPENDENCY:product-runtime-samruddhi-trade-bot`. The diagnosis then
  completed the downstream chain; Mitra did not apply the proposal.
- Each execution recorded six dependency-preflight responses. Success cases
  recorded 15 owner operations and the KESHAV case recorded 16. Every call
  returned HTTP 2xx, transport status `accepted`, a response hash, and no
  recorded error. Ashmit returned `ALLOW`, Karma returned `appended`, PRANA
  returned `forwarded`, InsightFlow returned `accepted`, and all Bucket
  replay validations returned `valid=true`.
- After the Atlas switch, execution `eco_ee8ba2cd935045b3a81b53055bb26652`
  passed 140 live assertions. Ashmit returned trace
  `trace_e301eb88a41eaf06`; direct Atlas read-back found its immutable
  `mitra_response_contract` record with integrity hash
  `12a85e8052360c7489b9904d4dc99ac123a0b841106aad58236c9e3905c09da1`.
- Replay packages `c77d72e0e1cbc6f9445807066be5472d9d433bc61614e2491f4e51583c05fb86`,
  `0bd258b0759bc2680d964c46ea2e6c771a19e1b17cd32cd08ec7e76586bd8583`,
  and `eb73fecea94d23e15e952e094edd9b55033e8fb6915eab33796c237200fe2553`
  each reconstructed `COMPLETED` from eleven immutable components with 123/123
  checks, `clean_state=true`, zero database reads, and zero live calls in an
  isolated Python process. A changed Raj response was rejected for every case.
- The canonical validator passed 425 response-level assertions and persisted
  all three replay packages under `/data/operational-acceptance-keshav-final`.
  Two retained pre-KESHAV v1 packages also passed all 112 checks.
- Bucket artifacts `d25a8e32b1f6313cdf41e5ab71daf7423498be60b478a03f2b4e5db80ad7b766`
  and `ec8c668b4888eab37164cfb3151da402bcce79c7103b33b28f9a253c6b7c31e5`
  remained readable with `chain_verified=true` after Redis and Bucket
  restarts. Artifact count stayed `3`, replay stayed valid, and last hash
  stayed `004bf46f1d9bf70ac85cd37e5f6439fb8d68df342b2ec17f5cd2e80fc431f2ea`.
- UniGuru initialized the personal Supabase client inside its container. A
  live anonymous-key request to Supabase Auth returned HTTP 200 from GoTrue;
  no credential value is stored in tracked files or printed in evidence.
- The final combined Mitra, contract-integration, and executable
  contract-service regression passed all 161 tests on 2026-07-23.
- The personal public Bucket accepted artifact
  `mitra-persistence-9cb0e1b3fb144a978531dc32b627a257` for Mitra with
  UniGuru and Samruddhi named in its minimal validation payload. Exact
  read-back and independent canonical SHA-256 recomputation matched server hash
  `8d8bf07bd8f5aee5da2a6491cd2c747f796d5404a4b5a325ece0a151d7b62dca`.
  After a Render service restart, the same artifact and hash remained readable,
  artifact count remained `1`, and global replay still returned `valid=true`.
- Hosted Mitra preflight `eco_325bd69eeeb44eea837bff952b228553`
  independently called the new public Bucket. Bucket `/health` and the
  Bucket-backed Central Depository `/bucket/latest-hash` both returned HTTP 200
  with transport status `accepted`; the remaining hosted execution block lists
  only Raj, Ashmit, Karma, PRANA, and InsightFlow.

## Errors And Pitfalls

| Area | Observed issue | Current handling |
| --- | --- | --- |
| UniGuru package declaration | Owner code imports `supabase` and Passlib without declaring both runtime packages | The owner Dockerfile installs `supabase`, `passlib`, and a compatible `bcrypt`; clean image import and live startup passed |
| UniGuru Supabase configuration | `SUPABASE_URL` and `SUPABASE_ANON_KEY` were previously absent | Both remain only in ignored `.env.local`; the client initialized and Supabase GoTrue returned HTTP 200 from inside the owner container |
| UniGuru image context | The owner repository had no effective secret-safe allowlist, so `.env.local` could enter an image context | `.dockerignore` and `COPY backend /app/backend` exclude all environment files; checks confirmed no `.env.local`, `.env.production`, or backend `.env` exists in the image |
| UniGuru public host | `uni-guru.in` serves frontend HTML for health/docs paths rather than the published backend JSON contract | Generic endpoint overrides route the published origin to the healthy local owner service while retaining the published URL in receipts |
| Raj origin lookup | Pydantic serialized the manifest base URL with a trailing slash, so the initial exact override lookup missed and the public host returned HTTP 301 | Raj normalizes both configured and requested origins with `rstrip("/")`; the regression test and both live product calls passed |
| UniGuru request validation | The first live request supplied `context` as a string and the owner returned HTTP 422 | The published schema requires an object; the corrected request reached the owner and completed the chain. No adapter weakened the schema |
| Trade Bot public host | `trade-bot-api.onrender.com/tools/health` returns HTTP 503 `Service Suspended` | Generic endpoint overrides route to the healthy local owner service; no simulated response is used |
| Trade Bot image build | Unbounded `xgboost>=1.7` selected a GPU wheel and NVIDIA NCCL on a CPU-only runtime | The official drop-in `xgboost-cpu==3.2.0` package preserves owner imports and reduced the wheel to 5.6 MB; image build, health, and real prediction passed |
| Ashmit Atlas access list | Atlas initially rejected Docker's distinct outbound IP before authentication | The exact container `/32` address was added; authenticated ping/write/read/cleanup and a full Mitra execution now pass without weakened TLS settings |
| Ashmit restart | The owner process caches an initial Mongo connection failure and does not reconnect after Atlas later becomes reachable | Restore Atlas reachability and restart Ashmit; the health gate prevents Mitra startup against a disconnected audit store |
| Bucket health | The owner-hosted public deployment previously had Redis disconnected | The personal public endpoint now reports `healthy`, MongoDB connected, Redis connected, append-only storage active, and deterministic replay enabled |
| Bucket schema | `/bucket/artifact` advertises a generic object at the path while the implementation requires the strict `ArtifactEnvelope` fields and rejects unknown fields | Mitra sends the strict component schema: timestamp, schema version, source module, trace, type, parent, and payload |
| Bucket per-artifact validator | Owner route `/bucket/validate-chain/{artifact_id}` reads the legacy store and reports append-only artifacts missing | Mitra uses exact append-only read-back plus global `/bucket/validate-replay`; both passed. The owner route mismatch remains documented and is not claimed as working |
| Bucket durability | Render's free Key Value service is transient and the free web service has no persistent disk | MongoDB Atlas is the authoritative append-only artifact ledger; Redis is operational runtime state. A real artifact, chain head, and replay count survived a Render service restart |
| Central Depository | The supplied `sl_validator_parity` repository is a language validator/compiler, not a Central Depository HTTP artifact service | Handover storage uses the configured Bucket append-only contract. The public record validates durable storage only; it is not presented as independent depository certification |
| Docker/BuildKit | Bounded product builds left orphaned CLI processes, blocked port forwarding, and caused `WSL_E_USER_VHD_ALREADY_ATTACHED` plus a `vpnkit-bridge` handshake failure | Stalled clients were removed, WSL was shut down to detach the VHD, and this Compose project was recreated without deleting volumes |
| Root Docker allowlist | The secure root `.dockerignore` initially excluded `integration_services`, so Raj failed at `COPY integration_services` | The allowlist now includes that source while continuing to exclude environment files and caches; Raj rebuilt healthy |
| Docker update validation | Earlier Docker Desktop builds had socket and WSL failures | Updated Desktop 4.82.0, Engine 29.6.1, and Compose 5.3.0 built and ran Bucket, UniGuru, Trade Bot, Raj, and Mitra successfully |
| PowerShell replay transport | Windows PowerShell 5 truncated high-precision market floats when deserializing and reserializing the Trade Bot package, causing 15 hash failures | Native validation and a Python JSON round-trip both passed 112/112 checks; replay clients must preserve JSON numeric precision |
| Automatic container restart | Docker restarted all containers concurrently and Ashmit started before Mongo was ready | The documented startup sequence is dependency ordered |
| Product routing | Production routing excludes degraded attachments even when their manifests are valid | `/api/v1/ecosystem/execute` fails closed until a real product health contract passes |
| Workflow request | Raj requires explicit `payload.raj_workflow.action_type`; Mitra does not invent an action | Callers must provide the published workflow instruction |
| Trade Bot missing symbols | Omitting `symbols` invokes the owner's AAPL default and therefore does not create an error | The KESHAV acceptance case sends an explicit empty list, preserving the owner's real HTTP 422 validation response |
| KESHAV authority | `/analyze` returns a diagnosis proposal, while its public wrapper does not expose independently verifiable bundled RAJYA, Sarathi, Core, or internal Bucket outputs | Mitra validates and stores only the published KESHAV response and never claims to authorize or execute its proposal |
| Public Mitra host | Vercel cannot resolve local Compose names such as `raj`, `ashmit`, or `prana` | Full-chain public execution requires separately hosted HTTPS owner services and public environment variables |

The Docker recovery preserved the named MongoDB, PostgreSQL, Karma, Mitra,
Bucket Redis, and Bucket artifact volumes. The 2026-07-20 stack completed both
successful product workflows plus the conditional KESHAV error workflow and
remained ready after the Bucket persistence restart.

## Rebuild Order

The sibling owner files must exist before generating the ignored local
configuration:

```text
../Ashmit-Mitra-T42/backend/.env
../BHIV-Bucket/main.py
../KESHAV-4/api.py
../uniguru_ai/.env.local
../trade-bot-main/backend/Dockerfile
../trade-bot-main/backend/api_server.py
```

The UniGuru file must contain `UNIGURU_API_TOKEN`, `SUPABASE_URL`, and
`SUPABASE_ANON_KEY`. Clone Bucket once when the sibling directory is absent:

```powershell
git clone https://github.com/siddheshnarkar76/bucket.git ..\BHIV-Bucket
```

From the Mitra repository root:

```powershell
python scripts/configure_local_ecosystem.py
docker compose -f docker-compose.ecosystem.yml up -d --wait ashmit-mongo bucket-redis insightflow-postgres
docker compose -f docker-compose.ecosystem.yml up -d --build --wait bucket
docker compose -f docker-compose.ecosystem.yml up -d --wait insightflow-registry insightflow-seed insightflow-bridge
docker compose -f docker-compose.ecosystem.yml --profile uniguru-product up -d --build --wait uniguru
docker compose -f docker-compose.ecosystem.yml --profile tradebot-product up -d --build --wait trade-bot
docker compose -f docker-compose.ecosystem.yml up -d --wait raj keshav karma prana ashmit
docker compose -f docker-compose.ecosystem.yml up -d --wait mitra
```

Do not include a product profile in production acceptance until its owner
health endpoint passes. Run the output-driven acceptance after startup:

```powershell
docker compose -f docker-compose.ecosystem.yml exec -T mitra python scripts/validate_ecosystem_runtime.py http://127.0.0.1:8090 --package-directory /data/operational-acceptance-keshav-final --summary
```

Check the configured core:

```powershell
docker compose -f docker-compose.ecosystem.yml ps
curl.exe http://127.0.0.1:8190/ready
curl.exe http://127.0.0.1:8190/api/v1/ecosystem/readiness
```

The readiness endpoint reports contract configuration. Only the acceptance
command proves product selection, owner responses, replay, telemetry, and
handover storage for submitted customer data.
