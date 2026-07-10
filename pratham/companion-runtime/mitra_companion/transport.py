from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin

import httpx

from .contracts import DispatchTarget, ProductAttachmentManifest
from .errors import AttachmentValidationError, TransportError
from .ports import TransportAdapter


TransportHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class LoopbackTransportAdapter:
    """In-memory adapter for tests, demos, and embedded host bindings."""

    mode = "loopback"

    def __init__(self):
        self._handlers: dict[tuple[str, str, str], TransportHandler] = {}

    def register_handler(
        self,
        product_id: str,
        capability_id: str,
        intent_id: str,
        handler: TransportHandler,
    ) -> None:
        self._handlers[(product_id, capability_id, intent_id)] = handler

    def validate_target(
        self,
        manifest: ProductAttachmentManifest,
        target: DispatchTarget,
    ) -> None:
        if not target.endpoint.startswith("loopback://"):
            raise AttachmentValidationError(
                "Loopback adapter endpoints must use loopback://"
            )

    async def dispatch(
        self,
        *,
        route: dict[str, Any],
        envelope: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        key = (
            route["product_id"],
            route["capability_id"],
            route["intent_id"],
        )
        handler = self._handlers.get(key)
        if handler is not None:
            return await handler(envelope)
        return {
            "accepted": True,
            "transport": self.mode,
            "product_id": route["product_id"],
            "capability_id": route["capability_id"],
            "intent_id": route["intent_id"],
            "correlation_id": envelope["correlation_id"],
            "received_context_scopes": sorted(
                envelope["context"]["partitions"]
            ),
            "payload": envelope["payload"],
        }


class HttpTransportAdapter:
    """HTTP adapter depending only on the published dispatch envelope."""

    mode = "http"
    _REQUEST_BODY_MODES = {"envelope", "payload", "none"}
    _HEALTH_FORMATS = {"json"}

    def __init__(
        self,
        *,
        default_timeout_seconds: float,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.default_timeout_seconds = default_timeout_seconds
        self.http_transport = http_transport

    def validate_target(
        self,
        manifest: ProductAttachmentManifest,
        target: DispatchTarget,
    ) -> None:
        endpoint = target.endpoint
        if not (
            endpoint.startswith("http://")
            or endpoint.startswith("https://")
            or manifest.base_url is not None
        ):
            raise AttachmentValidationError(
                "HTTP adapter requires an absolute endpoint or product base_url"
            )
        request_body = target.options.get("request_body", "envelope")
        if request_body not in self._REQUEST_BODY_MODES:
            raise AttachmentValidationError(
                "HTTP adapter request_body option must be one of: "
                "envelope, payload, none"
            )
        self._validate_header_options(target.options)

    def _validate_header_options(self, options: dict[str, Any]) -> None:
        headers = options.get("headers", {})
        if headers is not None and not isinstance(headers, dict):
            raise AttachmentValidationError(
                "HTTP adapter headers option must be an object"
            )
        secret_headers = options.get("secret_headers", {})
        if secret_headers is not None and not isinstance(secret_headers, dict):
            raise AttachmentValidationError(
                "HTTP adapter secret_headers option must be an object"
            )
        bearer_token_env = options.get("bearer_token_env")
        if bearer_token_env is not None and not isinstance(
            bearer_token_env,
            str,
        ):
            raise AttachmentValidationError(
                "HTTP adapter bearer_token_env option must be a string"
            )

    def _secret_value(self, env_name: str) -> str:
        direct = os.getenv(env_name, "").strip()
        if direct:
            return direct
        file_name = os.getenv(f"{env_name}_FILE", "").strip()
        if file_name:
            try:
                return Path(file_name).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise TransportError(
                    f"Configured secret file for {env_name} could not be read"
                ) from exc
        return ""

    def _headers_from_options(self, options: dict[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {}
        for name, value in (options.get("headers") or {}).items():
            if value is not None:
                headers[str(name)] = str(value)
        for name, env_name in (options.get("secret_headers") or {}).items():
            env_value = self._secret_value(str(env_name))
            if env_value:
                headers[str(name)] = env_value
        bearer_token_env = options.get("bearer_token_env")
        if bearer_token_env:
            token = self._secret_value(str(bearer_token_env))
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    async def dispatch(
        self,
        *,
        route: dict[str, Any],
        envelope: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        target = route["dispatch"]
        endpoint = target["endpoint"]
        base_url = manifest.get("base_url")
        if not endpoint.startswith(("http://", "https://")):
            if not base_url:
                raise TransportError(
                    "Relative HTTP endpoint requires product base_url"
                )
            endpoint = urljoin(
                base_url.rstrip("/") + "/",
                endpoint.lstrip("/"),
            )
        timeout = (
            target.get("timeout_seconds")
            or self.default_timeout_seconds
        )
        request_body = target.get("options", {}).get(
            "request_body",
            "envelope",
        )
        if request_body == "envelope":
            request_kwargs: dict[str, Any] = {"json": envelope}
        elif request_body == "payload":
            request_kwargs = {"json": envelope["payload"]}
        elif request_body == "none":
            request_kwargs = {}
        else:
            raise TransportError(
                "HTTP adapter request_body option must be one of: "
                "envelope, payload, none"
            )
        headers = self._headers_from_options(target.get("options", {}))
        headers.update(
            {
                "X-Contract-Version": envelope["contract_version"],
                "X-Companion-Session": envelope["session_id"],
                "X-Correlation-ID": envelope["correlation_id"],
            }
        )
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=timeout,
            ) as client:
                response = await client.post(
                    endpoint,
                    **request_kwargs,
                    headers=headers,
                )
                response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise TransportError(
                f"Capability endpoint failed: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError(
                "Capability endpoint returned a non-JSON response"
            ) from exc
        if not isinstance(payload, dict):
            raise TransportError(
                "Capability endpoint response must be a JSON object"
            )
        return payload

    @staticmethod
    def validate_health_contract(
        *,
        manifest: dict[str, Any],
        response: httpx.Response,
        payload: Any,
        json_response: bool,
    ) -> dict[str, Any]:
        contract = (manifest.get("metadata") or {}).get("health_contract") or {}
        if not isinstance(contract, dict) or not contract:
            return {"enabled": False, "valid": True}
        required_format = str(contract.get("required_format") or "").lower()
        if required_format:
            if required_format not in HttpTransportAdapter._HEALTH_FORMATS:
                return {
                    "enabled": True,
                    "valid": False,
                    "reason": (
                        "Unsupported health_contract.required_format: "
                        f"{required_format}"
                    ),
                }
            if required_format == "json" and not json_response:
                return {
                    "enabled": True,
                    "valid": False,
                    "reason": "Health endpoint did not return JSON",
                }

        expected_values = contract.get("healthy_status_values") or []
        if expected_values:
            if not isinstance(payload, dict):
                return {
                    "enabled": True,
                    "valid": False,
                    "reason": "Health response was not a JSON object",
                }
            status_field = str(contract.get("status_field") or "status")
            actual = payload.get(status_field)
            normalized_actual = str(actual or "").strip().lower()
            normalized_expected = {
                str(value).strip().lower() for value in expected_values
            }
            if normalized_actual not in normalized_expected:
                return {
                    "enabled": True,
                    "valid": False,
                    "reason": (
                        f"Health field {status_field!r} value "
                        f"{actual!r} was not one of "
                        f"{sorted(normalized_expected)}"
                    ),
                }

        expected_content_type = str(
            contract.get("expected_content_type") or ""
        ).lower()
        if expected_content_type:
            content_type = response.headers.get("content-type", "").lower()
            if expected_content_type not in content_type:
                return {
                    "enabled": True,
                    "valid": False,
                    "reason": (
                        "Health content type "
                        f"{content_type!r} did not include "
                        f"{expected_content_type!r}"
                    ),
                }
        return {"enabled": True, "valid": True}


class CapabilityTransport:
    """Adapter registry selected only by a manifest's published mode."""

    def __init__(
        self,
        *,
        default_timeout_seconds: float,
        http_transport: httpx.AsyncBaseTransport | None = None,
        adapters: list[TransportAdapter] | None = None,
    ):
        self.default_timeout_seconds = default_timeout_seconds
        self.http_transport = http_transport
        self._adapters: dict[str, TransportAdapter] = {}
        self.loopback_adapter = LoopbackTransportAdapter()
        self.register_adapter(self.loopback_adapter)
        self.register_adapter(
            HttpTransportAdapter(
                default_timeout_seconds=default_timeout_seconds,
                http_transport=http_transport,
            )
        )
        for adapter in adapters or []:
            self.register_adapter(adapter)

    def register_adapter(self, adapter: TransportAdapter) -> None:
        if adapter.mode in self._adapters:
            raise ValueError(
                f"Transport adapter mode is already registered: {adapter.mode}"
            )
        self._adapters[adapter.mode] = adapter

    def register_handler(
        self,
        product_id: str,
        capability_id: str,
        intent_id: str,
        handler: TransportHandler,
    ) -> None:
        self.loopback_adapter.register_handler(
            product_id,
            capability_id,
            intent_id,
            handler,
        )

    def validate_manifest(
        self,
        manifest: ProductAttachmentManifest,
    ) -> None:
        for capability in manifest.capabilities:
            for intent in capability.intents:
                adapter = self._adapters.get(intent.dispatch.mode)
                if adapter is None:
                    raise AttachmentValidationError(
                        "No transport adapter is registered for mode "
                        f"{intent.dispatch.mode}"
                    )
                adapter.validate_target(manifest, intent.dispatch)

    async def dispatch(
        self,
        *,
        route: dict[str, Any],
        envelope: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        mode = route["dispatch"]["mode"]
        adapter = self._adapters.get(mode)
        if adapter is None:
            raise TransportError(
                f"No transport adapter is registered for mode {mode}"
            )
        return await adapter.dispatch(
            route=route,
            envelope=envelope,
            manifest=manifest,
        )

    async def check_manifest_health(
        self,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        product_id = manifest["product_id"]
        health_endpoint = manifest.get("health_endpoint")
        if not health_endpoint:
            return {
                "product_id": product_id,
                "status": "not_configured",
                "transport": "none",
                "message": "No health_endpoint is published by the manifest",
            }
        endpoint = str(health_endpoint)
        base_url = manifest.get("base_url")
        if not endpoint.startswith(("http://", "https://")):
            if not base_url:
                return {
                    "product_id": product_id,
                    "status": "unknown",
                    "transport": "http",
                    "message": "Relative health_endpoint requires base_url",
                }
            endpoint = urljoin(
                str(base_url).rstrip("/") + "/",
                endpoint.lstrip("/"),
            )
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.default_timeout_seconds,
            ) as client:
                response = await client.get(endpoint)
            latency_ms = (time.perf_counter() - started) * 1000
            healthy = 200 <= response.status_code < 400
            try:
                payload: Any = response.json()
                json_response = True
            except ValueError:
                payload = {"body": response.text[:500]}
                json_response = False
            health_contract = HttpTransportAdapter.validate_health_contract(
                manifest=manifest,
                response=response,
                payload=payload,
                json_response=json_response,
            )
            healthy = healthy and health_contract["valid"]
            return {
                "product_id": product_id,
                "status": "healthy" if healthy else "unhealthy",
                "transport": "http",
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 3),
                "endpoint": endpoint,
                "response": payload,
                "health_contract": health_contract,
            }
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return {
                "product_id": product_id,
                "status": "unhealthy",
                "transport": "http",
                "latency_ms": round(latency_ms, 3),
                "endpoint": endpoint,
                "error": f"{type(exc).__name__}: {exc}",
            }
