from __future__ import annotations

from pathlib import Path

from .contracts import ProductAttachmentManifest
from .ports import FileReader


class LocalFileReader:
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")


class DirectoryManifestSourceAdapter:
    """Loads every published JSON manifest in a configured directory."""

    def __init__(
        self,
        directory: Path,
        *,
        reader: FileReader | None = None,
        allow_examples: bool = True,
        allow_simulated: bool = True,
        allow_loopback: bool = True,
        allow_localhost: bool = True,
        require_production_bootstrap: bool = False,
    ):
        self.directory = Path(directory)
        self.reader = reader or LocalFileReader()
        self.allow_examples = allow_examples
        self.allow_simulated = allow_simulated
        self.allow_loopback = allow_loopback
        self.allow_localhost = allow_localhost
        self.require_production_bootstrap = require_production_bootstrap

    def load(self) -> list[ProductAttachmentManifest]:
        if not self.directory.exists():
            return []
        manifests: list[ProductAttachmentManifest] = []
        for path in sorted(self.directory.glob("*.json")):
            manifest = ProductAttachmentManifest.model_validate_json(
                self.reader.read_text(path)
            )
            if self._allowed(manifest):
                manifests.append(manifest)
        return manifests

    def _allowed(self, manifest: ProductAttachmentManifest) -> bool:
        metadata = manifest.metadata or {}
        if (
            self.require_production_bootstrap
            and metadata.get("production_bootstrap") is not True
        ):
            return False
        if not self.allow_examples and metadata.get("example") is True:
            return False
        if not self.allow_simulated and manifest.attachment_mode == "simulated":
            return False
        if not self.allow_loopback and _uses_loopback(manifest):
            return False
        if not self.allow_localhost and _uses_localhost(manifest):
            return False
        return True


def _uses_loopback(manifest: ProductAttachmentManifest) -> bool:
    return any(
        intent.dispatch.mode == "loopback"
        for capability in manifest.capabilities
        for intent in capability.intents
    )


def _uses_localhost(manifest: ProductAttachmentManifest) -> bool:
    if manifest.base_url is None:
        return False
    host = getattr(manifest.base_url, "host", "") or ""
    return host.lower() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

