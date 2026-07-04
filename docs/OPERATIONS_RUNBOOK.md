# Operations Runbook

This runbook is for operating the Mitra Companion Runtime as a production
service consumed by BHIV products through published contracts.

## Deploy

1. Review `deploy/production.env.example` and set environment values for the
   target environment.
2. Start the runtime and collector:

```powershell
docker compose up -d --wait
```

3. Confirm readiness:

```powershell
curl http://127.0.0.1:8090/ready
curl http://127.0.0.1:8090/health
```

4. Confirm observability:

```powershell
curl http://127.0.0.1:8090/metrics
curl http://127.0.0.1:8090/api/v1/runtime/status
curl http://127.0.0.1:8889/metrics
```

## Validate Before Release

```powershell
python scripts/production_readiness_gate.py
pytest -q
k6 run scripts/load/k6_companion_runtime.js
```

Release is blocked if any of these fail.

## Monitor

Primary signals:

- `/ready` must return HTTP 200.
- `/api/v1/runtime/instances` should show every active runtime process or
  container with a recent `last_heartbeat_at`.
- `mitra_dispatch_failed_total` should stay within the SLO budget.
- `mitra_dispatch_latency_ms_avg` and per-product latency must remain below
  the target in `docs/SLO_AND_CAPACITY.md`.
- `attachment.health_checked` and `attachment.recovery_validated` events must
  appear after health probes.
- OpenTelemetry traces must include `mitra.dispatch` and
  `mitra.attachment_health_check` spans.

## Failure Response

1. Check `/api/v1/runtime/status` for lifecycle state and attached products.
2. Check `/api/v1/runtime/telemetry` for `dispatch.failed` events.
3. Run `POST /api/v1/attachments/{product_id}/health` for the affected product.
4. If only one product is degraded, keep other products online; the runtime
   contains failure to the affected attachment.
5. After the product health endpoint recovers, run the attachment health check
   again and confirm the attachment returns to `ATTACHED`.

## Restart Validation

Restart the runtime service, then verify:

- `/ready` returns HTTP 200.
- `/api/v1/attachments` still contains the attached product manifests.
- product-scoped sessions and deterministic routes are preserved.
- a dispatch receipt is persisted for the next successful dispatch.

The automated coverage for this is
`test_runtime_restart_preserves_bhiv_attachments_sessions_and_routes`.

## Multi-Instance Validation

Run at least two runtime processes against the same configured database path
and manifest directory. Each process should either leave
`MITRA_COMPANION_INSTANCE_ID` unset so a unique value is generated, or receive a
unique explicit value from the orchestrator.

Validate:

- `/api/v1/runtime/instances` lists both active runtime instances.
- a session created through one instance can be read and dispatched through the
  other instance.
- stopping one instance does not stop dispatch on the survivor.

The automated coverage for this is
`test_multiple_runtime_instances_share_state_routes_and_dispatch`.

## Rollback

1. Stop accepting new runtime traffic at the edge/load balancer.
2. Preserve the `/data` volume.
3. Redeploy the previous image or repository revision.
4. Run `/ready`, `/health`, `/metrics`, and one contract dispatch.
5. Re-enable traffic only after the readiness and dispatch checks pass.
