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
    ):
        self.directory = Path(directory)
        self.reader = reader or LocalFileReader()

    def load(self) -> list[ProductAttachmentManifest]:
        if not self.directory.exists():
            return []
        manifests: list[ProductAttachmentManifest] = []
        for path in sorted(self.directory.glob("*.json")):
            manifests.append(
                ProductAttachmentManifest.model_validate_json(
                    self.reader.read_text(path)
                )
            )
        return manifests

