# Testing Evidence

Execution date: `2026-07-09`

This packet records observed runtime outputs. It is not produced by an
evidence generator. Every result below comes from an install, test process,
HTTP request, or load process that was actually executed.

## Clean Deployment

**Result:** PASS for clean Python deployment and Docker Compose deployment.

The final source was built and installed into a new virtual environment:

```powershell
python -m venv C:\tmp\mitra-testing-optimized-20260709
C:\tmp\mitra-testing-optimized-20260709\Scripts\python.exe -m pip install ".[test]"
```

Observed wheel:

```text
mitra_companion_runtime-1.0.0-py3-none-any.whl
sha256=f40744881083d7b18398d31810112a45f2490ed6771306466cfef6956d27e5af
```

Final installed CLI validation used a brand-new data root:

```json
{
  "valid": true,
  "database_path": "C:\\tmp\\mitra-clean-validation-final-20260709\\runtime.db",
  "data_root": "C:\\tmp\\mitra-clean-validation-final-20260709"
}
```

Docker was rechecked and repaired on `2026-07-10`. The earlier Docker Desktop
engine/socket failure no longer blocks deployment.

Observed Docker repair and deployment path:

```text
docker desktop status: running
wsl docker-desktop state: Running
docker compose config --quiet: passed
docker compose build --pull --progress plain: built
docker compose up -d --force-recreate --wait --wait-timeout 180: healthy
```

The Compose issue exposed after Docker Desktop recovered was fixed by replacing
invalid top-level `pids_limit` keys with Compose v5-compatible
`deploy.resources.limits.pids` values, and by using one Uvicorn worker per
SQLite-backed container. After recreation:

```text
companion-runtime: Up, healthy, port 8090
otel-collector: Up, port 4318 and 8889
```

Runtime API checks from the Docker deployment:

```json
{
  "ready": true,
  "health_status": "healthy",
  "state": "READY",
  "accepting": true,
  "uvicorn_workers": 1,
  "manifest_directory": "/app/contracts/production",
  "attached_products": 0,
  "container_validate": {
    "valid": true,
    "database_path": "/data/companion-runtime.db",
    "data_root": "/data"
  }
}
```

## Replay Validation

**Result:** PASS.

After sustained load, the latest real dispatch was reconstructed through:

```http
GET /api/v1/dispatches/dsp_56c275785d2f4a43b01ba288f2d81acc/reconstruction
```

Observed output:

```json
{
  "dispatch_status": "COMPLETED",
  "replay_status": "verified",
  "deterministic": true,
  "replay_type": "mitra-true-deterministic-replay-v1",
  "verification_checks": 32,
  "failed_checks": 0,
  "input_message": "k6 runtime load 1-85",
  "output_message": "k6 runtime load 1-85"
}
```

All nine scopes were `true`: lifecycle, sessions, routing, attachments,
context, dispatch, telemetry, recovery, and failures.

## Production Validation

**Result:** PASS for runtime execution; external remote-product health remains
environment-dependent.

The final complete test suite executed from the isolated installation:

```text
104 passed
1 StarletteDeprecationWarning
```

After stress and acceptance load runs, the clean local runtime reported:

```json
{
  "accepting": true,
  "dispatches": 502,
  "failed_dispatches": 0,
  "dispatch_completed_total": 502,
  "dispatch_failed_total": 0
}
```

The aggregate health state became `DEGRADED` because the earlier local run
used the example manifest directory, including local product endpoints that
were not running. That fixture profile is no longer accepted as a production
bootstrap source. Production now uses `contracts/production` and rejects
example, simulated, loopback, and localhost manifests by default.

## Failover Validation

**Result:** PASS.

Focused tests executed two runtime instances against shared state, dispatched
through the second instance, stopped the first instance, and completed another
dispatch through the survivor. A separate stale-peer test allowed a peer
heartbeat to expire and verified that it was moved to `STOPPED`.

```text
test_multiple_runtime_instances_share_state_routes_and_dispatch PASSED
test_persistent_runtime_marks_stale_peer_instances PASSED
```

The real-process failover capture is
`review_packets/screenshots/failover.jpg`.

## Recovery Validation

**Result:** PASS.

The recovery test received an unhealthy product response, persisted a failed
dispatch, moved the attachment to `DEGRADED`, restored the fixture, returned
the attachment to `ATTACHED`, and completed a new dispatch. The interrupted
task test restarted a runtime and converted an orphaned `RUNNING` task to a
terminal recovered failure.

```text
test_attachment_health_monitoring_and_recovery_validation PASSED
test_persistent_runtime_recovers_interrupted_tasks_on_restart PASSED
```

Live operator recovery after load returned:

```json
{
  "http_status": 200,
  "recovery_status": "recovered",
  "completed_at": "2026-07-09T13:13:04.164476+00:00",
  "stale_instances": 0,
  "recovered_tasks": 0
}
```

## Load Testing

**Result:** PASS at the tested 5-VU sustained envelope. CAPACITY LIMIT observed
at 15 VUs.

The test used real HTTP requests, sessions, dispatch receipts, and
input/output equality checks for two minutes against the local runtime load
profile. It is a runtime capacity test, not proof that an external BHIV
product consumed the request.

Passing command:

```powershell
$env:BASE_URL="http://127.0.0.1:8094"
$env:PROFILE="runtime"
$env:MAX_VUS="5"
k6 run scripts/load/k6_companion_runtime.js
```

Passing result:

```text
max VUs:             5
iterations:          210
HTTP requests:       213
checks:              633/633 passed
HTTP failures:       0.00%
average latency:     434.80 ms
p90 latency:         653.00 ms
p95 latency:         803.92 ms
maximum latency:     1.28 s
threshold result:    PASS
```

The unchanged 15-VU stress ceiling returned 0% HTTP failures and 879/879
successful checks, but p95 was `3.74s`, exceeding the `1.5s` SLO. This is the
current verified capacity boundary for the SQLite deployment, not a passing
production claim.

Load discovery led to two runtime changes: replay components are now written
in one transaction, and replay snapshots contain dispatch-scoped state instead
of an expanding copy of unrelated runtime history.

## Hosted Runtime Validation

**Result:** READ-SURFACE PASS; ROUTING/REPLAY REQUIRES REAL ATTACHED PRODUCT.

Observed against
`https://mitra-live-runtime-sprint.vercel.app` at
`2026-07-09T12:44:11Z` before the production manifest-policy correction:

```json
{
  "passed": "superseded",
  "request_count": 22,
  "failed_results": [],
  "https": true,
  "api": true,
  "dashboard": true,
  "openapi": true,
  "routing": true,
  "attachments": true,
  "health": true,
  "metrics": true,
  "telemetry": true,
  "replay": true,
  "recovery": true
}
```

That prior run used a validator-created Echo Lab loopback fixture and is no
longer treated as production routing/replay evidence. The validator now
discovers an already attached real product and ignores example, simulated,
loopback, and localhost manifests. If no real product is attached, it reports
routing and replay as blocked instead of creating fixture data. The public host
uses ephemeral Vercel storage, so it also does not prove durable
multi-instance continuity.

Corrected validation after redeploy at `2026-07-10T07:24:13Z`:

```json
{
  "passed": false,
  "request_count": 16,
  "failed_results": [
    {
      "name": "validation-target",
      "http_status": null,
      "error": "no real attached product was available; examples, simulated manifests, loopback dispatches, and localhost manifests are ignored"
    }
  ],
  "https": true,
  "api": true,
  "dashboard": true,
  "openapi": true,
  "attachments": true,
  "health": true,
  "metrics": true,
  "telemetry": true,
  "recovery": true,
  "routing": false,
  "replay": false
}
```

## Integration Validation

**Result:** PASS for published-contract interoperability. Live external
acceptance remains unproven where endpoint credentials were unavailable.

Twelve focused tests passed in `30.01s`. They verified:

- every catalog operation declares a response contract;
- every test/documentation manifest publishes response schemas;
- Ashmit, Bucket, InsightFlow, Karma, PRANA, and Central Depository responses
  are captured;
- PRANA strict forwarding preserves exact Karma-accepted bytes;
- PRANA forwarding is suppressed after Karma rejection;
- cross-product context transfer and dispatch complete through published
  manifests.

No test imports downstream product business logic. Controlled transports
implement the published HTTP contracts; they do not claim live external
deployment consumption.

## Verification Commands

```powershell
python -m pytest -q
python scripts/production_readiness_gate.py
python scripts/validate_hosted_runtime.py --summary
$env:MAX_VUS="5"; k6 run scripts/load/k6_companion_runtime.js
```
