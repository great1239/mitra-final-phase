from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for package_root in (
    ROOT / "pratham" / "companion-runtime",
    ROOT / "pratham" / "context-runtime",
    ROOT / "pratham" / "intent-router",
    ROOT / "pratham" / "session-runtime",
    ROOT / "pratham" / "attachment-runtime",
):
    sys.path.insert(0, str(package_root))


os.environ.setdefault("MITRA_COMPANION_ENVIRONMENT", "production-vercel")
os.environ.setdefault("MITRA_COMPANION_CONFIG_PROFILE", "production-vercel")
os.environ.setdefault("MITRA_COMPANION_DATA_ROOT", "/tmp/mitra-runtime")
os.environ.setdefault(
    "MITRA_COMPANION_DATABASE_PATH",
    "/tmp/mitra-runtime/companion-runtime.db",
)
os.environ.setdefault(
    "MITRA_COMPANION_TELEMETRY_LOG_PATH",
    "/tmp/mitra-runtime/runtime-telemetry.jsonl",
)
os.environ.setdefault(
    "MITRA_COMPANION_LOG_PATH",
    "/tmp/mitra-runtime/production-runtime.jsonl",
)
os.environ.setdefault(
    "MITRA_COMPANION_MANIFEST_DIRECTORY",
    str(ROOT / "contracts" / "production"),
)
os.environ.setdefault("MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS", "false")
os.environ.setdefault("MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS", "false")
os.environ.setdefault("MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS", "false")
os.environ.setdefault("MITRA_COMPANION_ALLOW_LOCALHOST_MANIFESTS", "false")
os.environ.setdefault(
    "MITRA_COMPANION_REQUIRE_PRODUCTION_BOOTSTRAP_MANIFESTS",
    "true",
)
os.environ.setdefault("MITRA_COMPANION_OTEL_ENABLED", "false")
os.environ.setdefault("MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED", "false")
os.environ.setdefault("MITRA_COMPANION_LOG_TO_STDOUT", "true")


from mitra_companion.api import create_app  # noqa: E402
from mitra_companion.config import RuntimeSettings  # noqa: E402


app = create_app(settings=RuntimeSettings.from_environment())
