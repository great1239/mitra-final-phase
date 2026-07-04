from __future__ import annotations

import json
import threading
from pathlib import Path
from statistics import mean
from typing import Any

from .utils import utc_now


class RuntimeTelemetry:
    """Structured operational telemetry and in-process runtime metrics."""

    def __init__(
        self,
        log_path: Path | None = None,
        *,
        service_name: str = "mitra-companion-runtime",
        environment: str = "production",
        runtime_instance_id: str = "runtime-local",
    ):
        self.log_path = Path(log_path) if log_path is not None else None
        self.service_name = service_name
        self.environment = environment
        self.runtime_instance_id = runtime_instance_id
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._counters: dict[str, int] = {
            "runtime_events_total": 0,
            "dispatch_total": 0,
            "dispatch_completed_total": 0,
            "dispatch_failed_total": 0,
            "attachment_health_checks_total": 0,
            "attachment_health_failures_total": 0,
            "recovery_validations_total": 0,
            "recovery_success_total": 0,
        }
        self._latencies_ms: list[float] = []
        self._latencies_by_product: dict[str, list[float]] = {}
        self._last_attachment_health: dict[str, dict[str, Any]] = {}

    def record_event(
        self,
        event_type: str,
        *,
        severity: str = "info",
        **fields: Any,
    ) -> dict[str, Any]:
        event = {
            "timestamp": utc_now(),
            "service": self.service_name,
            "environment": self.environment,
            "runtime_instance_id": self.runtime_instance_id,
            "event_type": event_type,
            "severity": severity,
            **fields,
        }
        with self._lock:
            self._events.append(event)
            self._events = self._events[-500:]
            self._counters["runtime_events_total"] += 1
            if self.log_path is not None:
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            event,
                            sort_keys=True,
                            ensure_ascii=True,
                        )
                        + "\n"
                    )
        return event

    def record_dispatch(
        self,
        *,
        product_id: str,
        capability_id: str,
        intent_id: str,
        dispatch_id: str,
        status: str,
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        succeeded = status == "COMPLETED"
        with self._lock:
            self._counters["dispatch_total"] += 1
            if succeeded:
                self._counters["dispatch_completed_total"] += 1
            else:
                self._counters["dispatch_failed_total"] += 1
            self._latencies_ms.append(latency_ms)
            self._latencies_by_product.setdefault(product_id, []).append(
                latency_ms
            )
        self.record_event(
            "dispatch.completed" if succeeded else "dispatch.failed",
            severity="info" if succeeded else "error",
            product_id=product_id,
            capability_id=capability_id,
            intent_id=intent_id,
            dispatch_id=dispatch_id,
            status=status,
            latency_ms=round(latency_ms, 3),
            error=error,
        )

    def record_attachment_health(
        self,
        product_id: str,
        health: dict[str, Any],
    ) -> None:
        status = str(health.get("status", "unknown"))
        with self._lock:
            self._counters["attachment_health_checks_total"] += 1
            if status == "unhealthy":
                self._counters["attachment_health_failures_total"] += 1
            self._last_attachment_health[product_id] = health
        self.record_event(
            "attachment.health_checked",
            severity="error" if status == "unhealthy" else "info",
            product_id=product_id,
            status=status,
            detail=health,
        )

    def record_recovery_validation(
        self,
        *,
        product_id: str,
        recovered: bool,
        health: dict[str, Any],
    ) -> None:
        with self._lock:
            self._counters["recovery_validations_total"] += 1
            if recovered:
                self._counters["recovery_success_total"] += 1
        self.record_event(
            "attachment.recovery_validated",
            severity="info" if recovered else "warning",
            product_id=product_id,
            recovered=recovered,
            health=health,
        )

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events[-limit:])

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies_ms)
            by_product = {
                product_id: self._latency_summary(values)
                for product_id, values in self._latencies_by_product.items()
            }
            return {
                "counters": dict(self._counters),
                "dispatch_latency_ms": self._latency_summary(latencies),
                "dispatch_latency_by_product": by_product,
                "last_attachment_health": dict(
                    self._last_attachment_health
                ),
                "recent_event_count": len(self._events),
                "log_path": str(self.log_path) if self.log_path else None,
            }

    @staticmethod
    def _latency_summary(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {
                "count": 0,
                "avg": None,
                "max": None,
                "min": None,
            }
        return {
            "count": len(values),
            "avg": round(mean(values), 3),
            "max": round(max(values), 3),
            "min": round(min(values), 3),
        }

    def prometheus_text(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP mitra_runtime_events_total Structured runtime events.",
            "# TYPE mitra_runtime_events_total counter",
            "mitra_runtime_events_total "
            f"{snapshot['counters']['runtime_events_total']}",
            "# HELP mitra_dispatch_total Intent dispatch attempts.",
            "# TYPE mitra_dispatch_total counter",
            f"mitra_dispatch_total {snapshot['counters']['dispatch_total']}",
            "# HELP mitra_dispatch_completed_total Completed dispatches.",
            "# TYPE mitra_dispatch_completed_total counter",
            "mitra_dispatch_completed_total "
            f"{snapshot['counters']['dispatch_completed_total']}",
            "# HELP mitra_dispatch_failed_total Failed dispatches.",
            "# TYPE mitra_dispatch_failed_total counter",
            "mitra_dispatch_failed_total "
            f"{snapshot['counters']['dispatch_failed_total']}",
            "# HELP mitra_dispatch_latency_ms_avg Average dispatch latency.",
            "# TYPE mitra_dispatch_latency_ms_avg gauge",
            "mitra_dispatch_latency_ms_avg "
            f"{snapshot['dispatch_latency_ms']['avg'] or 0}",
            "# HELP mitra_dispatch_latency_ms_max Maximum dispatch latency.",
            "# TYPE mitra_dispatch_latency_ms_max gauge",
            "mitra_dispatch_latency_ms_max "
            f"{snapshot['dispatch_latency_ms']['max'] or 0}",
            "# HELP mitra_attachment_health_checks_total Attachment health checks.",
            "# TYPE mitra_attachment_health_checks_total counter",
            "mitra_attachment_health_checks_total "
            f"{snapshot['counters']['attachment_health_checks_total']}",
            "# HELP mitra_attachment_health_failures_total Unhealthy attachment checks.",
            "# TYPE mitra_attachment_health_failures_total counter",
            "mitra_attachment_health_failures_total "
            f"{snapshot['counters']['attachment_health_failures_total']}",
            "# HELP mitra_recovery_validations_total Recovery validation checks.",
            "# TYPE mitra_recovery_validations_total counter",
            "mitra_recovery_validations_total "
            f"{snapshot['counters']['recovery_validations_total']}",
            "# HELP mitra_recovery_success_total Successful attachment recoveries.",
            "# TYPE mitra_recovery_success_total counter",
            "mitra_recovery_success_total "
            f"{snapshot['counters']['recovery_success_total']}",
        ]
        for product_id, summary in sorted(
            snapshot["dispatch_latency_by_product"].items()
        ):
            lines.append(
                "mitra_dispatch_latency_ms_avg_by_product"
                f'{{product_id="{product_id}"}} {summary["avg"] or 0}'
            )
        return "\n".join(lines) + "\n"
