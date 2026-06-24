from __future__ import annotations

from typing import Any

from mitra_companion.constants import AttachmentState, SessionState
from mitra_companion.errors import (
    AmbiguousIntentError,
    IntentRoutingError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from mitra_companion.ports import (
    AttachmentRegistryPort,
    SessionLookupPort,
)


class IntentRouter:
    """Registers and routes explicit intent IDs without domain inference."""

    def __init__(
        self,
        attachments: AttachmentRegistryPort,
        sessions: SessionLookupPort,
    ):
        self.attachments = attachments
        self.sessions = sessions

    @staticmethod
    def _registration_id(
        product_id: str,
        capability_id: str,
        intent_id: str,
    ) -> str:
        return f"{product_id}:{capability_id}:{intent_id}"

    @classmethod
    def _registrations(
        cls,
        attachment: dict[str, Any],
    ) -> list[dict[str, Any]]:
        manifest = attachment["manifest"]
        registrations: list[dict[str, Any]] = []
        for capability in manifest["capabilities"]:
            for intent in capability["intents"]:
                registrations.append(
                    {
                        "registration_id": cls._registration_id(
                            manifest["product_id"],
                            capability["capability_id"],
                            intent["intent_id"],
                        ),
                        "product_id": manifest["product_id"],
                        "product_name": manifest["display_name"],
                        "product_version": manifest["product_version"],
                        "attachment_state": attachment["state"],
                        "registered_at": attachment["attached_at"],
                        "capability_id": capability["capability_id"],
                        "capability_description": capability["description"],
                        "capability_metadata": capability["metadata"],
                        "context_scopes": capability["context_scopes"],
                        **intent,
                    }
                )
        return sorted(
            registrations,
            key=lambda item: (
                item["product_id"],
                item["capability_id"],
                item["intent_id"],
            ),
        )

    def register(self, product_id: str) -> dict[str, Any]:
        """Materialize intent registrations from one attached manifest."""
        attachment = self.attachments.get(product_id)
        if attachment["state"] == AttachmentState.DETACHED.value:
            raise IntentRoutingError(
                f"Detached product cannot register intents: {product_id}"
            )
        registrations = self._registrations(attachment)
        return {
            "product_id": product_id,
            "product_version": attachment["manifest"]["product_version"],
            "attachment_state": attachment["state"],
            "registered_at": attachment["attached_at"],
            "registration_count": len(registrations),
            "registrations": registrations,
        }

    def discover(
        self,
        *,
        product_id: str | None = None,
        capability_id: str | None = None,
        intent_id: str | None = None,
        available_only: bool = False,
    ) -> list[dict[str, Any]]:
        attachments = (
            [self.attachments.get(product_id)]
            if product_id
            else self.attachments.list()
        )
        discovered: list[dict[str, Any]] = []
        for attachment in attachments:
            if attachment["state"] == AttachmentState.DETACHED.value:
                continue
            if (
                available_only
                and attachment["state"] != AttachmentState.ATTACHED.value
            ):
                continue
            for registration in self._registrations(attachment):
                if (
                    capability_id
                    and registration["capability_id"] != capability_id
                ):
                    continue
                if intent_id and registration["intent_id"] != intent_id:
                    continue
                discovered.append(registration)
        return sorted(
            discovered,
            key=lambda item: (
                item["product_id"],
                item["capability_id"],
                item["intent_id"],
            ),
        )

    def capabilities(
        self,
        *,
        product_id: str | None = None,
        available_only: bool = False,
    ) -> list[dict[str, Any]]:
        attachments = (
            [self.attachments.get(product_id)]
            if product_id
            else self.attachments.list()
        )
        capabilities: list[dict[str, Any]] = []
        for attachment in attachments:
            if attachment["state"] == AttachmentState.DETACHED.value:
                continue
            if (
                available_only
                and attachment["state"] != AttachmentState.ATTACHED.value
            ):
                continue
            manifest = attachment["manifest"]
            for capability in manifest["capabilities"]:
                capabilities.append(
                    {
                        "product_id": manifest["product_id"],
                        "product_name": manifest["display_name"],
                        "product_version": manifest["product_version"],
                        "attachment_state": attachment["state"],
                        "capability_id": capability["capability_id"],
                        "description": capability["description"],
                        "context_scopes": capability["context_scopes"],
                        "metadata": capability["metadata"],
                        "intent_ids": sorted(
                            intent["intent_id"]
                            for intent in capability["intents"]
                        ),
                        "intent_count": len(capability["intents"]),
                    }
                )
        return sorted(
            capabilities,
            key=lambda item: (
                item["product_id"],
                item["capability_id"],
            ),
        )

    def lookup_capability(
        self,
        *,
        product_id: str,
        capability_id: str,
    ) -> dict[str, Any]:
        matches = [
            capability
            for capability in self.capabilities(product_id=product_id)
            if capability["capability_id"] == capability_id
        ]
        if not matches:
            raise ResourceNotFoundError(
                f"Unknown capability {capability_id} in product {product_id}"
            )
        return matches[0]

    def route(
        self,
        *,
        session_id: str,
        intent_id: str,
        product_id: str | None,
        capability_id: str | None,
    ) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session["state"] != SessionState.ACTIVE.value:
            raise ResourceConflictError(
                "Only active sessions can route intents"
            )
        target_product = product_id or session["active_product_id"]
        if target_product is None:
            raise IntentRoutingError(
                "A product_id is required when the session has no active product"
            )
        if (
            session["active_product_id"]
            and target_product != session["active_product_id"]
        ):
            raise ResourceConflictError(
                "Cross-product dispatch requires an explicit context transfer"
            )

        if capability_id:
            self.lookup_capability(
                product_id=target_product,
                capability_id=capability_id,
            )
        matches = self.discover(
            product_id=target_product,
            capability_id=capability_id,
            intent_id=intent_id,
        )
        if not matches:
            raise IntentRoutingError(
                f"No registered route for intent {intent_id} in product "
                f"{target_product}"
            )
        if len(matches) > 1:
            raise AmbiguousIntentError(
                f"Intent {intent_id} resolves to multiple capabilities in "
                f"product {target_product}; provide capability_id"
            )
        route = matches[0]
        if route["attachment_state"] != AttachmentState.ATTACHED.value:
            raise IntentRoutingError(
                f"Product {target_product} is not available for dispatch"
            )
        return {
            **route,
            "product_resolution": (
                "explicit" if product_id is not None else "session"
            ),
            "capability_resolution": (
                "explicit" if capability_id is not None else "single-match"
            ),
        }
