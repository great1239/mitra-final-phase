from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from uuid import uuid4


_TRUE_VALUES: Final[set[str]] = {"1", "true", "yes", "on"}


def _default_instance_id() -> str:
    host = socket.gethostname().replace(" ", "-").lower() or "runtime"
    return f"{host}-{os.getpid()}-{uuid4().hex[:8]}"


@dataclass(slots=True)
class RuntimeSettings:
    service_root: Path
    data_root: Path
    database_path: Path
    telemetry_log_path: Path | None = None
    http_timeout_seconds: float = 10.0
    manifest_directory: Path | None = None
    otel_enabled: bool = True
    otel_service_name: str = "mitra-companion-runtime"
    otel_exporter_otlp_endpoint: str | None = None
    deployment_environment: str = "production"
    uvicorn_workers: int = 1
    runtime_instance_id: str = field(default_factory=_default_instance_id)
    deterministic_intent_threshold: float = 0.28
    ai_resolver_url: str | None = None
    ai_resolver_timeout_seconds: float = 8.0
    ai_analysis_url: str | None = None
    ai_analysis_timeout_seconds: float = 8.0
    persistent_runtime_enabled: bool = True
    persistent_heartbeat_interval_seconds: float = 5.0
    persistent_stale_after_seconds: float = 30.0
    persistent_maintenance_interval_seconds: float = 60.0
    persistent_task_timeout_seconds: float = 300.0

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        service_root = Path(__file__).resolve().parents[3]
        data_root = Path(
            os.getenv(
                "MITRA_COMPANION_DATA_ROOT",
                str(service_root / "var"),
            )
        ).resolve()
        database_path = Path(
            os.getenv(
                "MITRA_COMPANION_DATABASE_PATH",
                str(data_root / "companion-runtime.db"),
            )
        ).resolve()
        manifest_directory = os.getenv("MITRA_COMPANION_MANIFEST_DIRECTORY")
        return cls(
            service_root=service_root,
            data_root=data_root,
            database_path=database_path,
            telemetry_log_path=Path(
                os.getenv(
                    "MITRA_COMPANION_TELEMETRY_LOG_PATH",
                    str(data_root / "runtime-telemetry.jsonl"),
                )
            ).resolve(),
            http_timeout_seconds=float(
                os.getenv("MITRA_COMPANION_HTTP_TIMEOUT_SECONDS", "10")
            ),
            manifest_directory=(
                Path(manifest_directory).resolve()
                if manifest_directory
                else None
            ),
            otel_enabled=(
                os.getenv("MITRA_COMPANION_OTEL_ENABLED", "true")
                .strip()
                .lower()
                in _TRUE_VALUES
            ),
            otel_service_name=os.getenv(
                "OTEL_SERVICE_NAME",
                "mitra-companion-runtime",
            ),
            otel_exporter_otlp_endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT"
            ),
            deployment_environment=os.getenv(
                "MITRA_COMPANION_ENVIRONMENT",
                "production",
            ),
            uvicorn_workers=max(
                1,
                int(os.getenv("MITRA_COMPANION_UVICORN_WORKERS", "1")),
            ),
            runtime_instance_id=os.getenv(
                "MITRA_COMPANION_INSTANCE_ID",
                _default_instance_id(),
            ),
            deterministic_intent_threshold=float(
                os.getenv(
                    "MITRA_COMPANION_DETERMINISTIC_INTENT_THRESHOLD",
                    "0.28",
                )
            ),
            ai_resolver_url=os.getenv("MITRA_COMPANION_AI_RESOLVER_URL"),
            ai_resolver_timeout_seconds=float(
                os.getenv("MITRA_COMPANION_AI_RESOLVER_TIMEOUT_SECONDS", "8")
            ),
            ai_analysis_url=os.getenv(
                "MITRA_COMPANION_AI_ANALYSIS_URL",
                os.getenv("MITRA_COMPANION_AI_RESOLVER_URL"),
            ),
            ai_analysis_timeout_seconds=float(
                os.getenv("MITRA_COMPANION_AI_ANALYSIS_TIMEOUT_SECONDS", "8")
            ),
            persistent_runtime_enabled=(
                os.getenv("MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED", "true")
                .strip()
                .lower()
                in _TRUE_VALUES
            ),
            persistent_heartbeat_interval_seconds=float(
                os.getenv(
                    "MITRA_COMPANION_PERSISTENT_HEARTBEAT_INTERVAL_SECONDS",
                    "5",
                )
            ),
            persistent_stale_after_seconds=float(
                os.getenv(
                    "MITRA_COMPANION_PERSISTENT_STALE_AFTER_SECONDS",
                    "30",
                )
            ),
            persistent_maintenance_interval_seconds=float(
                os.getenv(
                    "MITRA_COMPANION_PERSISTENT_MAINTENANCE_INTERVAL_SECONDS",
                    "60",
                )
            ),
            persistent_task_timeout_seconds=float(
                os.getenv(
                    "MITRA_COMPANION_PERSISTENT_TASK_TIMEOUT_SECONDS",
                    "300",
                )
            ),
        )

    def prepare(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.telemetry_log_path is not None:
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)
