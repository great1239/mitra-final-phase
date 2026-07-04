# Load Testing Report

## Scenario

The focused hardening test runs 30 concurrent dispatches across the two selected
BHIV products:

- 15 UniGuru AI `uniguru.execute-query` dispatches;
- 15 Trade Bot Main `tradebot.predict` dispatches.

The test uses the same published manifests and generic HTTP transport path used
by normal runtime dispatch. Product endpoints are mocked to keep the validation
deterministic and independent from local product server availability.

## Result

| Check | Result |
| --- | --- |
| Concurrent dispatches | 30 |
| Completed dispatches | 30 |
| Failed dispatches | 0 |
| Runtime dispatch receipts | 30 |
| Per-product latency metrics | populated for `uniguru-ai` and `trade-bot-main` |
| Structured telemetry | `dispatch.completed` events emitted to JSONL |

Verification test:
`pratham/tests/test_production_hardening.py::test_bhiv_dispatch_concurrency_metrics_and_structured_log`.
