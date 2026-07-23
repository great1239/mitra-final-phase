from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import TransportError
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _manifest(name: str) -> ProductAttachmentManifest:
    path = ROOT / "contracts" / "examples" / name
    return ProductAttachmentManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _production_manifest(name: str) -> ProductAttachmentManifest:
    path = ROOT / "contracts" / "production" / name
    return ProductAttachmentManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


@pytest.mark.asyncio
async def test_bhiv_products_attach_create_sessions_and_dispatch(
    settings_factory,
):
    received: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8") or "{}")
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "uniguru-live-reasoning",
                },
            )
        if request.url.path == "/tools/health":
            return httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "service": "trade-bot-main",
                },
            )
        received.append(
            {
                "path": request.url.path,
                "payload": payload,
                "session": request.headers["X-Companion-Session"],
                "correlation": request.headers["X-Correlation-ID"],
            }
        )
        if request.url.path == "/runtime/execute":
            return httpx.Response(
                200,
                json={
                    "schema_version": "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1",
                    "response_payload": {"answer": "balanced diet"},
                    "trace_id": "uniguru-test",
                },
            )
        if request.url.path == "/tools/predict":
            return httpx.Response(
                200,
                json={
                    "metadata": {"count": len(payload["symbols"])},
                    "predictions": [{"symbol": payload["symbols"][0]}],
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        manifests = [
            _manifest("product-uniguru-runtime.json"),
            _manifest("product-trade-bot-main.json"),
        ]
        attached = runtime.attach_many(manifests)
        assert attached["attached_count"] == 2
        assert {
            item["product_id"] for item in attached["attachments"]
        } == {"uniguru-ai", "trade-bot-main"}

        uniguru_session = runtime.sessions.create(
            actor_id="bhiv-user",
            client_type="embedded",
            workspace_id="learning-workspace",
            product_id="uniguru-ai",
        )
        trade_session = runtime.sessions.create(
            actor_id="bhiv-user",
            client_type="standalone",
            workspace_id="trading-workspace",
            product_id="trade-bot-main",
        )

        uniguru_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=uniguru_session["session_id"],
                intent_id="uniguru.execute-query",
                payload={
                    "query": "What is a balanced diet?",
                    "grade": 6,
                    "subject": "Science",
                    "emit_proof": False,
                },
            )
        )
        trade_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=trade_session["session_id"],
                intent_id="tradebot.predict",
                payload={
                    "symbols": ["RELIANCE.NS"],
                    "horizon": "intraday",
                    "risk_profile": "moderate",
                },
            )
        )

        assert uniguru_dispatch["dispatch"]["status"] == "COMPLETED"
        assert trade_dispatch["dispatch"]["status"] == "COMPLETED"
        assert runtime.store.counts()["dispatches"] == 2
        assert [item["path"] for item in received] == [
            "/runtime/execute",
            "/tools/predict",
        ]
        assert received[0]["payload"] == {
            "query": "What is a balanced diet?",
            "grade": 6,
            "subject": "Science",
            "emit_proof": False,
        }
        assert received[1]["payload"] == {
            "symbols": ["RELIANCE.NS"],
            "horizon": "intraday",
            "risk_profile": "moderate",
        }
        metrics = runtime.metrics_snapshot()
        assert metrics["counters"]["dispatch_completed_total"] == 2
        assert set(metrics["dispatch_latency_by_product"]) == {
            "uniguru-ai",
            "trade-bot-main",
        }
        health = await runtime.check_attachment_health()
        assert health["checked_count"] == 2
        assert {
            item["product_id"]: item["health"]["status"]
            for item in health["checks"]
        } == {
            "uniguru-ai": "healthy",
            "trade-bot-main": "healthy",
        }
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_http_adapter_can_post_native_payload_body(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {"value": 42}
        assert "dispatch_id" not in payload
        return httpx.Response(200, json={"accepted": True})

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "native-http-product",
                "display_name": "Native HTTP Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://native.invalid",
                "capabilities": [
                    {
                        "capability_id": "native-capability",
                        "description": "Native payload projection fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "native.execute",
                                "description": "Execute native payload",
                                "input_schema": {
                                    "type": "object",
                                    "required": ["value"],
                                },
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/execute",
                                    "options": {"request_body": "payload"},
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="native-user",
            client_type="standalone",
            workspace_id="native-workspace",
            product_id="native-http-product",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="native.execute",
                payload={"value": 42},
            )
        )
        assert result["dispatch"]["response"] == {"accepted": True}
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_http_adapter_applies_manifest_headers_and_bearer_token_env(
    settings_factory,
    monkeypatch,
):
    monkeypatch.setenv("MITRA_TEST_PRODUCT_TOKEN", "secret-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {"query": "What is ahimsa?"}
        assert request.headers["X-Caller-Name"] == "bhiv-assistant"
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert request.headers["X-Correlation-ID"] == "header-contract-test"
        return httpx.Response(
            200,
            json={
                "decision": "accept",
                "answer": "Ahimsa means non-violence.",
            },
        )

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "auth-http-product",
                "display_name": "Authenticated HTTP Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://auth-product.invalid",
                "capabilities": [
                    {
                        "capability_id": "auth-capability",
                        "description": "Authenticated payload projection fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "auth.execute",
                                "description": "Execute with manifest headers",
                                "input_schema": {
                                    "type": "object",
                                    "required": ["query"],
                                },
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/ask",
                                    "options": {
                                        "request_body": "payload",
                                        "headers": {
                                            "X-Caller-Name": "bhiv-assistant"
                                        },
                                        "bearer_token_env": (
                                            "MITRA_TEST_PRODUCT_TOKEN"
                                        ),
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="auth-user",
            client_type="standalone",
            workspace_id="auth-workspace",
            product_id="auth-http-product",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="auth.execute",
                payload={"query": "What is ahimsa?"},
                correlation_id="header-contract-test",
            )
        )
        assert result["dispatch"]["status"] == "COMPLETED"
        assert result["dispatch"]["response"]["decision"] == "accept"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_uniguru_manifest_retries_published_rag_endpoint_on_safe_fallback(
    settings_factory,
    monkeypatch,
):
    monkeypatch.setenv("MITRA_PRODUCT_UNIGURU_RAG_TOKEN", "rag-secret")
    received: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8") or "{}")
        received.append(
            {
                "path": request.url.path,
                "payload": payload,
                "authorization": request.headers.get("Authorization"),
                "caller": request.headers.get("X-Caller-Name"),
            }
        )
        if request.url.path == "/ask":
            return httpx.Response(
                200,
                json={
                    "decision": "reject",
                    "answer": "Knowledge not found in verified ontology.",
                    "verification_status": "FAILED",
                    "reason": "/ask recovered from invalid response payload type.",
                },
            )
        if request.url.path == "/new_rag":
            assert payload == {"domain": "general", "query": "What is ahimsa?"}
            assert request.headers["Authorization"] == "Bearer rag-secret"
            return httpx.Response(
                200,
                json={
                    "query": "What is ahimsa?",
                    "domain": "general",
                    "signals_used": [{"signal_id": "sig-1"}],
                    "knowledge_ids": ["kosha-ahimsa"],
                    "confidence": 91.0,
                    "reasoning_trace": ["deterministic_synthesis"],
                    "final_answer": "Ahimsa means non-violence.",
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    settings: RuntimeSettings = settings_factory()
    runtime = CompanionRuntime(settings=settings, transport=transport)
    runtime.start()
    try:
        manifest_data = _production_manifest(
            "product-samruddhi-uniguru.json"
        ).model_dump(mode="json")
        manifest_data["base_url"] = "https://uniguru-fallback.invalid"
        manifest_data["metadata"]["production_bootstrap"] = False
        runtime.attach(ProductAttachmentManifest.model_validate(manifest_data))
        session = runtime.sessions.create(
            actor_id="uniguru-user",
            client_type="embedded",
            workspace_id="learning-workspace",
            product_id="samruddhi-uniguru",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="samruddhi.uniguru.ask",
                payload={
                    "query": "What is ahimsa?",
                    "context": {"caller": "bhiv-assistant"},
                    "allow_web": False,
                },
            )
        )
        response = result["dispatch"]["response"]
        assert response["decision"] == "accept"
        assert response["verification_status"] == "PARTIAL"
        assert response["answer"] == "Ahimsa means non-violence."
        assert response["fallback_source"] == "uniguru.new_rag"
        assert response["primary_response"]["verification_status"] == "FAILED"
        assert response["dispatch_fallback"]["applied"] is True
        assert [item["path"] for item in received] == ["/ask", "/new_rag"]
        assert received[0]["caller"] == "bhiv-assistant"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_tradebot_manifest_rejects_prediction_error_payload(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tools/predict":
            return httpx.Response(
                200,
                json={
                    "metadata": {"count": 1, "horizon": "intraday"},
                    "predictions": [
                        {
                            "symbol": "AAPL",
                            "horizon": "intraday",
                            "error": "Training failed: mixed timezone input",
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"error": request.url.path})

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    settings: RuntimeSettings = settings_factory()
    runtime = CompanionRuntime(settings=settings, transport=transport)
    runtime.start()
    try:
        manifest_data = _production_manifest(
            "product-samruddhi-trade-bot.json"
        ).model_dump(mode="json")
        manifest_data["base_url"] = "https://tradebot-error.invalid"
        manifest_data["metadata"]["production_bootstrap"] = False
        runtime.attach(ProductAttachmentManifest.model_validate(manifest_data))
        session = runtime.sessions.create(
            actor_id="tradebot-user",
            client_type="embedded",
            workspace_id="market-workspace",
            product_id="samruddhi-trade-bot",
        )
        with pytest.raises(TransportError) as exc_info:
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=session["session_id"],
                    intent_id="samruddhi.tradebot.predict",
                    payload={"symbols": ["AAPL"], "horizon": "intraday"},
                )
            )
        assert "response schema" in str(exc_info.value)
        attachment = runtime.attachments.get("samruddhi-trade-bot")
        assert attachment["state"] == "DEGRADED"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_manifest_health_contract_rejects_frontend_html_fallback(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            text="<html><body>frontend shell</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "html-health-product",
                "display_name": "HTML Health Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://html-health.invalid",
                "health_endpoint": "/health",
                "metadata": {
                    "health_contract": {
                        "required_format": "json",
                        "expected_content_type": "application/json",
                        "status_field": "status",
                        "healthy_status_values": ["ok", "healthy"],
                    }
                },
                "capabilities": [
                    {
                        "capability_id": "html-capability",
                        "description": "Health contract fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "html.execute",
                                "description": "Unused fixture intent",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/execute",
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        health = await runtime.check_attachment_health("html-health-product")
        check = health["checks"][0]
        assert check["health"]["status"] == "unhealthy"
        assert check["health"]["health_contract"] == {
            "enabled": True,
            "valid": False,
            "reason": "Health endpoint did not return JSON",
        }
        assert check["attachment"]["state"] == "DEGRADED"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_manifest_health_translator_follows_declared_redirect(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://uniguru-health.invalid/health":
            return httpx.Response(
                301,
                headers={
                    "location": "https://www.uniguru-health.invalid/health"
                },
            )
        assert str(request.url) == "https://www.uniguru-health.invalid/health"
        return httpx.Response(
            200,
            json={"status": "ok", "service": "uniguru-live-reasoning"},
            headers={"content-type": "application/json"},
        )

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "redirect-health-product",
                "display_name": "Redirect Health Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://uniguru-health.invalid",
                "health_endpoint": "/health",
                "metadata": {
                    "health_contract": {
                        "required_format": "json",
                        "expected_content_type": "application/json",
                        "status_field": "status",
                        "healthy_status_values": ["ok", "healthy"],
                        "translator": {"follow_redirects": True},
                    }
                },
                "capabilities": [
                    {
                        "capability_id": "redirect-capability",
                        "description": "Redirect health fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "redirect.execute",
                                "description": "Unused fixture intent",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/execute",
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        health = await runtime.check_attachment_health(
            "redirect-health-product"
        )
        check = health["checks"][0]
        assert check["health"]["status"] == "healthy"
        assert check["health"]["final_endpoint"] == (
            "https://www.uniguru-health.invalid/health"
        )
        assert check["health"]["redirect_chain"] == [
            {
                "status_code": 301,
                "url": "https://uniguru-health.invalid/health",
                "location": "https://www.uniguru-health.invalid/health",
            }
        ]
        assert check["health"]["health_translation"] == {
            "enabled": True,
            "applied": False,
        }
        assert check["attachment"]["state"] == "ATTACHED"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_manifest_health_translator_normalizes_service_suspended_page(
    settings_factory,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/tools/health"
        return httpx.Response(
            503,
            text=(
                "<html><body>This service has been suspended.</body></html>"
            ),
            headers={"content-type": "text/html; charset=utf-8"},
        )

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "suspended-health-product",
                "display_name": "Suspended Health Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://suspended-health.invalid",
                "health_endpoint": "/tools/health",
                "metadata": {
                    "health_contract": {
                        "required_format": "json",
                        "expected_content_type": "application/json",
                        "status_field": "status",
                        "healthy_status_values": ["ok", "healthy"],
                        "translator": {
                            "body_contains": [
                                {
                                    "contains": "service has been suspended",
                                    "status": "unhealthy",
                                    "reason": (
                                        "Downstream service is suspended"
                                    ),
                                }
                            ]
                        },
                    }
                },
                "capabilities": [
                    {
                        "capability_id": "suspended-capability",
                        "description": "Suspended health fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "suspended.execute",
                                "description": "Unused fixture intent",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/execute",
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        health = await runtime.check_attachment_health(
            "suspended-health-product"
        )
        check = health["checks"][0]
        assert check["health"]["status"] == "unhealthy"
        assert check["health"]["response"] == {
            "status": "unhealthy",
            "reason": "Downstream service is suspended",
        }
        assert check["health"]["health_translation"] == {
            "enabled": True,
            "applied": True,
            "rule": "body_contains",
            "matched": "service has been suspended",
            "source_content_type": "text/html; charset=utf-8",
            "source_status_code": 503,
        }
        assert check["health"]["raw_response"] == {
            "body": (
                "<html><body>This service has been suspended.</body></html>"
            )
        }
        assert check["attachment"]["state"] == "DEGRADED"
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_endpoint_override_rewrites_health_and_dispatch_urls():
    requested: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        assert request.url.host == "uniguru"
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={"status": "ok", "service": "uniguru-live-reasoning"},
                headers={"content-type": "application/json"},
            )
        if request.url.path == "/ask":
            return httpx.Response(
                200,
                json={
                    "decision": "accept",
                    "answer": "Runtime endpoint override reached UniGuru.",
                    "verification_status": "PASSED",
                },
            )
        return httpx.Response(404, json={"path": request.url.path})

    manifest = _production_manifest("product-samruddhi-uniguru.json")
    manifest_payload = manifest.model_dump(mode="json")
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(handler),
        endpoint_overrides={
            "https://uni-guru.in": "http://uniguru:8000"
        },
    )

    health = await transport.check_manifest_health(manifest_payload)
    intent = manifest_payload["capabilities"][0]["intents"][0]
    response = await transport.dispatch(
        route={"dispatch": intent["dispatch"]},
        envelope={
            "contract_version": "1.0.0",
            "session_id": "session-override",
            "correlation_id": "correlation-override",
            "payload": {"query": "Check runtime transport"},
        },
        manifest=manifest_payload,
    )

    assert health["status"] == "healthy"
    assert health["endpoint"] == "http://uniguru:8000/health"
    assert health["published_endpoint"] == "https://uni-guru.in/health"
    assert response["decision"] == "accept"
    assert requested == [
        "http://uniguru:8000/health",
        "http://uniguru:8000/ask",
    ]


def test_runtime_settings_parse_endpoint_overrides(monkeypatch, tmp_path):
    monkeypatch.delenv("MITRA_COMPANION_CONFIG_FILE", raising=False)
    monkeypatch.delenv("MITRA_COMPANION_ENV_FILE", raising=False)
    monkeypatch.setenv("MITRA_COMPANION_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "MITRA_COMPANION_ENDPOINT_OVERRIDES_JSON",
        json.dumps(
            {"https://uni-guru.in/": "http://uniguru:8000/"}
        ),
    )

    settings = RuntimeSettings.from_environment()

    assert settings.endpoint_overrides == {
        "https://uni-guru.in": "http://uniguru:8000"
    }
    assert settings.production_summary()["product_endpoint_overrides"] == {
        "configured": True,
        "count": 1,
        "published_origins": ["https://uni-guru.in"],
    }
