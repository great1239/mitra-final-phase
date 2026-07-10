from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
for package_root in (
    ROOT / "pratham" / "companion-runtime",
    ROOT / "pratham" / "context-runtime",
    ROOT / "pratham" / "intent-router",
    ROOT / "pratham" / "session-runtime",
    ROOT / "pratham" / "attachment-runtime",
):
    sys.path.insert(0, str(package_root))

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import ProductAttachmentManifest
from mitra_companion.runtime import CompanionRuntime


@pytest.fixture
def settings_factory(tmp_path):
    def build() -> RuntimeSettings:
        return RuntimeSettings(
            service_root=ROOT,
            data_root=tmp_path,
            database_path=tmp_path / "companion-runtime.db",
            telemetry_log_path=tmp_path / "runtime-telemetry.jsonl",
            http_timeout_seconds=0.2,
            allow_example_manifests=True,
            allow_simulated_manifests=True,
            allow_loopback_manifests=True,
            allow_localhost_manifests=True,
            require_production_bootstrap_manifests=False,
        )

    return build


@pytest.fixture
def runtime(settings_factory):
    instance = CompanionRuntime(settings_factory())
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


@pytest.fixture
def atlas_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        json.loads(
            (ROOT / "contracts" / "examples" / "product-atlas.json").read_text(
                encoding="utf-8"
            )
        )
    )


@pytest.fixture
def nova_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        json.loads(
            (ROOT / "contracts" / "examples" / "product-nova.json").read_text(
                encoding="utf-8"
            )
        )
    )
