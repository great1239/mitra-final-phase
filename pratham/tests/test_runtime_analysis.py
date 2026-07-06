from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.contracts import (
    ProductAttachmentManifest,
    RuntimeAnalysisRequest,
)


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate_json(
        (ROOT / "contracts" / "examples" / name).read_text(
            encoding="utf-8"
        )
    )


@pytest.mark.asyncio
async def test_runtime_analysis_matches_assignment_to_attached_product(runtime):
    runtime.attach(_manifest("product-trade-bot-main.json"))

    result = await runtime.analyze_runtime(
        RuntimeAnalysisRequest(
            message="Show my market prediction for TCS.NS",
            assignment=(
                "Understand an unknown customer request, inspect linked "
                "BHIV products, and match the expected market result to the "
                "best available runtime capability."
            ),
        )
    )

    analysis = result["analysis"]
    assert result["candidate_count"] == 2
    assert analysis["status"] == "matched"
    assert analysis["resolver"] == "deterministic"
    assert analysis["recommended_candidate"] == {
        "product_id": "trade-bot-main",
        "capability_id": "market-prediction",
        "intent_id": "tradebot.predict",
    }
    assert analysis["assignment_profile"]["constraints"][
        "requires_product_matching"
    ]
    assert analysis["user_expectation"]["requested_action"] == "predict"
    assert analysis["product_profiles"][0]["protocols"][0]["mode"] == "http"
    assert analysis["fit_matrix"][0]["intent_id"] == "tradebot.predict"
    assert analysis["fit_matrix"][0]["scores"]["schema_fit"] == 1.0


def test_runtime_analysis_api_returns_fit_matrix(settings_factory):
    app = create_app(settings_factory())
    manifest = _manifest("product-trade-bot-main.json")

    with TestClient(app) as client:
        attached = client.post(
            "/api/v1/attachments",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "manifest": manifest.model_dump(mode="json"),
            },
        )
        assert attached.status_code == 201, attached.text

        response = client.post(
            "/api/v1/runtime/analysis",
            json={
                "schema_version": "1.0.0",
                "contract_version": "1.0.0",
                "runtime_version": "1.0.0",
                "compatibility_version": "mitra-companion-1",
                "message": "Show my market prediction for INFY",
                "assignment": (
                    "Contextualize the assignment and find the linked product "
                    "capability that can return the requested customer result."
                ),
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["candidate_count"] == 2
        analysis = body["analysis"]
        assert analysis["recommended_candidate"]["intent_id"] == (
            "tradebot.predict"
        )
        assert analysis["product_profiles"][0]["product_id"] == (
            "trade-bot-main"
        )
        assert analysis["fit_matrix"][0]["protocol"]["endpoint_kind"] == (
            "relative-http"
        )
