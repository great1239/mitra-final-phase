# Vercel Deployment

This profile publishes the Mitra runtime independently on Vercel. The current
production deployment is live at:

```text
https://mitra-live-runtime-sprint.vercel.app
```

Use this Vercel URL for public review access and hosted validation. It is not a
production-certified runtime while the deployment parity gate is blocked.

## Team

```text
team_ciZh4E8ZRzVl7Gxnwl5y5Wbq
```

## Deployment Profile

Files:

- `api/index.py`
- `vercel.json`
- `requirements.txt`

This is a Vercel serverless profile backed by shared managed PostgreSQL.
Runtime state, checkpoints, leases, replay packages, and depository lineage use
`MITRA_COMPANION_DATABASE_URL`; `/tmp` is limited to process-local logs and a
non-active SQLite fallback path. The database URL is a sensitive Vercel
environment variable and is never committed or returned by runtime APIs.

The profile sets persistent storage and supervisor mode, and
`MITRA_COMPANION_REQUIRE_DURABLE_RUNTIME=true` verifies that Vercel cannot pass
the gate without the external PostgreSQL backend. A cold start creates a new
runtime instance against the same state and can resume incomplete checkpoints.
Vercel can still suspend compute between requests, so periodic background work
is opportunistic on this host. Use a continuously resident Docker/Render
runtime when strict wall-clock scheduling is required.

## Upload

With a valid Vercel login or `VERCEL_TOKEN`:

```powershell
pnpm dlx vercel@latest deploy --prod --scope team_ciZh4E8ZRzVl7Gxnwl5y5Wbq
```

If the project has not been linked before, choose:

```text
Project name: mitra-runtime-api
Framework: Other
Build/output settings: use vercel.json
```

After deployment:

```powershell
python scripts/validate_hosted_runtime.py
python scripts/validate_ecosystem_runtime.py https://mitra-live-runtime-sprint.vercel.app --summary
```

The validators exit nonzero when deployment parity, ecosystem configuration,
owner calls, dispatch output, or deterministic reconstruction is incomplete.
See `docs/DEPLOYMENT_PARITY.md`.
