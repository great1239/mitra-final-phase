from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mitra_companion.api import create_app
from mitra_companion.manifest_sources import DirectoryManifestSourceAdapter


def test_directory_manifest_source_discovers_arbitrary_filenames(
    tmp_path,
    atlas_manifest,
    nova_manifest,
):
    manifest_dir = tmp_path / "published-manifests"
    manifest_dir.mkdir()
    (manifest_dir / "first-published-interface.json").write_text(
        atlas_manifest.model_dump_json(),
        encoding="utf-8",
    )
    (manifest_dir / "another-interface.json").write_text(
        nova_manifest.model_dump_json(),
        encoding="utf-8",
    )
    source = DirectoryManifestSourceAdapter(manifest_dir)
    assert {item.product_id for item in source.load()} == {
        atlas_manifest.product_id,
        nova_manifest.product_id,
    }


def test_api_bootstrap_uses_manifest_source_adapter(
    settings_factory,
    atlas_manifest,
):
    class InMemoryManifestSource:
        def load(self):
            return [atlas_manifest]

    app = create_app(
        settings_factory(),
        manifest_sources=[InMemoryManifestSource()],
    )
    with TestClient(app) as client:
        attachments = client.get("/api/v1/attachments").json()["attachments"]
        assert [item["product_id"] for item in attachments] == [
            atlas_manifest.product_id
        ]


def test_runtime_implementation_contains_no_example_product_names():
    pratham_root = Path(__file__).resolve().parents[1]
    package_roots = [
        path
        for path in pratham_root.iterdir()
        if path.is_dir() and path.name != "tests"
    ]
    implementation = "\n".join(
        path.read_text(encoding="utf-8")
        for package_root in package_roots
        for path in package_root.rglob("*.py")
    ).lower()
    assert "atlas" not in implementation
    assert "nova" not in implementation
    assert "shakti" not in implementation
    assert "parikshak" not in implementation


def test_cross_module_implementations_depend_on_ports_not_concrete_classes():
    pratham_root = Path(__file__).resolve().parents[1]
    forbidden = (
        "from mitra_companion.store import RuntimeStore",
        "from mitra_attachment import AttachmentRuntime",
        "from mitra_session import SessionRuntime",
    )
    violations = []
    for path in pratham_root.rglob("*.py"):
        if path.parent.name == "tests":
            continue
        if path.name == "runtime.py" and path.parent.name == "mitra_companion":
            continue
        content = path.read_text(encoding="utf-8")
        if any(item in content for item in forbidden):
            violations.append(str(path))
    assert violations == []
