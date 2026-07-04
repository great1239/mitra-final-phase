# Ecosystem Runtime Hardening Package

This folder compiles the files associated with the Pratham ecosystem runtime
integration and production hardening task.

## Scope

- Runtime: Mitra Companion Runtime
- Integrated BHIV products:
  - `uniguru_ai`
  - `trade-bot-main`
- Validation status:
  - Focused BHIV and hardening suite: `6 passed`
  - Full repository suite: `65 passed`

## Included Runtime Files

- `README.md`
- `REVIEW_PACKET.md`
- `contracts/api/companion-runtime.openapi.yaml`
- `contracts/integration-contracts.json`
- `contracts/examples/product-uniguru-runtime.json`
- `contracts/examples/product-trade-bot-main.json`
- `docs/BHIV_PRODUCT_INTEGRATION.md`
- `docs/PRODUCTION_HARDENING.md`
- `evidence/README.md`
- `evidence/bhiv-product-integration-report.json`
- `evidence/failure-recovery-report.md`
- `evidence/load-testing-report.md`
- `evidence/metrics-sample.prom`
- `evidence/telemetry-sample.jsonl`
- `pratham/companion-runtime/mitra_companion/api.py`
- `pratham/companion-runtime/mitra_companion/config.py`
- `pratham/companion-runtime/mitra_companion/interfaces.py`
- `pratham/companion-runtime/mitra_companion/runtime.py`
- `pratham/companion-runtime/mitra_companion/telemetry.py`
- `pratham/companion-runtime/mitra_companion/transport.py`
- `pratham/tests/conftest.py`
- `pratham/tests/test_bhiv_product_integration.py`
- `pratham/tests/test_phase5_integration_contracts.py`
- `pratham/tests/test_production_hardening.py`

## Included Product Source References

These are copied for review context only. The runtime integration remains
contract-first through manifests and generic adapters.

- `source-products/uniguru_ai/uniguru_v2-main-main/backend/service/uniguru_runtime_api.py`
- `source-products/uniguru_ai/backend/service/api.py`
- `source-products/trade-bot-main/backend/api_server.py`
- `source-products/trade-bot-main/backend/core/mcp_adapter.py`

## Notes

The package is a copied review bundle. The active implementation remains in the
original repository paths.
