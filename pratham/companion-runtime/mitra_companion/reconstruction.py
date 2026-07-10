from __future__ import annotations

from typing import Any

from .constants import CONTRACT_VERSION, RUNTIME_VERSION, SCHEMA_VERSION
from .depository import CentralDepository
from .utils import sha256_json, utc_now


class DeterministicReconstructionLedger:
    """Records and reconstructs dispatches from immutable runtime artifacts."""

    SNAPSHOT_TYPE = "dispatch-reconstruction.snapshot"
    REPLAY_TYPE = "mitra-true-deterministic-replay-v1"
    REQUIRED_SCOPES = (
        "lifecycle",
        "sessions",
        "routing",
        "attachments",
        "context",
        "dispatch",
        "telemetry",
        "recovery",
        "failures",
    )

    def __init__(self, depository: CentralDepository):
        self.depository = depository

    def record_dispatch(
        self,
        *,
        dispatch: dict[str, Any],
        route: dict[str, Any],
        manifest: dict[str, Any],
        context: dict[str, Any],
        phases: list[dict[str, Any]],
        lifecycle: dict[str, Any] | None = None,
        sessions: dict[str, Any] | None = None,
        routing: dict[str, Any] | None = None,
        attachments: dict[str, Any] | None = None,
        telemetry: dict[str, Any] | None = None,
        recovery: dict[str, Any] | None = None,
        failures: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dispatch_id = dispatch["dispatch_id"]
        components = {
            "lifecycle.snapshot": lifecycle or {},
            "sessions.snapshot": sessions or {},
            "routing.snapshot": routing or {"selected_route": route},
            "attachments.snapshot": attachments or {},
            "dispatch.receipt": dispatch,
            "dispatch.request": dispatch.get("request") or {},
            "dispatch.response": dispatch.get("response") or {},
            "route.snapshot": route,
            "manifest.snapshot": manifest,
            "context.snapshot": context,
            "phase-journal.snapshot": {"phases": phases},
            "telemetry.snapshot": telemetry or {},
            "recovery.snapshot": recovery or {},
            "failures.snapshot": failures or {},
        }
        component_artifacts: dict[str, dict[str, Any]] = {}
        expected_component_hashes: dict[str, str] = {}
        stored_components = self.depository.put_many(
            [
                {
                    "artifact_type": artifact_type,
                    "artifact": artifact,
                    "metadata": {"dispatch_id": dispatch_id},
                }
                for artifact_type, artifact in components.items()
            ]
        )
        for stored in stored_components:
            artifact_type = stored["artifact_type"]
            expected_component_hashes[artifact_type] = stored[
                "artifact_hash"
            ]
            component_artifacts[artifact_type] = {
                "artifact_hash": stored["artifact_hash"],
                "artifact_type": stored["artifact_type"],
            }

        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "package_type": "mitra-deterministic-reconstruction-v1",
            "replay_type": self.REPLAY_TYPE,
            "recorded_at": utc_now(),
            "dispatch_id": dispatch_id,
            "terminal_status": dispatch["status"],
            "reconstruction_mode": "immutable-artifact-replay",
            "replay_authority": "immutable-runtime-artifacts-only",
            "external_consumer_boundary": (
                "This reconstructs the exact Mitra runtime execution from "
                "content-addressed artifacts for lifecycle, sessions, routing, "
                "attachments, context, dispatch, telemetry, recovery, and "
                "failures. External systems may consume the package for replay "
                "authority; Mitra does not re-execute product business logic."
            ),
            "component_artifacts": component_artifacts,
            "scope_coverage": {
                scope: True for scope in self.REQUIRED_SCOPES
            },
            "expected_hashes": {
                "component_hashes": expected_component_hashes,
                "request_hash": sha256_json(dispatch.get("request") or {}),
                "response_hash": sha256_json(dispatch.get("response") or {}),
                "route_hash": sha256_json(route),
                "manifest_hash": sha256_json(manifest),
                "context_hash": sha256_json(context),
                "phase_journal_hash": sha256_json({"phases": phases}),
            },
        }
        root = self.depository.put(
            artifact_type=self.SNAPSHOT_TYPE,
            artifact=snapshot,
            metadata={
                "dispatch_id": dispatch_id,
                "terminal_status": dispatch["status"],
            },
        )
        lineage = self.depository.append_lineage(
            subject_type="dispatch",
            subject_id=dispatch_id,
            artifact_hash=root["artifact_hash"],
            metadata={
                "artifact_type": self.SNAPSHOT_TYPE,
                "terminal_status": dispatch["status"],
                "component_count": len(component_artifacts),
            },
        )
        return {
            "package_type": snapshot["package_type"],
            "dispatch_id": dispatch_id,
            "package_hash": root["artifact_hash"],
            "lineage_id": lineage["lineage_id"],
            "chain_hash": lineage["chain_hash"],
            "component_artifacts": component_artifacts,
            "deterministic": True,
            "reconstruction_mode": snapshot["reconstruction_mode"],
            "replay_type": snapshot["replay_type"],
            "scope_coverage": snapshot["scope_coverage"],
        }

    def package(self, dispatch_id: str) -> dict[str, Any]:
        lineage = sorted(
            self.depository.lineage(
                subject_type="dispatch",
                subject_id=dispatch_id,
                limit=500,
            ),
            key=lambda item: item["sequence"],
        )
        entries = [
            item
            for item in lineage
            if item.get("metadata", {}).get("artifact_type")
            == self.SNAPSHOT_TYPE
        ]
        if not entries:
            return {
                "dispatch_id": dispatch_id,
                "status": "missing",
                "message": "No deterministic reconstruction snapshot recorded.",
            }
        latest = entries[-1]
        root = self.depository.artifact(latest["artifact_hash"])
        if root is None:
            return {
                "dispatch_id": dispatch_id,
                "status": "broken",
                "message": "Reconstruction lineage points to a missing artifact.",
                "lineage": lineage,
            }
        snapshot = root["artifact"]
        components = self._load_components(snapshot)
        verification = self.verify_snapshot(
            snapshot=snapshot,
            root_hash=root["artifact_hash"],
            lineage=lineage,
            components=components,
        )
        return {
            "dispatch_id": dispatch_id,
            "status": verification["status"],
            "package_hash": root["artifact_hash"],
            "lineage": lineage,
            "snapshot": snapshot,
            "components": components,
            "reconstructed_execution": self._reconstruct(components),
            "verification": verification,
        }

    def verify_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        root_hash: str,
        lineage: list[dict[str, Any]],
        components: dict[str, Any],
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = [
            {
                "check": "root-package-hash",
                "passed": sha256_json(snapshot) == root_hash,
            }
        ]
        expected_hashes = snapshot.get("expected_hashes") or {}
        expected_components = expected_hashes.get("component_hashes") or {}
        for artifact_type, expected_hash in sorted(
            expected_components.items()
        ):
            checks.append(
                {
                    "check": f"component-hash:{artifact_type}",
                    "passed": (
                        artifact_type in components
                        and sha256_json(components[artifact_type])
                        == expected_hash
                    ),
                }
            )
        compatibility_hash_checks = {
            "request_hash": components.get("dispatch.request") or {},
            "response_hash": components.get("dispatch.response") or {},
            "route_hash": components.get("route.snapshot") or {},
            "manifest_hash": components.get("manifest.snapshot") or {},
            "context_hash": components.get("context.snapshot") or {},
            "phase_journal_hash": components.get("phase-journal.snapshot") or {},
        }
        for name, artifact in compatibility_hash_checks.items():
            if name in expected_hashes:
                checks.append(
                    {
                        "check": name,
                        "passed": sha256_json(artifact)
                        == expected_hashes.get(name),
                    }
                )
        scope_coverage = self._scope_coverage(snapshot, components)
        for scope, passed_scope in scope_coverage.items():
            checks.append(
                {
                    "check": f"replay-scope:{scope}",
                    "passed": passed_scope,
                }
            )
        checks.extend(self._verify_lineage(lineage))
        passed = all(item["passed"] for item in checks)
        return {
            "status": "verified" if passed else "failed",
            "deterministic": passed,
            "replay_type": snapshot.get("replay_type"),
            "reconstruction_mode": snapshot.get("reconstruction_mode"),
            "scope_coverage": scope_coverage,
            "checks": checks,
        }

    @classmethod
    def _scope_coverage(
        cls,
        snapshot: dict[str, Any],
        components: dict[str, Any],
    ) -> dict[str, bool]:
        expected = snapshot.get("scope_coverage") or {}
        artifact_scopes = {
            "lifecycle": ("lifecycle.snapshot",),
            "sessions": ("sessions.snapshot",),
            "routing": ("routing.snapshot", "route.snapshot"),
            "attachments": ("attachments.snapshot", "manifest.snapshot"),
            "context": ("context.snapshot",),
            "dispatch": (
                "dispatch.receipt",
                "dispatch.request",
                "dispatch.response",
                "phase-journal.snapshot",
            ),
            "telemetry": ("telemetry.snapshot",),
            "recovery": ("recovery.snapshot",),
            "failures": ("failures.snapshot",),
        }
        coverage: dict[str, bool] = {}
        for scope in cls.REQUIRED_SCOPES:
            artifact_types = artifact_scopes[scope]
            coverage[scope] = (
                expected.get(scope) is True
                and all(artifact_type in components for artifact_type in artifact_types)
            )
        return coverage

    def _load_components(
        self,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        components: dict[str, Any] = {}
        for artifact_type, reference in (
            snapshot.get("component_artifacts") or {}
        ).items():
            artifact = self.depository.artifact(reference["artifact_hash"])
            if artifact is not None:
                components[artifact_type] = artifact["artifact"]
        return components

    @staticmethod
    def _verify_lineage(
        lineage: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        parent: str | None = None
        for entry in sorted(lineage, key=lambda item: item["sequence"]):
            expected = sha256_json(
                {
                    "subject_type": entry["subject_type"],
                    "subject_id": entry["subject_id"],
                    "artifact_hash": entry["artifact_hash"],
                    "parent_chain_hash": parent,
                    "sequence": entry["sequence"],
                    "metadata": entry.get("metadata") or {},
                }
            )
            checks.append(
                {
                    "check": f"lineage-chain-sequence-{entry['sequence']}",
                    "passed": (
                        entry.get("parent_chain_hash") == parent
                        and entry.get("chain_hash") == expected
                    ),
                }
            )
            parent = entry.get("chain_hash")
        return checks

    @staticmethod
    def _reconstruct(components: dict[str, Any]) -> dict[str, Any]:
        receipt = components.get("dispatch.receipt") or {}
        dispatch = {
            "receipt": receipt,
            "request": components.get("dispatch.request") or {},
            "response": components.get("dispatch.response") or {},
            "phase_journal": (
                components.get("phase-journal.snapshot") or {}
            ).get("phases", []),
        }
        return {
            "dispatch_id": receipt.get("dispatch_id"),
            "status": receipt.get("status"),
            "lifecycle": components.get("lifecycle.snapshot") or {},
            "sessions": components.get("sessions.snapshot") or {},
            "routing": components.get("routing.snapshot") or {},
            "attachments": components.get("attachments.snapshot") or {},
            "context": components.get("context.snapshot") or {},
            "dispatch": dispatch,
            "telemetry": components.get("telemetry.snapshot") or {},
            "recovery": components.get("recovery.snapshot") or {},
            "failures": components.get("failures.snapshot") or {},
            "request": dispatch["request"],
            "route": components.get("route.snapshot") or {},
            "manifest": components.get("manifest.snapshot") or {},
            "response": dispatch["response"],
            "phase_journal": dispatch["phase_journal"],
        }
