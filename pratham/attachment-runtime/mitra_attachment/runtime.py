from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from mitra_companion.constants import AttachmentState, CONTRACT_VERSION
from mitra_companion.contracts import ProductAttachmentManifest
from mitra_companion.errors import (
    AttachmentValidationError,
    ResourceNotFoundError,
)
from mitra_companion.ports import AttachmentStorePort


class AttachmentRuntime:
    """Registers product capabilities from published manifests only."""

    def __init__(self, store: AttachmentStorePort):
        self.store = store

    @staticmethod
    def _validate_manifest(manifest: ProductAttachmentManifest) -> None:
        if manifest.contract_version != CONTRACT_VERSION:
            raise AttachmentValidationError(
                f"Unsupported attachment contract {manifest.contract_version}; "
                f"expected {CONTRACT_VERSION}"
            )
        capability_ids: set[str] = set()
        for capability in manifest.capabilities:
            if capability.capability_id in capability_ids:
                raise AttachmentValidationError(
                    f"Duplicate capability ID: {capability.capability_id}"
                )
            capability_ids.add(capability.capability_id)
            if len(capability.context_scopes) != len(
                set(capability.context_scopes)
            ):
                raise AttachmentValidationError(
                    "Duplicate context scope in capability: "
                    f"{capability.capability_id}"
                )
            intent_ids: set[str] = set()
            for intent in capability.intents:
                if intent.intent_id in intent_ids:
                    raise AttachmentValidationError(
                        f"Duplicate intent ID in capability: "
                        f"{intent.intent_id}"
                    )
                intent_ids.add(intent.intent_id)
                try:
                    Draft202012Validator.check_schema(intent.input_schema)
                except SchemaError as exc:
                    raise AttachmentValidationError(
                        f"Invalid input schema for {intent.intent_id}: "
                        f"{exc.message}"
                    ) from exc

    def attach(
        self,
        manifest: ProductAttachmentManifest,
    ) -> dict[str, Any]:
        self._validate_manifest(manifest)
        return self.store.attach_product(
            manifest.product_id,
            manifest.model_dump(mode="json"),
        )

    def attach_many(
        self,
        manifests: Iterable[ProductAttachmentManifest],
    ) -> dict[str, Any]:
        attachments = [self.attach(manifest) for manifest in manifests]
        return {
            "attached_count": len(attachments),
            "attachments": attachments,
        }

    def get(self, product_id: str) -> dict[str, Any]:
        attachment = self.store.get_attachment(product_id)
        if attachment is None:
            raise ResourceNotFoundError(f"Unknown product: {product_id}")
        return attachment

    def list(
        self,
        *,
        include_detached: bool = False,
    ) -> list[dict[str, Any]]:
        return self.store.list_attachments(
            include_detached=include_detached,
        )

    def detach(self, product_id: str) -> dict[str, Any]:
        self.get(product_id)
        return self.store.set_attachment_state(
            product_id,
            AttachmentState.DETACHED,
        )

    def mark_degraded(
        self,
        product_id: str,
        error: str,
    ) -> dict[str, Any]:
        self.get(product_id)
        return self.store.set_attachment_state(
            product_id,
            AttachmentState.DEGRADED,
            error,
        )
