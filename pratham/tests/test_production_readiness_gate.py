from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


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
    assert "pids:" in compose
    assert "resources:" in compose
    assert "max-size:" in compose
    assert "MITRA_COMPANION_UVICORN_WORKERS" in compose
    assert "MITRA_COMPANION_MANIFEST_DIRECTORY: /app/contracts/production" in (
        compose
    )
    assert 'MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS: "false"' in compose


def test_operations_documents_and_environment_template_are_present():
    production_env = _read("deploy/production.env.example")
    assert "MITRA_COMPANION_CONFIG_PROFILE=production" in production_env
    assert "MITRA_COMPANION_ENV_FILE" in production_env
    assert "MITRA_COMPANION_LOG_PATH=/data/production-runtime.jsonl" in (
        production_env
    )
    assert "MITRA_COMPANION_LOG_LEVEL=INFO" in production_env
    assert "MITRA_COMPANION_SECRETS_DIR" in production_env
    assert "MITRA_COMPANION_UVICORN_WORKERS=1" in production_env
    assert "MITRA_COMPANION_INSTANCE_ID" in production_env
    assert "MITRA_COMPANION_SQLITE_SYNCHRONOUS=NORMAL" in production_env
    assert "MITRA_COMPANION_MANIFEST_DIRECTORY=/app/contracts/production" in (
        production_env
    )
    assert "MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS=false" in production_env
    assert "MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS=false" in production_env
    assert "MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS=false" in production_env
    assert "MITRA_RAJ_WORKFLOW_BASE_URL_FILE" in production_env
    assert "MITRA_RAJ_API_KEY_FILE" in production_env
    assert "MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true" in production_env
    assert "MITRA_COMPANION_PERSISTENT_HEARTBEAT_INTERVAL_SECONDS=5" in (
        production_env
    )
    assert "Failure Response" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Multi-Instance Validation" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "Recovery And Instance Reconciliation" in _read(
        "docs/OPERATIONS_RUNBOOK.md"
    )
    assert "/api/v1/runtime/restart" in _read("docs/OPERATIONS_RUNBOOK.md")
    assert "/api/v1/runtime/recovery" in _read("docs/OPERATIONS_RUNBOOK.md")
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
    assert "Runtime startup manager" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Persistent runtime process" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Production configuration loading" in _read(
        "docs/PRODUCTION_READINESS.md"
    )
    assert "Production secrets management" in _read(
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


def test_public_module_blueprint_is_portable_and_fail_closed():
    blueprint = yaml.safe_load(
        _read("render.yaml")
    )
    services = {
        service["name"]: service
        for service in blueprint["services"]
    }
    assert set(services) == {
        "pratham-mitra-raj-gateway",
        "pratham-mitra-karma-integrity",
        "pratham-mitra-prana-forwarder",
        "pratham-mitra-insightflow-registry",
        "pratham-mitra-insightflow-bridge",
    }
    assert all(service["plan"] == "free" for service in services.values())
    assert all(service["runtime"] == "docker" for service in services.values())
    assert all(
        service["repo"]
        == "https://github.com/great1239/mitra-final-phase"
        for service in services.values()
    )

    rendered = _read("render.yaml")
    assert "localhost" not in rendered
    assert "127.0.0.1" not in rendered
    assert "KARMA_DATABASE_URL" in rendered
    assert "sync: false" in rendered
    assert "integration_services/insightflow-owner.Dockerfile" in rendered

    bridge_env = {
        item["key"]: item
        for item in services[
            "pratham-mitra-insightflow-bridge"
        ]["envVars"]
    }
    assert bridge_env["INSIGHTFLOW_REGISTRY_API_KEY"]["fromService"] == {
        "type": "web",
        "name": "pratham-mitra-insightflow-registry",
        "envVarKey": "INSIGHTFLOW_REGISTRY_API_KEY",
    }

    prana_env = {
        item["key"]: item
        for item in services[
            "pratham-mitra-prana-forwarder"
        ]["envVars"]
    }
    assert prana_env["PRANA_TARGET_API_KEY"]["fromService"] == {
        "type": "web",
        "name": "pratham-mitra-insightflow-bridge",
        "envVarKey": "INSIGHTFLOW_BRIDGE_API_KEY",
    }


def test_vercel_runtime_uses_public_modules_without_committed_secrets():
    deployment = json.loads(_read("vercel.json"))
    environment = deployment["env"]

    assert environment["MITRA_RAJ_WORKFLOW_BASE_URL"] == (
        "https://pratham-mitra-raj-gateway.onrender.com"
    )
    assert environment["MITRA_BHIV_KARMA_BASE_URL"] == (
        "https://pratham-mitra-karma-integrity.onrender.com"
    )
    assert environment["MITRA_BHIV_PRANA_BASE_URL"] == (
        "https://pratham-mitra-prana-forwarder.onrender.com"
    )
    assert environment["MITRA_BHIV_INSIGHTFLOW_INGEST_URL"] == (
        "https://pratham-mitra-insightflow-bridge.onrender.com/"
        "ingest/execution"
    )
    assert environment["MITRA_COMPANION_RUNTIME_STORAGE_MODE"] == "persistent"
    assert environment["MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED"] == "true"
    assert all("localhost" not in value for value in environment.values())
    assert all("127.0.0.1" not in value for value in environment.values())
    assert "MITRA_COMPANION_DATABASE_URL" not in environment
    assert "MITRA_RAJ_API_KEY" not in environment
    assert "MITRA_BHIV_ASHMIT_API_KEY" not in environment
    assert "MITRA_BHIV_INSIGHTFLOW_API_KEY" not in environment


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
    assert "create_product_exchange" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "record_product_exchange_receipt" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "RuntimeStartupManager" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "RuntimeStartupManager" in _read(
        "pratham/companion-runtime/mitra_companion/startup.py"
    )
    assert "configure_production_logging" in _read(
        "pratham/companion-runtime/mitra_companion/production_logging.py"
    )
    assert "DISPATCH_PHASE_MODEL" in _read(
        "pratham/companion-runtime/mitra_companion/runtime.py"
    )
    assert "/api/v1/runtime/startup" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/restart" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/recovery" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/config" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/secrets" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/runtime/instances" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/products/connect" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/product-exchanges" in _read(
        "pratham/companion-runtime/mitra_companion/api.py"
    )
    assert "/api/v1/products/{product_id}/exchange-inbox" in _read(
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


def test_documentation_handover_contains_clean_rebuild_and_depository_protocol():
    index = _read("docs/DOCUMENTATION_INDEX.md")
    handover = _read("docs/HANDOVER.md")
    depository = _read("docs/CENTRAL_DEPOSITORY_HANDOVER.md")
    review_packet = _read("review_packets/REVIEW_PACKET.md")

    assert "docs/HANDOVER.md" in index
    assert "docs/CENTRAL_DEPOSITORY_HANDOVER.md" in index
    assert 'python -m pip install -e ".[test]"' in handover
    assert "python -m pytest" in handover
    assert "docker compose build --pull" in handover
    assert "scripts/validate_hosted_runtime.py" in handover
    assert "scripts/validate_ecosystem_runtime.py" in handover
    assert "contracts/operational-acceptance.json" in handover
    assert "total_assertions=425" in handover
    assert "MITRA_COMPANION_DATABASE_URL" in handover
    assert "shared PostgreSQL" in handover
    assert "GET /api/v1/runtime/depository" in depository
    assert "subject_type=dispatch&subject_id={dispatch_id}" in depository
    assert 'separators=(",", ":")' in depository
    assert "Lineage Verification" in depository
    assert "An HTTP 200 alone is not acceptance." in depository
    for heading in (
        "Entry Point",
        "Core Execution Flow",
        "Live Runtime Flow",
        "What Changed",
        "Failure Cases",
        "Production Evidence",
        "Known Limitations",
        "Replay Validation Summary",
    ):
        assert f"## {heading}" in review_packet


def test_code_packets_are_bounded_and_complete():
    packet_directory = ROOT / "review_packets" / "code_packets"
    packet_index = _read("review_packets/code_packets/README.md")
    assert "1baaadf313f4d8a91018321db1317c5c6b385ccc" in packet_index
    assert "only files added or modified after the baseline are listed" in (
        packet_index
    )

    packets = sorted(
        path
        for path in packet_directory.glob("*.md")
        if path.name != "README.md"
    )
    assert packets
    referenced_paths: set[str] = set()
    required_fields = (
        "Sprint change",
        "Purpose",
        "Why modified",
        "Key implementation areas",
        "Review focus",
        "Related tests",
    )
    for packet in packets:
        text = packet.read_text(encoding="utf-8")
        entries = list(
            re.finditer(
                r"^## File: `([^`\r\n]+)`\s*$",
                text,
                re.MULTILINE,
            )
        )
        assert 1 <= len(entries) <= 3
        for position, entry in enumerate(entries):
            relative_path = entry.group(1)
            block_end = (
                entries[position + 1].start()
                if position + 1 < len(entries)
                else len(text)
            )
            block = text[entry.end() : block_end]
            assert relative_path not in referenced_paths
            referenced_paths.add(relative_path)
            assert (ROOT / relative_path).is_file()
            for field in required_fields:
                assert f"**{field}:**" in block


def test_testing_evidence_records_all_executed_acceptance_paths():
    evidence = _read("review_packets/testing/TESTING_EVIDENCE.md")
    for heading in (
        "Clean Deployment",
        "Replay Validation",
        "Production Validation",
        "Failover Validation",
        "Recovery Validation",
        "Load Testing",
        "Hosted Runtime Validation",
        "Integration Validation",
    ):
        assert f"## {heading}" in evidence
    assert "15 passed" in evidence
    assert "controlled implementations" in evidence
    assert "database_reads=0" in evidence
    assert "live_service_calls=0" in evidence
    assert "no production convergence claim" in evidence
    assert "156 passed" in evidence
    assert "--validate-package /data/operational-acceptance" in evidence
    assert "144 passed" in evidence
    assert "23 / 23 / 0" not in evidence
    assert "9097.026 ms" not in evidence


def test_production_readiness_gate_blocks_only_on_missing_live_evidence():
    completed = subprocess.run(
        [sys.executable, "scripts/production_readiness_gate.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["production_readiness_gate"] == "blocked"
    assert payload["implementation_readiness"] == "passed"
    assert set(payload["checks"]) == {
        "container",
        "code_packets",
        "deployment",
        "runtime",
        "load_test",
        "operational_acceptance",
        "handover",
        "screenshots",
        "testing_evidence",
        "owner_configuration",
    }
    assert payload["failures"] == []
    assert payload["checks"]["screenshots"] == "blocked"
    assert payload["checks"]["owner_configuration"] == "passed"
    assert all(
        status == "passed"
        for name, status in payload["checks"].items()
        if name != "screenshots"
    )
    assert payload["blockers"]
    assert all("SCREENSHOTS" in item for item in payload["blockers"])
