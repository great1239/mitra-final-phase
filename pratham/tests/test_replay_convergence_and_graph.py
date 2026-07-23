from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mitra_companion.contracts import (
    CompanionMessageRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


def _scale_manifest(index: int) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        {
            "product_id": f"scale-product-{index:03d}",
            "display_name": f"Scale Product {index:03d}",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "capabilities": [
                {
                    "capability_id": f"scale-capability-{index:03d}",
                    "description": (
                        f"Scale validation capability number {index:03d}"
                    ),
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": f"scale.intent-{index:03d}",
                            "description": (
                                f"Run scale validation intent {index:03d}"
                            ),
                            "input_schema": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [f"input_{index:03d}"],
                                "properties": {
                                    f"input_{index:03d}": {
                                        "type": "string",
                                        "minLength": 1,
                                    }
                                },
                            },
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": (
                                    f"loopback://scale-product-{index:03d}/run"
                                ),
                            },
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_dispatch_records_verified_reconstruction_and_depository(runtime):
    runtime.attach(_manifest("product-bucket-insight.json"))
    session = runtime.sessions.create(
        actor_id="reviewer",
        client_type="standalone",
        workspace_id="acceptance",
        product_id="bucket-insight",
    )

    result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            product_id="bucket-insight",
            capability_id="artifact-insight",
            intent_id="bucket.lookup-artifact",
            payload={
                "artifact_hash": "abc123456789def0",
                "review_depth": "summary",
            },
        )
    )

    assert result["dispatch"]["status"] == "COMPLETED"
    assert result["reconstruction"]["deterministic"] is True
    reconstruction = runtime.dispatch_reconstruction(
        result["dispatch"]["dispatch_id"]
    )
    assert reconstruction["status"] == "verified"
    assert reconstruction["verification"]["deterministic"] is True
    assert reconstruction["verification"]["replay_type"] == (
        "mitra-true-deterministic-replay-v1"
    )
    assert all(reconstruction["verification"]["scope_coverage"].values())
    assert reconstruction["reconstructed_execution"]["request"]["payload"] == {
        "artifact_hash": "abc123456789def0",
        "review_depth": "summary",
    }
    reconstructed = reconstruction["reconstructed_execution"]
    assert reconstructed["lifecycle"]["state"] == "READY"
    assert reconstructed["sessions"]["active_session"]["session_id"] == (
        session["session_id"]
    )
    assert reconstructed["routing"]["selected_route"]["intent_id"] == (
        "bucket.lookup-artifact"
    )
    assert reconstructed["attachments"]["selected_attachment"][
        "product_id"
    ] == "bucket-insight"
    assert reconstructed["dispatch"]["receipt"]["status"] == "COMPLETED"
    assert [phase["phase_name"] for phase in reconstructed["phase_journal"]] == [
        "request.accepted",
        "route.selected",
        "payload.validated",
        "context.loaded",
        "transport.dispatched",
        "receipt.persisted",
        "dispatch.completed",
    ]
    assert any(
        event["event_type"] == "dispatch.completed"
        and event["dispatch_id"] == result["dispatch"]["dispatch_id"]
        for event in reconstructed["telemetry"]["events"]
    )
    assert reconstructed["recovery"]["runtime_instances"]
    assert reconstructed["failures"]["current_dispatch_error"] is None
    proof = runtime.dispatch_proof(result["dispatch"]["dispatch_id"])
    assert proof["deterministic_reconstruction"]["status"] == "verified"
    assert proof["deterministic_reconstruction"]["replay_type"] == (
        "mitra-true-deterministic-replay-v1"
    )
    assert all(proof["deterministic_reconstruction"]["scope_coverage"].values())
    depository = runtime.central_depository(
        subject_type="dispatch",
        subject_id=result["dispatch"]["dispatch_id"],
    )
    assert depository["filters"]["subject_id"] == result["dispatch"][
        "dispatch_id"
    ]
    assert depository["artifact_count"] == len(depository["artifacts"])
    assert depository["lineage_count"] == len(depository["lineage"])
    lineage_hashes = {
        item["artifact_hash"]
        for item in depository["lineage"]
    }
    assert {
        item["artifact_hash"]
        for item in depository["artifacts"]
    }.issubset(lineage_hashes)
    export_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "runtime-depository-export.schema.json"
        ).read_text(encoding="utf-8")
    )
    export_response = {
        "schema_version": "1.0.0",
        "contract_version": "1.0.0",
        "runtime_version": "1.0.0",
        "compatibility_version": "mitra-companion-1",
        "depository": depository,
    }
    assert list(
        Draft202012Validator(export_schema).iter_errors(export_response)
    ) == []
    reconstruction_lineage = [
        item
        for item in depository["lineage"]
        if item["metadata"].get("artifact_type")
        == "dispatch-reconstruction.snapshot"
    ]
    assert reconstruction_lineage[0]["chain_hash"] == result[
        "reconstruction"
    ]["chain_hash"]


@pytest.mark.asyncio
async def test_clean_state_replay_uses_only_immutable_package(
    runtime,
    settings_factory,
):
    runtime.attach(_manifest("product-bucket-insight.json"))
    session = runtime.sessions.create(
        actor_id="clean-replay-reviewer",
        client_type="standalone",
        workspace_id="acceptance",
        product_id="bucket-insight",
    )
    original = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            product_id="bucket-insight",
            capability_id="artifact-insight",
            intent_id="bucket.lookup-artifact",
            payload={
                "artifact_hash": "clean123456789def0",
                "review_depth": "full",
            },
            correlation_id="clean-state-replay-001",
        )
    )
    dispatch_id = original["dispatch"]["dispatch_id"]
    exported_package = runtime.dispatch_reconstruction(dispatch_id)
    original_reconstruction = copy.deepcopy(
        exported_package["reconstructed_execution"]
    )

    clean_settings = settings_factory()
    clean_settings.data_root = clean_settings.data_root / "clean-replay"
    clean_settings.database_path = (
        clean_settings.data_root / "companion-runtime.db"
    )
    clean_settings.telemetry_log_path = (
        clean_settings.data_root / "runtime-telemetry.jsonl"
    )
    clean_runtime = CompanionRuntime(clean_settings)
    clean_runtime.start()
    try:
        assert clean_runtime.store.list_dispatches(limit=10) == []
        replay = clean_runtime.validate_reconstruction_package(
            exported_package
        )
        assert clean_runtime.store.list_dispatches(limit=10) == []

        tampered_package = copy.deepcopy(exported_package)
        tampered_package["components"]["dispatch.response"][
            "tampered"
        ] = True
        tampered = clean_runtime.validate_reconstruction_package(
            tampered_package
        )
    finally:
        clean_runtime.stop()

    assert replay["status"] == "verified"
    assert replay["state_dependency"] == "none"
    assert replay["runtime_state_read"] is False
    assert replay["package_hash"] == exported_package["package_hash"]
    assert replay["reconstructed_execution"] == original_reconstruction
    assert replay["verification"]["deterministic"] is True
    assert all(replay["verification"]["scope_coverage"].values())
    assert any(
        check["check"] == "dispatch-identical-hash" and check["passed"]
        for check in replay["verification"]["checks"]
    )
    assert any(
        check["check"] == "reconstructed-response-hash" and check["passed"]
        for check in replay["verification"]["checks"]
    )

    assert tampered["status"] == "failed"
    assert any(
        check["check"] == "component-hash:dispatch.response"
        and not check["passed"]
        for check in tampered["verification"]["checks"]
    )


def test_capability_graph_and_plan_cover_bhiv_convergence_products(runtime):
    for name in (
        "product-bucket-insight.json",
        "product-prana-runtime.json",
        "product-karma-ledger.json",
        "product-setu-bridge.json",
        "product-keshav-knowledge.json",
        "product-sarathi-guide.json",
    ):
        runtime.attach(_manifest(name))

    graph = runtime.capability_graph(
        message="forward proof through setu and record karma event"
    )
    assert graph["node_count"] >= 18
    product_nodes = {
        node["product_id"]
        for node in graph["nodes"]
        if node["kind"] == "product"
    }
    assert {
        "bucket-insight",
        "prana-runtime",
        "karma-ledger",
        "setu-bridge",
        "keshav-knowledge",
        "sarathi-guide",
    }.issubset(product_nodes)

    plan = runtime.capability_plan(
        message="forward proof through setu and record karma event"
    )
    planned_products = {step["product_id"] for step in plan["steps"]}
    assert plan["plan_type"] == "multi_capability_candidate_plan"
    assert {"setu-bridge", "karma-ledger"}.issubset(planned_products)


@pytest.mark.asyncio
async def test_companion_profile_tracks_identity_preferences_and_trust(runtime):
    runtime.attach(_manifest("product-keshav-knowledge.json"))

    result = await runtime.companion_message(
        CompanionMessageRequest(
            actor_id="companion-user",
            client_type="mobile",
            workspace_id="companion-space",
            message="retrieve knowledge reference for replay provenance",
            metadata={
                "preferences": {
                    "preferred_tone": "concise",
                    "preferred_detail": "evidence-first",
                }
            },
        )
    )

    assert result["status"] == "COMPLETED"
    profile = result["memory"]["companion_profile"]
    assert profile["identity_continuity"]["actor_id"] == "companion-user"
    assert profile["identity_continuity"]["client_history"] == ["mobile"]
    assert profile["preferences"]["preferred_tone"] == "concise"
    assert profile["trust"]["successful_dispatches"] == 1
    assert profile["relationship_model"]["mode"] == (
        "bounded-runtime-companion"
    )


def test_scale_catalog_handles_200_simulated_products(runtime):
    for index in range(200):
        runtime.attach(_scale_manifest(index))

    graph = runtime.capability_graph()
    catalog = runtime.capability_catalog()

    assert len(runtime.attachments.list()) == 200
    assert graph["node_count"] == 600
    assert catalog["capability_graph"]["node_count"] == 600
    assert catalog["product_count"] == 200
