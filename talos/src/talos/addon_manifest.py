from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import click
import yaml

from .paths import REPO_ROOT


def discover_addons(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    """Discover and validate repository add-on manifests."""
    addons: dict[str, dict[str, Any]] = {}
    slugs: dict[str, str] = {}

    for addon_yaml in sorted(repo_root.glob("*/addon.yaml")):
        addon_key = addon_yaml.parent.name
        raw = yaml.safe_load(addon_yaml.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise click.ClickException(f"Invalid add-on manifest: {addon_yaml}")

        slug = raw.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            raise click.ClickException(f"Add-on '{addon_key}' has no valid slug.")
        if slug in slugs:
            raise click.ClickException(
                f"Duplicate add-on slug '{slug}' in '{slugs[slug]}' and '{addon_key}'."
            )
        slugs[slug] = addon_key

        dependencies = raw.get("depends_on", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item for item in dependencies
        ):
            raise click.ClickException(
                f"Invalid depends_on for add-on '{addon_key}'; expected a list of add-on names."
            )

        deploy_health_path = raw.get("deploy_health_path")
        if deploy_health_path is not None:
            if not isinstance(deploy_health_path, str) or not deploy_health_path.startswith("/"):
                raise click.ClickException(
                    f"Invalid deploy_health_path for add-on '{addon_key}'; "
                    "expected an absolute HTTP path."
                )
            if not raw.get("ports"):
                raise click.ClickException(
                    f"Add-on '{addon_key}' declares deploy_health_path without a port."
                )

        source_dir = addon_yaml.parent
        if raw.get("source_subdir"):
            source_dir = source_dir / str(raw["source_subdir"])
        raw["source_dir"] = source_dir
        addons[addon_key] = raw

    for addon_key, raw in addons.items():
        missing = sorted(set(raw.get("depends_on", [])) - addons.keys())
        if missing:
            raise click.ClickException(
                f"Add-on '{addon_key}' depends on missing add-on(s): {', '.join(missing)}."
            )

    # Validate the complete graph even when a caller later selects a subset.
    dependency_waves([repo_root / key for key in addons], manifests=addons)
    return addons


def resolve_addon_dirs(
    explicit: Iterable[str], repo_root: Path = REPO_ROOT
) -> list[Path]:
    manifests = discover_addons(repo_root)
    names = list(explicit)
    if names:
        unknown = [name for name in names if name not in manifests]
        if unknown:
            raise click.ClickException(f"Unknown add-on(s): {', '.join(unknown)}.")
        return [repo_root / name for name in names]
    if not manifests:
        raise click.ClickException("No add-on manifests found (expected */addon.yaml).")
    return [repo_root / name for name in sorted(manifests)]


def addon_dependencies(
    addon_dir: Path, manifests: dict[str, dict[str, Any]] | None = None
) -> set[str]:
    if manifests is None:
        raw = yaml.safe_load((addon_dir / "addon.yaml").read_text(encoding="utf-8")) or {}
        dependencies = raw.get("depends_on", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item for item in dependencies
        ):
            raise click.ClickException(
                f"Invalid depends_on for add-on '{addon_dir.name}'; expected a list of add-on names."
            )
        return set(dependencies)
    return set(manifests[addon_dir.name].get("depends_on", []))


def dependency_waves(
    addon_dirs: Iterable[Path],
    manifests: dict[str, dict[str, Any]] | None = None,
) -> list[list[Path]]:
    """Group selected add-ons into deterministic dependency-ordered waves."""
    paths = list(addon_dirs)
    by_name = {addon_dir.name: addon_dir for addon_dir in paths}
    if len(by_name) != len(paths):
        raise click.ClickException("Duplicate add-on names in dependency selection.")

    dependencies: dict[str, set[str]] = {}
    known = set(manifests) if manifests is not None else set()
    for name, addon_dir in by_name.items():
        declared = addon_dependencies(addon_dir, manifests)
        missing = declared - known
        if manifests is not None and missing:
            raise click.ClickException(
                f"Add-on '{name}' depends on missing add-on(s): {', '.join(sorted(missing))}."
            )
        dependencies[name] = declared & by_name.keys()

    remaining = set(by_name)
    completed: set[str] = set()
    waves: list[list[Path]] = []
    while remaining:
        ready = sorted(name for name in remaining if dependencies[name] <= completed)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise click.ClickException(f"Circular add-on dependencies: {cycle}")
        waves.append([by_name[name] for name in ready])
        completed.update(ready)
        remaining.difference_update(ready)
    return waves


def dependency_order(
    addon_dirs: Iterable[Path],
    manifests: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    return [path for wave in dependency_waves(addon_dirs, manifests) for path in wave]


def installed_addon_id(manifest: dict[str, Any]) -> str:
    return f"local_{manifest['slug']}"
