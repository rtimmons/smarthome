from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

import click
import yaml
from rich.console import Console

from .addon_builder import (
    DeploymentError,
    get_addon_logs,
    run_cmd,
    validate_deployment_prerequisites,
)

console = Console()

DEFAULT_EXCLUDES = (
    ".git",
    ".github",
    ".codex",
    "node_modules",
    "coverage",
    ".cache",
    ".ha-addon-dist",
    "*.tar.gz",
)


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _load_config(addon_dir: Path) -> dict:
    config_path = addon_dir / "config.yaml"
    if not config_path.exists():
        raise click.ClickException(f"Missing add-on config: {config_path}")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise click.ClickException(f"Invalid add-on config: {config_path}")

    slug = data.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        raise click.ClickException(f"Add-on config must define a non-empty slug: {config_path}")

    return data


def _read_excludes(addon_dir: Path, addon_dir_name: str) -> list[str]:
    excludes = list(DEFAULT_EXCLUDES)
    excludes.append(addon_dir_name)

    excludes_path = addon_dir / "package-excludes.txt"
    if excludes_path.exists():
        for raw in excludes_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            excludes.append(line.rstrip("/"))

    return excludes


def _matches_any(name: str, rel_path: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        normalized = pattern.rstrip("/")
        if not normalized:
            continue
        if fnmatch.fnmatch(name, normalized) or fnmatch.fnmatch(rel_path, normalized):
            return True
        if "/" not in normalized and name == normalized:
            return True
    return False


def _copy_app(app_dir: Path, dest: Path, excludes: list[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(app_dir, topdown=True, followlinks=False):
        root_path = Path(root)
        root_rel = root_path.relative_to(app_dir)
        root_rel_text = "" if root_rel == Path(".") else root_rel.as_posix()

        kept_dirs = []
        for dirname in dirs:
            rel_text = f"{root_rel_text}/{dirname}" if root_rel_text else dirname
            if not _matches_any(dirname, rel_text, excludes):
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        if root_rel_text:
            (dest / root_rel).mkdir(parents=True, exist_ok=True)

        for filename in files:
            src = root_path / filename
            rel = src.relative_to(app_dir)
            rel_text = rel.as_posix()
            if _matches_any(filename, rel_text, excludes):
                continue

            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                target.symlink_to(src.readlink())
            else:
                shutil.copy2(src, target)


def package_external_addon(
    app_dir: str | Path,
    addon_dir: str | Path,
    output_dir: str | Path | None = None,
    verbose: bool = False,
) -> Path:
    app_root = _resolve(app_dir)
    addon_root = _resolve(addon_dir)

    if not app_root.exists():
        raise click.ClickException(f"App directory does not exist: {app_root}")
    if not addon_root.exists():
        raise click.ClickException(f"Add-on directory does not exist: {addon_root}")
    if not (app_root / "package.json").exists():
        raise click.ClickException(f"Expected package.json in app directory: {app_root}")

    config = _load_config(addon_root)
    slug = config["slug"]
    out_root = _resolve(output_dir) if output_dir else app_root / ".ha-addon-dist"
    archive = out_root / f"{slug}.tar.gz"

    out_root.mkdir(parents=True, exist_ok=True)

    if archive.exists():
        archive.unlink()
    with tempfile.TemporaryDirectory(prefix="talos-external-addon-staging-") as tmp:
        staging_root = Path(tmp) / slug
        app_staging = staging_root / "app"
        staging_root.mkdir(parents=True, exist_ok=True)

        excludes = _read_excludes(addon_root, addon_root.name)
        try:
            output_rel = out_root.relative_to(app_root)
            excludes.append(output_rel.as_posix())
            if output_rel.parts:
                excludes.append(output_rel.parts[0])
        except ValueError:
            pass
        _copy_app(app_root, app_staging, excludes)

        for src in addon_root.iterdir():
            if src.name == "package-excludes.txt":
                shutil.copy2(src, staging_root / src.name)
            elif src.is_dir():
                shutil.copytree(src, staging_root / src.name, dirs_exist_ok=True)
            else:
                shutil.copy2(src, staging_root / src.name)

        run_sh = staging_root / "run.sh"
        if run_sh.exists():
            run_sh.chmod(0o755)

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(staging_root, arcname=slug)

    if verbose:
        console.print(f"[green]Packaged[/green] {slug} -> {archive}")

    return archive


def deploy_external_addon(
    app_dir: str | Path,
    addon_dir: str | Path,
    ha_host: str,
    ha_port: int,
    ha_user: str,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    validate_prereqs: bool = True,
) -> None:
    addon_root = _resolve(addon_dir)
    config = _load_config(addon_root)
    slug = config["slug"]
    addon_id = f"local_{slug}"
    remote_tar = f"/tmp/{slug}.tar.gz"
    remote_addons_dir = "/addons"
    remote_addon_dir = f"{remote_addons_dir}/{slug}"

    if dry_run:
        console.print(f"[bold]External Add-on Deployment Plan[/bold]")
        console.print(f"  • Add-on: {addon_id}")
        console.print(f"  • App dir: {_resolve(app_dir)}")
        console.print(f"  • Add-on dir: {addon_root}")
        console.print(f"  • Target: {ha_user}@{ha_host}:{ha_port}")
        console.print("")
        console.print("[dim]Operations that would be performed:[/dim]")
        console.print("  1. Package external app as a local add-on")
        console.print(f"  2. Upload archive to {ha_host}:{remote_tar}")
        console.print(f"  3. Replace {remote_addon_dir}")
        console.print(f"  4. Reload, rebuild/install, start, and verify {addon_id}")
        console.print("")
        console.print("[yellow]This is a dry run - no changes would be made[/yellow]")
        return

    try:
        if validate_prereqs:
            validate_deployment_prerequisites(ha_host, ha_port, ha_user, verbose=verbose)

        archive = package_external_addon(app_dir, addon_dir, output_dir=output_dir, verbose=verbose)
        run_cmd(["scp", "-P", str(ha_port), str(archive), f"{ha_user}@{ha_host}:{remote_tar}"], verbose=verbose)

        verbose_flag = "true" if verbose else "false"
        remote_script = f"""#!/bin/bash
set -euo pipefail

ADDON_SLUG="{slug}"
ADDON_ID="{addon_id}"
REMOTE_TAR="{remote_tar}"
REMOTE_ADDON_DIR="{remote_addon_dir}"
REMOTE_ADDONS_DIR="{remote_addons_dir}"
VERBOSE="{verbose_flag}"

log_info() {{
  if [ "$VERBOSE" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
  fi
}}

log_error() {{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}}

run_quiet() {{
  if [ "$VERBOSE" = "true" ]; then
    "$@"
  else
    "$@" >/dev/null 2>&1
  fi
}}

if ! command -v ha >/dev/null 2>&1; then
  log_error "Home Assistant CLI not found on remote host"
  exit 1
fi

log_info "Checking Home Assistant supervisor"
run_quiet ha supervisor info

if ha addons info "$ADDON_ID" >/dev/null 2>&1; then
  ADDON_STATE="$(ha addons info "$ADDON_ID" --raw-json 2>/dev/null | jq -r '.data.state // "unknown"' || echo "unknown")"
  if [ "$ADDON_STATE" = "started" ]; then
    log_info "Stopping $ADDON_ID"
    run_quiet ha addons stop "$ADDON_ID"
  fi
fi

log_info "Replacing local add-on files at $REMOTE_ADDON_DIR"
rm -rf "$REMOTE_ADDON_DIR"
mkdir -p "$REMOTE_ADDONS_DIR"
tar -xzf "$REMOTE_TAR" -C "$REMOTE_ADDONS_DIR"
rm -f "$REMOTE_TAR"

log_info "Reloading add-ons"
run_quiet ha addons reload
sleep 2

if ha addons info "$ADDON_ID" >/dev/null 2>&1; then
  log_info "Rebuilding $ADDON_ID"
  if ! run_quiet ha addons rebuild "$ADDON_ID"; then
    log_info "Rebuild failed; trying install"
    run_quiet ha addons install "$ADDON_ID"
  fi
else
  log_info "Installing $ADDON_ID"
  run_quiet ha addons install "$ADDON_ID"
fi

log_info "Starting $ADDON_ID"
run_quiet ha addons start "$ADDON_ID"
sleep 3

if ha addons info "$ADDON_ID" --raw-json | jq -e '.data.state == "started"' >/dev/null; then
  log_info "$ADDON_ID is started"
else
  log_error "$ADDON_ID did not reach started state"
  ha addons logs "$ADDON_ID" --lines 80 >&2 || true
  exit 1
fi
"""

        run_cmd(["ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}", remote_script], verbose=verbose)
        console.print(f"[green]Deployed[/green] {addon_id} to {ha_host}")
    except subprocess.CalledProcessError as e:
        recent_logs = get_addon_logs(ha_host, ha_port, ha_user, addon_id, lines=20)
        raise DeploymentError(
            f"Failed to deploy external add-on {addon_id}",
            error_type="EXTERNAL_ADDON_DEPLOY_FAILED",
            context={
                "addon_id": addon_id,
                "host": ha_host,
                "exit_code": e.returncode,
                "recent_logs": recent_logs,
            },
            troubleshooting_steps=[
                f"Check add-on logs: ssh -p {ha_port} {ha_user}@{ha_host} ha addons logs {addon_id}",
                f"Check add-on info: ssh -p {ha_port} {ha_user}@{ha_host} ha addons info {addon_id}",
                "Run the deploy again with --verbose",
            ],
        ) from e


def package_external_to_temp(app_dir: str | Path, addon_dir: str | Path, verbose: bool = False) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="talos-external-addon-"))
    return package_external_addon(app_dir, addon_dir, output_dir=temp_dir, verbose=verbose)
