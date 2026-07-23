from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "contracts" / "operational-acceptance.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8190"
LOCALHOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
VERSIONS = {
    "schema_version": "1.0.0",
    "contract_version": "1.0.0",
    "runtime_version": "1.0.0",
    "compatibility_version": "mitra-companion-1",
}
STAGE_ORDER = [
    "capability-selection",
    "dependency-preflight",
    "raj-execution",
    "keshav-diagnosis",
    "ashmit-provenance",
    "bucket-truth",
    "karma-integrity",
    "prana-forwarding",
    "insightflow-telemetry",
    "central-depository",
]
EXECUTION_OPERATIONS = {
    "raj.workflow-execute",
    "ashmit.mitra-evaluate",
    "bucket.latest-hash",
    "bucket.artifact",
    "bucket.get-artifact",
    "bucket.validate-replay",
    "karma.health-head",
    "karma.append-bucket-artifact",
    "prana.karma-strict",
    "prana.core",
    "insightflow.execution-trace",
    "central-depository.latest-hash",
    "central-depository.artifact",
    "central-depository.get-artifact",
    "central-depository.validate-replay",
}
PREFLIGHT_MODULES = {
    "raj",
    "ashmit",
    "bucket",
    "keshav",
    "prana",
    "central_depository",
}


class ValidationFailure(RuntimeError):
    pass


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _record(
    checks: list[dict[str, Any]],
    name: str,
    condition: bool,
    observed: Any = None,
) -> None:
    item = {"check": name, "passed": bool(condition)}
    if observed is not None:
        item["observed"] = observed
    checks.append(item)
    if not condition:
        raise ValidationFailure(f"{name} failed; observed={observed!r}")


def _path_get(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def _request_json(
    client: httpx.Client,
    method: str,
    base_url: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    expected_status: set[int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    started = time.perf_counter()
    response = client.request(method, url, json=payload, params=params)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    allowed = expected_status or set(range(200, 300))
    if response.status_code not in allowed:
        sample = response.text[:1000]
        raise ValidationFailure(
            f"{method} {path} returned HTTP {response.status_code}: {sample}"
        )
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise ValidationFailure(
            f"{method} {path} did not return JSON"
        ) from exc
    if not isinstance(body, dict):
        raise ValidationFailure(f"{method} {path} returned a non-object body")
    return body, {
        "method": method,
        "path": path,
        "http_status": response.status_code,
        "latency_ms": latency_ms,
        "response_sha256": hashlib.sha256(response.content).hexdigest(),
    }


def _execution_operations(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for stage in stages:
        response = stage.get("response")
        if not isinstance(response, dict):
            continue
        stage_operations = response.get("operations")
        if isinstance(stage_operations, list):
            operations.extend(
                item for item in stage_operations if isinstance(item, dict)
            )
            continue
        operation = response.get("operation")
        if isinstance(operation, dict):
            operations.append(operation)
    return operations


def _validate_owner_operation(
    checks: list[dict[str, Any]],
    operation: dict[str, Any],
    prefix: str,
) -> None:
    name = str(operation.get("operation"))
    status = operation.get("http_status")
    _record(checks, f"{prefix}:{name}:http-2xx", isinstance(status, int) and 200 <= status < 300, status)
    error = operation.get("error")
    _record(
        checks,
        f"{prefix}:{name}:no-error",
        error is None or error == "",
        error,
    )
    _record(checks, f"{prefix}:{name}:response-hash", _is_sha256(operation.get("response_sha256")), operation.get("response_sha256"))
    if (
        operation.get("method") in {"POST", "PUT", "PATCH"}
        and operation.get("request_body_utf8") is not None
    ):
        _record(checks, f"{prefix}:{name}:request-hash", _is_sha256(operation.get("request_sha256")), operation.get("request_sha256"))


def _isolated_replay(
    package: dict[str, Any],
    timeout: float,
    *,
    expected_status: str = "verified",
) -> dict[str, Any]:
    code = """
import json
import sys
from mitra_companion.ecosystem import EcosystemReplayLedger

package = json.load(sys.stdin)
result = EcosystemReplayLedger.validate(package)
summary = {
    "status": result.get("status"),
    "deterministic": result.get("deterministic"),
    "clean_state": result.get("clean_state"),
    "database_reads": result.get("database_reads"),
    "live_service_calls": result.get("live_service_calls"),
    "check_count": result.get("check_count"),
    "failed_check_count": result.get("failed_check_count"),
    "reconstructed_execution_matches": (
        result.get("reconstructed_execution")
        == package.get("reconstructed_execution")
    ),
}
print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", code],
        input=json.dumps(package, ensure_ascii=False, separators=(",", ":")),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if process.returncode != 0:
        raise ValidationFailure(
            "process-isolated replay failed: "
            + (process.stderr.strip() or process.stdout.strip())[:1000]
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationFailure(
            "process-isolated replay returned invalid JSON"
        ) from exc
    if result.get("status") != expected_status:
        raise ValidationFailure(
            "process-isolated replay returned "
            f"{result.get('status')!r}; expected {expected_status!r}"
        )
    result["process_isolated"] = True
    result["python_isolated_mode"] = True
    result["expected_status"] = expected_status
    return result


def _mutate_recorded_response(package: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(package)
    for component in mutated.get("components") or []:
        if component.get("name") != "raj-execution":
            continue
        payload = component.get("payload")
        response = payload.get("response") if isinstance(payload, dict) else None
        if isinstance(response, dict):
            response["status"] = "operational-acceptance-tamper"
            return mutated
    raise ValidationFailure("replay package has no mutable Raj response component")


def _write_package(
    package_directory: Path | None,
    case_id: str,
    execution_id: str,
    package: dict[str, Any],
) -> str | None:
    if package_directory is None:
        return None
    package_directory.mkdir(parents=True, exist_ok=True)
    target = package_directory / f"{case_id}-{execution_id}.replay.json"
    target.write_text(
        json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(target.resolve())


def _validate_case(
    client: httpx.Client,
    base_url: str,
    case: dict[str, Any],
    *,
    package_directory: Path | None,
    replay_timeout: float,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    checks: list[dict[str, Any]] = []
    api_calls: list[dict[str, Any]] = []
    expected = case.get("expected") or {}
    request = {
        **VERSIONS,
        "actor_id": "operational-acceptance",
        "client_type": "standalone",
        "workspace_id": "clean-room-acceptance",
        "message": case["message"],
        "assignment": case.get("assignment"),
        "payload": case.get("payload") or {},
        "idempotency_key": f"acceptance-{case_id}-{time.time_ns()}",
        "metadata": {"validation_case": case_id},
    }
    for selector in ("product_id", "capability_id"):
        if case.get(selector):
            request[selector] = case[selector]

    body, call = _request_json(
        client,
        "POST",
        base_url,
        "/api/v1/ecosystem/execute",
        payload=request,
        expected_status={201},
    )
    api_calls.append(call)
    result = body.get("ecosystem")
    _record(checks, "response:ecosystem-object", isinstance(result, dict))
    assert isinstance(result, dict)
    execution = result.get("execution")
    stages = result.get("stages")
    _record(checks, "execution:object", isinstance(execution, dict))
    _record(checks, "execution:completed", execution.get("status") == "COMPLETED", execution.get("status"))
    _record(checks, "execution:trace-hash", _is_sha256(execution.get("trace_id")), execution.get("trace_id"))
    _record(checks, "stages:count", isinstance(stages, list) and len(stages) == len(STAGE_ORDER), len(stages) if isinstance(stages, list) else None)
    assert isinstance(stages, list)
    _record(checks, "stages:order", [item.get("stage_name") for item in stages] == STAGE_ORDER, [item.get("stage_name") for item in stages])
    _record(checks, "stages:completed", all(item.get("status") == "COMPLETED" for item in stages))
    _record(checks, "stages:response-bearing", all(isinstance(item.get("response"), dict) for item in stages))
    _record(checks, "stages:immutable-artifacts", all(_is_sha256(item.get("artifact_hash")) for item in stages))

    by_stage = {item["stage_name"]: item for item in stages}
    selected = by_stage["capability-selection"]["response"]["capability_contract"]
    _record(checks, "selection:product", _path_get(selected, "product.product_id") == expected.get("product_id"), _path_get(selected, "product.product_id"))
    _record(checks, "selection:capability", _path_get(selected, "capability.capability_id") == expected.get("capability_id"), _path_get(selected, "capability.capability_id"))
    _record(checks, "selection:intent", _path_get(selected, "intent.intent_id") == expected.get("intent_id"), _path_get(selected, "intent.intent_id"))

    preflight = by_stage["dependency-preflight"]["response"]
    preflight_checks = preflight.get("checks") or []
    _record(checks, "preflight:healthy", preflight.get("status") == "healthy", preflight.get("status"))
    _record(checks, "preflight:module-set", {item.get("module") for item in preflight_checks} == PREFLIGHT_MODULES, sorted(item.get("module") for item in preflight_checks))
    for operation in preflight_checks:
        _validate_owner_operation(checks, operation, "preflight")

    operations = _execution_operations(stages)
    operation_names = {str(item.get("operation")) for item in operations}
    expected_product_success = expected.get("product_success", True) is True
    expected_operations = set(EXECUTION_OPERATIONS)
    if not expected_product_success:
        expected_operations.add("keshav.analyze")
    _record(checks, "owner-operations:count", len(operations) == len(expected_operations), len(operations))
    _record(checks, "owner-operations:complete-set", operation_names == expected_operations, sorted(operation_names))
    for operation in operations:
        _validate_owner_operation(checks, operation, "execution")

    trace_id = execution["trace_id"]
    _record(checks, "stages:trace-continuity", all(item["response"].get("trace_id") == trace_id for item in stages))
    raj = by_stage["raj-execution"]["response"]
    product_execution = raj.get("execution") or {}
    product_response = product_execution.get("product_response")
    expected_raj_status = "executed" if expected_product_success else "product_error"
    _record(checks, "raj:executed", raj.get("status") == expected_raj_status, raj.get("status"))
    _record(checks, "raj:product-success", product_execution.get("success") is expected_product_success, product_execution.get("success"))
    _record(checks, "raj:trace-continuity", product_execution.get("trace_id") == trace_id, product_execution.get("trace_id"))
    if expected_product_success:
        _record(checks, "raj:product-response", isinstance(product_response, dict), type(product_response).__name__)
    else:
        product_error = product_execution.get("error") or {}
        _record(checks, "raj:typed-product-error", isinstance(product_error, dict) and bool(product_error.get("type")), product_error)
        if expected.get("product_error_type"):
            _record(checks, "raj:product-error-type", product_error.get("type") == expected["product_error_type"], product_error.get("type"))
    for path in expected.get("required_product_response_paths") or []:
        _record(checks, f"product-response:path:{path}", _path_get(product_response, path) is not None)
    for path, value in (expected.get("product_response_equals") or {}).items():
        _record(checks, f"product-response:equals:{path}", _path_get(product_response, path) == value, _path_get(product_response, path))

    keshav = by_stage["keshav-diagnosis"]["response"]
    _record(checks, "keshav:trace-continuity", keshav.get("trace_id") == trace_id, keshav.get("trace_id"))
    _record(checks, "keshav:conditional-invocation", keshav.get("invoked") is (not expected_product_success), keshav.get("invoked"))
    if expected_product_success:
        _record(checks, "keshav:success-bypass", keshav.get("status") == "skipped", keshav.get("status"))
        _record(checks, "keshav:no-owner-call", keshav.get("operation") is None)
    else:
        diagnosis = keshav.get("diagnosis") or {}
        _record(checks, "keshav:diagnosed", keshav.get("status") == "diagnosed", keshav.get("status"))
        _record(checks, "keshav:execution-continuity", diagnosis.get("execution_id") == execution.get("execution_id"), diagnosis.get("execution_id"))
        _record(checks, "keshav:resolution-proposed", str(diagnosis.get("resolution_signal") or "").startswith("UNBLOCK_DEPENDENCY:"), diagnosis.get("resolution_signal"))
        _record(checks, "keshav:no-execution-authority", "Mitra does not authorize or execute" in str(keshav.get("authority") or ""), keshav.get("authority"))

    ashmit = by_stage["ashmit-provenance"]["response"]
    _record(checks, "ashmit:recorded", ashmit.get("status") == "recorded", ashmit.get("status"))
    _record(checks, "ashmit:accepted-decision", ashmit.get("decision") in {"ALLOW", "FLAG"}, ashmit.get("decision"))
    _record(checks, "ashmit:mongo-reference", _path_get(ashmit, "bucket_log_reference.backend") == "mongodb", _path_get(ashmit, "bucket_log_reference.backend"))

    bucket = by_stage["bucket-truth"]["response"]
    karma = by_stage["karma-integrity"]["response"]
    prana = by_stage["prana-forwarding"]["response"]
    insight = by_stage["insightflow-telemetry"]["response"]
    central = by_stage["central-depository"]["response"]
    _record(checks, "bucket:stored", bucket.get("status") == "stored", bucket.get("status"))
    _record(checks, "karma:appended", karma.get("status") == "appended", karma.get("status"))
    _record(checks, "prana:forwarded", prana.get("status") == "forwarded", prana.get("status"))
    _record(checks, "prana:strict-byte-hash", prana.get("strict_bytes_sha256") == karma.get("request_sha256"), prana.get("strict_bytes_sha256"))
    _record(checks, "insightflow:observed", insight.get("status") == "observed", insight.get("status"))
    _record(checks, "central-depository:exported", central.get("status") == "exported", central.get("status"))
    _record(checks, "central-depository:package-hash", _is_sha256(central.get("package_hash")), central.get("package_hash"))

    duplicate_body, call = _request_json(
        client,
        "POST",
        base_url,
        "/api/v1/ecosystem/execute",
        payload=request,
        expected_status={201},
    )
    api_calls.append(call)
    duplicate = duplicate_body.get("ecosystem") or {}
    _record(checks, "idempotency:same-execution", _path_get(duplicate, "execution.execution_id") == execution.get("execution_id"), _path_get(duplicate, "execution.execution_id"))
    _record(checks, "idempotency:no-new-attempts", len(duplicate.get("attempts") or []) == len(result.get("attempts") or []), len(duplicate.get("attempts") or []))

    execution_id = execution["execution_id"]
    details_body, call = _request_json(client, "GET", base_url, f"/api/v1/ecosystem/executions/{execution_id}")
    api_calls.append(call)
    details = details_body.get("ecosystem") or {}
    _record(checks, "details:execution-match", _path_get(details, "execution.execution_id") == execution_id)
    _record(checks, "details:stage-artifacts-match", [item.get("artifact_hash") for item in details.get("stages") or []] == [item.get("artifact_hash") for item in stages])

    replay_body, call = _request_json(client, "GET", base_url, f"/api/v1/ecosystem/executions/{execution_id}/replay")
    api_calls.append(call)
    replay = replay_body.get("replay") or {}
    package = replay.get("package")
    validation = replay.get("validation") or {}
    _record(checks, "replay:package", isinstance(package, dict))
    assert isinstance(package, dict)
    _record(checks, "replay:package-hash", package.get("package_hash") == execution.get("replay_package_hash"), package.get("package_hash"))
    _record(checks, "replay:component-count", len(package.get("components") or []) == len(STAGE_ORDER) + 1, len(package.get("components") or []))
    _record(checks, "replay:verified", validation.get("status") == "verified", validation.get("status"))
    _record(checks, "replay:deterministic", validation.get("deterministic") is True)
    _record(checks, "replay:clean-state", validation.get("clean_state") is True)
    _record(checks, "replay:no-database-reads", validation.get("database_reads") == 0, validation.get("database_reads"))
    _record(checks, "replay:no-live-calls", validation.get("live_service_calls") == 0, validation.get("live_service_calls"))
    request_component = next(
        (
            item
            for item in package.get("components") or []
            if item.get("name") == "request"
        ),
        {},
    )
    recorded_message = _path_get(
        request_component,
        "payload.request.message",
    )
    _record(
        checks,
        "replay:recorded-input",
        recorded_message == case["message"],
        recorded_message,
    )
    _record(
        checks,
        "replay:reconstructed-request-hash",
        _path_get(validation, "reconstructed_execution.request_hash")
        == execution.get("request_hash"),
        _path_get(validation, "reconstructed_execution.request_hash"),
    )

    validate_body, call = _request_json(
        client,
        "POST",
        base_url,
        "/api/v1/ecosystem/replay/validate",
        payload={**VERSIONS, "package": package},
    )
    api_calls.append(call)
    submitted_validation = validate_body.get("replay") or {}
    _record(checks, "replay:api-round-trip", submitted_validation.get("status") == "verified", submitted_validation.get("status"))
    _record(checks, "replay:api-reconstruction-match", submitted_validation.get("reconstructed_execution") == package.get("reconstructed_execution"))

    tampered_body, call = _request_json(
        client,
        "POST",
        base_url,
        "/api/v1/ecosystem/replay/validate",
        payload={**VERSIONS, "package": _mutate_recorded_response(package)},
    )
    api_calls.append(call)
    tampered = tampered_body.get("replay") or {}
    _record(checks, "replay:tamper-rejected", tampered.get("status") == "failed", tampered.get("status"))
    _record(checks, "replay:tamper-failures-recorded", int(tampered.get("failed_check_count") or 0) > 0, tampered.get("failed_check_count"))

    isolated = _isolated_replay(package, replay_timeout)
    _record(checks, "replay:isolated-verified", isolated.get("status") == "verified", isolated.get("status"))
    _record(checks, "replay:isolated-clean-state", isolated.get("clean_state") is True)
    _record(checks, "replay:isolated-no-database", isolated.get("database_reads") == 0, isolated.get("database_reads"))
    _record(checks, "replay:isolated-no-network", isolated.get("live_service_calls") == 0, isolated.get("live_service_calls"))
    _record(checks, "replay:isolated-output-match", isolated.get("reconstructed_execution_matches") is True)

    depository_body, call = _request_json(
        client,
        "GET",
        base_url,
        "/api/v1/runtime/depository",
        params={
            "subject_type": "ecosystem_execution",
            "subject_id": execution_id,
        },
    )
    api_calls.append(call)
    depository = depository_body.get("depository") or {}
    artifacts = depository.get("artifacts") or []
    lineage = depository.get("lineage") or []
    stage_hashes = {item["artifact_hash"] for item in stages}
    stored_stage_hashes = {
        item.get("artifact_hash")
        for item in artifacts
        if item.get("artifact_type") == "tantra.ecosystem-stage.v1"
    }
    _record(checks, "depository:artifact-count", len(artifacts) == len(STAGE_ORDER) + 1, len(artifacts))
    _record(checks, "depository:lineage-count", len(lineage) == len(artifacts), len(lineage))
    _record(checks, "depository:all-stage-artifacts", stage_hashes == stored_stage_hashes)
    _record(checks, "depository:one-replay-artifact", sum(item.get("artifact_type") == "tantra.ecosystem-replay.v1" for item in artifacts) == 1)
    _record(checks, "depository:subject-isolation", all(item.get("subject_type") == "ecosystem_execution" and item.get("subject_id") == execution_id for item in lineage))
    _record(checks, "depository:sequence-continuity", sorted(item.get("sequence") for item in lineage) == list(range(1, len(lineage) + 1)))
    _record(checks, "depository:lineage-hashes", all(_is_sha256(item.get("chain_hash")) for item in lineage))

    telemetry_body, call = _request_json(
        client,
        "GET",
        base_url,
        "/api/v1/runtime/telemetry",
        params={"limit": 500},
    )
    api_calls.append(call)
    events = [
        event
        for event in telemetry_body.get("events") or []
        if event.get("execution_id") == execution_id
    ]
    _record(checks, "telemetry:stage-events", sum(event.get("event_type") == "ecosystem.stage_completed" for event in events) == len(STAGE_ORDER), [event.get("event_type") for event in events])
    _record(checks, "telemetry:completion-event", sum(event.get("event_type") == "ecosystem.execution_completed" for event in events) == 1)

    package_path = _write_package(
        package_directory,
        case_id,
        execution_id,
        package,
    )
    return {
        "case_id": case_id,
        "passed": True,
        "execution_id": execution_id,
        "trace_id": trace_id,
        "selected_product": _path_get(selected, "product.product_id"),
        "selected_capability": _path_get(selected, "capability.capability_id"),
        "selected_intent": _path_get(selected, "intent.intent_id"),
        "stage_count": len(stages),
        "preflight_response_count": len(preflight_checks),
        "owner_operation_response_count": len(operations),
        "product_execution_status": raj.get("status"),
        "keshav": {
            "status": keshav.get("status"),
            "invoked": keshav.get("invoked"),
            "resolution_signal": _path_get(
                keshav,
                "diagnosis.resolution_signal",
            ),
        },
        "replay": {
            "package_hash": package.get("package_hash"),
            "component_count": len(package.get("components") or []),
            "check_count": validation.get("check_count"),
            "database_reads": validation.get("database_reads"),
            "live_service_calls": validation.get("live_service_calls"),
            "tamper_rejected": tampered.get("status") == "failed",
            "process_isolated": isolated,
        },
        "depository": {
            "artifact_count": len(artifacts),
            "lineage_count": len(lineage),
            "central_package_hash": central.get("package_hash"),
        },
        "product_response_hash": _canonical_sha256(product_response),
        "replay_package_path": package_path,
        "api_calls": api_calls,
        "check_count": len(checks),
        "checks": checks,
    }


def _load_cases(path: Path, selected: set[str]) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValidationFailure(f"{path} contains no acceptance cases")
    chosen = [case for case in cases if not selected or case.get("case_id") in selected]
    if not chosen:
        raise ValidationFailure("none of the requested acceptance cases exist")
    return chosen


def _package_paths(inputs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for value in inputs:
        resolved = value.resolve()
        if resolved.is_dir():
            paths.extend(sorted(resolved.glob("*.replay.json")))
        elif resolved.is_file():
            paths.append(resolved)
        else:
            raise ValidationFailure(f"replay package path is missing: {value}")
    unique = list(dict.fromkeys(paths))
    if not unique:
        raise ValidationFailure("no replay package files were found")
    return unique


def _validate_offline_packages(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {
        "validation_type": "mitra-offline-replay-package-acceptance",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": False,
        "packages": [],
    }
    try:
        for path in _package_paths(args.validate_package):
            raw = path.read_bytes()
            package = json.loads(raw)
            if not isinstance(package, dict):
                raise ValidationFailure(f"{path} does not contain a JSON object")
            validation = _isolated_replay(
                package,
                args.replay_timeout,
            )
            tamper_validation = _isolated_replay(
                _mutate_recorded_response(package),
                args.replay_timeout,
                expected_status="failed",
            )
            report["packages"].append(
                {
                    "path": str(path),
                    "file_sha256": hashlib.sha256(raw).hexdigest(),
                    "package_hash": package.get("package_hash"),
                    "component_count": len(package.get("components") or []),
                    "validation": validation,
                    "tamper_validation": tamper_validation,
                }
            )
        report.update(
            {
                "passed": True,
                "package_count": len(report["packages"]),
                "completed_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
            }
        )
    except Exception as exc:
        report.update(
            {
                "completed_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute real Mitra owner-contract workflows and validate their "
            "responses, replay, telemetry, and depository lineage."
        )
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default=os.getenv("MITRA_ECOSYSTEM_RUNTIME_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--replay-timeout", type=float, default=90.0)
    parser.add_argument("--package-directory", type=Path)
    parser.add_argument(
        "--validate-package",
        action="append",
        type=Path,
        default=[],
        help="validate one replay file or every *.replay.json file in a directory",
    )
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--require-independent-central-depository",
        action="store_true",
        help="Fail when Central Depository and Bucket use the same endpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.validate_package:
        return _validate_offline_packages(args)
    base_url = args.base_url.rstrip("/")
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report: dict[str, Any] = {
        "validation_type": "mitra-live-ecosystem-operational-acceptance",
        "started_at": started_at,
        "base_url": base_url,
        "passed": False,
        "cases": [],
    }
    try:
        host = (urlparse(base_url).hostname or "").lower()
        https_observed = base_url.startswith("https://")
        https_required = host not in LOCALHOSTS
        if https_required and not https_observed:
            raise ValidationFailure("public operational acceptance requires HTTPS")
        cases = _load_cases(args.cases.resolve(), set(args.case))
        with httpx.Client(
            timeout=httpx.Timeout(args.timeout),
            follow_redirects=True,
        ) as client:
            health, health_call = _request_json(client, "GET", base_url, "/health")
            ready, ready_call = _request_json(client, "GET", base_url, "/ready")
            if health.get("status") != "healthy":
                raise ValidationFailure(
                    f"runtime health is not healthy: {health.get('status')}"
                )
            if ready.get("ready") is not True:
                raise ValidationFailure("runtime readiness is false")
            ecosystem_body, ecosystem_call = _request_json(
                client,
                "GET",
                base_url,
                "/api/v1/ecosystem/readiness",
            )
            ecosystem = ecosystem_body.get("ecosystem") or {}
            if ecosystem.get("ready") is not True:
                raise ValidationFailure(
                    "ecosystem readiness is false: "
                    + json.dumps(ecosystem.get("pending_modules") or [])
                )
            modules = ecosystem.get("modules") or {}
            bucket_endpoint = _path_get(modules, "bucket.endpoint")
            central_endpoint = _path_get(modules, "central_depository.endpoint")
            independent_central = (
                bool(bucket_endpoint)
                and bool(central_endpoint)
                and bucket_endpoint != central_endpoint
            )
            if args.require_independent_central_depository and not independent_central:
                raise ValidationFailure(
                    "Central Depository uses the Bucket endpoint; an independent "
                    "owner endpoint was required"
                )
            for case in cases:
                report["cases"].append(
                    _validate_case(
                        client,
                        base_url,
                        case,
                        package_directory=args.package_directory,
                        replay_timeout=args.replay_timeout,
                    )
                )
            metrics_response = client.get(
                urljoin(base_url + "/", "metrics")
            )
            if metrics_response.status_code != 200:
                raise ValidationFailure(
                    f"GET /metrics returned HTTP {metrics_response.status_code}"
                )
            metrics = metrics_response.text
            for metric in (
                "mitra_ecosystem_ready 1",
                "mitra_ecosystem_executions{status=\"COMPLETED\"}",
                "mitra_runtime_continuity_issues 0",
            ):
                if metric not in metrics:
                    raise ValidationFailure(f"missing required metric: {metric}")
            recovery_body, recovery_call = _request_json(
                client,
                "POST",
                base_url,
                "/api/v1/runtime/recovery",
                payload=VERSIONS,
            )
            recovery = recovery_body.get("recovery") or {}
            if recovery.get("status") != "recovered":
                raise ValidationFailure(
                    "runtime recovery did not report recovered"
                )
        report.update(
            {
                "passed": True,
                "completed_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "transport_security": {
                    "https_observed": https_observed,
                    "https_required": https_required,
                    "loopback_exception": not https_required
                    and not https_observed,
                },
                "runtime": {
                    "health_status": health.get("status"),
                    "ready_status": _path_get(ready, "runtime.state"),
                    "ecosystem_ready": ecosystem.get("ready"),
                    "configured_modules": sorted(modules),
                    "startup_calls": [
                        health_call,
                        ready_call,
                        ecosystem_call,
                    ],
                    "recovery_call": recovery_call,
                    "recovery_state": recovery.get("status"),
                },
                "central_depository": {
                    "bucket_endpoint": bucket_endpoint,
                    "central_endpoint": central_endpoint,
                    "independent_owner_endpoint": independent_central,
                    "storage_contract_verified": True,
                    "acceptance_authority_claimed": False,
                },
                "metrics_verified": True,
                "case_count": len(report["cases"]),
                "total_live_execution_seconds": round(
                    sum(
                        sum(
                            call["latency_ms"]
                            for call in case["api_calls"]
                            if call["method"] == "POST"
                            and call["path"]
                            == "/api/v1/ecosystem/execute"
                        )
                        for case in report["cases"]
                    )
                    / 1000,
                    3,
                ),
                "total_assertions": sum(
                    case["check_count"] for case in report["cases"]
                ),
            }
        )
    except Exception as exc:
        report.update(
            {
                "completed_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    output = copy.deepcopy(report)
    if args.summary:
        for case in output.get("cases") or []:
            case.pop("checks", None)
            case.pop("api_calls", None)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
