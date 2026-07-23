from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str, relative_path: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hosted_validator_builds_required_nested_schema_values() -> None:
    validator = _load_script(
        "validate_hosted_runtime",
        "scripts/validate_hosted_runtime.py",
    )
    schema = {
        "type": "object",
        "required": ["symbols", "context"],
        "properties": {
            "symbols": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 20,
                },
            },
            "context": {
                "type": "object",
                "required": ["source"],
                "properties": {
                    "source": {"type": "string", "maxLength": 32},
                },
            },
        },
    }

    payload = validator._payload_from_schema(schema)

    assert payload["symbols"] == ["AAPL"]
    assert payload["context"]["source"]
    assert len(payload["context"]["source"]) <= 32


def test_operational_cases_cover_both_real_product_owners() -> None:
    validator = _load_script(
        "validate_ecosystem_runtime",
        "scripts/validate_ecosystem_runtime.py",
    )

    cases = validator._load_cases(
        ROOT / "contracts" / "operational-acceptance.json",
        set(),
    )

    assert {case["expected"]["product_id"] for case in cases} == {
        "samruddhi-trade-bot",
        "samruddhi-uniguru",
    }
    assert len(cases) == 3
    assert all(case["payload"]["raj_workflow"] for case in cases)
    failure = next(
        case
        for case in cases
        if case["case_id"] == "tradebot-product-error-keshav"
    )
    assert failure["expected"]["product_success"] is False
    assert failure["expected"]["product_error_type"] == (
        "product_rejected_workflow"
    )


def test_operational_validator_does_not_duplicate_stage_operations() -> None:
    validator = _load_script(
        "validate_ecosystem_runtime_operations",
        "scripts/validate_ecosystem_runtime.py",
    )
    stages = [
        {
            "response": {
                "operation": {"operation": "owner.append"},
                "operations": [
                    {"operation": "owner.health"},
                    {"operation": "owner.append"},
                ],
            }
        }
    ]

    operations = validator._execution_operations(stages)

    assert [item["operation"] for item in operations] == [
        "owner.health",
        "owner.append",
    ]


def test_replay_tamper_changes_recorded_response_only() -> None:
    validator = _load_script(
        "validate_ecosystem_runtime_tamper",
        "scripts/validate_ecosystem_runtime.py",
    )
    package = {
        "components": [
            {
                "name": "raj-execution",
                "payload": {"response": {"status": "executed"}},
            }
        ]
    }

    mutated = validator._mutate_recorded_response(package)

    assert package["components"][0]["payload"]["response"]["status"] == (
        "executed"
    )
    assert mutated["components"][0]["payload"]["response"]["status"] == (
        "operational-acceptance-tamper"
    )


def test_offline_replay_package_discovery_accepts_files_and_directories(
    tmp_path: Path,
) -> None:
    validator = _load_script(
        "validate_ecosystem_runtime_packages",
        "scripts/validate_ecosystem_runtime.py",
    )
    first = tmp_path / "first.replay.json"
    second = tmp_path / "second.replay.json"
    ignored = tmp_path / "notes.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    ignored.write_text("{}", encoding="utf-8")

    paths = validator._package_paths([tmp_path, first])

    assert paths == [first.resolve(), second.resolve()]
