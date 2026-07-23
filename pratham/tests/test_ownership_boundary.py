from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from mitra_attachment import AttachmentRuntime
from mitra_companion.constants import RuntimeState
from mitra_companion.contracts import ContextTransferRequest
from mitra_companion.bhiv_integrations import BHIVRuntimeIntegrator
from mitra_companion.depository import CentralDepository
from mitra_companion.lifecycle import RuntimeLifecycle
from mitra_companion.reconstruction import DeterministicReconstructionLedger
from mitra_companion.runtime import CompanionRuntime
from mitra_context import ContextRuntime
from mitra_intent import IntentRouter
from mitra_session import SessionRuntime


PRATHAM_ROOT = Path(__file__).resolve().parents[1]
ROOT = PRATHAM_ROOT.parent
IMPLEMENTATION_FOLDERS = {
    "companion-runtime",
    "session-runtime",
    "context-runtime",
    "intent-router",
    "attachment-runtime",
}
FORBIDDEN_TOKENS = {
    "conversation",
    "governance",
    "safety",
    "knowledge",
    "project_intelligence",
    "domain_intelligence",
    "evidence",
    "certification",
}
OWNED_CAPABILITIES = {
    "Companion Runtime",
    "Session Runtime",
    "Context Runtime",
    "Intent Router",
    "Capability Attachment Runtime",
    "Runtime Lifecycle",
    "Runtime State",
    "Context Transfer Runtime",
    "Product Attachment Runtime",
    "Deterministic Runtime Reconstruction",
    "Runtime Artifact Export",
    "BHIV Contract Integration",
}
EXTERNAL_CAPABILITIES = {
    "Product Conversation Design",
    "Product Business Logic",
    "Governance",
    "Safety Policy",
    "Knowledge Authority",
    "Project Intelligence",
    "Domain Intelligence",
    "External Evidence Authority",
    "External Replay Authority",
    "Certification",
    "Central Depository Acceptance",
}


def _implementation_files() -> list[Path]:
    return [
        path
        for folder in IMPLEMENTATION_FOLDERS
        for path in (PRATHAM_ROOT / folder).rglob("*.py")
    ]


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def test_only_assigned_implementation_folders_exist():
    actual = {
        path.name
        for path in PRATHAM_ROOT.iterdir()
        if path.is_dir() and path.name != "tests"
    }
    assert actual == IMPLEMENTATION_FOLDERS


def test_machine_readable_ownership_contract_is_exact_and_valid():
    contract = json.loads(
        (ROOT / "contracts" / "ownership-boundary.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "ownership-boundary.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert list(Draft202012Validator(schema).iter_errors(contract)) == []
    assert set(contract["owns"]) == OWNED_CAPABILITIES
    assert set(contract["does_not_own"]) == EXTERNAL_CAPABILITIES
    assert set(contract["implementation_folders"]) == IMPLEMENTATION_FOLDERS
    assert contract["integration_policy"] == (
        "published-interfaces-and-adapters-only"
    )


def test_all_owned_runtime_capabilities_have_concrete_symbols():
    assert CompanionRuntime
    assert SessionRuntime
    assert ContextRuntime
    assert IntentRouter
    assert AttachmentRuntime
    assert RuntimeLifecycle
    assert RuntimeState
    assert ContextTransferRequest
    assert DeterministicReconstructionLedger
    assert CentralDepository
    assert BHIVRuntimeIntegrator
    assert callable(SessionRuntime.transfer)
    assert callable(ContextRuntime.initialize_transfer)
    assert callable(AttachmentRuntime.attach)


def test_forbidden_subsystems_are_not_implementation_symbols_or_imports():
    violations: list[str] = []
    for path in _implementation_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_name = _normalized(path.stem)
        if any(token in module_name for token in FORBIDDEN_TOKENS):
            violations.append(f"{path}: forbidden module name")
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = _normalized(node.name)
                if any(token in symbol for token in FORBIDDEN_TOKENS):
                    violations.append(
                        f"{path}:{node.lineno}: forbidden symbol {node.name}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = _normalized(alias.name)
                    if any(token in imported for token in FORBIDDEN_TOKENS):
                        violations.append(
                            f"{path}:{node.lineno}: forbidden import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = _normalized(node.module)
                if any(token in imported for token in FORBIDDEN_TOKENS):
                    violations.append(
                        f"{path}:{node.lineno}: forbidden import {node.module}"
                    )
    assert violations == []


def test_runtime_reconstruction_does_not_claim_external_replay_authority():
    assert "Deterministic Runtime Reconstruction" in OWNED_CAPABILITIES
    assert "External Replay Authority" in EXTERNAL_CAPABILITIES


def test_forbidden_subsystems_are_not_api_surfaces():
    api_path = (
        PRATHAM_ROOT
        / "companion-runtime"
        / "mitra_companion"
        / "api.py"
    )
    tree = ast.parse(api_path.read_text(encoding="utf-8"))
    routes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            function = decorator.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr in {"get", "post", "patch", "put", "delete"}
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                routes.append(decorator.args[0].value)
    violations = [
        route
        for route in routes
        if any(token in _normalized(route) for token in FORBIDDEN_TOKENS)
    ]
    assert violations == []
