from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
for package_root in (
    ROOT / "pratham" / "companion-runtime",
    ROOT / "pratham" / "context-runtime",
    ROOT / "pratham" / "intent-router",
    ROOT / "pratham" / "session-runtime",
    ROOT / "pratham" / "attachment-runtime",
):
    sys.path.insert(0, str(package_root))

from mitra_companion.config import RuntimeSettings
from mitra_companion.contracts import (
    ContextTransferRequest,
    IntentDispatchRequest,
    ProductAttachmentManifest,
)
from mitra_companion.runtime import CompanionRuntime


def test_example_manifests_validate_against_published_schema():
    schema = json.loads(
        (
            ROOT
            / "contracts"
            / "schemas"
            / "product-attachment.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    for name in (
        "product-atlas.json",
        "product-nova.json",
        "product-bucket-insight.json",
        "product-prana-runtime.json",
        "product-karma-ledger.json",
        "product-setu-bridge.json",
        "product-keshav-knowledge.json",
        "product-sarathi-guide.json",
    ):
        example = json.loads(
            (ROOT / "contracts" / "examples" / name).read_text(
                encoding="utf-8"
            )
        )
        assert list(validator.iter_errors(example)) == []


@pytest.mark.asyncio
async def test_two_products_context_transfer_and_dispatch(tmp_path):
    runtime = CompanionRuntime(
        RuntimeSettings(
            service_root=ROOT,
            data_root=tmp_path,
            database_path=tmp_path / "integration.db",
            allow_example_manifests=True,
            allow_loopback_manifests=True,
            require_production_bootstrap_manifests=False,
        )
    )
    runtime.start()
    try:
        manifests = {}
        for name in ("product-atlas.json", "product-nova.json"):
            manifest = ProductAttachmentManifest.model_validate_json(
                (ROOT / "contracts" / "examples" / name).read_text(
                    encoding="utf-8"
                )
            )
            runtime.attach(manifest)
            manifests[manifest.product_id] = manifest

        atlas = runtime.sessions.create(
            actor_id="integration-user",
            client_type="embedded",
            workspace_id="atlas-sales",
            product_id="atlas-workspace",
        )
        runtime.context.update(
            session_id=atlas["session_id"],
            scope="session",
            patch={"locale": "en-IN"},
            expected_revision=0,
            replace=True,
        )
        runtime.context.update(
            session_id=atlas["session_id"],
            scope="product",
            patch={"atlas_selected_record": "lead-42"},
            expected_revision=0,
            replace=True,
        )
        atlas_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=atlas["session_id"],
                intent_id="workspace.open-record",
                payload={"record_type": "lead", "record_id": "lead-42"},
            )
        )
        assert atlas_dispatch["dispatch"]["status"] == "COMPLETED"

        transferred = runtime.transfer_context(
            atlas["session_id"],
            ContextTransferRequest(
                target_workspace_id="nova-ops",
                target_product_id="nova-operations",
                portable_context={"handoff_reference": "lead-42"},
            ),
        )
        nova = transferred["session"]
        assert "atlas_selected_record" not in transferred["context"]["merged"]
        nova_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=nova["session_id"],
                intent_id="operations.show-status",
                payload={"resource_id": "lead-42"},
            )
        )
        assert nova_dispatch["dispatch"]["status"] == "COMPLETED"
        assert runtime.store.counts() == {
            "sessions": 2,
            "attachments": 2,
            "dispatches": 2,
            "failed_dispatches": 0,
            "product_exchanges": 0,
        }
    finally:
        runtime.stop()
