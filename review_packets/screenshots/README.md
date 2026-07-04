# Screenshot Index

This folder is the sprint-required screenshot landing point.

Copied runtime screenshots:

- `runtime-dashboard.png`
- `runtime-health.png`
- `runtime-intents.png`
- `runtime-openapi.png`

Mapped evidence for the mandatory list:

| Required screenshot | Evidence source |
|---|---|
| Application running | `runtime-dashboard.png` |
| Docker | `../TEST_PACKET.md` Docker artifact list; rerun Compose for fresh capture |
| Runtime dashboard | `runtime-dashboard.png` |
| Runtime lifecycle | `GET /api/v1/runtime/lifecycle` |
| Capability registry | `GET /api/v1/capabilities` |
| Intent registry | `runtime-intents.png` |
| Health endpoint | `runtime-health.png` |
| Metrics endpoint | `../TEST_PACKET.md` and `../../evidence/metrics-sample.prom` |
| Prometheus | `../../deploy/otel-collector-config.yaml` |
| OpenTelemetry | `../../deploy/otel-collector-config.yaml` and telemetry sample |
| Logs | `../../evidence/telemetry-sample.jsonl` |
| Database | runtime SQLite under configured data root |
| Running attached products | `../../evidence/bhiv-product-integration-report.json` |
| Execution flow | `../LIVE_RUNTIME_PACKET.md` |
| Test execution | `../TEST_PACKET.md` |
| Folder structure | repository tree and `README.md` |
