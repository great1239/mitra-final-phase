# Phase 3 Production Deployment

Generated: 2026-07-08T18:37:10Z

## Live Deployment

- Production URL: <https://mitra-live-runtime-sprint.vercel.app>
- Vercel deployment id: `dpl_AtXQK9F5wn6BXe9tto3sm7tVFG5c`
- Production deployment URL: <https://mitra-live-runtime-sprint-j3ya00fct-bhiv-intern.vercel.app>
- Vercel target: `production`
- Vercel status: `Ready`
- Runtime service: `services/mitra-runtime-api/index`
- Hosting team: `team_ciZh4E8ZRzVl7Gxnwl5y5Wbq`

The deploy was built by Vercel in a clean remote build environment and exposed
as a production FastAPI service.

## Runtime Validation

This historical validation used a validator-created `echo-lab` loopback
fixture. It is retained for traceability, but it is superseded by the
production manifest policy added after review: hosted production no longer
loads or creates example, simulated, loopback, or localhost manifests by
default.

The older validator executed 22 live HTTPS calls against the hosted runtime and
confirmed the following surfaces for that revision:

- live runtime
- HTTPS
- API
- dashboard
- OpenAPI
- routing
- attachments
- health
- metrics
- telemetry
- replay reconstruction
- recovery

The superseded validation flow used the public runtime API to:

1. Load dashboard, health, readiness, metrics, OpenAPI, telemetry, integration,
   and depository endpoints.
2. Create or confirm the `echo-lab` fixture attachment.
3. Create a validation session.
4. Dispatch `echo.repeat` through the intent router.
5. Read dispatch reconstruction, proof, and phase journal artifacts.
6. Run attachment health and runtime recovery endpoints.
7. Re-read dashboard, telemetry, and metrics after execution.

Current production validation must use
`scripts/validate_hosted_runtime.py`, which dispatches only when a real
non-fixture product is already attached. If no real product target is
available, routing and replay are reported as blocked rather than simulated.

## Canonical Host Decision

Use the Vercel production host for this sprint:

```text
https://mitra-live-runtime-sprint.vercel.app
```

Ignore custom-domain binding for this sprint. All production validation,
runtime validation, reviewer links, and handoff documentation should use the
Vercel host above unless a new host is explicitly requested.
