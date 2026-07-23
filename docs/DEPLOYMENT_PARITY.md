# Deployment Parity

Mitra treats local execution and production acceptance as separate facts. A
successful Docker run does not make a hosted deployment ready.

## Enforced Gate

Production profiles set:

```text
MITRA_COMPANION_REQUIRE_ECOSYSTEM_READY=true
MITRA_COMPANION_REQUIRE_PUBLIC_OWNER_ENDPOINTS=true
MITRA_COMPANION_REQUIRE_DURABLE_RUNTIME=true
MITRA_COMPANION_RELEASE_REVISION=<deployed commit SHA>
```

`GET /api/v1/runtime/deployment-parity` reports the resulting checks without
returning credentials. `GET /ready` returns HTTP 503 when any enforced check
fails. `GET /health` remains a liveness endpoint, but its response reports
`status=degraded` and includes the blocking issue codes.

The gate rejects:

- missing Raj, Ashmit, Bucket, KESHAV, Karma, PRANA, InsightFlow, or Central
  Depository configuration;
- an Ashmit URL without its required API key;
- loopback, private, unqualified, Docker-only, or non-HTTPS owner endpoints in
  a public-host profile;
- simulated, example, loopback, or localhost product manifests;
- an unavailable production manifest directory;
- ephemeral storage or a disabled persistent supervisor when durable runtime
  state is required.

## Platform Profiles

The complete Docker ecosystem uses internal service DNS and a persistent
volume. It therefore requires ecosystem and durable-runtime readiness but does
not require public HTTPS between containers.

The Vercel profile uses `/tmp` and cannot provide durable runtime SQLite or a
continuous supervisor. It is intentionally marked `ephemeral` while the
durable-runtime requirement remains enabled. It must not pass production
readiness until Mitra is moved to a persistent host or its runtime store is
externalized. Public dashboard availability is not production certification.

## Reproducible Validation

Run the same behavior checks against the actual target:

```powershell
python scripts/validate_hosted_runtime.py https://mitra-live-runtime-sprint.vercel.app --summary
python scripts/validate_ecosystem_runtime.py https://mitra-live-runtime-sprint.vercel.app --summary
```

Set `MITRA_EXPECTED_RELEASE_REVISION` to the commit SHA expected in production.
The hosted validator then rejects a stale deployment even when its endpoints
otherwise respond.

The GitHub workflow `.github/workflows/deployment-parity.yml` runs regression
tests for repository changes and runs both hosted validators after a successful
deployment, on demand, and daily. A release is operationally accepted only
when the hosted workflow passes.

## Promotion Checklist

1. Deploy the exact reviewed commit.
2. Configure every owner contract as a deployment secret or environment value.
3. Use persistent runtime storage.
4. Confirm `/ready` returns HTTP 200.
5. Confirm deployment parity and ecosystem readiness both report `ready=true`.
6. Execute the canonical hosted workflow and deterministic replay validators.
7. Promote only the deployment that produced those responses.
