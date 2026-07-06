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
    production_env = _read("deploy/production.env.example")
    assert "MITRA_COMPANION_UVICORN_WORKERS=2" in production_env
    assert "MITRA_COMPANION_INSTANCE_ID" in production_env
    assert "MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true" in production_env
    assert "MITRA_COMPANION_PERSISTENT_HEARTBEAT_INTERVAL_SECONDS=5" in (
        production_env
    )
    assert "Failure Response" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Multi-Instance Validation" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "persistent_runtime.supervisor_running" in _read(
        "docs/OPERATIONS_RUNBOOK.md"
    )
    assert "Rollback" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Dispatch success" in _read("docs/SLO_AND_CAPACITY.md")
    assert "Multi-instance continuity" in _read("docs/SLO_AND_CAPACITY.md")
    assert "Persistent heartbeat freshness" in _read(
        "docs/SLO_AND_CAPACITY.md"
    )
    assert "Multiple runtime instances" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Persistent runtime process" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Automated production-readiness gate" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    reuse_doc = _read("docs/PREVIOUS_SUBMISSION_REUSE.md")
    assert "Phase IV durable execution checkpoints" in reuse_doc
    assert "Commercial Foundation public contract registry" in reuse_doc
    assert "Runtime proof-bundle producer" in reuse_doc
    assert "Source scope and prior-submission feature catalog" in reuse_doc


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
    assert "mark_stale_runtime_instances" in _read(
        "pratham/companion-runtime/mitra_companion/store.py"
    )
    assert "recover_interrupted_companion_tasks" in _read(
        "pratham/companion-runtime/mitra_companion/store.py"
    )
    assert "dispatch_phases" in _read(
        "pratham/companion-runtime/mitra_companion/store.py"
    )
    assert "PersistentRuntimeSupervisor" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "persistent_tick" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "DISPATCH_PHASE_MODEL" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "/api/v1/runtime/instances" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/capability-catalog" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/source-scope" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/dispatches/{dispatch_id}/proof" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "CapabilityDependencyRegistry" in _read(
        "pratham/companion-runtime/mitra_companion/dependency_registry.py"
    )
    assert "DispatchProofBuilder" in _read(
        "pratham/companion-runtime/mitra_companion/proofs.py"
    )
    assert "SourceScopeRegistry" in _read(
        "pratham/companion-runtime/mitra_companion/source_scope.py"
    )
    assert "source-scope-catalog" in _read(
        "contracts/integration-contracts.json"
    )
    assert (
        "test_multiple_runtime_instances_share_state_routes_and_dispatch"
        in _read("pratham/tests/test_production_hardening.py")
    )
    assert (
        "test_persistent_runtime_supervisor_refreshes_heartbeat"
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
