from __future__ import annotations

from pathlib import Path

import pytest

from talos.addon_manifest import dependency_waves, discover_addons, installed_addon_id


def _manifest(root: Path, name: str, slug: str, dependencies: list[str] | None = None) -> None:
    addon = root / name
    addon.mkdir()
    dependency_yaml = ""
    if dependencies:
        dependency_yaml = "depends_on:\n" + "".join(f"  - {item}\n" for item in dependencies)
    (addon / "addon.yaml").write_text(
        f"slug: {slug}\nname: {name}\ndescription: test\n{dependency_yaml}",
        encoding="utf-8",
    )


def test_repository_dependency_graph_is_valid_and_deterministic():
    manifests = discover_addons()
    waves = dependency_waves(
        [Path(manifest["source_dir"]).parent if manifest.get("source_subdir") else Path(manifest["source_dir"])
         for manifest in manifests.values()],
        manifests=manifests,
    )

    assert [[path.name for path in wave] for wave in waves] == [
        ["mongodb", "node-sonos-http-api", "snapshot-service"],
        ["printer", "sonos-api", "tinyurl-service"],
        ["grid-dashboard"],
    ]
    assert installed_addon_id(manifests["tinyurl-service"]) == "local_tinyurl_service"


def test_dependency_order_allows_a_valid_explicit_subset():
    manifests = discover_addons()
    printer = Path(manifests["printer"]["source_dir"])
    assert dependency_waves([printer]) == [[printer]]


def test_discovery_rejects_missing_dependencies(tmp_path: Path):
    _manifest(tmp_path, "first", "first", ["missing"])
    with pytest.raises(Exception, match="depends on missing add-on"):
        discover_addons(tmp_path)


def test_discovery_rejects_duplicate_slugs(tmp_path: Path):
    _manifest(tmp_path, "first", "duplicate")
    _manifest(tmp_path, "second", "duplicate")
    with pytest.raises(Exception, match="Duplicate add-on slug"):
        discover_addons(tmp_path)


def test_discovery_rejects_cycles(tmp_path: Path):
    _manifest(tmp_path, "first", "first", ["second"])
    _manifest(tmp_path, "second", "second", ["first"])
    with pytest.raises(Exception, match="Circular add-on dependencies"):
        discover_addons(tmp_path)


def test_discovery_rejects_health_path_without_port(tmp_path: Path):
    _manifest(tmp_path, "first", "first")
    manifest = tmp_path / "first" / "addon.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "deploy_health_path: /healthz\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="without a port"):
        discover_addons(tmp_path)
