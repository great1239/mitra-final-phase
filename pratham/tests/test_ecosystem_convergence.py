from __future__ import annotations

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from integration_services.raj import _effective_base_url
from mitra_companion.api import create_app
from mitra_companion.contracts import (
    EcosystemExecutionRequest,
    ProductAttachmentManifest,
)
from mitra_companion.ecosystem import EcosystemReplayLedger
from mitra_companion.errors import (
    EcosystemConfigurationError,
    EcosystemIntegrationError,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.utils import sha256_json


ROOT = Path(__file__).resolve().parents[2]


def test_raj_endpoint_override_normalizes_manifest_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "RAJ_ENDPOINT_OVERRIDES_JSON",
        json.dumps({"https://uni-guru.in": "http://uniguru:8000/"}),
    )

    assert _effective_base_url("https://uni-guru.in/") == "http://uniguru:8000"


def _manifest(name: str = "product-trade-bot-main.json"):
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def _request(
    *,
    idempotency_key: str | None = None,
) -> EcosystemExecutionRequest:
    return EcosystemExecutionRequest(
        actor_id="operator-1",
        workspace_id="production-validation",
        product_id="trade-bot-main",
        capability_id="market-prediction",
        message="Generate a market prediction for TCS.NS",
        assignment=(
            "Select the attached market prediction capability and execute it "
            "through the TANTRA ecosystem convergence chain."
        ),
        payload={
            "symbols": ["TCS.NS"],
            "horizon": "short",
            "raj_workflow": {
                "action_type": "task",
                "title": "Run the selected market prediction capability",
                "description": "Execute the manifest-selected capability",
            },
        },
        idempotency_key=idempotency_key,
    )


class ContractEnvironment:
    """Controlled implementations of owner-published HTTP contracts."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail_insight_once = False
        self.insight_failed = False
        self.karma_status = "appended"
        self.raj_success = True
        self.keshav_mutates_trace = False
        self.ashmit_decision = "ALLOW"
        self.ashmit_mongo_connected = True
        self.heads = {
            "bucket.test": "bucket-head",
            "central.test": "central-head",
        }
        self.artifacts: dict[str, dict] = {}
        self.bucket_parent_hashes: list[str] = []
        self.karma_parent_hashes: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = request.content
        call = {
            "method": request.method,
            "host": request.url.host,
            "path": request.url.path,
            "body": body,
        }
        self.calls.append(call)
        host = request.url.host
        path = request.url.path

        if host == "raj.test" and path == "/healthz":
            return httpx.Response(
                200,
                json={"status": "ok", "service": "workflow-executor"},
            )
        if host == "keshav.test" and path == "/health":
            return httpx.Response(
                200,
                json={"status": "OK", "service": "KESHAV"},
            )
        if host == "keshav.test" and path == "/analyze":
            payload = json.loads(body)
            task = payload["tasks"][0]
            impact = payload["propagation_results"][0]["impact_score"]
            return httpx.Response(
                200,
                json={
                    "trace_id": (
                        "mutated-trace"
                        if self.keshav_mutates_trace
                        else payload["trace_id"]
                    ),
                    "execution_id": payload["execution_id"],
                    "root_cause": task["task_id"],
                    "resolution_signal": (
                        "UNBLOCK_DEPENDENCY:" + task["task_id"]
                    ),
                    "impact_score": impact,
                    "severity": "MEDIUM",
                    "timestamp": "2026-07-20T00:00:00Z",
                },
            )
        if request.method == "GET" and path == "/health":
            response = {"status": "healthy"}
            if host == "karma.test":
                response["last_hash"] = (
                    f"karma-head-{len(self.karma_parent_hashes)}"
                    if self.karma_parent_hashes
                    else "karma-genesis"
                )
            return httpx.Response(200, json=response)
        if host == "ashmit.test" and path == "/health/system":
            return httpx.Response(
                200,
                json={
                    "system": "mitra_runtime",
                    "modules": {"execution": {"status": "active"}},
                    "bucket": {
                        "status": "active",
                        "mongo_connected": self.ashmit_mongo_connected,
                        "audit_active": self.ashmit_mongo_connected,
                    },
                },
            )
        if host == "ashmit.test" and path == "/api/mitra/evaluate":
            assert request.headers["X-API-Key"] == "ashmit-secret"
            payload = json.loads(body)
            assert payload["context"]["system_context"]["mitra_trace_id"]
            ashmit_trace_id = "ashmit-" + hashlib.sha256(body).hexdigest()[:24]
            return httpx.Response(
                200,
                json={
                    "status": self.ashmit_decision,
                    "risk_level": (
                        "LOW" if self.ashmit_decision == "ALLOW" else "HIGH"
                    ),
                    "trace_id": ashmit_trace_id,
                    "bucket_log_reference": {
                        "trace_id": ashmit_trace_id,
                        "stage": "mitra_response_contract",
                        "artifact_locator": (
                            f"{ashmit_trace_id}:mitra_response_contract"
                        ),
                        "backend": "mongodb",
                    },
                },
            )
        if host == "raj.test" and path == "/api/workflow/execute":
            payload = json.loads(body)
            return httpx.Response(
                200,
                json={
                    "trace_id": payload["trace_id"],
                    "status": (
                        "success" if self.raj_success else "product_error"
                    ),
                    "execution_result": {
                        "success": self.raj_success,
                        "trace_id": payload["trace_id"],
                        "task_status": "CREATED",
                        "output": {"prediction": "hold"},
                        "error": (
                            None
                            if self.raj_success
                            else {
                                "type": "product_rejected_workflow",
                                "message": "product rejected workflow",
                                "http_status": 422,
                            }
                        ),
                    },
                },
            )
        if host in self.heads and path == "/bucket/latest-hash":
            return httpx.Response(
                200,
                json={
                    "last_hash": self.heads[host],
                    "artifact_count": len(
                        [item for item in self.artifacts.values() if item["host"] == host]
                    ),
                },
            )
        if host in self.heads and path == "/bucket/artifact":
            payload = json.loads(body)
            if host == "bucket.test":
                self.bucket_parent_hashes.append(payload["parent_hash"])
            if payload["parent_hash"] != self.heads[host]:
                return httpx.Response(
                    409,
                    json={
                        "status": "append_violation",
                        "expected_parent_hash": self.heads[host],
                    },
                )
            assert set(payload) == {
                "artifact_id",
                "trace_id",
                "timestamp_utc",
                "schema_version",
                "source_module_id",
                "artifact_type",
                "parent_hash",
                "payload",
            }
            server_hash = hashlib.sha256(body).hexdigest()
            self.heads[host] = server_hash
            self.artifacts[f"{host}:{payload['artifact_id']}"] = {
                "host": host,
                "artifact": payload,
            }
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "artifact_id": payload["artifact_id"],
                    "hash": server_hash,
                    "parent_hash": payload["parent_hash"],
                },
            )
        if host in self.heads and path.startswith("/bucket/artifact/"):
            artifact_id = path.rsplit("/", 1)[-1]
            stored = self.artifacts[f"{host}:{artifact_id}"]
            return httpx.Response(
                200,
                json={
                    "artifact": stored["artifact"],
                    "chain_verified": True,
                },
            )
        if host in self.heads and path == "/bucket/validate-replay":
            return httpx.Response(
                200,
                json={"valid": True, "last_hash": self.heads[host]},
            )
        if host == "karma.test" and path == (
            "/integrity/append-bucket-artifact"
        ):
            payload = json.loads(body)
            self.karma_parent_hashes.append(payload["parent_hash"])
            return httpx.Response(
                200,
                json={
                    "status": self.karma_status,
                    "current_hash": (
                        f"karma-head-{len(self.karma_parent_hashes)}"
                    ),
                },
            )
        if host == "prana.test" and path == "/forward/karma-strict":
            digest = hashlib.sha256(body).hexdigest()
            return httpx.Response(
                200,
                json={"status": "forwarded"},
                headers={
                    "X-PRANA-Strict-Bytes-Equal": "true",
                    "X-PRANA-Payload-SHA256": digest,
                },
            )
        if host == "prana.test" and path == "/forward/core":
            payload = json.loads(body)
            return httpx.Response(
                200,
                json={"status": "forwarded", "trace_id": payload["trace_id"]},
            )
        if host == "insight.test" and path == "/v1/executions":
            if self.fail_insight_once and not self.insight_failed:
                self.insight_failed = True
                return httpx.Response(503, json={"status": "unavailable"})
            payload = json.loads(body)
            return httpx.Response(
                202,
                json={"status": "accepted", "trace_id": payload["trace_id"]},
            )
        return httpx.Response(404, json={"status": "not-found"})

    def count(self, method: str, path: str, *, host: str | None = None) -> int:
        return sum(
            1
            for call in self.calls
            if call["method"] == method
            and call["path"] == path
            and (host is None or call["host"] == host)
        )


class DelayedContractTransport(httpx.AsyncBaseTransport):
    def __init__(self, environment: ContractEnvironment) -> None:
        self.environment = environment

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path in {
            "/bucket/artifact",
            "/integrity/append-bucket-artifact",
        }:
            await asyncio.sleep(0.05)
        return self.environment.handler(request)


def _configured_runtime(
    settings_factory,
    environment: ContractEnvironment,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
):
    settings = settings_factory()
    settings.persistent_runtime_enabled = False
    settings.raj_workflow_base_url = "https://raj.test"
    settings.raj_api_key = "raj-secret"
    settings.bhiv_ashmit_base_url = "https://ashmit.test"
    settings.bhiv_ashmit_api_key = "ashmit-secret"
    settings.bhiv_bucket_base_url = "https://bucket.test"
    settings.bhiv_bucket_parent_hash = "bucket-genesis"
    settings.bhiv_keshav_base_url = "https://keshav.test"
    settings.bhiv_karma_base_url = "https://karma.test"
    settings.bhiv_karma_previous_hash = "karma-genesis"
    settings.bhiv_prana_base_url = "https://prana.test"
    settings.bhiv_insightflow_ingest_url = (
        "https://insight.test/v1/executions"
    )
    settings.bhiv_insightflow_api_key = "insight-secret"
    settings.central_depository_base_url = "https://central.test"
    runtime = CompanionRuntime(
        settings,
        ecosystem_http_transport=(
            transport or httpx.MockTransport(environment.handler)
        ),
    )
    runtime.start()
    runtime.attach(_manifest())
    return runtime


@pytest.mark.asyncio
async def test_strict_ecosystem_flow_records_every_owner_response(
    settings_factory,
):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    try:
        result = await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    execution = result["execution"]
    assert execution["status"] == "COMPLETED"
    assert [stage["stage_name"] for stage in result["stages"]] == [
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
    assert all(stage["response"] is not None for stage in result["stages"])
    assert all(stage["artifact_hash"] for stage in result["stages"])
    raj = result["stages"][2]["response"]
    assert raj["trace_id"] == raj["raj_trace_id"]
    assert environment.count("POST", "/api/workflow/execute") == 1
    assert environment.count("POST", "/analyze", host="keshav.test") == 0
    assert environment.count("POST", "/api/mitra/evaluate") == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="bucket.test"
    ) == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="central.test"
    ) == 1
    assert environment.count("POST", "/integrity/append-bucket-artifact") == 1
    assert environment.count("POST", "/forward/karma-strict") == 1
    assert environment.count("POST", "/v1/executions") == 1


@pytest.mark.asyncio
async def test_product_error_invokes_keshav_then_persists_diagnosis(
    settings_factory,
):
    environment = ContractEnvironment()
    environment.raj_success = False
    runtime = _configured_runtime(settings_factory, environment)
    try:
        result = await runtime.execute_ecosystem(_request())
        package = runtime.ecosystem_replay(
            result["execution"]["execution_id"]
        )["package"]
    finally:
        runtime.stop()

    assert result["execution"]["status"] == "COMPLETED"
    by_stage = {
        stage["stage_name"]: stage["response"]
        for stage in result["stages"]
    }
    raj = by_stage["raj-execution"]
    diagnosis = by_stage["keshav-diagnosis"]
    assert raj["status"] == "product_error"
    assert raj["execution"]["success"] is False
    assert diagnosis["status"] == "diagnosed"
    assert diagnosis["invoked"] is True
    assert diagnosis["diagnosis"]["trace_id"] == result["execution"][
        "trace_id"
    ]
    assert diagnosis["diagnosis"]["resolution_signal"].startswith(
        "UNBLOCK_DEPENDENCY:product-runtime-"
    )
    assert "Mitra does not authorize or execute" in diagnosis["authority"]
    assert environment.count("POST", "/analyze", host="keshav.test") == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="bucket.test"
    ) == 1
    assert environment.count("POST", "/integrity/append-bucket-artifact") == 1
    assert environment.count("POST", "/v1/executions") == 1
    replay = runtime.validate_ecosystem_replay(package)
    assert replay["status"] == "verified"
    assert replay["reconstructed_execution"]["keshav_invoked"] is True


@pytest.mark.asyncio
async def test_keshav_trace_mutation_stops_before_truth_storage(
    settings_factory,
):
    environment = ContractEnvironment()
    environment.raj_success = False
    environment.keshav_mutates_trace = True
    runtime = _configured_runtime(settings_factory, environment)
    try:
        with pytest.raises(EcosystemIntegrationError):
            await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    assert environment.count("POST", "/analyze", host="keshav.test") == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="bucket.test"
    ) == 0
    failed = runtime.ecosystem_executions(status="FAILED")
    assert len(failed) == 1
    detail = runtime.ecosystem_execution(failed[0]["execution_id"])
    stage = next(
        item
        for item in detail["stages"]
        if item["stage_name"] == "keshav-diagnosis"
    )
    assert stage["status"] == "FAILED"
    assert stage["response"]["contract_validation"]["valid"] is False


@pytest.mark.asyncio
async def test_replay_reconstructs_after_runtime_state_is_removed(
    settings_factory,
    tmp_path,
):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    result = await runtime.execute_ecosystem(_request())
    package = deepcopy(
        runtime.ecosystem_replay(result["execution"]["execution_id"])[
            "package"
        ]
    )
    original = package["reconstructed_execution"]
    runtime.stop()

    clean_settings = settings_factory()
    clean_settings.data_root = tmp_path / "clean-state"
    clean_settings.database_path = clean_settings.data_root / "runtime.db"
    clean_settings.telemetry_log_path = clean_settings.data_root / "telemetry.jsonl"
    clean_settings.persistent_runtime_enabled = False
    clean_runtime = CompanionRuntime(clean_settings)
    clean_runtime.start()
    try:
        assert clean_runtime.store.ecosystem_execution_counts()["TOTAL"] == 0
        validation = EcosystemReplayLedger.validate(package)
    finally:
        clean_runtime.stop()

    assert validation["status"] == "verified"
    assert validation["database_reads"] == 0
    assert validation["live_service_calls"] == 0
    assert validation["reconstructed_execution"] == original
    assert validation["deterministic"] is True


@pytest.mark.asyncio
async def test_replay_accepts_pre_keshav_v1_package(settings_factory):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    try:
        result = await runtime.execute_ecosystem(_request())
        package = deepcopy(
            runtime.ecosystem_replay(result["execution"]["execution_id"])[
                "package"
            ]
        )
    finally:
        runtime.stop()

    package["replay_type"] = "mitra-tantra-ecosystem-replay-v1"
    package["components"] = [
        component
        for component in package["components"]
        if component["name"] != "keshav-diagnosis"
    ]
    previous_component_hash = None
    previous_lineage_hash = None
    for index, component in enumerate(package["components"]):
        component["index"] = index
        component["previous_component_hash"] = previous_component_hash
        payload = component["payload"]
        if component["name"] != "request":
            metadata = {
                "artifact_type": "tantra.ecosystem-stage.v1",
                "stage_name": component["name"],
            }
            lineage_id = "lin_" + sha256_json(
                {
                    "subject_type": "ecosystem_execution",
                    "subject_id": package["execution_id"],
                    "artifact_hash": payload["artifact_hash"],
                    "metadata": metadata,
                }
            )[:32]
            chain_hash = sha256_json(
                {
                    "subject_type": "ecosystem_execution",
                    "subject_id": package["execution_id"],
                    "artifact_hash": payload["artifact_hash"],
                    "parent_chain_hash": previous_lineage_hash,
                    "sequence": index,
                    "metadata": metadata,
                }
            )
            payload["lineage_id"] = lineage_id
            payload["chain_hash"] = chain_hash
            payload["lineage"].update(
                {
                    "lineage_id": lineage_id,
                    "parent_chain_hash": previous_lineage_hash,
                    "sequence": index,
                    "chain_hash": chain_hash,
                }
            )
            previous_lineage_hash = chain_hash
        component["component_hash"] = sha256_json(payload)
        previous_component_hash = component["component_hash"]

    package["component_chain_head"] = previous_component_hash
    reconstructed = EcosystemReplayLedger._reconstruct(package["components"])
    package["reconstructed_execution"] = reconstructed
    package["reconstructed_execution_hash"] = sha256_json(reconstructed)
    core = {key: value for key, value in package.items() if key != "package_hash"}
    package["package_hash"] = sha256_json(core)

    validation = EcosystemReplayLedger.validate(package)
    assert validation["status"] == "verified"
    assert validation["reconstructed_execution"] == reconstructed
    assert "keshav_status" not in reconstructed


@pytest.mark.asyncio
async def test_replay_rejects_mutated_recorded_response(settings_factory):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    try:
        result = await runtime.execute_ecosystem(_request())
        replay = runtime.ecosystem_replay(
            result["execution"]["execution_id"]
        )["package"]
    finally:
        runtime.stop()
    replay["components"][3]["payload"]["response"]["status"] = "mutated"

    validation = EcosystemReplayLedger.validate(replay)

    assert validation["status"] == "failed"
    assert any(
        item["check"] == "stage-response-hash:raj-execution"
        for item in validation["failed_checks"]
    )


@pytest.mark.asyncio
async def test_karma_rejection_stops_prana_and_downstream(settings_factory):
    environment = ContractEnvironment()
    environment.karma_status = "replay_detected"
    runtime = _configured_runtime(settings_factory, environment)
    try:
        with pytest.raises(EcosystemIntegrationError):
            await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    assert environment.count("POST", "/forward/karma-strict") == 0
    assert environment.count("POST", "/v1/executions") == 0


@pytest.mark.asyncio
async def test_ashmit_rejection_stops_truth_and_integrity_stages(
    settings_factory,
):
    environment = ContractEnvironment()
    environment.ashmit_decision = "BLOCK"
    runtime = _configured_runtime(settings_factory, environment)
    try:
        with pytest.raises(EcosystemIntegrationError):
            await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    assert environment.count("POST", "/api/workflow/execute") == 1
    assert environment.count("POST", "/api/mitra/evaluate") == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="bucket.test"
    ) == 0
    assert environment.count("POST", "/integrity/append-bucket-artifact") == 0


@pytest.mark.asyncio
async def test_recovery_resumes_at_failed_stage_without_repeating_owners(
    settings_factory,
):
    environment = ContractEnvironment()
    environment.fail_insight_once = True
    runtime = _configured_runtime(settings_factory, environment)
    try:
        with pytest.raises(EcosystemIntegrationError):
            await runtime.execute_ecosystem(_request())
        execution = runtime.ecosystem_executions(status="FAILED")[0]

        recovered = await runtime.recover_ecosystem_execution(
            execution["execution_id"]
        )
    finally:
        runtime.stop()

    assert recovered["execution"]["status"] == "COMPLETED"
    assert environment.count("POST", "/api/workflow/execute") == 1
    assert environment.count("POST", "/api/mitra/evaluate") == 1
    assert environment.count(
        "POST", "/bucket/artifact", host="bucket.test"
    ) == 1
    assert environment.count("POST", "/integrity/append-bucket-artifact") == 1
    assert environment.count("POST", "/forward/karma-strict") == 1
    assert environment.count("POST", "/v1/executions") == 2
    insight_attempts = [
        item
        for item in recovered["attempts"]
        if item["stage_name"] == "insightflow-telemetry"
    ]
    assert [item["status"] for item in insight_attempts] == [
        "FAILED",
        "COMPLETED",
    ]


@pytest.mark.asyncio
async def test_idempotency_does_not_repeat_external_execution(settings_factory):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    try:
        first = await runtime.execute_ecosystem(
            _request(idempotency_key="ecosystem:test:001")
        )
        second = await runtime.execute_ecosystem(
            _request(idempotency_key="ecosystem:test:001")
        )
    finally:
        runtime.stop()

    assert first["execution"]["execution_id"] == second["execution"][
        "execution_id"
    ]
    assert environment.count("POST", "/api/workflow/execute") == 1
    assert environment.count("POST", "/api/mitra/evaluate") == 1
    assert runtime.store.counts()["sessions"] == 1


@pytest.mark.asyncio
async def test_restart_uses_durable_karma_chain_head(settings_factory):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    settings = deepcopy(runtime.settings)
    try:
        await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    settings.bhiv_karma_previous_hash = "karma-genesis"
    restarted = CompanionRuntime(
        settings,
        ecosystem_http_transport=httpx.MockTransport(environment.handler),
    )
    restarted.start()
    restarted.attach(_manifest())
    try:
        result = await restarted.execute_ecosystem(
            EcosystemExecutionRequest(
                **{
                    **_request().model_dump(mode="json"),
                    "message": "Generate a market prediction for INFY.NS",
                    "payload": {
                        **_request().payload,
                        "symbols": ["INFY.NS"],
                        "horizon": "short",
                    },
                }
            )
        )
    finally:
        restarted.stop()

    assert result["execution"]["status"] == "COMPLETED"
    assert environment.karma_parent_hashes == [
        "karma-genesis",
        "karma-head-1",
    ]
    bucket_calls = [
        call
        for call in environment.calls
        if call["method"] == "POST"
        and call["host"] == "bucket.test"
        and call["path"] == "/bucket/artifact"
    ]
    assert environment.bucket_parent_hashes == [
        "bucket-head",
        hashlib.sha256(bucket_calls[0]["body"]).hexdigest(),
    ]


@pytest.mark.asyncio
async def test_concurrent_executions_serialize_bucket_and_karma_heads(
    settings_factory,
):
    environment = ContractEnvironment()
    runtime = _configured_runtime(
        settings_factory,
        environment,
        transport=DelayedContractTransport(environment),
    )
    try:
        first, second = await asyncio.gather(
            runtime.execute_ecosystem(_request()),
            runtime.execute_ecosystem(
                EcosystemExecutionRequest(
                    **{
                    **_request().model_dump(mode="json"),
                    "message": "Generate a market prediction for INFY.NS",
                    "payload": {
                        **_request().payload,
                        "symbols": ["INFY.NS"],
                        "horizon": "short",
                        },
                    }
                )
            ),
        )
    finally:
        runtime.stop()

    assert first["execution"]["status"] == "COMPLETED"
    assert second["execution"]["status"] == "COMPLETED"
    assert environment.karma_parent_hashes == [
        "karma-genesis",
        "karma-head-1",
    ]
    bucket_calls = [
        call
        for call in environment.calls
        if call["method"] == "POST"
        and call["host"] == "bucket.test"
        and call["path"] == "/bucket/artifact"
    ]
    assert environment.bucket_parent_hashes == [
        "bucket-head",
        hashlib.sha256(bucket_calls[0]["body"]).hexdigest(),
    ]


@pytest.mark.asyncio
async def test_partially_configured_ecosystem_probes_available_owners_then_blocks(
    settings_factory,
):
    settings = settings_factory()
    settings.persistent_runtime_enabled = False
    settings.bhiv_ashmit_base_url = "https://ashmit.test"
    settings.bhiv_ashmit_api_key = "ashmit-secret"
    settings.bhiv_bucket_base_url = "https://bucket.test"
    settings.central_depository_base_url = "https://central.test"
    environment = ContractEnvironment()
    environment.ashmit_mongo_connected = False
    runtime = CompanionRuntime(
        settings,
        ecosystem_http_transport=httpx.MockTransport(environment.handler),
    )
    runtime.start()
    runtime.attach(_manifest())
    try:
        with pytest.raises(EcosystemConfigurationError):
            await runtime.execute_ecosystem(_request())
    finally:
        runtime.stop()

    failed = runtime.ecosystem_executions(status="FAILED")
    assert len(failed) == 1
    detail = runtime.ecosystem_execution(failed[0]["execution_id"])
    assert detail["execution"]["current_stage"] == "dependency-preflight"
    preflight = next(
        stage
        for stage in detail["stages"]
        if stage["stage_name"] == "dependency-preflight"
    )
    assert preflight["status"] == "FAILED"
    assert preflight["response"]["status"] == "blocked"
    assert set(preflight["response"]["pending_modules"]) == {
        "raj",
        "keshav",
        "karma",
        "prana",
        "insightflow",
    }
    checks = preflight["response"]["checks"]
    assert [check["module"] for check in checks] == [
        "bucket",
        "ashmit",
        "central_depository",
    ]
    assert [check["status"] for check in checks] == [
        "accepted",
        "failed",
        "accepted",
    ]
    assert preflight["response"]["unhealthy_modules"] == ["ashmit"]
    ashmit_check = next(
        check for check in checks if check["module"] == "ashmit"
    )
    assert "Mongo-backed Bucket" in ashmit_check["semantic_validation"][
        "error"
    ]
    assert environment.count("GET", "/health", host="bucket.test") == 1
    assert environment.count("GET", "/health/system", host="ashmit.test") == 1
    assert environment.count(
        "GET",
        "/bucket/latest-hash",
        host="central.test",
    ) == 1
    assert preflight["response"]["embedded_fallback"] is False
    assert runtime.ecosystem_readiness()["embedded_fallback"] is False


def test_ecosystem_api_and_openapi_expose_operator_surface(settings_factory):
    environment = ContractEnvironment()
    runtime = _configured_runtime(settings_factory, environment)
    app = create_app(runtime=runtime, start_runtime=False)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ecosystem/execute",
                json=_request().model_dump(mode="json"),
            )
            assert response.status_code == 201, response.text
            execution_id = response.json()["ecosystem"]["execution"][
                "execution_id"
            ]
            assert client.get("/api/v1/ecosystem/readiness").status_code == 200
            assert client.get(
                f"/api/v1/ecosystem/executions/{execution_id}/replay"
            ).json()["replay"]["validation"]["status"] == "verified"
            operator = client.get(
                f"/operator/ecosystem/{execution_id}?stage=raj-execution"
            )
            assert operator.status_code == 200
            assert "Recorded response" in operator.text
            assert "raj-execution" in operator.text
            replay_view = client.get(
                "/operator/runtime",
                params={"view": "replay", "execution_id": execution_id},
            )
            assert replay_view.status_code == 200
            assert "database_reads" in replay_view.text
            assert "live_service_calls" in replay_view.text
            schema = client.get("/openapi.json").json()
            assert "/api/v1/ecosystem/execute" in schema["paths"]
            assert "/api/v1/ecosystem/replay/validate" in schema["paths"]
    finally:
        runtime.stop()
