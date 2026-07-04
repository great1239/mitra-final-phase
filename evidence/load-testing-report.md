# Load Testing Report

## Scenario

The focused hardening test runs 30 concurrent dispatches across the two selected
BHIV products:

- 15 UniGuru backward integration `uniguru.execute-query` dispatches;
- 15 Samruddhi forward integration `tradebot.predict` dispatches.

The test uses the same published manifests and generic HTTP transport path used
by normal runtime dispatch. Product endpoints are mocked to keep the validation
deterministic and independent from local product server availability.

The production load profile is also captured as k6 in
`scripts/load/k6_companion_runtime.js`. It attaches the UniGuru and Samruddhi
manifests, creates product-scoped sessions, loads context, alternates dispatches
between `uniguru.execute-query` and `tradebot.predict`, and enforces failure,
latency, and check-rate thresholds.

## Result

| Check | Result |
| --- | --- |
| Concurrent dispatches | 30 |
| Completed dispatches | 30 |
| Failed dispatches | 0 |
| Runtime dispatch receipts | 30 |
| Per-product latency metrics | populated for `uniguru-ai` and `trade-bot-main` |
| Structured telemetry | `dispatch.completed` events emitted to JSONL |
| k6 production profile | `ramping-vus` scenario with `http_req_failed`, `http_req_duration`, and `checks` thresholds |

Verification test:
`pratham/tests/test_production_hardening.py::test_bhiv_dispatch_concurrency_metrics_and_structured_log`.

Production k6 command:

```powershell
k6 run scripts/load/k6_companion_runtime.js
```
