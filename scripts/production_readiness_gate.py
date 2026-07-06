from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _contains(relative_path: str, *needles: str) -> list[str]:
    text = _read(relative_path)
    return [needle for needle in needles if needle not in text]


def main() -> int:
    required_files = [
        "Dockerfile",
        "docker-compose.yml",
        "deploy/production.env.example",
        "deploy/otel-collector-config.yaml",
        "docs/PRODUCTION_READINESS.md",
        "docs/OPERATIONS_RUNBOOK.md",
        "docs/SLO_AND_CAPACITY.md",
        "docs/PRODUCTION_HARDENING.md",
        "docs/PRODUCTION_TACTICS.md",
        "docs/PREVIOUS_SUBMISSION_REUSE.md",
        "contracts/schemas/source-scope-catalog.schema.json",
        "contracts/source-scope-catalog.json",
        "scripts/load/k6_companion_runtime.js",
        "evidence/load-testing-report.md",
        "evidence/failure-recovery-report.md",
        "evidence/metrics-sample.prom",
        "evidence/telemetry-sample.jsonl",
    ]
    failures: list[str] = []
    for relative_path in required_files:
        if not (ROOT / relative_path).exists():
            failures.append(f"missing required file: {relative_path}")

    content_checks = {
        "Dockerfile": [
            "USER mitra",
            "HEALTHCHECK",
            "PYTHONUNBUFFERED=1",
            "MITRA_COMPANION_ENVIRONMENT=production",
        ],
        "docker-compose.yml": [
            "restart: unless-stopped",
            "read_only: true",
            "no-new-privileges:true",
            "cap_drop:",
            "pids_limit:",
            "resources:",
            "max-size:",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
        ],
        "deploy/production.env.example": [
            "MITRA_COMPANION_UVICORN_WORKERS=2",
            "MITRA_COMPANION_INSTANCE_ID",
            "MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true",
            "MITRA_COMPANION_PERSISTENT_HEARTBEAT_INTERVAL_SECONDS=5",
            "MITRA_COMPANION_PERSISTENT_STALE_AFTER_SECONDS=30",
        ],
        "pratham/companion-runtime/mitra_companion/config.py": [
            "runtime_instance_id",
            "MITRA_COMPANION_INSTANCE_ID",
            "persistent_runtime_enabled",
        ],
        "pratham/companion-runtime/mitra_companion/runtime.py": [
            "PersistentRuntimeSupervisor",
            "persistent_tick",
            "source_scope_registry",
            "DISPATCH_PHASE_MODEL",
        ],
        "pratham/companion-runtime/mitra_companion/api.py": [
            "/api/v1/runtime/instances",
            "/api/v1/runtime/capability-catalog",
            "/api/v1/runtime/source-scope",
            "/api/v1/dispatches/{dispatch_id}/proof",
        ],
        "contracts/source-scope-catalog.json": [
            "persistent-production-runtime",
            "dispatch-proof-and-phase-journal",
            "downstream-command-chain-understanding",
            "future_product_intake",
        ],
        "pratham/companion-runtime/mitra_companion/store.py": [
            "runtime_instances",
            "heartbeat_runtime_instance",
            "mark_stale_runtime_instances",
            "recover_interrupted_companion_tasks",
            "dispatch_phases",
        ],
        "pratham/companion-runtime/mitra_companion/dependency_registry.py": [
            "CapabilityDependencyRegistry",
            "semantic version dependency validation",
            "public API/event/permission catalog",
        ],
        "pratham/companion-runtime/mitra_companion/proofs.py": [
            "DispatchProofBuilder",
            "mitra-dispatch-proof-v1",
            "phase_summary",
        ],
        "scripts/load/k6_companion_runtime.js": [
            "ramping-vus",
            "http_req_failed",
            "http_req_duration",
            "checks",
            "product-uniguru-runtime.json",
            "product-trade-bot-main.json",
        ],
        "docs/OPERATIONS_RUNBOOK.md": [
            "Deploy",
            "Monitor",
            "Failure Response",
            "Restart Validation",
            "persistent_runtime.supervisor_running",
            "Rollback",
        ],
        "docs/SLO_AND_CAPACITY.md": [
            "Dispatch success",
            "Dispatch latency",
            "Attachment recovery",
            "Restart recovery",
            "Persistent heartbeat freshness",
        ],
        "docs/PRODUCTION_READINESS.md": [
            "Container runs without root privileges",
            "Multiple runtime instances",
            "Persistent runtime process",
            "Automated production-readiness gate",
            "Production Acceptance Boundary",
        ],
        "docs/PREVIOUS_SUBMISSION_REUSE.md": [
            "Phase IV durable execution checkpoints",
            "Commercial Foundation public contract registry",
            "Runtime proof-bundle producer",
        ],
        "evidence/telemetry-sample.jsonl": [
            '"service":"mitra-companion-runtime"',
            '"environment":"production"',
            '"event_type":"dispatch.completed"',
        ],
    }
    for relative_path, needles in content_checks.items():
        for missing in _contains(relative_path, *needles):
            failures.append(f"{relative_path} missing: {missing}")

    report = json.loads(
        _read("evidence/bhiv-product-integration-report.json")
    )
    product_count = len(report["scope"]["bhiv_products"])
    if product_count != 2:
        failures.append(
            "expected exactly two accessible BHIV products in this workspace"
        )
    if report["product_scope_note"]["pdf_requested_real_product_count"] != 3:
        failures.append("PDF three-product constraint is not documented")

    result = {
        "production_readiness_gate": "passed" if not failures else "failed",
        "checked_files": len(required_files),
        "accessible_bhiv_products": product_count,
        "failures": failures,
    }
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
