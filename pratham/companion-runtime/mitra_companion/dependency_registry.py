from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any

from .constants import CONTRACT_VERSION, RUNTIME_VERSION


_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?$"
)
_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=)?(.+)$")


@total_ordering
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _VERSION_RE.match(value.strip())
        if match is None:
            raise ValueError(f"Invalid semantic version: {value!r}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("prerelease") or "",
        )

    def _sort_key(self) -> tuple[int, int, int, int, str]:
        return (
            self.major,
            self.minor,
            self.patch,
            1 if not self.prerelease else 0,
            self.prerelease,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.prerelease}" if self.prerelease else base


@dataclass(frozen=True)
class VersionRange:
    expression: str
    comparators: tuple[tuple[str, Version], ...]

    @classmethod
    def parse(cls, expression: str) -> "VersionRange":
        cleaned = expression.strip()
        if not cleaned:
            raise ValueError("Version range cannot be empty")
        comparators: list[tuple[str, Version]] = []
        for token in cleaned.split():
            match = _COMPARATOR_RE.match(token)
            if match is None:
                raise ValueError(f"Invalid version comparator: {token!r}")
            operator = match.group(1) or "="
            comparators.append((operator, Version.parse(match.group(2))))
        return cls(cleaned, tuple(comparators))

    def contains(self, version: str | Version) -> bool:
        candidate = Version.parse(version) if isinstance(version, str) else version
        for operator, expected in self.comparators:
            if operator == ">=" and not candidate >= expected:
                return False
            if operator == "<=" and not candidate <= expected:
                return False
            if operator == ">" and not candidate > expected:
                return False
            if operator == "<" and not candidate < expected:
                return False
            if operator == "=" and candidate != expected:
                return False
        return True


def _metadata_items(metadata: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _metadata_object(metadata: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _public_contracts(metadata: dict[str, Any]) -> dict[str, Any]:
    contracts = _metadata_object(metadata, "public_contracts", "contracts")
    events = _metadata_object(contracts, "events")
    ui = _metadata_object(contracts, "ui")
    return {
        "apis": _metadata_items(contracts, "apis", "api_contracts"),
        "published_events": _string_items(
            events.get("publishes") or contracts.get("publishes")
        ),
        "consumed_events": _string_items(
            events.get("consumes") or contracts.get("consumes")
        ),
        "permissions": _string_items(contracts.get("permissions")),
        "ui_routes": _string_items(ui.get("routes") or contracts.get("ui_routes")),
        "ui_slots": _string_items(ui.get("slots") or contracts.get("ui_slots")),
    }


class CapabilityDependencyRegistry:
    """Builds product-neutral dependency and contract reports from manifests."""

    def __init__(self, attachments: list[dict[str, Any]]):
        self.attachments = attachments

    def catalog(self) -> dict[str, Any]:
        products = [self._product_entry(item) for item in self.attachments]
        reports = self._dependency_reports(products)
        public_contracts = self._public_contract_catalog(products)
        return {
            "runtime_contract": {
                "runtime_version": RUNTIME_VERSION,
                "contract_version": CONTRACT_VERSION,
            },
            "product_count": len(products),
            "capability_count": sum(
                len(product["capabilities"]) for product in products
            ),
            "intent_count": sum(
                capability["intent_count"]
                for product in products
                for capability in product["capabilities"]
            ),
            "products": products,
            "dependency_reports": reports,
            "public_contracts": public_contracts,
            "compatible": (
                all(report["compatible"] for report in reports)
                and public_contracts["compatible"]
            ),
            "imported_patterns": [
                "manifest-backed module catalog",
                "semantic version dependency validation",
                "contract registration summary",
                "public API/event/permission catalog",
            ],
        }

    @staticmethod
    def _product_entry(attachment: dict[str, Any]) -> dict[str, Any]:
        manifest = attachment["manifest"]
        capabilities = []
        for capability in manifest.get("capabilities") or []:
            intents = capability.get("intents") or []
            capability_contracts = _public_contracts(
                capability.get("metadata") or {}
            )
            capabilities.append(
                {
                    "product_id": manifest["product_id"],
                    "capability_id": capability["capability_id"],
                    "description": capability["description"],
                    "context_scopes": list(capability.get("context_scopes") or []),
                    "intent_count": len(intents),
                    "intents": [
                        {
                            "intent_id": intent["intent_id"],
                            "dispatch_mode": intent["dispatch"]["mode"],
                            "endpoint": intent["dispatch"]["endpoint"],
                            "metadata_keys": sorted(
                                (intent.get("metadata") or {}).keys()
                            ),
                        }
                        for intent in intents
                    ],
                    "dependencies": _metadata_items(
                        capability.get("metadata") or {},
                        "dependencies",
                        "requires",
                    ),
                    "public_contracts": capability_contracts,
                    "metadata_keys": sorted(
                        (capability.get("metadata") or {}).keys()
                    ),
                }
            )
        product_contracts = _public_contracts(manifest.get("metadata") or {})
        return {
            "product_id": manifest["product_id"],
            "display_name": manifest["display_name"],
            "product_version": manifest["product_version"],
            "contract_version": manifest["contract_version"],
            "attachment_state": attachment["state"],
            "attachment_mode": manifest["attachment_mode"],
            "health_endpoint_configured": bool(manifest.get("health_endpoint")),
            "dependencies": _metadata_items(
                manifest.get("metadata") or {},
                "dependencies",
                "requires",
            ),
            "public_contracts": product_contracts,
            "metadata_keys": sorted((manifest.get("metadata") or {}).keys()),
            "capabilities": capabilities,
        }

    @staticmethod
    def _public_contract_catalog(
        products: list[dict[str, Any]],
    ) -> dict[str, Any]:
        api_contracts: dict[str, list[dict[str, Any]]] = {}
        published_events: dict[str, str] = {}
        consumed_events: dict[str, list[str]] = {}
        permissions: dict[str, list[str]] = {}
        ui_routes: dict[str, list[str]] = {}
        ui_slots: dict[str, list[str]] = {}
        conflicts: list[dict[str, Any]] = []

        for product in products:
            owner = product["product_id"]
            entries = [product["public_contracts"]]
            entries.extend(
                capability["public_contracts"]
                for capability in product["capabilities"]
            )
            for entry in entries:
                if entry["apis"]:
                    api_contracts.setdefault(owner, []).extend(entry["apis"])
                for event_type in entry["published_events"]:
                    existing = published_events.get(event_type)
                    if existing is not None and existing != owner:
                        conflicts.append(
                            {
                                "kind": "published_event",
                                "event_type": event_type,
                                "owners": sorted({existing, owner}),
                            }
                        )
                    published_events[event_type] = owner
                for event_type in entry["consumed_events"]:
                    consumed_events.setdefault(event_type, [])
                    if owner not in consumed_events[event_type]:
                        consumed_events[event_type].append(owner)
                if entry["permissions"]:
                    permissions.setdefault(owner, []).extend(
                        permission
                        for permission in entry["permissions"]
                        if permission not in permissions.get(owner, [])
                    )
                if entry["ui_routes"]:
                    ui_routes.setdefault(owner, []).extend(
                        route
                        for route in entry["ui_routes"]
                        if route not in ui_routes.get(owner, [])
                    )
                if entry["ui_slots"]:
                    ui_slots.setdefault(owner, []).extend(
                        slot
                        for slot in entry["ui_slots"]
                        if slot not in ui_slots.get(owner, [])
                    )
        event_catalog = {
            event_type: {
                "type": event_type,
                "publisher": owner,
                "consumers": sorted(consumed_events.get(event_type, [])),
            }
            for event_type, owner in sorted(published_events.items())
        }
        for event_type, consumers in sorted(consumed_events.items()):
            event_catalog.setdefault(
                event_type,
                {
                    "type": event_type,
                    "publisher": None,
                    "consumers": sorted(consumers),
                },
            )
        return {
            "api_contracts": api_contracts,
            "published_events": published_events,
            "consumed_events": {
                key: sorted(value)
                for key, value in sorted(consumed_events.items())
            },
            "event_catalog": event_catalog,
            "permissions": permissions,
            "ui_routes": ui_routes,
            "ui_slots": ui_slots,
            "conflicts": conflicts,
            "compatible": not conflicts,
        }

    def _dependency_reports(
        self,
        products: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        product_versions = {
            product["product_id"]: product["product_version"]
            for product in products
        }
        capability_versions = {}
        for product in products:
            for capability in product["capabilities"]:
                capability_versions[
                    f"{product['product_id']}:{capability['capability_id']}"
                ] = product["product_version"]

        reports = []
        for product in products:
            checks = []
            errors = []
            for dependency in product["dependencies"]:
                checked = self._check_product_dependency(
                    dependency,
                    product_versions,
                )
                checks.append(checked)
                if not checked["compatible"]:
                    errors.append(checked["detail"])
            for capability in product["capabilities"]:
                for dependency in capability["dependencies"]:
                    checked = self._check_capability_dependency(
                        dependency,
                        product_versions,
                        capability_versions,
                    )
                    checked["declared_by_capability_id"] = capability[
                        "capability_id"
                    ]
                    checks.append(checked)
                    if not checked["compatible"]:
                        errors.append(checked["detail"])
            reports.append(
                {
                    "product_id": product["product_id"],
                    "compatible": not errors,
                    "checks": checks,
                    "errors": errors,
                }
            )
        return reports

    @staticmethod
    def _required_range(dependency: dict[str, Any]) -> str:
        for key in ("version", "version_range", "product_version"):
            value = dependency.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ">=0.0.0"

    def _check_product_dependency(
        self,
        dependency: dict[str, Any],
        product_versions: dict[str, str],
    ) -> dict[str, Any]:
        product_id = dependency.get("product_id")
        required = self._required_range(dependency)
        if not isinstance(product_id, str) or not product_id:
            return {
                "kind": "product",
                "target": "",
                "required": required,
                "found": "",
                "compatible": False,
                "detail": "product dependency is missing product_id",
            }
        found = product_versions.get(product_id)
        return self._range_check("product", product_id, required, found)

    def _check_capability_dependency(
        self,
        dependency: dict[str, Any],
        product_versions: dict[str, str],
        capability_versions: dict[str, str],
    ) -> dict[str, Any]:
        required = self._required_range(dependency)
        product_id = dependency.get("product_id")
        capability_id = dependency.get("capability_id")
        if isinstance(capability_id, str) and capability_id:
            if isinstance(product_id, str) and product_id:
                target = f"{product_id}:{capability_id}"
                found = capability_versions.get(target)
            else:
                matches = [
                    (target, version)
                    for target, version in capability_versions.items()
                    if target.endswith(f":{capability_id}")
                ]
                target, found = matches[0] if len(matches) == 1 else ("", None)
                if len(matches) > 1:
                    return {
                        "kind": "capability",
                        "target": capability_id,
                        "required": required,
                        "found": "",
                        "compatible": False,
                        "detail": (
                            "capability dependency is ambiguous without product_id"
                        ),
                    }
            return self._range_check("capability", target, required, found)
        return self._check_product_dependency(dependency, product_versions)

    @staticmethod
    def _range_check(
        kind: str,
        target: str,
        required: str,
        found: str | None,
    ) -> dict[str, Any]:
        if found is None:
            return {
                "kind": kind,
                "target": target,
                "required": required,
                "found": "",
                "compatible": False,
                "detail": f"missing dependency {target}",
            }
        try:
            compatible = VersionRange.parse(required).contains(found)
        except ValueError as exc:
            return {
                "kind": kind,
                "target": target,
                "required": required,
                "found": found,
                "compatible": False,
                "detail": str(exc),
            }
        return {
            "kind": kind,
            "target": target,
            "required": required,
            "found": found,
            "compatible": compatible,
            "detail": (
                "compatible"
                if compatible
                else f"{target} requires {required}, found {found}"
            ),
        }
