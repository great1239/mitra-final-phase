# Independent Hosting

Use the deployed Vercel production host as the canonical public Mitra runtime:

```text
https://mitra-live-runtime-sprint.vercel.app
```

Ignore custom-domain binding for this sprint. The production evidence, hosted
validation, and review handoff should point to the Vercel host above.

Recommended split:

```text
https://mitra-live-runtime-sprint.vercel.app      Mitra Runtime API
Docker/Render deployment                           optional persistent profile
```

## Recommended Platform

Use Vercel for the public hosted API proof. The repo includes `vercel.json`,
`api/index.py`, and `requirements.txt` for this serverless profile.

For persistent runtime behavior, use a Docker-capable host such as Render,
Fly.io, Railway, or a VPS. The repo also includes `render.yaml` for that
alternate profile.

Current production URL:

```text
https://mitra-live-runtime-sprint.vercel.app
```

This is the alternate public host for the complete Mitra runtime system. The
main website at `https://mitra.blackholeinfiverse.com` is a separate frontend
surface and can connect to this runtime whenever required by setting its API
base/proxy to `https://mitra-live-runtime-sprint.vercel.app`.

The runtime exposes compatibility routes for that frontend:

```text
POST /api/companion/chat
GET  /api/companion/greeting/{user_id}
GET  /api/companion/memory/{user_id}
GET  /api/companion/capabilities
POST /api/workflow/run
```

Those routes preserve the existing companion contract. The final strict
cross-owner flow is `POST /api/v1/ecosystem/execute`; the frontend can call it
directly or proxy it under its own API when full TANTRA convergence is needed.

Default hosted runtime variable:

```text
MITRA_HOSTED_RUNTIME_URL=https://mitra-live-runtime-sprint.vercel.app
```

Override `MITRA_HOSTED_RUNTIME_URL` only when deliberately validating a new
alternate deployment.

## Deploy With Vercel

Use team id:

```text
team_ciZh4E8ZRzVl7Gxnwl5y5Wbq
```

Command:

```powershell
pnpm dlx vercel@latest deploy --prod --scope team_ciZh4E8ZRzVl7Gxnwl5y5Wbq
```

Confirm these endpoints:

```text
/health
/ready
/metrics
/docs
/api/v1/runtime/status
/api/v1/runtime/integrations
/api/v1/ecosystem/readiness
/api/v1/ecosystem/contracts
/api/v1/dispatches
```

Run hosted validation:

```powershell
python scripts/validate_hosted_runtime.py
```

## Required Environment Variables

Minimum:

```text
MITRA_COMPANION_DATA_ROOT=/data
MITRA_COMPANION_DATABASE_PATH=/data/companion-runtime.db
MITRA_COMPANION_MANIFEST_DIRECTORY=/app/contracts/production
MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS=false
MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS=false
MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS=false
MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS=false
MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS=true
MITRA_COMPANION_ENVIRONMENT=production
MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true
```

`contracts/examples` is excluded from hosted startup. The dashboard should
show no attached products until a real module connects through
`POST /api/v1/products/connect` or an approved manifest is added under
`contracts/production`.

Required for live `POST /api/v1/ecosystem/execute` acceptance:

```text
MITRA_RAJ_WORKFLOW_BASE_URL
MITRA_RAJ_API_KEY
MITRA_BHIV_ASHMIT_BASE_URL
MITRA_BHIV_BUCKET_BASE_URL
MITRA_BHIV_INSIGHTFLOW_INGEST_URL
MITRA_BHIV_INSIGHTFLOW_API_KEY
MITRA_BHIV_KARMA_BASE_URL
MITRA_BHIV_PRANA_BASE_URL
MITRA_BHIV_BUCKET_PARENT_HASH
MITRA_BHIV_KARMA_PREVIOUS_HASH
MITRA_ECOSYSTEM_TIMEOUT_SECONDS
```

## Evidence Boundary

Local evidence remains valid for reproducibility. Hosted evidence is complete
after `scripts/validate_hosted_runtime.py` succeeds against
`https://mitra-live-runtime-sprint.vercel.app` and screenshots/logs are
captured from that deployed service.

See `docs/VERCEL_DEPLOYMENT.md` for the serverless-runtime caveat.
