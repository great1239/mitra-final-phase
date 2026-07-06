from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from uuid import uuid4


_TRUE_VALUES: Final[set[str]] = {"1", "true", "yes", "on"}
_SECRET_VALUE_KEYS: Final[set[str]] = {
    "MITRA_COMPANION_AI_RESOLVER_URL",
    "MITRA_COMPANION_AI_ANALYSIS_URL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
}


def _default_instance_id() -> str:
    host = socket.gethostname().replace(" ", "-").lower() or "runtime"
    return f"{host}-{os.getpid()}-{uuid4().hex[:8]}"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Production config file not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _path_or_none(value: str | None) -> Path | None:
    return Path(value).resolve() if value else None


def _bool_value(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _redact_path(path: Path | None, data_root: Path) -> str | None:
    if path is None:
        return None
    try:
        relative = path.resolve().relative_to(data_root.resolve())
        return "${MITRA_COMPANION_DATA_ROOT}/" + relative.as_posix()
    except ValueError:
        return str(path)


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
    production_config_profile: str = "production"
    production_config_file: Path | None = None
    production_log_path: Path | None = None
    production_log_level: str = "INFO"
    production_log_to_stdout: bool = True
    secrets_directory: Path | None = None
    secret_keys_loaded: list[str] = field(default_factory=list)
    config_sources: list[str] = field(default_factory=lambda: ["environment"])

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        service_root = Path(__file__).resolve().parents[3]
        environment = dict(os.environ)
        config_file_value = environment.get(
            "MITRA_COMPANION_CONFIG_FILE",
            environment.get("MITRA_COMPANION_ENV_FILE"),
        )
        config_sources = ["environment"]
        file_values: dict[str, str] = {}
        production_config_file = _path_or_none(config_file_value)
        if production_config_file is not None:
            file_values = _read_env_file(production_config_file)
            config_sources.insert(0, f"env-file:{production_config_file}")
        values = {**file_values, **environment}

        def get(name: str, default: str | None = None) -> str | None:
            return values.get(name, default)

        secrets_directory = _path_or_none(
            get("MITRA_COMPANION_SECRETS_DIR")
        )
        if secrets_directory is not None:
            config_sources.append(f"secrets-dir:{secrets_directory}")

        secret_keys_loaded: list[str] = []

        def get_secret(name: str) -> str | None:
            file_name = get(f"{name}_FILE")
            if file_name:
                secret_keys_loaded.append(name)
                return Path(file_name).resolve().read_text(
                    encoding="utf-8"
                ).strip()
            if name in values:
                return values[name]
            if secrets_directory is not None:
                mounted = secrets_directory / name
                if mounted.exists():
                    secret_keys_loaded.append(name)
                    return mounted.read_text(encoding="utf-8").strip()
            return None

        data_root = Path(
            get(
                "MITRA_COMPANION_DATA_ROOT",
                str(service_root / "var"),
            )
            or str(service_root / "var")
        ).resolve()
        database_path = Path(
            get(
                "MITRA_COMPANION_DATABASE_PATH",
                str(data_root / "companion-runtime.db"),
            )
            or str(data_root / "companion-runtime.db")
        ).resolve()
        manifest_directory = get("MITRA_COMPANION_MANIFEST_DIRECTORY")
        ai_resolver_url = get_secret("MITRA_COMPANION_AI_RESOLVER_URL")
        ai_analysis_url = (
            get_secret("MITRA_COMPANION_AI_ANALYSIS_URL")
            or ai_resolver_url
        )
        otel_endpoint = get_secret("OTEL_EXPORTER_OTLP_ENDPOINT")
        return cls(
            service_root=service_root,
            data_root=data_root,
            database_path=database_path,
            telemetry_log_path=Path(
                get(
                    "MITRA_COMPANION_TELEMETRY_LOG_PATH",
                    str(data_root / "runtime-telemetry.jsonl"),
                )
                or str(data_root / "runtime-telemetry.jsonl")
            ).resolve(),
            http_timeout_seconds=float(
                get("MITRA_COMPANION_HTTP_TIMEOUT_SECONDS", "10") or "10"
            ),
            manifest_directory=(
                Path(manifest_directory).resolve()
                if manifest_directory
                else None
            ),
            otel_enabled=_bool_value(
                get("MITRA_COMPANION_OTEL_ENABLED", "true"),
                True,
            ),
            otel_service_name=get(
                "OTEL_SERVICE_NAME",
                "mitra-companion-runtime",
            )
            or "mitra-companion-runtime",
            otel_exporter_otlp_endpoint=otel_endpoint,
            deployment_environment=get(
                "MITRA_COMPANION_ENVIRONMENT",
                "production",
            )
            or "production",
            uvicorn_workers=max(
                1,
                int(get("MITRA_COMPANION_UVICORN_WORKERS", "1") or "1"),
            ),
            runtime_instance_id=get(
                "MITRA_COMPANION_INSTANCE_ID",
                _default_instance_id(),
            )
            or _default_instance_id(),
            deterministic_intent_threshold=float(
                get(
                    "MITRA_COMPANION_DETERMINISTIC_INTENT_THRESHOLD",
                    "0.28",
                )
                or "0.28"
            ),
            ai_resolver_url=ai_resolver_url,
            ai_resolver_timeout_seconds=float(
                get("MITRA_COMPANION_AI_RESOLVER_TIMEOUT_SECONDS", "8")
                or "8"
            ),
            ai_analysis_url=ai_analysis_url,
            ai_analysis_timeout_seconds=float(
                get("MITRA_COMPANION_AI_ANALYSIS_TIMEOUT_SECONDS", "8")
                or "8"
            ),
            persistent_runtime_enabled=_bool_value(
                get("MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED", "true"),
                True,
            ),
            persistent_heartbeat_interval_seconds=float(
                get(
                    "MITRA_COMPANION_PERSISTENT_HEARTBEAT_INTERVAL_SECONDS",
                    "5",
                )
                or "5"
            ),
            persistent_stale_after_seconds=float(
                get(
                    "MITRA_COMPANION_PERSISTENT_STALE_AFTER_SECONDS",
                    "30",
                )
                or "30"
            ),
            persistent_maintenance_interval_seconds=float(
                get(
                    "MITRA_COMPANION_PERSISTENT_MAINTENANCE_INTERVAL_SECONDS",
                    "60",
                )
                or "60"
            ),
            persistent_task_timeout_seconds=float(
                get(
                    "MITRA_COMPANION_PERSISTENT_TASK_TIMEOUT_SECONDS",
                    "300",
                )
                or "300"
            ),
            production_config_profile=get(
                "MITRA_COMPANION_CONFIG_PROFILE",
                get("MITRA_COMPANION_ENVIRONMENT", "production"),
            )
            or "production",
            production_config_file=production_config_file,
            production_log_path=Path(
                get(
                    "MITRA_COMPANION_LOG_PATH",
                    str(data_root / "production-runtime.jsonl"),
                )
                or str(data_root / "production-runtime.jsonl")
            ).resolve(),
            production_log_level=(
                get("MITRA_COMPANION_LOG_LEVEL", "INFO") or "INFO"
            ).upper(),
            production_log_to_stdout=_bool_value(
                get("MITRA_COMPANION_LOG_TO_STDOUT", "true"),
                True,
            ),
            secrets_directory=secrets_directory,
            secret_keys_loaded=sorted(set(secret_keys_loaded)),
            config_sources=config_sources,
        )

    def prepare(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.telemetry_log_path is not None:
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.production_log_path is not None:
            self.production_log_path.parent.mkdir(parents=True, exist_ok=True)

    def production_summary(self) -> dict[str, object]:
        return {
            "profile": self.production_config_profile,
            "environment": self.deployment_environment,
            "service_name": self.otel_service_name,
            "runtime_instance_id": self.runtime_instance_id,
            "config_sources": list(self.config_sources),
            "config_file": str(self.production_config_file)
            if self.production_config_file
            else None,
            "data_root": str(self.data_root),
            "database_path": _redact_path(self.database_path, self.data_root),
            "telemetry_log_path": _redact_path(
                self.telemetry_log_path,
                self.data_root,
            ),
            "production_log_path": _redact_path(
                self.production_log_path,
                self.data_root,
            ),
            "production_log_level": self.production_log_level,
            "production_log_to_stdout": self.production_log_to_stdout,
            "manifest_directory": str(self.manifest_directory)
            if self.manifest_directory
            else None,
            "http_timeout_seconds": self.http_timeout_seconds,
            "uvicorn_workers": self.uvicorn_workers,
            "otel_enabled": self.otel_enabled,
            "otel_exporter_configured": bool(
                self.otel_exporter_otlp_endpoint
            ),
            "ai_resolver_configured": bool(self.ai_resolver_url),
            "ai_analysis_configured": bool(self.ai_analysis_url),
            "persistent_runtime": {
                "enabled": self.persistent_runtime_enabled,
                "heartbeat_interval_seconds": (
                    self.persistent_heartbeat_interval_seconds
                ),
                "stale_after_seconds": self.persistent_stale_after_seconds,
                "maintenance_interval_seconds": (
                    self.persistent_maintenance_interval_seconds
                ),
                "task_timeout_seconds": (
                    self.persistent_task_timeout_seconds
                ),
            },
            "secrets": self.secrets_summary(),
        }

    def secrets_summary(self) -> dict[str, object]:
        loaded = sorted(set(self.secret_keys_loaded))
        configured = sorted(
            key
            for key in _SECRET_VALUE_KEYS
            if (
                (key == "MITRA_COMPANION_AI_RESOLVER_URL" and self.ai_resolver_url)
                or (
                    key == "MITRA_COMPANION_AI_ANALYSIS_URL"
                    and self.ai_analysis_url
                )
                or (
                    key == "OTEL_EXPORTER_OTLP_ENDPOINT"
                    and self.otel_exporter_otlp_endpoint
                )
            )
        )
        return {
            "secrets_directory_configured": self.secrets_directory is not None,
            "secrets_directory": str(self.secrets_directory)
            if self.secrets_directory
            else None,
            "secret_keys_configured": configured,
            "secret_keys_loaded_from_files": loaded,
            "redaction": "values are never returned by runtime APIs",
        }
