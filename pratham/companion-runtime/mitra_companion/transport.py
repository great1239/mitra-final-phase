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


def _normalize_endpoint_overrides(
    overrides: dict[str, str] | None,
) -> dict[str, str]:
    return {
        source.rstrip("/"): target.rstrip("/")
        for source, target in (overrides or {}).items()
    }


def _rewrite_endpoint(endpoint: str, overrides: dict[str, str]) -> str:
    for source in sorted(overrides, key=len, reverse=True):
        if endpoint == source or endpoint.startswith(source + "/"):
            return overrides[source] + endpoint[len(source) :]
    return endpoint


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
        endpoint_overrides: dict[str, str] | None = None,
    ):
        self.default_timeout_seconds = default_timeout_seconds
        self.http_transport = http_transport
        self.endpoint_overrides = _normalize_endpoint_overrides(
            endpoint_overrides
        )

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
        self._validate_response_fallbacks(target.options)

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

    def _validate_response_fallbacks(self, options: dict[str, Any]) -> None:
        fallbacks = options.get("response_fallbacks")
        if fallbacks is None:
            return
        if not isinstance(fallbacks, list):
            raise AttachmentValidationError(
                "HTTP adapter response_fallbacks option must be an array"
            )
        for fallback in fallbacks:
            if not isinstance(fallback, dict):
                raise AttachmentValidationError(
                    "HTTP adapter response_fallbacks entries must be objects"
                )
            endpoint = fallback.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint:
                raise AttachmentValidationError(
                    "HTTP adapter response fallback endpoint is required"
                )
            request_body = fallback.get("request_body", "payload")
            if request_body not in self._REQUEST_BODY_MODES:
                raise AttachmentValidationError(
                    "HTTP adapter response fallback request_body option must "
                    "be one of: envelope, payload, none"
                )
            self._validate_header_options(fallback)

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

    @staticmethod
    def _resolve_endpoint(endpoint: str, base_url: str | None) -> str:
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        if not base_url:
            raise TransportError("Relative HTTP endpoint requires product base_url")
        return urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))

    def _resolve_runtime_endpoint(
        self,
        endpoint: str,
        base_url: str | None,
    ) -> str:
        published = self._resolve_endpoint(endpoint, base_url)
        return _rewrite_endpoint(published, self.endpoint_overrides)

    @staticmethod
    def _request_kwargs(
        *,
        request_body: str,
        envelope: dict[str, Any],
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if request_body == "envelope":
            return {"json": envelope}
        if request_body == "payload":
            return {"json": envelope["payload"] if payload is None else payload}
        if request_body == "none":
            return {}
        raise TransportError(
            "HTTP adapter request_body option must be one of: "
            "envelope, payload, none"
        )

    @staticmethod
    def _lookup_field(payload: dict[str, Any], path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _matches_response_condition(
        cls,
        payload: dict[str, Any],
        condition: dict[str, Any],
    ) -> bool:
        equals = condition.get("field_equals") or {}
        if isinstance(equals, dict):
            for field, expected in equals.items():
                if cls._lookup_field(payload, str(field)) != expected:
                    return False
        contains = condition.get("field_contains") or {}
        if isinstance(contains, dict):
            for field, expected in contains.items():
                actual = cls._lookup_field(payload, str(field))
                if str(expected).lower() not in str(actual or "").lower():
                    return False
        return True

    @classmethod
    def _fallback_payload(
        cls,
        *,
        fallback: dict[str, Any],
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        payload_spec = fallback.get("payload") or {}
        source = envelope["payload"]
        if not isinstance(payload_spec, dict):
            raise TransportError("HTTP response fallback payload must be an object")
        result: dict[str, Any] = {}
        defaults = payload_spec.get("defaults") or {}
        if isinstance(defaults, dict):
            result.update(defaults)
        copy_fields = payload_spec.get("copy_fields") or []
        if isinstance(copy_fields, list):
            for field in copy_fields:
                value = cls._lookup_field(source, str(field))
                if value is not None:
                    result[str(field).split(".")[-1]] = value
        elif isinstance(copy_fields, dict):
            for target_field, source_field in copy_fields.items():
                value = cls._lookup_field(source, str(source_field))
                if value is not None:
                    result[str(target_field)] = value
        set_values = payload_spec.get("set") or {}
        if isinstance(set_values, dict):
            result.update(set_values)
        return result

    @classmethod
    def _translated_fallback_response(
        cls,
        *,
        fallback: dict[str, Any],
        primary_payload: dict[str, Any],
        fallback_payload: dict[str, Any],
        fallback_endpoint: str,
    ) -> dict[str, Any]:
        response_spec = fallback.get("response") or {}
        if not isinstance(response_spec, dict):
            return fallback_payload
        result: dict[str, Any] = {}
        copy_fields = response_spec.get("copy_fields") or {}
        if isinstance(copy_fields, list):
            for field in copy_fields:
                value = cls._lookup_field(fallback_payload, str(field))
                if value is not None:
                    result[str(field).split(".")[-1]] = value
        elif isinstance(copy_fields, dict):
            for target_field, source_field in copy_fields.items():
                value = cls._lookup_field(fallback_payload, str(source_field))
                if value is not None:
                    result[str(target_field)] = value
        set_values = response_spec.get("set") or {}
        if isinstance(set_values, dict):
            result.update(set_values)
        include_raw_as = response_spec.get("include_raw_as")
        if include_raw_as:
            result[str(include_raw_as)] = fallback_payload
        include_original_as = response_spec.get("include_original_as")
        if include_original_as:
            result[str(include_original_as)] = primary_payload
        result["dispatch_fallback"] = {
            "applied": True,
            "name": fallback.get("name"),
            "endpoint": fallback_endpoint,
        }
        return result or fallback_payload

    async def _post_json(
        self,
        *,
        client: httpx.AsyncClient,
        endpoint: str,
        request_kwargs: dict[str, Any],
        headers: dict[str, str],
        failure_prefix: str,
    ) -> dict[str, Any]:
        try:
            response = await client.post(endpoint, **request_kwargs, headers=headers)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise TransportError(
                f"{failure_prefix}: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError(
                f"{failure_prefix}: endpoint returned a non-JSON response"
            ) from exc
        if not isinstance(payload, dict):
            raise TransportError(
                f"{failure_prefix}: endpoint response must be a JSON object"
            )
        return payload

    async def _apply_response_fallbacks(
        self,
        *,
        client: httpx.AsyncClient,
        primary_payload: dict[str, Any],
        route: dict[str, Any],
        envelope: dict[str, Any],
        base_url: str | None,
        timeout_headers: dict[str, str],
    ) -> dict[str, Any]:
        fallbacks = route["dispatch"].get("options", {}).get(
            "response_fallbacks",
            [],
        )
        if not isinstance(fallbacks, list):
            return primary_payload
        for fallback in fallbacks:
            if not isinstance(fallback, dict):
                continue
            condition = fallback.get("when") or {}
            if not isinstance(condition, dict):
                continue
            if not self._matches_response_condition(primary_payload, condition):
                continue
            fallback_endpoint = self._resolve_runtime_endpoint(
                str(fallback["endpoint"]),
                base_url,
            )
            fallback_body = self._fallback_payload(
                fallback=fallback,
                envelope=envelope,
            )
            fallback_headers = self._headers_from_options(fallback)
            fallback_headers.update(timeout_headers)
            request_kwargs = self._request_kwargs(
                request_body=str(fallback.get("request_body", "payload")),
                envelope=envelope,
                payload=fallback_body,
            )
            fallback_response = await self._post_json(
                client=client,
                endpoint=fallback_endpoint,
                request_kwargs=request_kwargs,
                headers=fallback_headers,
                failure_prefix="Capability response fallback failed",
            )
            return self._translated_fallback_response(
                fallback=fallback,
                primary_payload=primary_payload,
                fallback_payload=fallback_response,
                fallback_endpoint=fallback_endpoint,
            )
        return primary_payload

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
        endpoint = self._resolve_runtime_endpoint(endpoint, base_url)
        timeout = (
            target.get("timeout_seconds")
            or self.default_timeout_seconds
        )
        request_body = target.get("options", {}).get(
            "request_body",
            "envelope",
        )
        request_kwargs = self._request_kwargs(
            request_body=request_body,
            envelope=envelope,
        )
        headers = self._headers_from_options(target.get("options", {}))
        runtime_headers = {
            "X-Contract-Version": envelope["contract_version"],
            "X-Companion-Session": envelope["session_id"],
            "X-Correlation-ID": envelope["correlation_id"],
        }
        headers.update(runtime_headers)
        async with httpx.AsyncClient(
            transport=self.http_transport,
            timeout=timeout,
        ) as client:
            payload = await self._post_json(
                client=client,
                endpoint=endpoint,
                request_kwargs=request_kwargs,
                headers=headers,
                failure_prefix="Capability endpoint failed",
            )
            return await self._apply_response_fallbacks(
                client=client,
                primary_payload=payload,
                route=route,
                envelope=envelope,
                base_url=base_url,
                timeout_headers=runtime_headers,
            )

    @staticmethod
    def _health_contract(manifest: dict[str, Any]) -> dict[str, Any]:
        contract = (manifest.get("metadata") or {}).get("health_contract") or {}
        return contract if isinstance(contract, dict) else {}

    @staticmethod
    def _health_translator(manifest: dict[str, Any]) -> dict[str, Any]:
        translator = HttpTransportAdapter._health_contract(manifest).get(
            "translator",
            {},
        )
        return translator if isinstance(translator, dict) else {}

    @staticmethod
    def health_follow_redirects(manifest: dict[str, Any]) -> bool:
        contract = HttpTransportAdapter._health_contract(manifest)
        translator = HttpTransportAdapter._health_translator(manifest)
        return bool(
            contract.get("follow_redirects")
            or translator.get("follow_redirects")
        )

    @staticmethod
    def translate_health_payload(
        *,
        manifest: dict[str, Any],
        response: httpx.Response,
        payload: Any,
        json_response: bool,
    ) -> tuple[Any, bool, dict[str, Any]]:
        contract = HttpTransportAdapter._health_contract(manifest)
        translator = HttpTransportAdapter._health_translator(manifest)
        result: dict[str, Any] = {
            "enabled": bool(translator),
            "applied": False,
        }
        if not translator:
            return payload, json_response, result

        status_field = str(contract.get("status_field") or "status")
        if isinstance(payload, dict) and json_response:
            translated = dict(payload)
            for alias in translator.get("status_field_aliases", []) or []:
                alias_key = str(alias)
                if status_field not in translated and alias_key in translated:
                    translated[status_field] = translated[alias_key]
                    result.update(
                        {
                            "applied": True,
                            "rule": "status_field_alias",
                            "source_field": alias_key,
                            "target_field": status_field,
                        }
                    )
                    break

            value_map = translator.get("status_value_map") or {}
            if isinstance(value_map, dict) and status_field in translated:
                current = str(translated.get(status_field) or "").lower()
                if current in value_map:
                    translated[status_field] = value_map[current]
                    result.update(
                        {
                            "applied": True,
                            "rule": "status_value_map",
                            "source_value": current,
                            "target_value": translated[status_field],
                        }
                    )
            return translated, True, result

        body = ""
        if isinstance(payload, dict):
            body = str(payload.get("body") or "")
        elif isinstance(payload, str):
            body = payload
        lowered_body = body.lower()
        for rule in translator.get("body_contains", []) or []:
            if not isinstance(rule, dict):
                continue
            contains = str(rule.get("contains") or "")
            if contains and contains.lower() in lowered_body:
                translated_status_field = str(
                    rule.get("status_field") or status_field
                )
                translated = {
                    translated_status_field: str(
                        rule.get("status") or "unknown"
                    )
                }
                if rule.get("reason"):
                    translated["reason"] = str(rule["reason"])
                result.update(
                    {
                        "applied": True,
                        "rule": "body_contains",
                        "matched": contains,
                        "source_content_type": response.headers.get(
                            "content-type",
                            "",
                        ),
                        "source_status_code": response.status_code,
                    }
                )
                return translated, True, result

        return payload, json_response, result

    @staticmethod
    def validate_health_contract(
        *,
        manifest: dict[str, Any],
        response: httpx.Response,
        payload: Any,
        json_response: bool,
    ) -> dict[str, Any]:
        contract = HttpTransportAdapter._health_contract(manifest)
        if not contract:
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
        endpoint_overrides: dict[str, str] | None = None,
    ):
        self.default_timeout_seconds = default_timeout_seconds
        self.http_transport = http_transport
        self.endpoint_overrides = _normalize_endpoint_overrides(
            endpoint_overrides
        )
        self._adapters: dict[str, TransportAdapter] = {}
        self.loopback_adapter = LoopbackTransportAdapter()
        self.register_adapter(self.loopback_adapter)
        self.register_adapter(
            HttpTransportAdapter(
                default_timeout_seconds=default_timeout_seconds,
                http_transport=http_transport,
                endpoint_overrides=self.endpoint_overrides,
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
        published_endpoint = endpoint
        endpoint = _rewrite_endpoint(endpoint, self.endpoint_overrides)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=self.default_timeout_seconds,
            ) as client:
                response = await client.get(
                    endpoint,
                    follow_redirects=(
                        HttpTransportAdapter.health_follow_redirects(
                            manifest
                        )
                    ),
                )
            latency_ms = (time.perf_counter() - started) * 1000
            healthy = 200 <= response.status_code < 400
            try:
                payload: Any = response.json()
                json_response = True
            except ValueError:
                payload = {"body": response.text[:500]}
                json_response = False
            raw_payload = payload
            (
                payload,
                json_response,
                health_translation,
            ) = HttpTransportAdapter.translate_health_payload(
                manifest=manifest,
                response=response,
                payload=payload,
                json_response=json_response,
            )
            health_contract = HttpTransportAdapter.validate_health_contract(
                manifest=manifest,
                response=response,
                payload=payload,
                json_response=json_response,
            )
            healthy = healthy and health_contract["valid"]
            result = {
                "product_id": product_id,
                "status": "healthy" if healthy else "unhealthy",
                "transport": "http",
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 3),
                "endpoint": endpoint,
                "response": payload,
                "health_contract": health_contract,
            }
            if endpoint != published_endpoint:
                result["published_endpoint"] = published_endpoint
            if str(response.url) != endpoint:
                result["final_endpoint"] = str(response.url)
            if response.history:
                result["redirect_chain"] = [
                    {
                        "status_code": item.status_code,
                        "url": str(item.url),
                        "location": item.headers.get("location"),
                    }
                    for item in response.history
                ]
            if health_translation["enabled"]:
                result["health_translation"] = health_translation
            if health_translation["applied"]:
                result["raw_response"] = raw_payload
            return result
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = {
                "product_id": product_id,
                "status": "unhealthy",
                "transport": "http",
                "latency_ms": round(latency_ms, 3),
                "endpoint": endpoint,
                "error": f"{type(exc).__name__}: {exc}",
            }
            if endpoint != published_endpoint:
                result["published_endpoint"] = published_endpoint
            return result
