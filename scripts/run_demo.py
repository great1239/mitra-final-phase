from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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


async def run() -> dict:
    evidence_root = ROOT / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    data_root = ROOT / "var" / "demo"
    database_path = data_root / "demo.db"
    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        if candidate.exists():
            candidate.unlink()
    runtime = CompanionRuntime(
        RuntimeSettings(
            service_root=ROOT,
            data_root=data_root,
            database_path=database_path,
        )
    )
    runtime.start()
    try:
        attachments = []
        for name in ("product-atlas.json", "product-nova.json"):
            manifest = ProductAttachmentManifest.model_validate_json(
                (ROOT / "contracts" / "examples" / name).read_text(
                    encoding="utf-8"
                )
            )
            attachments.append(runtime.attach(manifest))

        atlas = runtime.sessions.create(
            actor_id="demo-user",
            client_type="embedded",
            workspace_id="atlas-sales",
            product_id="atlas-workspace",
            metadata={"device": "desktop"},
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
            patch={"selected_record": "lead-42"},
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

        transfer = runtime.transfer_context(
            atlas["session_id"],
            ContextTransferRequest(
                target_workspace_id="nova-operations",
                target_product_id="nova-operations",
                portable_context={"handoff_reference": "lead-42"},
            ),
        )
        nova_dispatch = await runtime.dispatch(
            IntentDispatchRequest(
                session_id=transfer["session"]["session_id"],
                intent_id="operations.show-status",
                payload={"resource_id": "lead-42"},
            )
        )
        result = {
            "status": "DEMO_COMPLETED",
            "runtime": runtime.status(),
            "attachments": [
                {
                    "product_id": item["product_id"],
                    "state": item["state"],
                }
                for item in attachments
            ],
            "atlas_session": {
                key: value
                for key, value in atlas.items()
                if key != "resume_token"
            },
            "atlas_dispatch": atlas_dispatch["dispatch"],
            "transfer": {
                "receipt": transfer["transfer"],
                "target_session_id": transfer["session"]["session_id"],
                "target_context": transfer["context"],
            },
            "nova_dispatch": nova_dispatch["dispatch"],
            "product_isolation_verified": (
                "selected_record" not in transfer["context"]["merged"]
            ),
        }
        (evidence_root / "demo-transcript.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return result
    finally:
        runtime.stop()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False))
