# Ashmit Owner Runtime

Mitra integrates with Ashmit through published HTTP contracts only. Ashmit
retains policy, enforcement, Bucket audit persistence, and provenance
authority. No Ashmit source code is copied into the Mitra runtime.

## Contracts

| Method and path | Mitra use |
| --- | --- |
| `GET /health/system` | Require active execution plus connected MongoDB audit persistence |
| `POST /api/mitra/evaluate` | Record the completed Raj execution and receive Ashmit's decision, trace ID, and Mongo artifact locator |

`POST /api/mitra/evaluate` requires `X-API-Key`. Mitra records the actual HTTP
response and its SHA-256 hash in the `ashmit-provenance` checkpoint. `BLOCK`, a
missing Ashmit trace, or a non-Mongo artifact reference stops Bucket and every
downstream stage.

## Local Owner Setup

Use the owner repository as a sibling checkout:

```powershell
cd ..\Ashmit-Mitra-T42\backend
docker compose --env-file .env -f docker-compose.mitra.yml up -d --build
docker compose --env-file .env -f docker-compose.mitra.yml ps
```

The owner `.env` is ignored by Git and must define nonempty
`MONGO_ROOT_USERNAME`, `MONGO_ROOT_PASSWORD`, `API_KEY`, `JWT_SECRET_KEY`,
`DATABASE_NAME`, and `ASHMIT_PORT`. The ecosystem configuration generator passes
the owner-provided Atlas application URI to Ashmit as `MONGODB_URI`. Bucket has
the separate `BUCKET_MONGODB_URI` variable and continues using the authenticated
local MongoDB service. Mitra receives only Ashmit's HTTP URL and API key and
does not connect to Atlas directly during normal execution.

The corrected owner Dockerfile uses Python 3.11, matching its Render profile
and documented Python 3.10+ requirement. Python 3.9 cannot execute the type
annotations used by the owner source.

Expected local endpoints:

```text
http://127.0.0.1:8010/health
http://127.0.0.1:8010/health/system
http://127.0.0.1:8010/docs
```

For a host-run Mitra process:

```env
MITRA_BHIV_ASHMIT_BASE_URL=http://127.0.0.1:8010
MITRA_BHIV_ASHMIT_API_KEY=<same value as Ashmit API_KEY>
```

For hosted Mitra, use Ashmit's reachable HTTPS deployment instead. A Vercel or
Render process cannot call this workstation's loopback address. Store the API
key in the host secret manager or use `MITRA_BHIV_ASHMIT_API_KEY_FILE`.

## Verified Runtime Output

On 2026-07-20, an Atlas probe executed inside the Ashmit container completed an
authenticated ping, temporary write, exact read-back, and cleanup against
`mitra_production`. Ashmit was then configured with that Atlas URI independently
from Bucket's local MongoDB connection. `GET /health/system` returned
`mongo_connected=true` and `audit_active=true` after restart.

A real Mitra execution `eco_ee8ba2cd935045b3a81b53055bb26652`
called authenticated `POST /api/mitra/evaluate`. Ashmit returned HTTP 200,
status `ALLOW`, risk `LOW`, trace `trace_e301eb88a41eaf06`, and MongoDB locator
`trace_e301eb88a41eaf06:mitra_response_contract`. An independent Atlas read-back
found that immutable record with integrity hash
`12a85e8052360c7489b9904d4dc99ac123a0b841106aad58236c9e3905c09da1`.
The API key remained inside the container and was not written to runtime output.

Before the successful probe, Atlas rejected the Docker egress address at its
network access gate. Adding the container's exact `/32` address resolved the
TLS alert; no credential change or permissive TLS option was used.

Ashmit has one startup caveat: if it starts while Atlas is unavailable, the
owner process retains that initial connection failure instead of reconnecting.
Restore Atlas reachability, then restart `ashmit`; its health gate prevents
Mitra from starting against a disconnected audit store.
