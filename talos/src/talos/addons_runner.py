from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

import click

from .addon_builder import discover_addons
from .paths import REPO_ROOT


def _has_recipe(addon_dir: Path, target: str) -> bool:
    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(addon_dir / "Justfile"),
            "--working-directory",
            str(addon_dir),
            "--color",
            "never",
            "--list",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False

    lines = result.stdout.splitlines()
    for line in lines[1:]:
        recipe = line.split()[0]
        if recipe == target:
            return True
    return False


def _run_just(addon_dir: Path, recipe: str) -> None:
    subprocess.run(
        ["just", "--justfile", str(addon_dir / "Justfile"), "--working-directory", str(addon_dir), recipe],
        check=True,
    )


def _resolve_addons(explicit: Iterable[str]) -> List[Path]:
    if explicit:
        addon_dirs = []
        for name in explicit:
            path = REPO_ROOT / name
            if not (path.exists() and (path / "addon.yaml").exists()):
                raise click.ClickException(f"Unknown add-on '{name}' (no addon.yaml in {path}).")
            addon_dirs.append(path)
        return addon_dirs

    addons = discover_addons()
    if not addons:
        raise click.ClickException("No add-on manifests found (expected */addon.yaml).")
    return [REPO_ROOT / name for name in sorted(addons.keys())]


def run_recipes(recipe: str, addons: Iterable[str]) -> None:
    addon_dirs = _resolve_addons(addons)

    for addon_dir in addon_dirs:
        addon_name = addon_dir.name
        if not (addon_dir / "Justfile").exists():
            click.echo(f"==> {addon_name}: skipping, no Justfile")
            continue

        if recipe == "deploy":
            for pre in ("generate", "build", "test", "ha-addon"):
                if _has_recipe(addon_dir, pre):
                    click.echo(f"==> {addon_name}: just {pre} (pre-deploy)")
                    _run_just(addon_dir, pre)

        if _has_recipe(addon_dir, recipe):
            click.echo(f"==> {addon_name}: just {recipe}")
            _run_just(addon_dir, recipe)
        else:
            click.echo(f"==> {addon_name}: skipping, no '{recipe}' recipe")
