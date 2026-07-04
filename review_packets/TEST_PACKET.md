# Test Packet

## Pytest

Command:

```powershell
python -m pip install -r requirements.txt ".[test]" --target C:\tmp\companion-runtime-pytest --upgrade
$env:PYTHONPATH="C:\tmp\companion-runtime-pytest;pratham/companion-runtime;pratham/context-runtime;pratham/intent-router;pratham/session-runtime;pratham/attachment-runtime"
$env:PYTHONIOENCODING="utf-8"
python -m pytest -q
```

Result: passed.

Collected tests: 75.

New tests:

- `test_companion_message_selects_executes_and_persists_memory`
- `test_companion_message_requests_clarification_for_missing_schema_field`
- `test_companion_understands_sparse_attached_bhiv_capability`
- `test_companion_api_exposes_message_memory_task_and_stream`

## API Proof Points

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /api/v1/runtime/metrics`
- `GET /api/v1/runtime/chain`
- `POST /api/v1/companion/messages`
- `POST /api/v1/companion/messages/stream`
- `GET /api/v1/companion/sessions/{session_id}/memory`
- `GET /api/v1/companion/tasks`

## Runtime Evidence

Existing evidence remains under `evidence/`:

- runtime dashboard PNG;
- health view PNG;
- intent registry PNG;
- OpenAPI PNG;
- telemetry sample JSONL;
- metrics sample Prometheus text;
- load-testing report;
- failure-recovery report;
- BHIV product integration report.

## Docker

Docker deployment artifacts are present:

- `Dockerfile`
- `docker-compose.yml`
- `deploy/otel-collector-config.yaml`
- `deploy/production.env.example`
- `scripts/load/k6_companion_runtime.js`

The current verification pass ran pytest and contract checks. Docker Compose
was not rerun in this turn.
