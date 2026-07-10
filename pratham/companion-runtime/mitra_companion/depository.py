from __future__ import annotations

from typing import Any
from uuid import uuid4

from .store import RuntimeStore
from .utils import sha256_json


class CentralDepository:
    """Content-addressed runtime artifact depository.

    Mitra does not become the external BHIV depository authority here. This is
    the runtime-owned content-addressed-runtime-export surface: immutable
    artifacts, hash references, and lineage entries that MDU, replay, evidence,
    or review systems can consume.
    """

    def __init__(self, store: RuntimeStore):
        self.store = store

    def put(
        self,
        *,
        artifact_type: str,
        artifact: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact_hash = sha256_json(artifact)
        return self.store.put_central_artifact(
            artifact_hash=artifact_hash,
            artifact_type=artifact_type,
            artifact=artifact,
            metadata=metadata,
        )

    def put_many(
        self,
        artifacts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prepared = [
            {
                "artifact_hash": sha256_json(item["artifact"]),
                "artifact_type": item["artifact_type"],
                "artifact": item["artifact"],
                "metadata": item.get("metadata") or {},
            }
            for item in artifacts
        ]
        return self.store.put_central_artifacts(prepared)

    def append_lineage(
        self,
        *,
        subject_type: str,
        subject_id: str,
        artifact_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.append_central_lineage(
            lineage_id=f"lin_{uuid4().hex}",
            subject_type=subject_type,
            subject_id=subject_id,
            artifact_hash=artifact_hash,
            metadata=metadata,
        )

    def artifact(self, artifact_hash: str) -> dict[str, Any] | None:
        return self.store.get_central_artifact(artifact_hash)

    def artifacts(
        self,
        *,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.store.list_central_artifacts(
            artifact_type=artifact_type,
            limit=limit,
        )

    def lineage(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.store.list_central_lineage(
            subject_type=subject_type,
            subject_id=subject_id,
            limit=limit,
        )

    def snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        artifacts = self.artifacts(limit=limit)
        lineage = self.lineage(limit=limit)
        return {
            "depository_type": "mitra-runtime-central-depository-export",
            "authority_boundary": (
                "runtime-owned immutable export; external MDU remains the "
                "cross-system provenance authority"
            ),
            "artifact_count": len(artifacts),
            "lineage_count": len(lineage),
            "artifacts": artifacts,
            "lineage": lineage,
        }
