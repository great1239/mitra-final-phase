from __future__ import annotations

import httpx
import pytest

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.errors import (
    IntentRoutingError,
    ResourceConflictError,
    TransportError,
)
from mitra_companion.runtime import CompanionRuntime
from mitra_companion.transport import CapabilityTransport
from mitra_companion.utils import sha256_json


EXPECTED_DISPATCH_PHASES = [
    "request.accepted",
    "route.selected",
    "payload.validated",
    "context.loaded",
    "transport.dispatched",
    "receipt.persisted",
    "dispatch.completed",
]


@pytest.mark.asyncio
async def test_loopback_dispatch_receives_only_declared_context(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="dispatch-user",
        client_type="embedded",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    runtime.context.update(
        session_id=session["session_id"],
        scope="product",
        patch={"record_id": "lead-42"},
        expected_revision=0,
        replace=True,
    )
    result = await runtime.dispatch(
        IntentDispatchRequest(
            session_id=session["session_id"],
            intent_id="workspace.open-record",
            payload={"record_type": "lead", "record_id": "lead-42"},
        )
    )
    dispatch = result["dispatch"]
    assert dispatch["status"] == "COMPLETED"
    assert dispatch["response"]["transport"] == "loopback"
    assert dispatch["response"]["payload"]["record_id"] == "lead-42"
    assert dispatch["request"]["context"]["loaded_scopes"] == [
        "session",
        "workspace",
        "handoff",
        "product",
    ]
    assert [phase["phase_name"] for phase in result["phases"]] == [
        *EXPECTED_DISPATCH_PHASES,
    ]
    assert {phase["status"] for phase in result["phases"]} == {"COMPLETED"}
    assert {phase["attempts"] for phase in result["phases"]} == {1}

    proof = runtime.dispatch_proof(dispatch["dispatch_id"])
    assert proof["proof_type"] == "mitra-dispatch-proof-v1"
    assert proof["phase_summary"] == {
        "expected_phases": EXPECTED_DISPATCH_PHASES,
        "recorded_phase_count": 7,
        "missing_phases": [],
        "failed_phases": [],
        "complete": True,
    }
    assert proof["input"]["payload_hash"] == sha256_json(
        {"record_type": "lead", "record_id": "lead-42"}
    )
    assert proof["artifact_hashes"]["phase_journal"] == sha256_json(
        proof["phase_journal"]
    )
    assert proof["lineage"]["nodes"][1]["kind"] == "mitra-runtime"


@pytest.mark.asyncio
async def test_cross_product_dispatch_requires_transfer(
    runtime,
    atlas_manifest,
    nova_manifest,
):
    runtime.attach(atlas_manifest)
    runtime.attach(nova_manifest)
    session = runtime.sessions.create(
        actor_id="dispatch-user",
        client_type="standalone",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    with pytest.raises(ResourceConflictError):
        await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                product_id="nova-operations",
                intent_id="operations.show-status",
                payload={"resource_id": "worker-1"},
            )
        )


@pytest.mark.asyncio
async def test_dispatch_validates_registered_input_schema(
    runtime,
    atlas_manifest,
):
    runtime.attach(atlas_manifest)
    session = runtime.sessions.create(
        actor_id="schema-user",
        client_type="embedded",
        workspace_id="atlas",
        product_id="atlas-workspace",
    )
    with pytest.raises(IntentRoutingError):
        await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="workspace.open-record",
                payload={"record_type": "lead"},
            )
        )
    assert runtime.store.counts()["dispatches"] == 0


@pytest.mark.asyncio
async def test_http_transport_failure_degrades_attachment(settings_factory):
    async def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    settings: RuntimeSettings = settings_factory()
    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        http_transport=httpx.MockTransport(failing_handler),
    )
    runtime = CompanionRuntime(settings, transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "remote-product",
                "display_name": "Remote Product",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "remote",
                "base_url": "https://remote.invalid",
                "capabilities": [
                    {
                        "capability_id": "remote-navigation",
                        "description": "Remote navigation test capability",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "remote.open",
                                "description": "Open remote resource",
                                "input_schema": {"type": "object"},
                                "dispatch": {
                                    "mode": "http",
                                    "endpoint": "/dispatch"
                                }
                            }
                        ]
                    }
                ]
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="remote-user",
            client_type="standalone",
            workspace_id="remote",
            product_id="remote-product",
        )
        with pytest.raises(TransportError):
            await runtime.dispatch(
                IntentDispatchRequest(
                    session_id=session["session_id"],
                    intent_id="remote.open",
                    payload={"resource_id": "r-1"},
                )
            )
        assert runtime.attachments.get("remote-product")["state"] == "DEGRADED"
        assert runtime.lifecycle.state.value == "DEGRADED"
        assert runtime.store.counts()["failed_dispatches"] == 1
        failed = runtime.store.list_dispatches(limit=1)[0]
        phases = runtime.dispatch_phases(failed["dispatch_id"])
        assert [phase["phase_name"] for phase in phases] == (
            EXPECTED_DISPATCH_PHASES
        )
        assert phases[-3]["phase_name"] == "transport.dispatched"
        assert phases[-3]["status"] == "FAILED"
        assert phases[-2]["phase_name"] == "receipt.persisted"
        assert phases[-2]["status"] == "COMPLETED"
        assert phases[-1]["phase_name"] == "dispatch.completed"
        assert phases[-1]["status"] == "FAILED"
        restored = runtime.attach(manifest)
        assert restored["state"] == "ATTACHED"
        assert runtime.lifecycle.state.value == "READY"
    finally:
        runtime.stop()


def test_capability_catalog_validates_manifest_dependencies(runtime):
    foundation_manifest = ProductAttachmentManifest.model_validate(
        {
            "product_id": "foundation-product",
            "display_name": "Foundation Product",
            "product_version": "1.2.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "metadata": {
                "public_contracts": {
                    "apis": [
                        {
                            "name": "foundation-api",
                            "spec": "contracts/foundation.openapi.yaml",
                        }
                    ],
                    "events": {
                        "publishes": ["foundation.core.ready.v1"],
                    },
                    "permissions": ["foundation.read"],
                    "ui": {
                        "routes": ["/foundation"],
                        "slots": ["runtime.catalog"],
                    },
                }
            },
            "capabilities": [
                {
                    "capability_id": "foundation-core",
                    "description": "Core dependency target",
                    "context_scopes": ["session"],
                    "intents": [
                        {
                            "intent_id": "foundation.run",
                            "description": "Run foundation target",
                            "input_schema": {"type": "object"},
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": "loopback://foundation/run",
                            },
                        }
                    ],
                }
            ],
        }
    )
    dependent_manifest = ProductAttachmentManifest.model_validate(
        {
            "product_id": "dependent-product",
            "display_name": "Dependent Product",
            "product_version": "1.0.0",
            "contract_version": "1.0.0",
            "attachment_mode": "simulated",
            "metadata": {
                "dependencies": [
                    {
                        "product_id": "foundation-product",
                        "version": ">=1.0.0 <2.0.0",
                    }
                ],
                "public_contracts": {
                    "events": {
                        "consumes": ["foundation.core.ready.v1"],
                    },
                    "permissions": ["dependent.run"],
                },
            },
            "capabilities": [
                {
                    "capability_id": "dependent-core",
                    "description": "Capability with a target dependency",
                    "context_scopes": ["session"],
                    "metadata": {
                        "dependencies": [
                            {
                                "product_id": "foundation-product",
                                "capability_id": "foundation-core",
                                "version": ">=1.2.0",
                            }
                        ]
                    },
                    "intents": [
                        {
                            "intent_id": "dependent.run",
                            "description": "Run dependent target",
                            "input_schema": {"type": "object"},
                            "dispatch": {
                                "mode": "loopback",
                                "endpoint": "loopback://dependent/run",
                            },
                        }
                    ],
                }
            ],
        }
    )
    runtime.attach(foundation_manifest)
    runtime.attach(dependent_manifest)

    catalog = runtime.capability_catalog()
    assert catalog["compatible"] is True
    assert catalog["product_count"] == 2
    report = next(
        item
        for item in catalog["dependency_reports"]
        if item["product_id"] == "dependent-product"
    )
    assert report["compatible"] is True
    assert {check["kind"] for check in report["checks"]} == {
        "product",
        "capability",
    }
    assert "semantic version dependency validation" in (
        catalog["imported_patterns"]
    )
    public_contracts = catalog["public_contracts"]
    assert public_contracts["compatible"] is True
    assert public_contracts["published_events"] == {
        "foundation.core.ready.v1": "foundation-product"
    }
    assert public_contracts["event_catalog"][
        "foundation.core.ready.v1"
    ]["consumers"] == ["dependent-product"]
    assert public_contracts["permissions"]["foundation-product"] == [
        "foundation.read"
    ]
    assert public_contracts["permissions"]["dependent-product"] == [
        "dependent.run"
    ]


@pytest.mark.asyncio
async def test_custom_transport_adapter_requires_no_runtime_product_branch(
    settings_factory,
):
    class MemoryTransportAdapter:
        mode = "memory"

        def validate_target(self, manifest, target):
            assert target.endpoint.startswith("memory://")

        async def dispatch(self, *, route, envelope, manifest):
            return {
                "accepted": True,
                "transport": self.mode,
                "endpoint": route["dispatch"]["endpoint"],
                "payload": envelope["payload"],
            }

    transport = CapabilityTransport(
        default_timeout_seconds=0.2,
        adapters=[MemoryTransportAdapter()],
    )
    runtime = CompanionRuntime(settings_factory(), transport=transport)
    runtime.start()
    try:
        manifest = ProductAttachmentManifest.model_validate(
            {
                "product_id": "adapter-fixture",
                "display_name": "Adapter Fixture",
                "product_version": "1.0.0",
                "contract_version": "1.0.0",
                "attachment_mode": "simulated",
                "capabilities": [
                    {
                        "capability_id": "fixture-capability",
                        "description": "Adapter boundary fixture",
                        "context_scopes": ["session"],
                        "intents": [
                            {
                                "intent_id": "fixture.execute",
                                "description": "Execute through a custom adapter",
                                "input_schema": {
                                    "type": "object",
                                    "required": ["value"]
                                },
                                "dispatch": {
                                    "mode": "memory",
                                    "endpoint": "memory://fixture/execute",
                                    "options": {"fixture": True}
                                }
                            }
                        ]
                    }
                ]
            }
        )
        runtime.attach(manifest)
        session = runtime.sessions.create(
            actor_id="adapter-user",
            client_type="standalone",
            workspace_id="adapter-workspace",
            product_id="adapter-fixture",
        )
        result = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=session["session_id"],
                intent_id="fixture.execute",
                payload={"value": 7},
            )
        )
        assert result["dispatch"]["response"] == {
            "accepted": True,
            "transport": "memory",
            "endpoint": "memory://fixture/execute",
            "payload": {"value": 7},
        }
    finally:
        runtime.stop()
