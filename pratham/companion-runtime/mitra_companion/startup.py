from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .production_logging import production_log
from .utils import utc_now

if TYPE_CHECKING:
    from .ports import ManifestSourceAdapter
    from .runtime import CompanionRuntime


class RuntimeStartupManager:
    """Coordinates production startup, restart, and recovery operations."""

    def __init__(self, runtime: "CompanionRuntime"):
        self.runtime = runtime
        self._last_report: dict[str, Any] = {
            "status": "not_started",
            "phases": [],
            "completed_at": None,
        }

    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def start(
        self,
        manifest_sources: Iterable["ManifestSourceAdapter"] = (),
    ) -> dict[str, Any]:
        phases: list[dict[str, Any]] = []
        phases.append(
            self._phase(
                "production_configuration_loaded",
                self.runtime.settings.production_summary(),
            )
        )
        status = self.runtime.start()
        phases.append(
            self._phase(
                "runtime_process_started",
                {
                    "state": status["state"],
                    "accepting": status["accepting"],
                    "runtime_instance_id": status["runtime_instance_id"],
                },
            )
        )
        loaded_sources = self._attach_sources(manifest_sources)
        phases.append(
            self._phase(
                "manifest_sources_loaded",
                {"sources": loaded_sources},
            )
        )
        phases.append(
            self._phase(
                "persistent_supervisor_checked",
                self.runtime.status()["persistent_runtime"],
            )
        )
        self._last_report = {
            "status": "started",
            "runtime_instance_id": self.runtime.instance_id,
            "completed_at": utc_now(),
            "phases": phases,
        }
        self.runtime.telemetry.record_event(
            "runtime.startup_completed",
            phase_count=len(phases),
        )
        production_log(
            self.runtime.production_logger,
            "runtime.startup_completed",
            runtime_instance_id=self.runtime.instance_id,
            phase_count=len(phases),
        )
        return self.last_report()

    def restart(
        self,
        manifest_sources: Iterable["ManifestSourceAdapter"] = (),
    ) -> dict[str, Any]:
        before = self.runtime.status()
        stopped = self.runtime.stop()
        started = self.start(manifest_sources)
        report = {
            "status": "restarted",
            "runtime_instance_id": self.runtime.instance_id,
            "completed_at": utc_now(),
            "phases": started.get("phases", []),
            "before": {
                "state": before["state"],
                "accepting": before["accepting"],
                "active_runtime_instance_count": (
                    before["active_runtime_instance_count"]
                ),
            },
            "stopped_instance": stopped.get("stopped_instance"),
            "startup": started,
        }
        self._last_report = report
        self.runtime.telemetry.record_event("runtime.restart_completed")
        production_log(
            self.runtime.production_logger,
            "runtime.restart_completed",
            runtime_instance_id=self.runtime.instance_id,
            state=self.runtime.lifecycle.state.value,
        )
        return dict(report)

    def recover(self) -> dict[str, Any]:
        tick = self.runtime.persistent_tick(run_maintenance=False)
        instances = self.runtime.runtime_instances(include_stopped=True)
        tasks = self.runtime.companion_tasks(limit=25)
        report = {
            "status": "recovered",
            "runtime_instance_id": self.runtime.instance_id,
            "completed_at": utc_now(),
            "tick": tick,
            "instances": instances,
            "recent_tasks": tasks,
        }
        self.runtime.telemetry.record_event(
            "runtime.recovery_completed",
            stale_instance_count=len(tick.get("stale_instances", [])),
            recovered_task_count=len(tick.get("recovered_tasks", [])),
        )
        production_log(
            self.runtime.production_logger,
            "runtime.recovery_completed",
            runtime_instance_id=self.runtime.instance_id,
            stale_instance_count=len(tick.get("stale_instances", [])),
            recovered_task_count=len(tick.get("recovered_tasks", [])),
        )
        return report

    def _attach_sources(
        self,
        manifest_sources: Iterable["ManifestSourceAdapter"],
    ) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for source in manifest_sources:
            manifests = source.load()
            # Configured startup sources are authoritative for their product
            # manifests. Replace a persisted prior revision atomically after
            # the new manifest has passed runtime and transport validation.
            attachments = self.runtime.attach_many(
                manifests,
                replace_existing=True,
            )
            loaded.append(
                {
                    "source": type(source).__name__,
                    "manifest_count": len(manifests),
                    "attachment_count": attachments["attached_count"],
                }
            )
        return loaded

    @staticmethod
    def _phase(name: str, detail: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "completed_at": utc_now(),
            "detail": detail,
        }
