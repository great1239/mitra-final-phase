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

For a clean rebuild use `docs/HANDOVER.md`. Do not delete the production data
volume during a routine redeploy.

### SQLite Durability

`MITRA_COMPANION_SQLITE_SYNCHRONOUS` accepts `EXTRA`, `FULL`, or `NORMAL`.
The code default is `FULL`. The Docker production profile uses `NORMAL` with
WAL for sustained throughput; transactions remain atomic and the database
remains consistent, but an operating-system or power failure can lose the
newest committed WAL records. Use `FULL` or `EXTRA` when local tail durability
is more important than dispatch latency.

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

Run two processes on the same durable host against the same SQLite database
and manifest directory. Validate:

- each process has a unique runtime instance ID;
- `/api/v1/runtime/instances` lists both active instances;
- one instance can read sessions and attachments created by the other;
- stale peers stop appearing after the stale heartbeat window.

Every process needs a unique `MITRA_COMPANION_INSTANCE_ID` unless generated
automatically. Do not place SQLite on an unsupported distributed network
filesystem; use one durable host or replace the storage adapter before
cross-host scaling.

## Backup And Restore

1. Stop writes or stop the runtime cleanly.
2. Preserve the SQLite database, telemetry log, production log, environment
   configuration, secrets references, and manifest set.
3. Record the deployed image or commit.
4. Restore those files to the same configured paths.
5. Start one instance and verify readiness, sessions, attachments, routes,
   reconstruction, and a subject-filtered depository export.
6. Start additional instances only after the first instance is healthy.

The database is the durable source for runtime state. Screenshots and generated
reports are not backups.

## Central Depository Transfer

For an accepted dispatch, retrieve the dispatch response, deterministic
reconstruction, and subject-filtered depository export. Verify hashes and
lineage using `docs/CENTRAL_DEPOSITORY_HANDOVER.md`.

## Rollback

1. Stop traffic at the edge.
2. Preserve `/data`.
3. Deploy the previous image or revision.
4. Re-run `/ready`, `/health`, `/metrics`, and one dispatch.
5. Re-enable traffic.

After rollback, do not claim recovery until one real dispatch returns the
expected output and its reconstruction verifies.
