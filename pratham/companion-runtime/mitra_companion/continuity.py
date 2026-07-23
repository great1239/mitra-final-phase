from __future__ import annotations

from collections import defaultdict
from typing import Any

from .reconstruction import DeterministicReconstructionLedger
from .store import RuntimeStore
from .tantra_handover import INTEGRATION_NAME
from .utils import utc_now


def _trace_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "trace_id" and isinstance(nested, str):
                values.append(nested)
            else:
                values.extend(_trace_values(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_trace_values(nested))
    return values


class RuntimeContinuityMonitor:
    """Checks runtime-owned integrity and delivery facts continuously."""

    def __init__(
        self,
        *,
        store: RuntimeStore,
        reconstruction: DeterministicReconstructionLedger,
        runtime_instance_id: str,
    ) -> None:
        self.store = store
        self.reconstruction = reconstruction
        self.runtime_instance_id = runtime_instance_id

    def inspect_dispatch(self, dispatch_id: str) -> dict[str, Any]:
        package = self.reconstruction.package(dispatch_id)
        package_available = package.get("status") not in {"missing", "broken"}
        validation = (
            DeterministicReconstructionLedger.validate_portable_package(package)
            if package_available
            else {"status": "failed", "verification": {"checks": []}}
        )
        verification_checks = validation.get("verification", {}).get(
            "checks", []
        )
        lineage_checks = [
            item
            for item in verification_checks
            if str(item.get("check", "")).startswith("lineage-chain-")
        ]
        dependency_checks = [
            item
            for item in verification_checks
            if item.get("check")
            in {
                "component-hash:dependencies.snapshot",
                "component-reference:dependencies.snapshot",
                "dependencies_hash",
                "dependencies-fidelity",
                "replay-scope:dependencies",
            }
        ]
        deliveries = self.store.list_integration_deliveries(
            integration_name=INTEGRATION_NAME,
            dispatch_id=dispatch_id,
            limit=100,
        )
        observed_traces: list[str] = []
        for delivery in deliveries:
            observed_traces.append(delivery["trace_id"])
            observed_traces.extend(_trace_values(delivery.get("request") or {}))
            observed_traces.extend(
                _trace_values(delivery.get("last_response") or {})
            )
        trace_continuity = bool(observed_traces) and len(set(observed_traces)) == 1
        delivery_statuses = sorted(
            {str(item["status"]) for item in deliveries}
        )
        terminal_delivery_failure = "FAILED" in delivery_statuses
        accepted_delivery = "ACCEPTED" in delivery_statuses
        trace_observations = (
            self.store.list_dependency_observations(
                product_id=f"tantra-trace:{observed_traces[0]}",
                limit=1,
            )
            if accepted_delivery and trace_continuity
            else []
        )
        latest_trace_observation = (
            trace_observations[0] if trace_observations else None
        )
        if not accepted_delivery:
            remote_trace_passed: bool | None = True
        elif latest_trace_observation is None:
            remote_trace_passed = None
        else:
            remote_trace_passed = bool(
                latest_trace_observation.get("status") == "healthy"
                and latest_trace_observation.get("detail", {}).get(
                    "trace_continuity"
                )
                is True
            )

        checks = [
            {
                "check": "portable-package-available",
                "passed": package_available,
            },
            {
                "check": "clean-state-reconstruction",
                "passed": validation.get("status") == "verified",
            },
            {
                "check": "lineage-chain",
                "passed": bool(lineage_checks)
                and all(item.get("passed") for item in lineage_checks),
            },
            {
                "check": "dependency-snapshot",
                "passed": bool(dependency_checks)
                and all(item.get("passed") for item in dependency_checks),
            },
            {
                "check": "tantra-delivery-recorded",
                "passed": bool(deliveries),
            },
            {
                "check": "trace-continuity",
                "passed": trace_continuity,
            },
            {
                "check": "accepted-trace-reconciliation",
                "passed": remote_trace_passed,
                "observation_id": (
                    latest_trace_observation.get("observation_id")
                    if latest_trace_observation
                    else None
                ),
            },
            {
                "check": "no-terminal-delivery-failure",
                "passed": not terminal_delivery_failure,
            },
        ]
        failed = any(item["passed"] is False for item in checks)
        pending = any(
            status in {
                "PENDING",
                "RETRY",
                "IN_PROGRESS",
                "WAITING_CONFIGURATION",
            }
            for status in delivery_statuses
        ) or any(item["passed"] is None for item in checks)
        return {
            "dispatch_id": dispatch_id,
            "status": "failed" if failed else (
                "attention" if pending else "healthy"
            ),
            "checked_at": utc_now(),
            "checks": checks,
            "package_hash": package.get("package_hash"),
            "delivery_ids": [item["delivery_id"] for item in deliveries],
            "delivery_statuses": delivery_statuses,
            "trace_id": observed_traces[0] if trace_continuity else None,
            "authority_boundary": (
                "Operational integrity and transport state only; external "
                "systems retain downstream decision authority."
            ),
        }

    def scan(self, *, limit: int) -> dict[str, Any]:
        dispatches = [
            item
            for item in self.store.list_dispatches(limit=limit)
            if item.get("status") in {"COMPLETED", "FAILED"}
        ]
        inspections = [
            self.inspect_dispatch(item["dispatch_id"]) for item in dispatches
        ]
        issue_count = sum(item["status"] == "failed" for item in inspections)
        attention_count = sum(
            item["status"] == "attention" for item in inspections
        )
        status = (
            "not-evaluated"
            if not inspections
            else "failed"
            if issue_count
            else "attention"
            if attention_count
            else "healthy"
        )
        snapshot = {
            "status": status,
            "checked_at": utc_now(),
            "checked_count": len(inspections),
            "issue_count": issue_count,
            "attention_count": attention_count,
            "dispatches": inspections,
            "dependency_health": self.dependency_health(limit=500),
            "delivery_counts": self.store.integration_delivery_counts(
                integration_name=INTEGRATION_NAME
            ),
            "runtime_leases": self.store.list_runtime_leases(),
        }
        stored = self.store.record_continuity_snapshot(
            runtime_instance_id=self.runtime_instance_id,
            status=status,
            checked_count=len(inspections),
            issue_count=issue_count,
            snapshot=snapshot,
        )
        return {**snapshot, "snapshot_id": stored["snapshot_id"]}

    def latest(self) -> dict[str, Any]:
        stored = self.store.latest_continuity_snapshot()
        if stored is None:
            return {
                "status": "not-run",
                "snapshot": None,
                "dependency_health": self.dependency_health(limit=500),
                "delivery_counts": self.store.integration_delivery_counts(
                    integration_name=INTEGRATION_NAME
                ),
                "runtime_leases": self.store.list_runtime_leases(),
            }
        return stored

    def dependency_health(
        self,
        *,
        product_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        observations = self.store.list_dependency_observations(
            product_id=product_id,
            limit=limit,
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for observation in observations:
            grouped[observation["product_id"]].append(observation)
        products: list[dict[str, Any]] = []
        for current_product_id, samples in sorted(grouped.items()):
            ordered = sorted(
                samples,
                key=lambda item: item["observed_at"],
                reverse=True,
            )
            statuses = [str(item["status"]) for item in ordered]
            latencies = [
                float(item["latency_ms"])
                for item in ordered
                if item.get("latency_ms") is not None
            ]
            consecutive_failures = 0
            for status in statuses:
                if status != "unhealthy":
                    break
                consecutive_failures += 1
            status_changes = sum(
                statuses[index] != statuses[index - 1]
                for index in range(1, len(statuses))
            )
            products.append(
                {
                    "product_id": current_product_id,
                    "latest_status": statuses[0],
                    "latest_observed_at": ordered[0]["observed_at"],
                    "sample_count": len(ordered),
                    "healthy_count": statuses.count("healthy"),
                    "unhealthy_count": statuses.count("unhealthy"),
                    "indeterminate_count": len(statuses)
                    - statuses.count("healthy")
                    - statuses.count("unhealthy"),
                    "consecutive_failures": consecutive_failures,
                    "status_changes": status_changes,
                    "average_latency_ms": (
                        round(sum(latencies) / len(latencies), 3)
                        if latencies
                        else None
                    ),
                    "recent_pattern": (
                        "stable-healthy"
                        if set(statuses) == {"healthy"}
                        else "stable-unhealthy"
                        if set(statuses) == {"unhealthy"}
                        else "indeterminate"
                        if not ({"healthy", "unhealthy"} & set(statuses))
                        else "mixed"
                    ),
                }
            )
        return {
            "product_count": len(products),
            "observation_count": len(observations),
            "products": products,
            "interpretation": (
                "Historical observations only; no degradation prediction is "
                "claimed by the runtime."
            ),
        }
