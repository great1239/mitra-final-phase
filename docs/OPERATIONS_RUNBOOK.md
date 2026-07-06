# Operations Runbook

## Deploy

```powershell
docker compose up -d --wait
```

Then check:

```powershell
curl http://127.0.0.1:8090/ready
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8090/api/v1/runtime/startup
curl http://127.0.0.1:8090/api/v1/runtime/status
curl http://127.0.0.1:8090/metrics
```

## Monitor

- `/ready` returns HTTP 200.
- `/api/v1/runtime/status` reports `runtime_mode: persistent`.
- `persistent_runtime.supervisor_running` is `true`.
- `/api/v1/runtime/instances` has recent `last_heartbeat_at` values.
- `/api/v1/runtime/config` and `/api/v1/runtime/secrets` stay redacted.
- Dispatch failure and latency remain inside `docs/SLO_AND_CAPACITY.md`.

## Failure Response

1. Check `/api/v1/runtime/status`.
2. Check `/api/v1/runtime/telemetry` for `dispatch.failed`.
3. Run product health checks with `/api/v1/attachments/{product_id}/health`.
4. Keep unaffected products online.
5. Re-run health after product recovery and confirm `ATTACHED`.

## Restart Validation

Operator restart:

```powershell
curl -X POST http://127.0.0.1:8090/api/v1/runtime/restart `
  -H "Content-Type: application/json" `
  -d "{\"schema_version\":\"1.0.0\",\"contract_version\":\"1.0.0\",\"runtime_version\":\"1.0.0\",\"compatibility_version\":\"mitra-companion-1\"}"
```

Validate `/ready`, `/api/v1/runtime/startup`, attachments, sessions, routes,
and a fresh dispatch receipt.

## Recovery And Instance Reconciliation

```powershell
curl -X POST http://127.0.0.1:8090/api/v1/runtime/recovery `
  -H "Content-Type: application/json" `
  -d "{\"schema_version\":\"1.0.0\",\"contract_version\":\"1.0.0\",\"runtime_version\":\"1.0.0\",\"compatibility_version\":\"mitra-companion-1\"}"

curl -X POST http://127.0.0.1:8090/api/v1/runtime/instances/reconcile `
  -H "Content-Type: application/json" `
  -d "{\"schema_version\":\"1.0.0\",\"contract_version\":\"1.0.0\",\"runtime_version\":\"1.0.0\",\"compatibility_version\":\"mitra-companion-1\"}"
```

Use this after a process crash, stale peer, or interrupted task.

## Multi-Instance Validation

Run two processes against the same database and manifest directory. Validate:

- each process has a unique runtime instance ID;
- `/api/v1/runtime/instances` lists both active instances;
- one instance can read sessions and attachments created by the other;
- stale peers stop appearing after the stale heartbeat window.

## Rollback

1. Stop traffic at the edge.
2. Preserve `/data`.
3. Deploy the previous image or revision.
4. Re-run `/ready`, `/health`, `/metrics`, and one dispatch.
5. Re-enable traffic.
