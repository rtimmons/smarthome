#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "tools" / "templates"
BUILD_ROOT = REPO_ROOT / "build" / "home-assistant-addon"

console = Console()


def discover_addons() -> Dict[str, Any]:
    """Discover all addons by finding */addon.yaml files in the repo."""
    addons = {}
    for addon_yaml in REPO_ROOT.glob("*/addon.yaml"):
        addon_dir = addon_yaml.parent
        addon_key = addon_dir.name

        data = yaml.safe_load(addon_yaml.read_text(encoding="utf-8"))
        if not data:
            continue

        # Derive source_dir from addon location
        # If there's a source_subdir, use that as the working directory
        if "source_subdir" in data:
            source_dir = addon_dir / data["source_subdir"]
        else:
            source_dir = addon_dir

        data["source_dir"] = source_dir
        addons[addon_key] = data

    return addons


def load_manifest() -> Dict[str, Any]:
    """Load all addon manifests from */addon.yaml files."""
    return discover_addons()


def read_package_version(path: Path) -> str:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def read_pyproject_version(path: Path) -> str:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            import re
            raw = path.read_text()
            match = re.search(r'^version\s*=\s*"(?P<version>[^"]+)"', raw, re.MULTILINE)
            return match.group("version") if match else "0.0.0"

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def default_yaml(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(data or {}, default_flow_style=False, sort_keys=False).strip() or "{}"


def read_runtime_versions() -> Dict[str, str]:
    """Read runtime versions from .nvmrc and .python-version files."""
    versions = {}

    # Read Node version from .nvmrc
    nvmrc_path = REPO_ROOT / ".nvmrc"
    if nvmrc_path.exists():
        node_version = nvmrc_path.read_text().strip()
        # Convert v20.18.2 to 20.18.2 for Docker image tags
        versions["node"] = node_version.lstrip('v')
        versions["node_major"] = node_version.lstrip('v').split('.')[0]
    else:
        versions["node"] = "20.18.2"
        versions["node_major"] = "20"

    # Read Python version from .python-version
    python_version_path = REPO_ROOT / ".python-version"
    if python_version_path.exists():
        python_version = python_version_path.read_text().strip()
        versions["python"] = python_version
        versions["python_minor"] = '.'.join(python_version.split('.')[:2])  # 3.9.0 -> 3.9
    else:
        versions["python"] = "3.9.0"
        versions["python_minor"] = "3.9"

    return versions


def build_context(addon_key: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if addon_key not in manifest:
        raise click.ClickException(f"Addon '{addon_key}' not found in {MANIFEST_PATH}")

    raw = manifest[addon_key]
    source_dir = REPO_ROOT / raw["source_dir"]

    # Read runtime versions from version files
    runtime_versions = read_runtime_versions()

    # Determine version based on project type
    if raw.get("python", False):
        version_from = source_dir / "pyproject.toml"
        version = read_pyproject_version(version_from) if version_from.exists() else "0.0.0"
    else:
        version_from = source_dir / "package.json"
        version = read_package_version(version_from) if version_from.exists() else "0.0.0"

    ports = raw.get("ports") or {}
    port = int(next(iter(ports.keys()))) if ports else None

    context = {
        "addon": {
            "key": addon_key,
            "slug": raw["slug"],
            "name": raw["name"],
            "description": raw["description"],
            "url": raw.get("url", ""),
            "source_dir": source_dir,
            "copy": raw.get("copy", []),
            "container_workdir": raw.get("container_workdir", f"/opt/{raw['slug']}/app"),
            "homeassistant_min": raw.get("homeassistant_min", "2024.6.0"),
            "ingress": raw.get("ingress", False),
            "ingress_entry": raw.get("ingress_entry"),
            "panel_icon": raw.get("panel_icon"),
            "panel_title": raw.get("panel_title"),
            "homeassistant_api": raw.get("homeassistant_api", False),
            "auth_api": raw.get("auth_api", False),
            "host_network": raw.get("host_network", False),
            "ports": ports,
            "ports_description": raw.get("ports_description", {}),
            "environment": raw.get("environment", {}),
            "options": raw.get("options", {}),
            "schema": raw.get("schema", {}),
            "translations": raw.get("translations", {}),
            "docs": raw.get("docs", {}),
            "version": version,
            "npm_build": raw.get("npm_build", False),
            "python": raw.get("python", False),
            "python_module": raw.get("python_module", ""),
            "port": port,
            "run_env": raw.get("run_env", []),
            "git_clone": raw.get("git_clone"),
            "tests": raw.get("tests", []),
            "map": raw.get("map", []),
            "usb": raw.get("usb", False),
            "audio": raw.get("audio", False),
            "gpio": raw.get("gpio", False),
            # Runtime versions from .nvmrc and .python-version
            "node_version": runtime_versions["node"],
            "node_major": runtime_versions["node_major"],
            "python_version": runtime_versions["python"],
            "python_minor": runtime_versions["python_minor"],
        },
        "ports_yaml": default_yaml({f"{k}/tcp": v for k, v in ports.items()}),
        "ports_desc_yaml": default_yaml({f"{k}/tcp": v for k, v in raw.get("ports_description", {}).items()}),
        "environment_yaml": default_yaml(raw.get("environment", {})),
        "options_yaml": default_yaml(raw.get("options", {})),
        "schema_yaml": default_yaml(raw.get("schema", {})),
        "translations_yaml": default_yaml(raw.get("translations", {})),
    }
    return context


def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson"] = lambda obj: json.dumps(obj)
    env.filters["shquote"] = lambda obj: shlex.quote(str(obj))
    return env


def render_template(env: Environment, template_name: str, context: Dict[str, Any]) -> str:
    return env.get_template(template_name).render(**context)


def copy_sources(addon: Dict[str, Any], app_root: Path) -> None:
    source_dir: Path = addon["source_dir"]
    for item in addon.get("copy", []):
        src = source_dir / item
        if not src.exists():
            raise click.ClickException(f"Missing source path: {src}")
        dest = app_root / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_placeholder_images(addon_root: Path) -> None:
    placeholder = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAIwAAACMCAYAAAB1Hg1ZAAAABmJLR0QA/wD/AP+gvaeTAAABhUlEQVR4nO3aPW7CMBQG4M3lDAZhgXcwiAIwJgrAHRhBsENwDozBCnSlYB5iM5dfHpuO83I5ZrSX7/y3t59n9/PNHtq5VABERERERERERETkFy8A+gN1M1vHM/4O1Zhq6B3QK9jFrZqdd3kc1oAuY4ZrXtUa6PbUDrCOatbfRQuwN1kHtrTxBEcX3W6DBZR264yugPVkHYqVvRCuwR1kHarkgAV6HoUDLVKixj0J6gDtZB2Klb0QrsEdZB2rpJAFel6FAy1SosY9CeoA7WQdiplFRAb0DuoA7WQdiqW0gZ6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZB2KpbSBnoHNAaKlT0QnsDugg7WQ9Kla9ICNUAZ7Bf0yu9oJvhYpoRERERERERERkd4TB5g2bgDW2lzQAAAABJRU5ErkJggg=="
    )
    for name in ("icon.png", "logo.png"):
        target = addon_root / name
        if not target.exists():
            target.write_bytes(placeholder)


def make_tarball(addon_root: Path, slug: str) -> Path:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    archive = BUILD_ROOT / f"{slug}.tar.gz"
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(addon_root, arcname=slug)
    return archive


def build_addon(addon_key: str) -> Path:
    manifest = load_manifest()
    context = build_context(addon_key, manifest)
    addon = context["addon"]
    addon_root = BUILD_ROOT / addon["slug"]
    app_root = addon_root / "app"
    translations_root = addon_root / "translations"

    if addon_root.exists():
        shutil.rmtree(addon_root)
    app_root.mkdir(parents=True, exist_ok=True)
    translations_root.mkdir(parents=True, exist_ok=True)

    copy_sources(addon, app_root)

    env = jinja_env()
    write_file(addon_root / "config.yaml", render_template(env, "config.yaml.j2", context))
    write_file(addon_root / "Dockerfile", render_template(env, "Dockerfile.j2", context))
    write_file(addon_root / "run.sh", render_template(env, "run.sh.j2", context))
    os.chmod(addon_root / "run.sh", 0o755)
    write_file(addon_root / "README.md", render_template(env, "README.md.j2", context))
    write_file(addon_root / "DOCS.md", render_template(env, "DOCS.md.j2", context))
    write_file(addon_root / "CHANGELOG.md", f"## {addon['version']}\n\n- Automated Home Assistant add-on packaging.")
    write_file(addon_root / "apparmor.txt", render_template(env, "apparmor.txt.j2", context))
    write_file(translations_root / "en.yaml", render_template(env, "translations_en.yaml.j2", context))

    generate_placeholder_images(addon_root)
    archive = make_tarball(addon_root, addon["slug"])
    console.print(f"[green]Built[/green] {addon_key} -> {addon_root}")
    console.print(f"[green]Tarball[/green] {archive}")
    return archive


def run_cmd(cmd: list[str], dry_run: bool = False, cwd: Optional[Path] = None) -> None:
    console.print(f"[cyan]$ {' '.join(cmd)}[/cyan]" + (f" (cwd={cwd})" if cwd else ""))
    if dry_run:
        return
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def deploy_addon(addon_key: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool) -> None:
    manifest = load_manifest()
    context = build_context(addon_key, manifest)
    addon = context["addon"]
    archive = build_addon(addon_key)
    slug = addon["slug"]
    remote_tar = f"/root/{slug}.tar.gz"
    remote_addon_dir = f"/addons/{slug}"

    scp_cmd = ["scp", "-P", str(ha_port), str(archive), f"{ha_user}@{ha_host}:{remote_tar}"]
    run_cmd(scp_cmd, dry_run=dry_run)

    remote_script = f"""
set -euo pipefail
ADDON_SLUG="{slug}"
ADDON_ID="local_{slug}"
REMOTE_TAR="{remote_tar}"
REMOTE_ADDON_DIR="{remote_addon_dir}"

ha addons stop "${{ADDON_ID}}" >/dev/null 2>&1 || true
rm -rf "${{REMOTE_ADDON_DIR}}"
mkdir -p "/addons"
tar -xzf "${{REMOTE_TAR}}" -C "/addons"
rm -f "${{REMOTE_TAR}}"

ha addons reload
sleep 2
if ha addons info "${{ADDON_ID}}" >/dev/null 2>&1; then
  ha addons rebuild "${{ADDON_ID}}"
else
  ha addons install "${{ADDON_ID}}"
fi
ha addons start "${{ADDON_ID}}" || true
"""
    ssh_cmd = ["ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}", remote_script]
    run_cmd(ssh_cmd, dry_run=dry_run)
    console.print(f"[green]Deployed[/green] {addon_key} to {ha_host}")


@click.group()
def cli() -> None:
    """Home Assistant add-on builder."""


@cli.command("list")
def list_addons() -> None:
    manifest = load_manifest()
    for key, cfg in manifest.items():
        console.print(f"- {key}: slug={cfg.get('slug')} port={list((cfg.get('ports') or {}).keys())}")


@cli.command("names")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON array.")
def addon_names(as_json: bool) -> None:
    names = list(load_manifest().keys())
    if as_json:
        console.print(json.dumps(names))
    else:
        console.print(" ".join(names))


@cli.command()
@click.argument("addon")
def build(addon: str) -> None:
    build_addon(addon)


@cli.command()
@click.argument("addon")
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print commands without executing.")
def deploy(addon: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool) -> None:
    deploy_addon(addon, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=dry_run)


def run_tests(addon_key: str) -> None:
    manifest = load_manifest()
    context = build_context(addon_key, manifest)
    addon = context["addon"]
    tests: List[str] = addon.get("tests") or []
    if not tests:
        console.print(f"[yellow]Skipping[/yellow] {addon_key}: no tests configured.")
        return

    for test_cmd in tests:
        run_cmd(["bash", "-lc", test_cmd], cwd=addon["source_dir"])
    console.print(f"[green]Tests passed[/green] for {addon_key}")


@cli.command()
@click.argument("addon")
def test(addon: str) -> None:
    run_tests(addon)


if __name__ == "__main__":
    cli()
