from __future__ import annotations

from typing import Any

from .constants import CONTRACT_VERSION, RUNTIME_VERSION, SCHEMA_VERSION
from .depository import CentralDepository
from .utils import sha256_json, utc_now


class DeterministicReconstructionLedger:
    """Records and reconstructs dispatches from immutable runtime artifacts."""

    SNAPSHOT_TYPE = "dispatch-reconstruction.snapshot"
    REPLAY_TYPE = "mitra-true-deterministic-replay-v1"
    PORTABLE_PACKAGE_TYPE = "mitra-portable-replay-package-v1"
    REQUIRED_SCOPES = (
        "lifecycle",
        "sessions",
        "routing",
        "attachments",
        "dependencies",
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
        dependencies: dict[str, Any] | None = None,
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
            "dependencies.snapshot": dependencies or {},
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
                "attachments, dependencies, context, dispatch, telemetry, "
                "recovery, and failures. External systems may consume the package for replay "
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
                "dependencies_hash": sha256_json(dependencies or {}),
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
        immutable_artifacts = self._portable_artifacts(
            snapshot=snapshot,
            components=components,
        )
        return {
            "package_format": self.PORTABLE_PACKAGE_TYPE,
            "dispatch_id": dispatch_id,
            "status": verification["status"],
            "package_hash": root["artifact_hash"],
            "lineage": lineage,
            "snapshot": snapshot,
            "components": components,
            "immutable_artifacts": immutable_artifacts,
            "reconstructed_execution": self._reconstruct(components),
            "verification": verification,
            "clean_state_replay": {
                "required_runtime_state": "none",
                "validation_endpoint": "/api/v1/reconstruction/validate",
                "replay_authority": "portable immutable artifact package",
            },
        }

    def verify_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        root_hash: str,
        lineage: list[dict[str, Any]],
        components: dict[str, Any],
    ) -> dict[str, Any]:
        return self.verify_portable_artifacts(
            snapshot=snapshot,
            root_hash=root_hash,
            lineage=lineage,
            components=components,
        )

    @classmethod
    def validate_portable_package(
        cls,
        package: dict[str, Any],
    ) -> dict[str, Any]:
        """Reconstruct an execution with no runtime store or depository.

        This is the true deterministic replay surface: it accepts the exported
        package as an immutable artifact bundle and never reads local runtime
        state, dispatch tables, sessions, telemetry logs, or attachment stores.
        """

        normalized = cls._normalize_portable_package(package)
        snapshot = normalized["snapshot"]
        components = normalized["components"]
        lineage = normalized["lineage"]
        root_hash = normalized["package_hash"]
        verification = cls.verify_portable_artifacts(
            snapshot=snapshot,
            root_hash=root_hash,
            lineage=lineage,
            components=components,
        )
        reconstructed = cls._reconstruct(components)
        execution_fidelity = cls._execution_fidelity(
            snapshot=snapshot,
            components=components,
            reconstructed=reconstructed,
        )
        verification["checks"].extend(execution_fidelity)
        verification["status"] = (
            "verified"
            if verification["status"] == "verified"
            and all(item["passed"] for item in execution_fidelity)
            else "failed"
        )
        verification["deterministic"] = verification["status"] == "verified"
        return {
            "package_format": cls.PORTABLE_PACKAGE_TYPE,
            "dispatch_id": snapshot.get("dispatch_id"),
            "status": verification["status"],
            "package_hash": root_hash,
            "replay_mode": "clean-state-portable-artifact-replay",
            "state_dependency": "none",
            "runtime_state_read": False,
            "snapshot": snapshot,
            "components": components,
            "immutable_artifacts": cls._portable_artifacts(
                snapshot=snapshot,
                components=components,
            ),
            "reconstructed_execution": reconstructed,
            "verification": verification,
        }

    @classmethod
    def verify_portable_artifacts(
        cls,
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
                "expected": root_hash,
                "actual": sha256_json(snapshot),
            },
            {
                "check": "replay-type",
                "passed": snapshot.get("replay_type") == cls.REPLAY_TYPE,
                "expected": cls.REPLAY_TYPE,
                "actual": snapshot.get("replay_type"),
            },
            {
                "check": "replay-authority",
                "passed": (
                    snapshot.get("replay_authority")
                    == "immutable-runtime-artifacts-only"
                ),
                "expected": "immutable-runtime-artifacts-only",
                "actual": snapshot.get("replay_authority"),
            }
        ]
        expected_hashes = snapshot.get("expected_hashes") or {}
        expected_components = expected_hashes.get("component_hashes") or {}
        component_references = snapshot.get("component_artifacts") or {}
        for artifact_type, expected_hash in sorted(
            expected_components.items()
        ):
            actual_hash = (
                sha256_json(components[artifact_type])
                if artifact_type in components
                else None
            )
            reference_hash = (
                component_references.get(artifact_type) or {}
            ).get("artifact_hash")
            checks.append(
                {
                    "check": f"component-hash:{artifact_type}",
                    "passed": actual_hash == expected_hash,
                    "expected": expected_hash,
                    "actual": actual_hash,
                }
            )
            checks.append(
                {
                    "check": f"component-reference:{artifact_type}",
                    "passed": reference_hash == expected_hash,
                    "expected": expected_hash,
                    "actual": reference_hash,
                }
            )
        compatibility_hash_checks = {
            "request_hash": components.get("dispatch.request") or {},
            "response_hash": components.get("dispatch.response") or {},
            "route_hash": components.get("route.snapshot") or {},
            "manifest_hash": components.get("manifest.snapshot") or {},
            "dependencies_hash": components.get("dependencies.snapshot") or {},
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
                        "expected": expected_hashes.get(name),
                        "actual": sha256_json(artifact),
                    }
                )
        scope_coverage = cls._scope_coverage(snapshot, components)
        for scope, passed_scope in scope_coverage.items():
            checks.append(
                {
                    "check": f"replay-scope:{scope}",
                    "passed": passed_scope,
                }
            )
        checks.extend(cls._verify_lineage(lineage))
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
    def _normalize_portable_package(
        cls,
        package: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = package.get("package") if "package" in package else package
        snapshot = candidate.get("snapshot")
        root_hash = candidate.get("package_hash")
        if not isinstance(snapshot, dict) or not isinstance(root_hash, str):
            return {
                "snapshot": {},
                "components": {},
                "lineage": [],
                "package_hash": root_hash or "",
            }
        components = candidate.get("components")
        if not isinstance(components, dict):
            components = {}
        if not components and isinstance(candidate.get("immutable_artifacts"), list):
            components = {
                item["artifact_type"]: item["artifact"]
                for item in candidate["immutable_artifacts"]
                if isinstance(item, dict)
                and isinstance(item.get("artifact_type"), str)
                and isinstance(item.get("artifact"), dict)
            }
        lineage = candidate.get("lineage")
        if not isinstance(lineage, list):
            lineage = []
        return {
            "snapshot": snapshot,
            "components": components,
            "lineage": lineage,
            "package_hash": root_hash,
        }

    @classmethod
    def _portable_artifacts(
        cls,
        *,
        snapshot: dict[str, Any],
        components: dict[str, Any],
    ) -> list[dict[str, Any]]:
        references = snapshot.get("component_artifacts") or {}
        artifacts: list[dict[str, Any]] = []
        for artifact_type, artifact in sorted(components.items()):
            reference = references.get(artifact_type) or {}
            artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "artifact_hash": reference.get(
                        "artifact_hash",
                        sha256_json(artifact),
                    ),
                    "artifact": artifact,
                }
            )
        return artifacts

    @classmethod
    def _execution_fidelity(
        cls,
        *,
        snapshot: dict[str, Any],
        components: dict[str, Any],
        reconstructed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        receipt = components.get("dispatch.receipt") or {}
        request = components.get("dispatch.request") or {}
        response = components.get("dispatch.response") or {}
        route = components.get("route.snapshot") or {}
        manifest = components.get("manifest.snapshot") or {}
        context = components.get("context.snapshot") or {}
        dependencies = components.get("dependencies.snapshot") or {}
        phase_journal = components.get("phase-journal.snapshot") or {}
        expected_hashes = snapshot.get("expected_hashes") or {}
        checks = [
            {
                "check": "dispatch-id-fidelity",
                "passed": reconstructed.get("dispatch_id")
                == snapshot.get("dispatch_id")
                == receipt.get("dispatch_id"),
            },
            {
                "check": "terminal-status-fidelity",
                "passed": reconstructed.get("status")
                == snapshot.get("terminal_status")
                == receipt.get("status"),
            },
            {
                "check": "request-fidelity",
                "passed": reconstructed.get("request") == request,
            },
            {
                "check": "response-fidelity",
                "passed": reconstructed.get("response") == response,
            },
            {
                "check": "route-fidelity",
                "passed": reconstructed.get("route") == route,
            },
            {
                "check": "manifest-fidelity",
                "passed": reconstructed.get("manifest") == manifest,
            },
            {
                "check": "context-fidelity",
                "passed": reconstructed.get("context") == context,
            },
            {
                "check": "dependencies-fidelity",
                "passed": reconstructed.get("dependencies") == dependencies,
            },
            {
                "check": "phase-journal-fidelity",
                "passed": reconstructed.get("phase_journal")
                == phase_journal.get("phases", []),
            },
            {
                "check": "dispatch-identical-hash",
                "passed": sha256_json(receipt)
                == sha256_json(reconstructed.get("dispatch", {}).get("receipt") or {}),
            },
            {
                "check": "reconstructed-request-hash",
                "passed": sha256_json(reconstructed.get("request") or {})
                == expected_hashes.get("request_hash"),
            },
            {
                "check": "reconstructed-response-hash",
                "passed": sha256_json(reconstructed.get("response") or {})
                == expected_hashes.get("response_hash"),
            },
            {
                "check": "reconstructed-route-hash",
                "passed": sha256_json(reconstructed.get("route") or {})
                == expected_hashes.get("route_hash"),
            },
        ]
        return checks

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
            "dependencies": ("dependencies.snapshot",),
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
            "dependencies": components.get("dependencies.snapshot") or {},
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
