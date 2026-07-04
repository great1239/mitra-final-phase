# Failure And Recovery Report

## Scenario

A remote product publishes a manifest with `health_endpoint: /health`. The
dispatch endpoint first returns `503`, then the health endpoint later returns
`200`.

## Runtime Behavior

1. The failed dispatch is persisted with status `FAILED`.
2. Only the affected product attachment is marked `DEGRADED`.
3. Runtime lifecycle moves to `DEGRADED`.
4. A failing health check records `attachment.health_checked` and a recovery
   validation with `recovered: false`.
5. A later healthy check revalidates the original published manifest and restores
   the attachment to `ATTACHED`.
6. A follow-up dispatch completes successfully.

## Metrics Verified

| Metric | Expected |
| --- | --- |
| `dispatch_failed_total` | `1` |
| `recovery_success_total` | `1` |
| `attachment_health_checks_total` | at least `2` |

Verification test:
`pratham/tests/test_production_hardening.py::test_attachment_health_monitoring_and_recovery_validation`.
