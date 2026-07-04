from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mitra_companion.constants import (
    COMPATIBILITY_VERSION,
    CONTRACT_VERSION,
    RUNTIME_VERSION,
    SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_phase5_integration_contract_catalog_is_valid_and_complete():
    catalog = _json("contracts/integration-contracts.json")
    schema = _json("contracts/schemas/integration-contracts.schema.json")
    Draft202012Validator(schema).validate(catalog)

    assert catalog["schema_version"] == SCHEMA_VERSION
    assert catalog["contract_version"] == CONTRACT_VERSION
    assert catalog["runtime_version"] == RUNTIME_VERSION
    assert catalog["compatibility_version"] == COMPATIBILITY_VERSION

    openapi_text = (ROOT / catalog["api"]["openapi"]).read_text(
        encoding="utf-8"
    )
    for path in catalog["api"]["paths"]:
        assert f"  {path}:" in openapi_text

    for schema_ref in catalog["schemas"]:
        assert (ROOT / schema_ref["path"]).exists(), schema_ref
    for example_ref in catalog["examples"]:
        assert (ROOT / example_ref["path"]).exists(), example_ref


def test_phase5_attachment_policy_and_record_contracts_validate():
    policy = _json("contracts/product-attachment-runtime-policy.json")
    policy_schema = _json(
        "contracts/schemas/product-attachment-runtime-policy.schema.json"
    )
    Draft202012Validator(policy_schema).validate(policy)

    assert (
        policy["extension_policy"][
            "companion_runtime_modification_required"
        ]
        is False
    )
    assert (
        policy["extension_policy"]["product_specific_branches_allowed"]
        is False
    )
    assert policy["state_policy"]["DEGRADED"] == {
        "discoverable": True,
        "routable": False,
    }


def test_phase5_example_products_validate_against_manifest_schema():
    manifest_schema = _json("contracts/schemas/product-attachment.schema.json")
    validator = Draft202012Validator(manifest_schema)
    for name in (
        "product-atlas.json",
        "product-nova.json",
        "product-echo.json",
        "product-uniguru-runtime.json",
        "product-trade-bot-main.json",
    ):
        errors = list(
            validator.iter_errors(
                _json(f"contracts/examples/{name}")
            )
        )
        assert errors == []
