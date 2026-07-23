from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCREENSHOTS = (
    "01-runtime-startup.png",
    "02-runtime-dashboard.png",
    "03-attached-products.png",
    "04-raj-integration.png",
    "05-ashmit-integration.png",
    "06-bucket-persistence.png",
    "07-prana-event.png",
    "08-karma-event.png",
    "09-insightflow-telemetry.png",
    "10-replay-reconstruction.png",
    "11-central-depository-export.png",
    "12-hosted-deployment.png",
    "13-production-metrics.png",
    "14-opentelemetry-traces.png",
    "15-health-endpoints.png",
    "16-multi-instance-runtime.png",
    "17-failover.png",
    "18-disaster-recovery.png",
    "19-operator-dashboard.png",
)


def _contains(relative_path: str, *required: str) -> list[str]:
    path = ROOT / relative_path
    if not path.is_file():
        return [f"{relative_path}: missing file"]
    text = path.read_text(encoding="utf-8")
    return [
        f"{relative_path}: missing {value!r}"
        for value in required
        if value not in text
    ]


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _check_screenshots() -> list[str]:
    failures: list[str] = []
    directory = ROOT / "review_packets" / "SCREENSHOTS"
    index = directory / "README.md"
    if not index.is_file():
        return ["review_packets/SCREENSHOTS/README.md: missing file"]
    index_text = index.read_text(encoding="utf-8")
    for name in REQUIRED_SCREENSHOTS:
        if name not in index_text:
            failures.append(
                f"review_packets/SCREENSHOTS/README.md: missing {name!r}"
            )
        path = directory / name
        if not path.is_file():
            failures.append(f"review_packets/SCREENSHOTS/{name}: missing file")
            continue
        dimensions = _png_dimensions(path.read_bytes())
        if dimensions is None:
            failures.append(f"review_packets/SCREENSHOTS/{name}: invalid PNG")
            continue
        width, height = dimensions
        if width < 1000 or height < 600:
            failures.append(
                f"review_packets/SCREENSHOTS/{name}: resolution "
                f"{width}x{height} is below 1000x600"
            )
    return failures


def _check_code_packet() -> list[str]:
    failures: list[str] = []
    directory = ROOT / "review_packets" / "CODE_REVIEW_PACKET"
    required_files = {
        "README.md": ("Primary implementation path",),
        "REPOSITORY_TREE.md": ("Owned Repository Tree",),
        "FILE_CHANGES.md": ("New Files", "Modified Files", "Deleted Files"),
        "TOP_FILES.md": (
            "Execution Paths",
            "Integration Files",
            "Replay Files",
            "Deployment Files",
        ),
        "DEPENDENCY_GRAPHS.md": (
            "Runtime Dependency Graph",
            "Integration Dependency Graph",
        ),
        "ARCHITECTURE_CHANGE_SUMMARY.md": ("Before", "After"),
        "IMPLEMENTATION_AREAS.md": (
            "Purpose:",
            "Why modified:",
            "Key areas:",
            "Review focus:",
            "Related tests:",
        ),
    }
    for name, required in required_files.items():
        failures.extend(
            _contains(
                f"review_packets/CODE_REVIEW_PACKET/{name}",
                *required,
            )
        )
    areas = directory / "IMPLEMENTATION_AREAS.md"
    if areas.is_file():
        for block in areas.read_text(encoding="utf-8").split("\n## ")[1:]:
            count = block.count("- Path: `")
            if count > 3:
                failures.append(
                    "review_packets/CODE_REVIEW_PACKET/"
                    f"IMPLEMENTATION_AREAS.md: area has {count} critical files"
                )
    return failures


def _check_json_contracts() -> list[str]:
    failures: list[str] = []
    for relative_path in (
        "contracts/integration-contracts.json",
        "contracts/runtime-command-chain.json",
        "contracts/source-scope-catalog.json",
        "contracts/schemas/ecosystem-execution.schema.json",
        "contracts/schemas/ecosystem-replay-validation.schema.json",
        "contracts/operational-acceptance.json",
    ):
        path = ROOT / relative_path
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{relative_path}: {type(exc).__name__}: {exc}")
    return failures


def _check_hosted_owner_configuration() -> list[str]:
    path = ROOT / "vercel.json"
    try:
        deployment = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"vercel.json: {type(exc).__name__}: {exc}"]
    configured = deployment.get("env") or {}
    required = {
        "raj": "MITRA_RAJ_WORKFLOW_BASE_URL",
        "ashmit": "MITRA_BHIV_ASHMIT_BASE_URL",
        "bucket": "MITRA_BHIV_BUCKET_BASE_URL",
        "keshav": "MITRA_BHIV_KESHAV_BASE_URL",
        "karma": "MITRA_BHIV_KARMA_BASE_URL",
        "prana": "MITRA_BHIV_PRANA_BASE_URL",
        "insightflow": "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
        "central_depository": "MITRA_CENTRAL_DEPOSITORY_BASE_URL",
    }
    return [
        f"hosted owner configuration missing: {module} ({key})"
        for module, key in required.items()
        if not configured.get(key)
    ]


def main() -> int:
    failures: list[str] = []
    blockers: list[str] = []
    checks = {
        "container": {
            "Dockerfile": (
                "USER mitra",
                "HEALTHCHECK",
                "MITRA_COMPANION_ENVIRONMENT=production",
            ),
            "docker-compose.yml": (
                "restart: unless-stopped",
                "read_only: true",
                "MITRA_COMPANION_MANIFEST_DIRECTORY: /app/contracts/production",
                "MITRA_COMPANION_REQUIRE_ECOSYSTEM_READY",
                "MITRA_COMPANION_REQUIRE_DURABLE_RUNTIME",
                "MITRA_RAJ_WORKFLOW_BASE_URL",
                "MITRA_BHIV_KESHAV_BASE_URL",
                "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
            ),
        },
        "deployment": {
            "api/index.py": (
                'ROOT / "contracts" / "production"',
                '"MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS", "false"',
                '"MITRA_COMPANION_REQUIRE_ECOSYSTEM_READY", "true"',
                '"MITRA_COMPANION_REQUIRE_DURABLE_RUNTIME", "true"',
            ),
            "vercel.json": (
                '"MITRA_COMPANION_MANIFEST_DIRECTORY": "contracts/production"',
                '"MITRA_ECOSYSTEM_TIMEOUT_SECONDS": "45"',
                '"MITRA_COMPANION_RUNTIME_STORAGE_MODE": "persistent"',
                '"MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED": "true"',
                '"MITRA_COMPANION_REQUIRE_PUBLIC_OWNER_ENDPOINTS": "true"',
            ),
            "deploy/render.persistent-runtime.yaml": (
                "healthCheckPath: /ready",
                "value: /app/contracts/production",
                "key: MITRA_RAJ_WORKFLOW_BASE_URL",
                "key: MITRA_BHIV_KESHAV_BASE_URL",
            ),
            "render.yaml": (
                "name: pratham-mitra-raj-gateway",
                "name: pratham-mitra-karma-integrity",
                "name: pratham-mitra-prana-forwarder",
                "name: pratham-mitra-insightflow-registry",
                "name: pratham-mitra-insightflow-bridge",
            ),
            "deploy/production.env.example": (
                "MITRA_RAJ_WORKFLOW_BASE_URL_FILE",
                "MITRA_RAJ_API_KEY_FILE",
                "MITRA_BHIV_KARMA_BASE_URL_FILE",
                "MITRA_BHIV_KESHAV_BASE_URL_FILE",
                "MITRA_BHIV_PRANA_BASE_URL_FILE",
                "MITRA_BHIV_INSIGHTFLOW_INGEST_URL_FILE",
            ),
        },
        "runtime": {
            "pratham/companion-runtime/mitra_companion/ecosystem.py": (
                "class PublishedEcosystemClient",
                "class EcosystemReplayLedger",
                "class EcosystemRuntime",
                "embedded_fallback",
                "keshav-diagnosis",
                "forward/karma-strict",
            ),
            "pratham/companion-runtime/mitra_companion/api.py": (
                "/api/v1/ecosystem/execute",
                "/api/v1/ecosystem/replay/validate",
                "/api/v1/ecosystem/executions/{execution_id}/recover",
                "/api/v1/runtime/deployment-parity",
            ),
            "pratham/companion-runtime/mitra_companion/deployment.py": (
                "OWNER_CONFIGURATION_MISSING",
                "OWNER_ENDPOINT_NOT_PORTABLE",
                "DURABLE_RUNTIME_STORAGE_REQUIRED",
            ),
            "pratham/companion-runtime/mitra_companion/store.py": (
                "class _PostgresConnection",
                "ecosystem_executions",
                "ecosystem_execution_stages",
                "ecosystem_stage_attempts",
            ),
        },
        "load_test": {
            "scripts/load/k6_companion_runtime.js": (
                'PROFILE === "ecosystem"',
                "/api/v1/ecosystem/execute",
                "ecosystem execution completed",
            ),
        },
        "operational_acceptance": {
            "scripts/validate_ecosystem_runtime.py": (
                "/api/v1/ecosystem/execute",
                "/api/v1/ecosystem/replay/validate",
                "process-isolated replay",
                "central-depository:exported",
                "replay:tamper-rejected",
            ),
            "contracts/operational-acceptance.json": (
                '"tradebot-nvda"',
                '"uniguru-drip-irrigation"',
                '"tradebot-product-error-keshav"',
                '"product_response_equals"',
            ),
        },
        "testing_evidence": {
            "review_packets/testing/TESTING_EVIDENCE.md": (
                "## Clean Deployment",
                "## Replay Validation",
                "## Production Validation",
                "## Failover Validation",
                "## Recovery Validation",
                "## Load Testing",
                "## Hosted Runtime Validation",
                "## Integration Validation",
                "controlled implementations",
                "no production convergence claim",
            ),
        },
        "handover": {
            "docs/TANTRA_ECOSYSTEM_CONVERGENCE.md": (
                "## Canonical Flow",
                "## Required Configuration",
                "## Deterministic Replay",
            ),
            "review_packets/REVIEW_PACKET.md": (
                "## Entry Point",
                "## Core Execution Flow",
                "## Live Runtime Flow",
                "## What Changed",
                "## Failure Cases",
                "## Production Evidence",
                "## Known Limitations",
                "## Replay Validation Summary",
            ),
        },
    }

    check_results: dict[str, str] = {}
    for group, files in checks.items():
        group_failures: list[str] = []
        for relative_path, required in files.items():
            group_failures.extend(_contains(relative_path, *required))
        failures.extend(group_failures)
        check_results[group] = "passed" if not group_failures else "failed"

    screenshot_failures = _check_screenshots()
    blockers.extend(screenshot_failures)
    check_results["screenshots"] = (
        "passed" if not screenshot_failures else "blocked"
    )

    code_packet_failures = _check_code_packet()
    failures.extend(code_packet_failures)
    check_results["code_packets"] = (
        "passed" if not code_packet_failures else "failed"
    )

    contract_failures = _check_json_contracts()
    failures.extend(contract_failures)
    if contract_failures:
        check_results["runtime"] = "failed"

    owner_blockers = _check_hosted_owner_configuration()
    blockers.extend(owner_blockers)
    check_results["owner_configuration"] = (
        "passed" if not owner_blockers else "blocked"
    )

    if failures:
        readiness = "failed"
    elif blockers:
        readiness = "blocked"
    else:
        readiness = "passed"

    result = {
        "production_readiness_gate": readiness,
        "implementation_readiness": "failed" if failures else "passed",
        "checks": check_results,
        "failures": failures,
        "blockers": blockers,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if readiness == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
