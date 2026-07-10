from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .constants import (
    COMPATIBILITY_VERSION,
    CONTRACT_VERSION,
    RUNTIME_VERSION,
    SCHEMA_VERSION,
)
from .errors import ContractCompatibilityError


class VersionedContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    runtime_version: str = RUNTIME_VERSION
    compatibility_version: str = COMPATIBILITY_VERSION


class DispatchTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(pattern=r"^[a-z][a-z0-9-]{1,31}$")
    endpoint: str = Field(min_length=1)
    timeout_seconds: float | None = Field(default=None, gt=0, le=120)
    options: dict[str, Any] = Field(default_factory=dict)


class IntentRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,95}$")
    description: str = Field(min_length=3, max_length=500)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"}
    )
    dispatch: DispatchTarget
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    description: str = Field(min_length=3, max_length=500)
    context_scopes: list[
        Literal["session", "workspace", "product", "handoff"]
    ] = Field(default_factory=lambda: ["session", "workspace", "product"])
    intents: list[IntentRegistration] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductAttachmentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    display_name: str = Field(min_length=3, max_length=120)
    product_version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$"
    )
    contract_version: str = CONTRACT_VERSION
    attachment_mode: Literal["standalone", "embedded", "remote", "simulated"]
    base_url: HttpUrl | None = None
    health_endpoint: str | None = None
    capabilities: list[CapabilityRegistration] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttachmentRequest(VersionedContract):
    manifest: ProductAttachmentManifest


class SessionCreateRequest(VersionedContract):
    actor_id: str = Field(min_length=1, max_length=200)
    client_type: Literal["standalone", "embedded", "mobile", "xr", "robotics"]
    workspace_id: str = Field(min_length=1, max_length=200)
    product_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResumeRequest(VersionedContract):
    resume_token: str = Field(min_length=24, max_length=300)


class ContextUpdateRequest(VersionedContract):
    scope: Literal["session", "workspace", "product", "handoff"]
    patch: dict[str, Any]
    expected_revision: int | None = Field(default=None, ge=0)
    replace: bool = False


class ContextTransferRequest(VersionedContract):
    target_workspace_id: str = Field(min_length=1, max_length=200)
    target_product_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    portable_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductExchangeRequest(VersionedContract):
    source_product_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    target_product_ids: list[str] = Field(min_length=1, max_length=50)
    session_id: str | None = Field(default=None, min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=200)
    exchange_type: Literal[
        "context",
        "event",
        "artifact",
        "status",
        "handoff",
    ] = "context"
    classification: Literal["public", "internal", "confidential"] = "internal"
    subject: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_ref: str | None = Field(default=None, min_length=1, max_length=500)
    ttl_seconds: int | None = Field(default=None, gt=0, le=2_592_000)
    correlation_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductExchangeAckRequest(VersionedContract):
    product_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    status: Literal["RECEIVED", "CONSUMED", "REJECTED"] = "RECEIVED"
    note: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentDispatchRequest(VersionedContract):
    session_id: str = Field(min_length=1)
    intent_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,95}$")
    product_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    capability_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class CompanionMessageRequest(VersionedContract):
    session_id: str | None = Field(default=None, min_length=1)
    actor_id: str | None = Field(default=None, min_length=1, max_length=200)
    client_type: Literal["standalone", "embedded", "mobile", "xr", "robotics"] = (
        "standalone"
    )
    workspace_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    product_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    capability_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    message: str = Field(min_length=1, max_length=4000)
    assignment: str | None = Field(default=None, min_length=1, max_length=12000)
    payload: dict[str, Any] = Field(default_factory=dict)
    auto_dispatch: bool = True
    allow_ai_fallback: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeAnalysisRequest(VersionedContract):
    session_id: str | None = Field(default=None, min_length=1)
    product_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    capability_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    message: str = Field(min_length=1, max_length=4000)
    assignment: str | None = Field(default=None, min_length=1, max_length=12000)
    payload: dict[str, Any] = Field(default_factory=dict)
    allow_ai_fallback: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_contract(contract: VersionedContract) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "compatibility_version": COMPATIBILITY_VERSION,
    }
    received = contract.model_dump(include=set(expected))
    incompatible = {
        field: {"received": received[field], "supported": value}
        for field, value in expected.items()
        if received[field] != value
    }
    if incompatible:
        raise ContractCompatibilityError(
            f"Incompatible companion runtime contract: {incompatible}"
        )


def versioned_response(**payload: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "compatibility_version": COMPATIBILITY_VERSION,
        **payload,
    }
