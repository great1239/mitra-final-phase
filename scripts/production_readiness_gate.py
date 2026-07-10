from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCREENSHOTS = (
    "live-dashboard.jpg",
    "runtime-startup.jpg",
    "attached-products.jpg",
    "replay-execution.jpg",
    "metrics.jpg",
    "telemetry.jpg",
    "openapi.jpg",
    "deployment.jpg",
    "health.jpg",
    "recovery.jpg",
    "failover.jpg",
    "hosted-runtime.jpg",
    "runtime-analysis.jpg",
    "production-monitoring.jpg",
)
CODE_PACKET_FIELDS = (
    "Sprint change",
    "Purpose",
    "Why modified",
    "Key implementation areas",
    "Review focus",
    "Related tests",
)
CODE_PACKET_ENTRY = re.compile(
    r"^## File: `([^`\r\n]+)`\s*$",
    re.MULTILINE,
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


def _check_screenshots() -> list[str]:
    failures: list[str] = []
    directory = ROOT / "review_packets" / "screenshots"
    for name in REQUIRED_SCREENSHOTS:
        path = directory / name
        if not path.is_file():
            failures.append(f"review_packets/screenshots/{name}: missing file")
            continue
        data = path.read_bytes()
        if len(data) < 4 or data[:2] != b"\xff\xd8":
            failures.append(f"review_packets/screenshots/{name}: invalid JPEG")
            continue
        width = height = 0
        offset = 2
        while offset + 8 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                break
            if length < 2:
                break
            offset += length
        if width < 1000 or height < 600:
            failures.append(
                "review_packets/screenshots/"
                f"{name}: resolution {width}x{height} is below 1000x600"
            )
    return failures


def _check_code_packets() -> list[str]:
    failures: list[str] = []
    directory = ROOT / "review_packets" / "code_packets"
    index = directory / "README.md"
    if not index.is_file():
        return ["review_packets/code_packets/README.md: missing file"]

    index_text = index.read_text(encoding="utf-8")
    for required in (
        "Baseline commit:",
        "only files added or modified after the baseline are listed",
        "no implementation area contains more than three critical",
    ):
        if required not in index_text:
            failures.append(
                "review_packets/code_packets/README.md: "
                f"missing {required!r}"
            )

    packets = sorted(
        path
        for path in directory.glob("*.md")
        if path.name != "README.md"
    )
    if not packets:
        failures.append("review_packets/code_packets: no area packets found")
        return failures

    root = ROOT.resolve()
    referenced_paths: set[str] = set()
    for packet in packets:
        relative_packet = packet.relative_to(ROOT).as_posix()
        text = packet.read_text(encoding="utf-8")
        matches = list(CODE_PACKET_ENTRY.finditer(text))
        if not matches:
            failures.append(f"{relative_packet}: no file entries")
            continue
        if len(matches) > 3:
            failures.append(
                f"{relative_packet}: {len(matches)} critical files exceeds 3"
            )

        for index_position, match in enumerate(matches):
            relative_path = match.group(1)
            block_end = (
                matches[index_position + 1].start()
                if index_position + 1 < len(matches)
                else len(text)
            )
            block = text[match.end() : block_end]
            for field in CODE_PACKET_FIELDS:
                if f"**{field}:**" not in block:
                    failures.append(
                        f"{relative_packet}: {relative_path} missing "
                        f"{field!r}"
                    )

            if relative_path in referenced_paths:
                failures.append(
                    f"{relative_packet}: duplicate file entry {relative_path}"
                )
            referenced_paths.add(relative_path)

            source = (ROOT / relative_path).resolve()
            try:
                source.relative_to(root)
            except ValueError:
                failures.append(
                    f"{relative_packet}: path escapes repository "
                    f"{relative_path}"
                )
                continue
            if not source.is_file():
                failures.append(
                    f"{relative_packet}: referenced file missing "
                    f"{relative_path}"
                )
    return failures


def main() -> int:
    failures: list[str] = []
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
                "no-new-privileges:true",
                "cap_drop:",
                "resources:",
                "MITRA_COMPANION_MANIFEST_DIRECTORY: /app/contracts/production",
                'MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS: "false"',
            ),
        },
        "deployment": {
            "vercel.json": (
                "api/index.py",
                '"MITRA_COMPANION_MANIFEST_DIRECTORY": "contracts/production"',
                '"MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS": "false"',
                '"MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS": "false"',
            ),
            "render.yaml": ("healthCheckPath: /ready",),
            "deploy/production.env.example": (
                "MITRA_COMPANION_CONFIG_PROFILE=production",
                "MITRA_COMPANION_SQLITE_SYNCHRONOUS=NORMAL",
                "MITRA_COMPANION_PERSISTENT_RUNTIME_ENABLED=true",
                "MITRA_COMPANION_MANIFEST_DIRECTORY=/app/contracts/production",
                "MITRA_COMPANION_ALLOW_EXAMPLE_MANIFESTS=false",
                "MITRA_COMPANION_ALLOW_SIMULATED_MANIFESTS=false",
                "MITRA_COMPANION_ALLOW_LOOPBACK_MANIFESTS=false",
                "MITRA_BHIV_KARMA_BASE_URL",
                "MITRA_BHIV_PRANA_BASE_URL",
                "MITRA_BHIV_BUCKET_BASE_URL",
                "MITRA_BHIV_INSIGHTFLOW_INGEST_URL",
            ),
        },
        "runtime": {
            "pratham/companion-runtime/mitra_companion/api.py": (
                "/health",
                "/ready",
                "/metrics",
                "/api/v1/intents/dispatch",
                "/api/v1/dispatches/{dispatch_id}/reconstruction",
                "/api/v1/runtime/depository",
                "/api/v1/runtime/recovery",
            ),
            "pratham/companion-runtime/mitra_companion/runtime.py": (
                "PersistentRuntimeSupervisor",
                "BHIVRuntimeIntegrator",
                "_publish_bhiv_convergence",
            ),
            "pratham/companion-runtime/mitra_companion/reconstruction.py": (
                "DeterministicReconstructionLedger",
            ),
        },
        "load_test": {
            "scripts/load/k6_companion_runtime.js": (
                "/api/v1/sessions",
                "/api/v1/intents/dispatch",
                'const PROFILE = (__ENV.PROFILE || "runtime")',
                'const MAX_VUS = Math.max(1, Number(__ENV.MAX_VUS || "15"))',
                "dispatch output matches input",
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
                "104 passed",
                "633/633 passed",
                "p95 latency:         803.92 ms",
                "CAPACITY LIMIT",
                "Docker was rechecked and repaired on `2026-07-10`",
                "docker compose config --quiet: passed",
                "docker compose up -d --force-recreate --wait --wait-timeout 180: healthy",
                '"uvicorn_workers": 1',
                '"passed": "superseded"',
                "ROUTING/REPLAY REQUIRES REAL ATTACHED PRODUCT",
            ),
        },
        "handover": {
            "docs/DOCUMENTATION_INDEX.md": (
                "docs/HANDOVER.md",
                "docs/CENTRAL_DEPOSITORY_HANDOVER.md",
            ),
            "docs/HANDOVER.md": (
                'python -m pip install -e ".[test]"',
                "python -m pytest",
                "docker compose build --pull",
                "scripts/validate_hosted_runtime.py",
            ),
            "docs/CENTRAL_DEPOSITORY_HANDOVER.md": (
                "GET /api/v1/runtime/depository",
                "Artifact Verification",
                "Lineage Verification",
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
    failures.extend(screenshot_failures)
    check_results["screenshots"] = (
        "passed" if not screenshot_failures else "failed"
    )

    code_packet_failures = _check_code_packets()
    failures.extend(code_packet_failures)
    check_results["code_packets"] = (
        "passed" if not code_packet_failures else "failed"
    )

    result = {
        "production_readiness_gate": "passed" if not failures else "failed",
        "checks": check_results,
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
