from __future__ import annotations

import importlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mitra_companion.constants import (
    AttachmentState,
    DispatchStatus,
    RuntimeState,
    SessionState,
)
from mitra_companion.interfaces import (
    AttachmentRuntimeInterface,
    CompanionRuntimeInterface,
    ContextRuntimeInterface,
    ContextTransferRuntimeInterface,
    IntentRouterInterface,
    LifecycleInterface,
    SessionRuntimeInterface,
)
from mitra_companion.lifecycle import ALLOWED_TRANSITIONS


ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_phase1_state_machine_schema_and_runtime_transitions_match():
    catalog = _load_json("contracts/runtime-state-machine.json")
    schema = _load_json(
        "contracts/schemas/runtime-state-machine.schema.json"
    )
    assert list(Draft202012Validator(schema).iter_errors(catalog)) == []

    runtime_states = {
        item["name"] for item in catalog["runtime"]["states"]
    }
    assert runtime_states == {state.value for state in RuntimeState}

    catalog_transitions = {
        (item["from"], item["to"])
        for item in catalog["runtime"]["transitions"]
    }
    implementation_transitions = {
        (source.value, target.value)
        for source, targets in ALLOWED_TRANSITIONS.items()
        for target in targets
    }
    assert catalog_transitions == implementation_transitions

    assert {
        item["name"] for item in catalog["session"]["states"]
    } == {state.value for state in SessionState}
    assert {
        item["name"] for item in catalog["attachment"]["states"]
    } == {state.value for state in AttachmentState}
    assert {
        item["name"] for item in catalog["dispatch"]["states"]
    } == {state.value for state in DispatchStatus}


def test_phase1_interface_catalog_is_valid_and_protocol_operations_exist():
    catalog = _load_json("contracts/runtime-interface-catalog.json")
    schema = _load_json(
        "contracts/schemas/runtime-interface-catalog.schema.json"
    )
    assert list(Draft202012Validator(schema).iter_errors(catalog)) == []

    for interface in catalog["interfaces"]:
        module_name, protocol_name = interface["python_protocol"].rsplit(
            ".",
            1,
        )
        protocol = getattr(importlib.import_module(module_name), protocol_name)
        for operation in interface["operations"]:
            assert hasattr(protocol, operation["name"]), (
                f"{protocol_name} missing {operation['name']}"
            )


def test_concrete_runtime_components_conform_to_phase1_interfaces(runtime):
    assert isinstance(runtime, CompanionRuntimeInterface)
    assert isinstance(runtime, ContextTransferRuntimeInterface)
    assert isinstance(runtime.lifecycle, LifecycleInterface)
    assert isinstance(runtime.sessions, SessionRuntimeInterface)
    assert isinstance(runtime.context, ContextRuntimeInterface)
    assert isinstance(runtime.router, IntentRouterInterface)
    assert isinstance(runtime.attachments, AttachmentRuntimeInterface)


def test_phase1_document_contains_all_required_design_sections():
    document = (
        ROOT / "docs" / "PHASE_1_COMPANION_RUNTIME_DESIGN.md"
    ).read_text(encoding="utf-8")
    for section in (
        "## Architecture",
        "## Lifecycle",
        "## States",
        "## Runtime interfaces",
        "## Phase 1 acceptance criteria",
    ):
        assert section in document

