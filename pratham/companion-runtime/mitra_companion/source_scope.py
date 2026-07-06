from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SourceScopeRegistry:
    """Loads reusable prior-submission runtime knowledge from contracts."""

    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path

    def catalog(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return self._missing_catalog()
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def summary(self) -> dict[str, Any]:
        catalog = self.catalog()
        runtime_imports = catalog.get("runtime_imports") or []
        external_systems = catalog.get("external_systems") or []
        previous_submissions = catalog.get("previous_submissions") or []
        boundaries: dict[str, int] = {}
        for item in runtime_imports:
            boundary = str(item.get("boundary") or "unknown")
            boundaries[boundary] = boundaries.get(boundary, 0) + 1
        return {
            "catalog_version": catalog.get("catalog_version"),
            "previous_submission_count": len(previous_submissions),
            "runtime_import_count": len(runtime_imports),
            "external_system_count": len(external_systems),
            "boundaries": boundaries,
            "future_product_intake": catalog.get("future_product_intake", []),
        }

    def analysis_hints(self) -> dict[str, Any]:
        catalog = self.catalog()
        runtime_imports = catalog.get("runtime_imports") or []
        external_systems = catalog.get("external_systems") or []
        return {
            "catalog_version": catalog.get("catalog_version"),
            "selection_policy": catalog.get("selection_policy", {}),
            "runtime_imports": [
                {
                    "feature_id": item.get("feature_id"),
                    "runtime_surface": item.get("runtime_surface"),
                    "used_for": item.get("used_for", []),
                    "boundary": item.get("boundary"),
                }
                for item in runtime_imports
            ],
            "external_systems": [
                {
                    "system_id": item.get("system_id"),
                    "runtime_relationship": item.get("runtime_relationship"),
                    "integration_method": item.get("integration_method"),
                }
                for item in external_systems
            ],
            "future_product_intake": catalog.get("future_product_intake", []),
        }

    @staticmethod
    def _missing_catalog() -> dict[str, Any]:
        return {
            "catalog_version": "missing",
            "purpose": "source scope catalog unavailable",
            "selection_policy": {
                "import_when": [],
                "externalize_when": [],
                "never_import": [],
            },
            "previous_submissions": [],
            "runtime_imports": [],
            "external_systems": [],
            "future_product_intake": [],
        }
