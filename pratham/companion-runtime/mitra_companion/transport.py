from __future__ import annotations

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
        try:
            async with httpx.AsyncClient(
                transport=self.http_transport,
                timeout=timeout,
            ) as client:
                response = await client.post(
                    endpoint,
                    json=envelope,
                    headers={
                        "X-Contract-Version": envelope["contract_version"],
                        "X-Companion-Session": envelope["session_id"],
                        "X-Correlation-ID": envelope["correlation_id"],
                    },
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


class CapabilityTransport:
    """Adapter registry selected only by a manifest's published mode."""

    def __init__(
        self,
        *,
        default_timeout_seconds: float,
        http_transport: httpx.AsyncBaseTransport | None = None,
        adapters: list[TransportAdapter] | None = None,
    ):
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

