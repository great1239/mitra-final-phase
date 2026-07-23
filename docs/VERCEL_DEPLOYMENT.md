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

This is a Vercel serverless profile. It is suitable for public hosted API
proof, dashboard/OpenAPI checks, and review access. It is not equivalent to the
Docker persistent runtime profile because Vercel functions use ephemeral local
storage under `/tmp`.

The Vercel profile deliberately sets
`MITRA_COMPANION_REQUIRE_DURABLE_RUNTIME=true` while identifying its storage as
`ephemeral`. Consequently, `/ready` returns HTTP 503 instead of allowing a
publicly reachable dashboard to be mistaken for production readiness. For
long-duration validation, persistent SQLite, and supervisor behavior, use the
Docker/Render profile or externalize the runtime store.

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
