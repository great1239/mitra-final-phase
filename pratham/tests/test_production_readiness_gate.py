from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_container_deployment_has_production_safety_controls():
    dockerfile = _read("Dockerfile")
    compose = _read("docker-compose.yml")

    assert "USER mitra" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "MITRA_COMPANION_ENVIRONMENT=production" in dockerfile
    assert "restart: unless-stopped" in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "pids_limit:" in compose
    assert "resources:" in compose
    assert "max-size:" in compose
    assert "MITRA_COMPANION_UVICORN_WORKERS" in compose


def test_operations_documents_and_environment_template_are_present():
    assert "MITRA_COMPANION_UVICORN_WORKERS=2" in _read(
        "deploy/production.env.example"
    )
    assert "MITRA_COMPANION_INSTANCE_ID" in _read(
        "deploy/production.env.example"
    )
    assert "Failure Response" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Multi-Instance Validation" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Rollback" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Dispatch success" in _read("docs/SLO_AND_CAPACITY.md")
    assert "Multi-instance continuity" in _read("docs/SLO_AND_CAPACITY.md")
    assert "Multiple runtime instances" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Automated production-readiness gate" in _read(
        "docs/PRODUCTION_READINESS.md"
    )


def test_runtime_instances_are_first_class_production_surface():
    assert "runtime_instance_id" in _read(
        "pratham/companion-runtime/mitra_companion/config.py"
    )
    assert "runtime_instances" in _read(
        "pratham/companion-runtime/mitra_companion/store.py"
    )
    assert "heartbeat_runtime_instance" in _read(
        "pratham/companion-runtime/mitra_companion/store.py"
    )
    assert "/api/v1/runtime/instances" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert (
        "test_multiple_runtime_instances_share_state_routes_and_dispatch"
        in _read("pratham/tests/test_production_hardening.py")
    )


def test_production_readiness_gate_script_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/production_readiness_gate.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["production_readiness_gate"] == "passed"
    assert payload["accessible_bhiv_products"] == 2
    assert payload["failures"] == []
