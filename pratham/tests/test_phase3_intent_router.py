from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import (
    AmbiguousIntentError,
    AttachmentValidationError,
    IntentRoutingError,
    ResourceNotFoundError,
    TransportError,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport


ROOT = Path(__file__).resolve().parents[2]


def _ambiguous_manifest() -> ProductAttachmentManifest:
    return ProductAttachmentManifest.model_validate(
        {
            "product_id": "routing-fixture",
            "display_name": "Routing Fixture",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "capabilities": [
                {
                    "capability_id": "primary-navigation",
                    "description": "Primary explicit navigation capability",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "fixture.open",
                            "description": "Open through the primary capability",
                            "input_schema": {
                                "type": "object",
                                "required": ["resource_id"],
                            },
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": "loopback://fixture/primary",
                            },
                        }
                    ],
                },
                {
                    "capability_id": "secondary-navigation",
                    "description": "Secondary explicit navigation capability",
                    "context_scopes": ["workspace"],
                    "intents": [
                        {
                            "intent_id": "fixture.open",
                            "description": "Open through the secondary capability",
                            "input_schema": {
                                "type": "object",
                                "required": ["resource_id"],
                            },
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": "loopback://fixture/secondary",
                            },
                        }
                    ],
                },
            ],
        }
    )


def test_manifest_attachment_materializes_deterministic_registrations(
    runtime,
    atlas_manifest,
):
    attached = runtime.attach(atlas_manifest)
    registration = runtime.router.register(atlas_manifest.product_id)

    assert attached["intent_registration_count"] == 2
    assert registration["registration_count"] == 2
    assert [
        item["registration_id"]
        for item in registration["registrations"]
    ] == [
        "atlas-workspace:workspace-navigation:workspace.open-record",
        "atlas-workspace:workspace-navigation:workspace.show-queue",
    ]


def test_intent_discovery_filters_and_capability_lookup(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(nova_manifest)
    runtime.attach(atlas_manifest)

    discovered = runtime.router.discover(
        product_id=atlas_manifest.product_id,
        capability_id="workspace-navigation",
        intent_id="workspace.show-queue",
    )
    assert [item["intent_id"] for item in discovered] == [
        "workspace.show-queue"
    ]

    capabilities = runtime.router.capabilities()
    assert [
        (item["product_id"], item["capability_id"])
        for item in capabilities
    ] == [
        ("atlas-workspace", "workspace-navigation"),
        ("nova-operations", "operations-navigation"),
    ]
    capability = runtime.router.lookup_capability(
        product_id="atlas-workspace",
        capability_id="workspace-navigation",
    )
    assert capability["intent_count"] == 2
    assert capability["intent_ids"] == [
        "workspace.open-record",
        "workspace.show-queue",
    ]
    with pytest.raises(ResourceNotFoundError):
        runtime.router.lookup_capability(
            product_id="atlas-workspace",
            capability_id="missing-capability",
        )


@pytest.mark.asyncio
async def test_ambiguous_intent_requires_explicit_capability(runtime):
    manifest = _ambiguous_manifest()
    runtime.attach(manifest)
    session = runtime.sessions.create(
        actor_id="ambiguity-user",
        client_type="embedded",
        workspace_id="ambiguity-workspace",
        product_id=manifest.product_id,
    )

    with pytest.raises(AmbiguousIntentError):
        runtime.router.route(
            session_id=session["session_id"],
            intent_id="fixture.open",
            product_id=None,
            capability_id=None,
        )

    result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            intent_id="fixture.open",
            capability_id="secondary-navigation",
            payload={"resource_id": "record-1"},
        )
    )
    assert result["route"]["capability_id"] == "secondary-navigation"
    assert result["route"]["capability_resolution"] == "explicit"
    assert result["dispatch"]["status"] == "COMPLETED"


def test_explicit_product_routing_for_unbound_session(runtime, atlas_manifest):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="unbound-user",
        client_type="standalone",
        workspace_id="unbound-workspace",
        product_id=None,
    )
    route = runtime.router.route(
        session_id=session["session_id"],
        intent_id="workspace.show-queue",
        product_id=atlas_manifest.product_id,
        capability_id=None,
    )
    assert route["product_id"] == atlas_manifest.product_id
    assert route["product_resolution"] == "explicit"


def test_unavailable_product_is_discoverable_but_not_routable(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="degraded-user",
        client_type="embedded",
        workspace_id="degraded-workspace",
        product_id=atlas_manifest.product_id,
    )
    runtime.attachments.mark_degraded(
        atlas_manifest.product_id,
        "fixture unavailable",
    )

    assert len(
        runtime.router.discover(product_id=atlas_manifest.product_id)
    ) == 2
    assert runtime.router.discover(
        product_id=atlas_manifest.product_id,
        available_only=True,
    ) == []
    with pytest.raises(IntentRoutingError):
        runtime.router.route(
            session_id=session["session_id"],
            intent_id="workspace.show-queue",
            product_id=None,
            capability_id=None,
        )


def test_registration_rejects_duplicate_scope_and_duplicate_intent_in_capability(
    runtime,
):
    duplicate_scope = _ambiguous_manifest().model_copy(deep=True)
    duplicate_scope.capabilities[0].context_scopes = ["session", "session"]
    with pytest.raises(AttachmentValidationError):
        runtime.attach(duplicate_scope)

    duplicate_intent = _ambiguous_manifest().model_copy(deep=True)
    duplicate_intent.capabilities[0].intents.append(
        duplicate_intent.capabilities[0].intents[0].model_copy()
    )
    with pytest.raises(AttachmentValidationError):
        runtime.attach(duplicate_intent)


@pytest.mark.asyncio
async def test_unexpected_adapter_exception_is_persisted_as_failed_dispatch(
    settings_factory,
):
    class ExplodingAdapter:
        mode = "exploding"

        def validate_target(self, manifest, target):
            assert target.endpoint.startswith("exploding://")

        async def dispatch(self, *, route, envelope, manifest):
            raise ValueError("adapter fixture exploded")

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        adapters=[ExplodingAdapter()],
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "exploding-fixture",
                "display_name": "Exploding Fixture",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "simulated",
                "capabilities": [
                    {
                        "capability_id": "fixture-execution",
                        "description": "Adapter failure fixture capability",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "fixture.explode",
                                "description": "Trigger the adapter fixture",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "exploding",
                                    "endpoint": "exploding://fixture",
                                },
                            }
                        ],
                    }
                ],
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="adapter-failure-user",
            client_type="standalone",
            workspace_id="adapter-failure-workspace",
            product_id=manifest.product_id,
        )

        with pytest.raises(TransportError):
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=session["session_id"],
                    intent_id="fixture.explode",
                    payload={},
                )
            )

        dispatches = runtime.store.list_dispatches()
        assert len(dispatches) == 1
        assert dispatches[0]["status"] == "FAILED"
        assert "ValueError" in dispatches[0]["error"]
        assert runtime.attachments.get(manifest.product_id)["state"] == (
            "DEGRADED"
        )
    finally:
        runtime.stop()


def test_phase3_router_contracts_validate_against_runtime_views(
    runtime,
    atlas_manifest,
):
    policy = json.loads(
        (ROOT / "contracts" / "intent-router-policy.json").read_text(
            encoding="utf-8"
        )
    )
    policy_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "intent-router-policy.schema.json"
        ).read_text(encoding="utf-8")
    )
    registration_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "intent-registration.schema.json"
        ).read_text(encoding="utf-8")
    )
    capability_schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "capability-view.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(policy_schema).validate(policy)

    runtime.attach(atlas_manifest)
    registration = runtime.router.discover(
        product_id=atlas_manifest.product_id
    )[0]
    capability = runtime.router.lookup_capability(
        product_id=atlas_manifest.product_id,
        capability_id="workspace-navigation",
    )
    Draft202012Validator(registration_schema).validate(registration)
    Draft202012Validator(capability_schema).validate(capability)


def test_intent_registrations_survive_runtime_recreation(
    settings_factory,
    atlas_manifest,
):
    first = CompanionRuntime(settings_factory())
    first.start()
    first.attach(atlas_manifest)
    first.stop()

    second = CompanionRuntime(settings_factory())
    second.start()
    try:
        registration = second.router.register(atlas_manifest.product_id)
        assert registration["registration_count"] == 2
    finally:
        second.stop()
