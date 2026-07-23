from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from uuid import uuid4


_TRUE_VALUES: Final[set[str]] = {"1", "true", "yes", "on"}
_SQLITE_SYNCHRONOUS_VALUES: Final[set[str]] = {"EXTRA", "FULL", "NORMAL"}
_NON_PRODUCTION_ENVIRONMENTS: Final[set[str]] = {
    "dev",
    "development",
    "local",
    "test",
    "testing",
}
_SECRET_VALUE_KEYS: Final[set[str]] = {
    "MITRA_COMPANION_AI_RESOLVER_URL",
    "MITRA_COMPANION_AI_ANALYSIS_URL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "MITRA_BHIV_ASHMIT_BASE_URL",
    "MITRA_BHIV_ASHMIT_API_KEY",
    "MITRA_BHIV_BUCKET_BASE_URL",
    "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
    "MITRA_BHIV_INSIGHTFLOW_API_KEY",
    "MITRA_BHIV_KESHAV_BASE_URL",
    "MITRA_BHIV_KARMA_BASE_URL",
    "MITRA_BHIV_PRANA_BASE_URL",
    "MITRA_CENTRAL_DEPOSITORY_BASE_URL",
    "MITRA_RAJ_WORKFLOW_BASE_URL",
    "MITRA_RAJ_API_KEY",
    "MITRA_TANTRA_GATEWAY_URL",
    "MITRA_TANTRA_API_KEY",
}
_DEFAULT_CORS_ALLOWED_ORIGINS: Final[list[str]] = [
    "https://mitra.blackholeinfiverse.com",
    "https://mitra-live-runtime-sprint.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


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


def _csv_values(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _endpoint_overrides(value: str | None) -> dict[str, str]:
    if value is None or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON must be a JSON object"
        )
    overrides: dict[str, str] = {}
    for source, target in payload.items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError(
                "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON keys and values "
                "must be strings"
            )
        source = source.strip().rstrip("/")
        target = target.strip().rstrip("/")
        if not source.startswith(("http://", "https://")) or not target.startswith(
            ("http://", "https://")
        ):
            raise ValueError(
                "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON entries must use "
                "absolute HTTP(S) URLs"
            )
        overrides[source] = target
    return overrides


def _sqlite_synchronous(value: str | None) -> str:
    normalized = (value or "FULL").strip().upper()
    if normalized not in _SQLITE_SYNCHRONOUS_VALUES:
        allowed = ", ".join(sorted(_SQLITE_SYNCHRONOUS_VALUES))
        raise ValueError(
            "MITRA_COMPANION_SQLITE_SYNCHRONOUS must be one of "
            f"{allowed}; received {normalized!r}"
        )
    return normalized


def _non_production_manifest_default(
    environment: str,
    profile: str,
) -> bool:
    return (
        environment.strip().lower() in _NON_PRODUCTION_ENVIRONMENTS
        or profile.strip().lower() in _NON_PRODUCTION_ENVIRONMENTS
    )


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
    sqlite_synchronous: str = "FULL"
    runtime_version: str = "1.0.0"
    compatibility_version: str = "mitra-companion-1"
    telemetry_log_path: Path | None = None
    http_timeout_seconds: float = 10.0
    manifest_directory: Path | None = None
    allow_example_manifests: bool = False
    allow_simulated_manifests: bool = False
    allow_loopback_manifests: bool = False
    allow_localhost_manifests: bool = False
    require_production_bootstrap_manifests: bool = True
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
    endpoint_overrides: dict[str, str] = field(default_factory=dict)
    persistent_runtime_enabled: bool = True
    persistent_heartbeat_interval_seconds: float = 5.0
    persistent_stale_after_seconds: float = 30.0
    persistent_maintenance_interval_seconds: float = 60.0
    persistent_task_timeout_seconds: float = 300.0
    persistent_coordination_lease_seconds: float = 20.0
    runtime_continuity_dispatch_limit: int = 25
    production_config_profile: str = "production"
    production_config_file: Path | None = None
    production_log_path: Path | None = None
    production_log_level: str = "INFO"
    production_log_to_stdout: bool = True
    bhiv_integration_timeout_seconds: float = 10.0
    bhiv_integration_fail_closed: bool = True
    bhiv_ashmit_base_url: str | None = None
    bhiv_ashmit_api_key: str | None = None
    bhiv_bucket_base_url: str | None = None
    bhiv_bucket_parent_hash: str | None = None
    bhiv_insightflow_ingest_url: str | None = None
    bhiv_insightflow_api_key: str | None = None
    bhiv_keshav_base_url: str | None = None
    bhiv_karma_base_url: str | None = None
    bhiv_karma_previous_hash: str | None = None
    bhiv_prana_base_url: str | None = None
    central_depository_base_url: str | None = None
    ecosystem_timeout_seconds: float = 45.0
    raj_workflow_base_url: str | None = None
    raj_api_key: str | None = None
    tantra_integration_timeout_seconds: float = 15.0
    tantra_gateway_url: str | None = None
    tantra_api_key: str | None = None
    tantra_delivery_lease_seconds: float = 30.0
    tantra_delivery_initial_backoff_seconds: float = 5.0
    tantra_delivery_max_backoff_seconds: float = 300.0
    tantra_delivery_max_attempts: int = 8
    tantra_delivery_batch_size: int = 20
    cors_allowed_origins: list[str] = field(
        default_factory=lambda: list(_DEFAULT_CORS_ALLOWED_ORIGINS)
    )
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
        deployment_environment = (
            get("MITRA_COMPANION_ENVIRONMENT", "production") or "production"
        )
        production_config_profile = (
            get("MITRA_COMPANION_CONFIG_PROFILE", deployment_environment)
            or "production"
        )
        manifest_dev_default = _non_production_manifest_default(
            deployment_environment,
            production_config_profile,
        )
        ai_resolver_url = get_secret("MITRA_COMPANION_AI_RESOLVER_URL")
        ai_analysis_url = (
            get_secret("MITRA_COMPANION_AI_ANALYSIS_URL")
            or ai_resolver_url
        )
        otel_endpoint = get_secret("OTEL_EXPORTER_OTLP_ENDPOINT")
        bhiv_ashmit_base_url = get_secret("MITRA_BHIV_ASHMIT_BASE_URL")
        bhiv_ashmit_api_key = get_secret("MITRA_BHIV_ASHMIT_API_KEY")
        bhiv_bucket_base_url = get_secret("MITRA_BHIV_BUCKET_BASE_URL")
        bhiv_insightflow_ingest_url = get_secret(
            "MITRA_BHIV_INSIGHTFLOW_INGEST_URL"
        )
        bhiv_insightflow_api_key = get_secret(
            "MITRA_BHIV_INSIGHTFLOW_API_KEY"
        )
        bhiv_keshav_base_url = get_secret("MITRA_BHIV_KESHAV_BASE_URL")
        bhiv_karma_base_url = get_secret("MITRA_BHIV_KARMA_BASE_URL")
        bhiv_prana_base_url = get_secret("MITRA_BHIV_PRANA_BASE_URL")
        central_depository_base_url = get_secret(
            "MITRA_CENTRAL_DEPOSITORY_BASE_URL"
        )
        raj_workflow_base_url = get_secret("MITRA_RAJ_WORKFLOW_BASE_URL")
        raj_api_key = get_secret("MITRA_RAJ_API_KEY")
        tantra_gateway_url = get_secret("MITRA_TANTRA_GATEWAY_URL")
        tantra_api_key = get_secret("MITRA_TANTRA_API_KEY")
        return cls(
            service_root=service_root,
            data_root=data_root,
            database_path=database_path,
            sqlite_synchronous=_sqlite_synchronous(
                get("MITRA_COMPANION_SQLITE_SYNCHRONOUS", "FULL")
            ),
            runtime_version=(
                get("MITRA_COMPANION_RUNTIME_VERSION", "1.0.0") or "1.0.0"
            ),
            compatibility_version=(
                get(
                    "MITRA_COMPANION_COMPATIBILITY_VERSION",
                    "mitra-companion-1",
                )
                or "mitra-companion-1"
            ),
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
            allow_example_manifests=_bool_value(
                get("MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS"),
                manifest_dev_default,
            ),
            allow_simulated_manifests=_bool_value(
                get("MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS"),
                manifest_dev_default,
            ),
            allow_loopback_manifests=_bool_value(
                get("MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS"),
                manifest_dev_default,
            ),
            allow_localhost_manifests=_bool_value(
                get("MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS"),
                manifest_dev_default,
            ),
            require_production_bootstrap_manifests=_bool_value(
                get("MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS"),
                not manifest_dev_default,
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
            deployment_environment=deployment_environment,
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
            endpoint_overrides=_endpoint_overrides(
                get("MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON")
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
            persistent_coordination_lease_seconds=float(
                get(
                    "MITRA_COMPANION_COORDINATION_LEASE_SECONDS",
                    "20",
                )
                or "20"
            ),
            runtime_continuity_dispatch_limit=max(
                1,
                int(
                    get(
                        "MITRA_COMPANION_CONTINUITY_DISPATCH_LIMIT",
                        "25",
                    )
                    or "25"
                ),
            ),
            production_config_profile=production_config_profile,
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
            bhiv_integration_timeout_seconds=float(
                get("MITRA_BHIV_INTEGRATION_TIMEOUT_SECONDS", "10") or "10"
            ),
            bhiv_integration_fail_closed=_bool_value(
                get("MITRA_BHIV_INTEGRATION_FAIL_CLOSED", "true"),
                True,
            ),
            bhiv_ashmit_base_url=bhiv_ashmit_base_url,
            bhiv_ashmit_api_key=bhiv_ashmit_api_key,
            bhiv_bucket_base_url=bhiv_bucket_base_url,
            bhiv_bucket_parent_hash=get("MITRA_BHIV_BUCKET_PARENT_HASH"),
            bhiv_insightflow_ingest_url=bhiv_insightflow_ingest_url,
            bhiv_insightflow_api_key=bhiv_insightflow_api_key,
            bhiv_keshav_base_url=bhiv_keshav_base_url,
            bhiv_karma_base_url=bhiv_karma_base_url,
            bhiv_karma_previous_hash=get("MITRA_BHIV_KARMA_PREVIOUS_HASH"),
            bhiv_prana_base_url=bhiv_prana_base_url,
            central_depository_base_url=central_depository_base_url,
            ecosystem_timeout_seconds=float(
                get("MITRA_ECOSYSTEM_TIMEOUT_SECONDS", "45") or "45"
            ),
            raj_workflow_base_url=raj_workflow_base_url,
            raj_api_key=raj_api_key,
            tantra_integration_timeout_seconds=float(
                get("MITRA_TANTRA_INTEGRATION_TIMEOUT_SECONDS", "15")
                or "15"
            ),
            tantra_gateway_url=tantra_gateway_url,
            tantra_api_key=tantra_api_key,
            tantra_delivery_lease_seconds=float(
                get("MITRA_TANTRA_DELIVERY_LEASE_SECONDS", "30") or "30"
            ),
            tantra_delivery_initial_backoff_seconds=float(
                get("MITRA_TANTRA_INITIAL_BACKOFF_SECONDS", "5") or "5"
            ),
            tantra_delivery_max_backoff_seconds=float(
                get("MITRA_TANTRA_MAX_BACKOFF_SECONDS", "300") or "300"
            ),
            tantra_delivery_max_attempts=max(
                1,
                int(get("MITRA_TANTRA_MAX_ATTEMPTS", "8") or "8"),
            ),
            tantra_delivery_batch_size=max(
                1,
                int(get("MITRA_TANTRA_DELIVERY_BATCH_SIZE", "20") or "20"),
            ),
            cors_allowed_origins=_csv_values(
                get(
                    "MITRA_COMPANION_CORS_ORIGINS",
                    ",".join(_DEFAULT_CORS_ALLOWED_ORIGINS),
                )
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
        bhiv_configured = {
            "ashmit": bool(
                self.bhiv_ashmit_base_url and self.bhiv_ashmit_api_key
            ),
            "bucket": bool(self.bhiv_bucket_base_url),
            "central_depository": bool(
                self.central_depository_base_url
            ),
            "insightflow": bool(self.bhiv_insightflow_ingest_url),
            "keshav": bool(self.bhiv_keshav_base_url),
            "karma": bool(self.bhiv_karma_base_url),
            "prana": bool(self.bhiv_prana_base_url),
        }
        bhiv_pending = [
            name
            for name, is_configured in bhiv_configured.items()
            if not is_configured
        ]
        tantra_gateway_configured = bool(self.tantra_gateway_url)
        canonical_ecosystem_configured = {
            "raj": bool(self.raj_workflow_base_url),
            "ashmit": bool(
                self.bhiv_ashmit_base_url and self.bhiv_ashmit_api_key
            ),
            "bucket": bool(self.bhiv_bucket_base_url),
            "keshav": bool(self.bhiv_keshav_base_url),
            "prana": bool(self.bhiv_prana_base_url),
            "karma": bool(self.bhiv_karma_base_url),
            "insightflow": bool(self.bhiv_insightflow_ingest_url),
            "central_depository": bool(self.central_depository_base_url),
        }
        canonical_pending = [
            name
            for name, configured in canonical_ecosystem_configured.items()
            if not configured
        ]
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
            "sqlite_synchronous": self.sqlite_synchronous,
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
            "manifest_policy": {
                "allow_examples": self.allow_example_manifests,
                "allow_simulated": self.allow_simulated_manifests,
                "allow_loopback": self.allow_loopback_manifests,
                "allow_localhost": self.allow_localhost_manifests,
                "require_production_bootstrap": (
                    self.require_production_bootstrap_manifests
                ),
            },
            "http_timeout_seconds": self.http_timeout_seconds,
            "uvicorn_workers": self.uvicorn_workers,
            "cors_allowed_origins": list(self.cors_allowed_origins),
            "otel_enabled": self.otel_enabled,
            "otel_exporter_configured": bool(
                self.otel_exporter_otlp_endpoint
            ),
            "ai_resolver_configured": bool(self.ai_resolver_url),
            "ai_analysis_configured": bool(self.ai_analysis_url),
            "product_endpoint_overrides": {
                "configured": bool(self.endpoint_overrides),
                "count": len(self.endpoint_overrides),
                "published_origins": sorted(self.endpoint_overrides),
            },
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
                "coordination_lease_seconds": (
                    self.persistent_coordination_lease_seconds
                ),
                "continuity_dispatch_limit": (
                    self.runtime_continuity_dispatch_limit
                ),
            },
            "bhiv_integrations": {
                "timeout_seconds": self.bhiv_integration_timeout_seconds,
                "fail_closed": self.bhiv_integration_fail_closed,
                "readiness": "ready" if not bhiv_pending else "blocked",
                "required_modules": [
                    "ashmit",
                    "bucket",
                    "central_depository",
                    "insightflow",
                    "keshav",
                    "karma",
                    "prana",
                ],
                "active_modules": [
                    name
                    for name, is_configured in bhiv_configured.items()
                    if is_configured
                ],
                "external_endpoints_configured": [
                    name
                    for name, is_configured in bhiv_configured.items()
                    if is_configured
                ],
                "embedded_contract_modules": [],
                "unavailable_owner_modules": bhiv_pending,
                "external_settings_pending": [
                    {
                        "ashmit": "MITRA_BHIV_ASHMIT_BASE_URL",
                        "bucket": "MITRA_BHIV_BUCKET_BASE_URL",
                        "central_depository": (
                            "MITRA_CENTRAL_DEPOSITORY_BASE_URL"
                        ),
                        "insightflow": (
                            "MITRA_BHIV_INSIGHTFLOW_INGEST_URL"
                        ),
                        "keshav": "MITRA_BHIV_KESHAV_BASE_URL",
                        "karma": "MITRA_BHIV_KARMA_BASE_URL",
                        "prana": "MITRA_BHIV_PRANA_BASE_URL",
                    }[name]
                    for name in bhiv_pending
                ],
                "ashmit_configured": bhiv_configured["ashmit"],
                "bucket_configured": bhiv_configured["bucket"],
                "central_depository_configured": bhiv_configured[
                    "central_depository"
                ],
                "insightflow_configured": bhiv_configured["insightflow"],
                "keshav_configured": bhiv_configured["keshav"],
                "karma_configured": bhiv_configured["karma"],
                "prana_configured": bhiv_configured["prana"],
                "bucket_parent_hash_configured": bool(
                    self.bhiv_bucket_parent_hash
                ),
                "karma_previous_hash_configured": bool(
                    self.bhiv_karma_previous_hash
                ),
            },
            "ecosystem_convergence": {
                "mode": "strict-published-contracts",
                "timeout_seconds": self.ecosystem_timeout_seconds,
                "ready": not canonical_pending,
                "required_flow": [
                    "mitra.capability-selection",
                    "raj.workflow-execution",
                    "keshav.conditional-diagnosis",
                    "bucket.truth-persistence",
                    "karma.integrity-append",
                    "prana.strict-forwarding",
                    "insightflow.telemetry",
                    "mitra.deterministic-replay",
                    "central-depository.export",
                ],
                "configured_modules": [
                    name
                    for name, configured in canonical_ecosystem_configured.items()
                    if configured
                ],
                "pending_modules": canonical_pending,
                "embedded_fallback": False,
                "raj_contract": "POST /api/workflow/execute (version 1.0.0)",
                "raj_url_configured": bool(self.raj_workflow_base_url),
                "raj_api_key_configured": bool(self.raj_api_key),
                "insightflow_api_key_configured": bool(
                    self.bhiv_insightflow_api_key
                ),
            },
            "tantra_integration": {
                "timeout_seconds": self.tantra_integration_timeout_seconds,
                "package_production": "active",
                "mode": "gateway"
                if tantra_gateway_configured
                else "package-only",
                "gateway_configured": tantra_gateway_configured,
                "api_key_configured": bool(self.tantra_api_key),
                "delivery_outbox": {
                    "lease_seconds": self.tantra_delivery_lease_seconds,
                    "initial_backoff_seconds": (
                        self.tantra_delivery_initial_backoff_seconds
                    ),
                    "max_backoff_seconds": (
                        self.tantra_delivery_max_backoff_seconds
                    ),
                    "max_attempts": self.tantra_delivery_max_attempts,
                    "batch_size": self.tantra_delivery_batch_size,
                },
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
                or (
                    key == "MITRA_BHIV_ASHMIT_BASE_URL"
                    and self.bhiv_ashmit_base_url
                )
                or (
                    key == "MITRA_BHIV_BUCKET_BASE_URL"
                    and self.bhiv_bucket_base_url
                )
                or (
                    key == "MITRA_BHIV_INSIGHTFLOW_INGEST_URL"
                    and self.bhiv_insightflow_ingest_url
                )
                or (
                    key == "MITRA_BHIV_INSIGHTFLOW_API_KEY"
                    and self.bhiv_insightflow_api_key
                )
                or (
                    key == "MITRA_BHIV_KESHAV_BASE_URL"
                    and self.bhiv_keshav_base_url
                )
                or (
                    key == "MITRA_BHIV_KARMA_BASE_URL"
                    and self.bhiv_karma_base_url
                )
                or (
                    key == "MITRA_BHIV_PRANA_BASE_URL"
                    and self.bhiv_prana_base_url
                )
                or (
                    key == "MITRA_CENTRAL_DEPOSITORY_BASE_URL"
                    and self.central_depository_base_url
                )
                or (
                    key == "MITRA_RAJ_WORKFLOW_BASE_URL"
                    and self.raj_workflow_base_url
                )
                or (
                    key == "MITRA_RAJ_API_KEY"
                    and self.raj_api_key
                )
                or (
                    key == "MITRA_TANTRA_GATEWAY_URL"
                    and self.tantra_gateway_url
                )
                or (
                    key == "MITRA_TANTRA_API_KEY"
                    and self.tantra_api_key
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
