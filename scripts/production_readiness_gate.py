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
        ],
        "pratham/companion-runtime/mitra_companion/config.py": [
            "runtime_instance_id",
            "MITRA_COMPANION_INSTANCE_ID",
        ],
        "pratham/companion-runtime/mitra_companion/api.py": [
            "/api/v1/runtime/instances",
        ],
        "pratham/companion-runtime/mitra_companion/store.py": [
            "runtime_instances",
            "heartbeat_runtime_instance",
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
            "Rollback",
        ],
        "docs/SLO_AND_CAPACITY.md": [
            "Dispatch success",
            "Dispatch latency",
            "Attachment recovery",
            "Restart recovery",
        ],
        "docs/PRODUCTION_READINESS.md": [
            "Container runs without root privileges",
            "Multiple runtime instances",
            "Automated production-readiness gate",
            "Production Acceptance Boundary",
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
