from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from mitra_companion.api import create_app


ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_source_scope_catalog_validates_previous_submission_imports():
    catalog = _json("contracts/source-scope-catalog.json")
    schema = _json("contracts/schemas/source-scope-catalog.schema.json")
    Draft202012Validator(schema).validate(catalog)

    feature_ids = {
        item["feature_id"] for item in catalog["runtime_imports"]
    }
    assert {
        "durable-session-context-routing-foundation",
        "persistent-production-runtime",
        "capability-dependency-catalog",
        "assignment-and-product-fit-analysis",
        "dispatch-proof-and-phase-journal",
        "downstream-command-chain-understanding",
        "real-product-contract-fixtures",
    } <= feature_ids

    external_ids = {
        item["system_id"] for item in catalog["external_systems"]
    }
    assert {"TANTRA", "SHAKTI", "MDU", "TMS", "Parikshak"} <= external_ids
    assert any(
        "Product-specific branches" in item
        for item in catalog["selection_policy"]["never_import"]
    )


def test_runtime_exposes_source_scope_and_uses_it_in_analysis(
    settings_factory,
):
    app = create_app(settings_factory())
    with TestClient(app) as client:
        scope = client.get("/api/v1/runtime/source-scope")
        assert scope.status_code == 200, scope.text
        source_scope = scope.json()["source_scope"]
        assert len(source_scope["previous_submissions"]) >= 7
        assert len(source_scope["runtime_imports"]) >= 7

        status = client.get("/api/v1/runtime/status")
        assert status.status_code == 200, status.text
        summary = status.json()["runtime"]["source_scope"]
        assert summary["previous_submission_count"] >= 7
        assert summary["runtime_import_count"] >= 7
        assert summary["external_system_count"] >= 5

        analysis = client.post(
            "/api/v1/runtime/analysis",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "message": "Show my market prediction.",
                "assignment": (
                    "Use previous submissions where useful, understand the "
                    "assignment, then match the request to attached products."
                ),
            },
        )
        assert analysis.status_code == 200, analysis.text
        hints = analysis.json()["analysis"]["previous_submission_scope"]
        assert hints["catalog_version"] == source_scope["catalog_version"]
        assert hints["future_product_intake"][-1].startswith(
            "Expose dispatch phases"
        )
