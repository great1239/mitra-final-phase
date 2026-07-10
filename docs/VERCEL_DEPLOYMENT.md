# Vercel Deployment

This profile publishes the Mitra runtime independently on Vercel. The current
production deployment is live at:

```text
https://mitra-live-runtime-sprint.vercel.app
```

Use this Vercel URL as the canonical hosted runtime for production validation
and review handoff. Ignore custom-domain binding for this sprint.

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

For long-duration validation, persistent SQLite, and supervisor behavior, use
the Docker/Render profile.

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
```

The validator prints each request and response check and exits nonzero if the
hosted dispatch output or deterministic reconstruction does not match the
submitted payload.
