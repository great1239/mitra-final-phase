# Production Hardening

This document lists the production controls that matter for review. Detailed
endpoint behavior is in OpenAPI and the integration guide.

## Controls

| Area | Runtime support |
| --- | --- |
| Deployment | Docker Compose runs `mitra-companion serve` with Uvicorn workers, proxy headers, `/ready`, and production env values. |
| Container posture | Non-root user, read-only filesystem, explicit `/data` and `/tmp`, dropped capabilities, resource limits, and restart policy. |
| Persistent process | `RuntimeStartupManager` starts the service and `PersistentRuntimeSupervisor` keeps heartbeats fresh, cleans stale peers, and recovers interrupted tasks. |
| Multi-instance runtime | Runtime instances register unique IDs and share durable sessions, attachments, routes, exchanges, and dispatches through storage. |
| Attached-product information sharing | Connected products use `/api/v1/product-exchanges` and `/api/v1/products/{product_id}/exchange-inbox` as a durable mailbox with acknowledgement state. |
| Product-to-product exchange | `ProductExchangeRequest`, `ProductExchangeAckRequest`, `product_exchanges`, `product_exchange_targets`, `/api/v1/product-exchanges`, `/api/v1/products/{product_id}/exchange-inbox`, `test_product_exchange_api_contract`. |
| Restart and recovery | `/api/v1/runtime/restart`, `/api/v1/runtime/recovery`, and `/api/v1/runtime/instances/reconcile`. |
| Config and secrets | `MITRA_COMPANION_ENV_FILE`, mounted `*_FILE` secrets, redacted `/api/v1/runtime/config`, and redacted `/api/v1/runtime/secrets`. |
| Observability | JSONL telemetry, JSONL production process logs, `/metrics`, `/api/v1/runtime/metrics`, and OpenTelemetry spans. |
| Product containment | Transport failure degrades only the affected attachment; healthy checks restore it. |
| Prior-runtime reuse | Source-scope catalog, capability catalog, semantic dependency checks, phase journals, and dispatch proof bundles. |

## Evidence

- `test_product_exchange_runtime_persists_inbox_and_acknowledgement`
- `test_product_exchange_api_contract`
- `test_multiple_runtime_instances_share_state_routes_and_dispatch`
- `test_persistent_runtime_supervisor_refreshes_heartbeat`
- `test_persistent_runtime_marks_stale_peer_instances`
- `test_persistent_runtime_recovers_interrupted_tasks_on_restart`
- `test_production_configuration_loads_env_file_and_secret_files`
- `test_runtime_operations_api_exposes_production_mode`
- `test_production_logging_writes_process_events`
- `test_production_readiness_gate.py`

Run:

```powershell
pytest
python scripts/production_readiness_gate.py
```

## Boundary

The runtime keeps product logic out of Mitra. Products connect by manifest,
share only explicit exchange payloads, and execute through their own declared
transport endpoints.
