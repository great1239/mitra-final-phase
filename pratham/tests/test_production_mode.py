from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.config import RuntimeSettings
from mitra_companion.constants import (
    COMPATIBILITY_VERSION,
    CONTRACT_VERSION,
    RUNTIME_VERSION,
    SCHEMA_VERSION,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.contracts import ProductAttachmentManifest


ROOT = Path(__file__).resolve().parents[2]
VERSIONED = {
    "schema_version": SCHEMA_VERSION,
    "contract_version": CONTRACT_VERSION,
    "runtime_version": RUNTIME_VERSION,
    "compatibility_version": COMPATIBILITY_VERSION,
}


def test_production_configuration_loads_env_file_and_secret_files(
    tmp_path,
    monkeypatch,
):
    for name in [
        "MITRA_COMPANION_CONFIG_FILE",
        "MITRA_COMPANION_DATA_ROOT",
        "MITRA_COMPANION_DATABASE_PATH",
        "MITRA_COMPANION_SQLITE_SYNCHRONOUS",
        "MITRA_COMPANION_TELEMETRY_LOG_PATH",
        "MITRA_COMPANION_LOG_PATH",
        "MITRA_COMPANION_LOG_LEVEL",
        "MITRA_COMPANION_LOG_TO_STDOUT",
        "MITRA_COMPANION_AI_RESOLVER_URL",
        "MITRA_COMPANION_AI_RESOLVER_URL_FILE",
        "MITRA_COMPANION_AI_ANALYSIS_URL",
        "MITRA_COMPANION_AI_ANALYSIS_URL_FILE",
        "MITRA_COMPANION_SECRETS_DIR",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_ENDPOINT_FILE",
    ]:
        monkeypatch.delenv(name, raising=False)

    data_root = tmp_path / "data"
    resolver_secret = tmp_path / "resolver-url.secret"
    otel_secret = tmp_path / "otel-url.secret"
    resolver_secret.write_text(
        "https://resolver.internal/runtime-analysis\n",
        encoding="utf-8",
    )
    otel_secret.write_text(
        "http://otel.internal:4318/v1/traces\n",
        encoding="utf-8",
    )
    env_file = tmp_path / "production.env"
    env_file.write_text(
        "\n".join(
            [
                "MITRA_COMPANION_CONFIG_PROFILE=production-test",
                "MITRA_COMPANION_ENVIRONMENT=production-test",
                f"MITRA_COMPANION_DATA_ROOT={data_root}",
                f"MITRA_COMPANION_DATABASE_PATH={data_root / 'runtime.db'}",
                "MITRA_COMPANION_SQLITE_SYNCHRONOUS=NORMAL",
                f"MITRA_COMPANION_TELEMETRY_LOG_PATH={data_root / 'telemetry.jsonl'}",
                f"MITRA_COMPANION_LOG_PATH={data_root / 'production.jsonl'}",
                "MITRA_COMPANION_LOG_LEVEL=WARNING",
                "MITRA_COMPANION_LOG_TO_STDOUT=false",
                f"MITRA_COMPANION_AI_RESOLVER_URL_FILE={resolver_secret}",
                f"OTEL_EXPORTER_OTLP_ENDPOINT_FILE={otel_secret}",
                "MITRA_COMPANION_INSTANCE_ID=production-config-runtime",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MITRA_COMPANION_ENV_FILE", str(env_file))

    settings = RuntimeSettings.from_environment()
    summary = settings.production_summary()
    summary_text = json.dumps(summary)

    assert settings.production_config_profile == "production-test"
    assert settings.deployment_environment == "production-test"
    assert settings.ai_resolver_url == (
        "https://resolver.internal/runtime-analysis"
    )
    assert settings.otel_exporter_otlp_endpoint == (
        "http://otel.internal:4318/v1/traces"
    )
    assert settings.production_log_level == "WARNING"
    assert settings.production_log_to_stdout is False
    assert settings.sqlite_synchronous == "NORMAL"
    assert summary["sqlite_synchronous"] == "NORMAL"
    assert "MITRA_COMPANION_AI_RESOLVER_URL" in (
        summary["secrets"]["secret_keys_loaded_from_files"]
    )
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in (
        summary["secrets"]["secret_keys_loaded_from_files"]
    )
    assert "resolver.internal" not in summary_text
    assert "otel.internal" not in summary_text


def test_runtime_operations_api_exposes_production_mode(settings_factory):
    settings = settings_factory()
    settings.persistent_runtime_enabled = False
    settings.production_log_to_stdout = False
    app = create_app(settings)

    with TestClient(app) as client:
        startup = client.get("/api/v1/runtime/startup")
        assert startup.status_code == 200
        phase_names = {
            item["name"] for item in startup.json()["startup"]["phases"]
        }
        assert "production_configuration_loaded" in phase_names
        assert "runtime_process_started" in phase_names

        configuration = client.get("/api/v1/runtime/config").json()[
            "configuration"
        ]
        assert configuration["profile"] == "production"
        assert configuration["persistent_runtime"]["enabled"] is False
        assert "ai_resolver_url" not in json.dumps(configuration).lower()

        secrets = client.get("/api/v1/runtime/secrets").json()["secrets"]
        assert secrets["redaction"] == (
            "values are never returned by runtime APIs"
        )

        recovery = client.post(
            "/api/v1/runtime/recovery",
            json=VERSIONED,
        )
        assert recovery.status_code == 200
        assert recovery.json()["recovery"]["status"] == "recovered"

        reconcile = client.post(
            "/api/v1/runtime/instances/reconcile",
            json=VERSIONED,
        )
        assert reconcile.status_code == 200
        instances = client.get(
            "/api/v1/runtime/instances",
            params={"include_stopped": True},
        ).json()["instances"]
        assert {item["instance_id"] for item in instances}

        instance_id = instances[0]["instance_id"]
        instance = client.get(
            f"/api/v1/runtime/instances/{instance_id}"
        ).json()["instance"]
        assert instance["instance_id"] == instance_id

        restarted = client.post("/api/v1/runtime/restart", json=VERSIONED)
        assert restarted.status_code == 200
        assert restarted.json()["restart"]["status"] == "restarted"
        assert client.get("/ready").status_code == 200


def test_startup_source_reconciles_a_persisted_manifest_revision(
    settings_factory,
):
    settings = settings_factory()
    settings.persistent_runtime_enabled = False
    original = ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / "product-uniguru-runtime.json")
        .read_text(encoding="utf-8")
    )
    revised = original.model_copy(update={"product_version": "1.0.1"})

    class ManifestSource:
        def __init__(self, manifest):
            self.manifest = manifest

        def load(self):
            return [self.manifest]

    first = CompanionRuntime(settings)
    first.startup_manager.start([ManifestSource(original)])
    first.stop()

    restarted = CompanionRuntime(settings)
    try:
        report = restarted.startup_manager.start([ManifestSource(revised)])
        attachment = restarted.attachments.get(original.product_id)
        assert attachment["state"] == "ATTACHED"
        assert attachment["manifest"]["product_version"] == "1.0.1"
        source_phase = next(
            phase
            for phase in report["phases"]
            if phase["name"] == "manifest_sources_loaded"
        )
        assert source_phase["detail"]["sources"][0][
            "attachment_count"
        ] == 1
    finally:
        restarted.stop()


def test_production_policy_does_not_bootstrap_example_manifests(
    settings_factory,
):
    settings = settings_factory()
    settings.deployment_environment = "production"
    settings.production_config_profile = "production"
    settings.manifest_directory = ROOT / "contracts" / "examples"
    settings.allow_example_manifests = False
    settings.allow_simulated_manifests = False
    settings.allow_loopback_manifests = False
    settings.allow_localhost_manifests = False
    settings.require_production_bootstrap_manifests = True

    app = create_app(settings)

    with TestClient(app) as client:
        attachments = client.get("/api/v1/attachments").json()[
            "attachments"
        ]
        assert attachments == []
        startup_sources = [
            phase["detail"]["sources"]
            for phase in client.get("/api/v1/runtime/startup")
            .json()["startup"]["phases"]
            if phase["name"] == "manifest_sources_loaded"
        ][0]
        assert startup_sources == [
            {
                "source": "DirectoryManifestSourceAdapter",
                "manifest_count": 0,
                "attachment_count": 0,
            }
        ]


def test_production_attachment_api_rejects_example_and_simulated_manifests(
    settings_factory,
):
    settings = settings_factory()
    settings.deployment_environment = "production"
    settings.production_config_profile = "production"
    settings.allow_example_manifests = False
    settings.allow_simulated_manifests = False
    settings.allow_loopback_manifests = False
    settings.allow_localhost_manifests = False
    settings.require_production_bootstrap_manifests = True
    app = create_app(settings)
    nova = json.loads(
        (ROOT / "contracts" / "examples" / "product-nova.json").read_text(
            encoding="utf-8"
        )
    )
    keshav = json.loads(
        (
            ROOT / "contracts" / "examples" / "product-keshav-knowledge.json"
        ).read_text(encoding="utf-8")
    )

    with TestClient(app) as client:
        nova_response = client.post(
            "/api/v1/attachments",
            json={**VERSIONED, "manifest": nova},
        )
        assert nova_response.status_code == 422
        assert nova_response.json()["error"]["code"] == "ATTACHMENT_INVALID"

        keshav_response = client.post(
            "/api/v1/attachments",
            json={**VERSIONED, "manifest": keshav},
        )
        assert keshav_response.status_code == 422
        assert keshav_response.json()["error"]["code"] == (
            "ATTACHMENT_INVALID"
        )


def test_production_logging_writes_process_events(tmp_path):
    settings = RuntimeSettings(
        service_root=ROOT,
        data_root=tmp_path,
        database_path=tmp_path / "runtime.db",
        telemetry_log_path=tmp_path / "telemetry.jsonl",
        production_log_path=tmp_path / "production-runtime.jsonl",
        production_log_to_stdout=False,
        persistent_runtime_enabled=False,
        runtime_instance_id="production-log-runtime",
    )
    runtime = CompanionRuntime(settings)
    runtime.start()
    runtime.recover_runtime()
    runtime.stop()

    events = [
        json.loads(line)
        for line in settings.production_log_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    event_types = {event["event_type"] for event in events}
    assert "runtime.started" in event_types
    assert "runtime.recovery_completed" in event_types
    assert "runtime.stopped" in event_types
    assert {
        event["runtime_instance_id"]
        for event in events
        if "runtime_instance_id" in event
    } == {"production-log-runtime"}
