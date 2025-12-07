from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .paths import ADDON_BUILD_ROOT, REPO_ROOT, TEMPLATE_DIR

console = Console()


class DeploymentError(Exception):
    """Enhanced deployment error with context and troubleshooting info."""

    def __init__(self, message: str, error_type: str = "DEPLOYMENT_ERROR",
                 context: Optional[Dict[str, Any]] = None,
                 troubleshooting_steps: Optional[List[str]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.context = context or {}
        self.troubleshooting_steps = troubleshooting_steps or []
        self.timestamp = datetime.now()

    def display_error(self):
        """Display a rich error message with troubleshooting info."""
        console.print(f"\n[red]❌ Deployment Error: {self.error_type}[/red]")
        console.print(f"\n[bold]Details:[/bold]")
        console.print(f"  {self.args[0]}")

        if self.context:
            console.print(f"\n[bold]Context:[/bold]")
            for key, value in self.context.items():
                console.print(f"  • {key}: {value}")

        if self.troubleshooting_steps:
            console.print(f"\n[bold]Troubleshooting Steps:[/bold]")
            for i, step in enumerate(self.troubleshooting_steps, 1):
                console.print(f"  {i}. {step}")

        console.print(f"\n[dim]Timestamp: {self.timestamp.isoformat()}[/dim]")


def validate_deployment_prerequisites(ha_host: str, ha_port: int, ha_user: str) -> None:
    """Validate that deployment prerequisites are met."""
    console.print("🔍 [bold]Validating deployment prerequisites...[/bold]")

    # Test SSH connectivity
    try:
        result = run_cmd([
            "ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "echo 'SSH connection successful'"
        ], verbose=False, capture_output=True)
        console.print("  ✓ SSH connection established")
    except subprocess.CalledProcessError as e:
        raise DeploymentError(
            f"Cannot establish SSH connection to {ha_host}:{ha_port}",
            error_type="SSH_CONNECTION_FAILED",
            context={
                "host": ha_host,
                "port": ha_port,
                "user": ha_user,
                "exit_code": e.returncode
            },
            troubleshooting_steps=[
                f"Verify SSH access: ssh -p {ha_port} {ha_user}@{ha_host}",
                "Check if Home Assistant is running",
                "Verify network connectivity",
                "Check SSH key authentication"
            ]
        )

    # Check Home Assistant health
    try:
        result = run_cmd([
            "ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}",
            "ha core info --raw-json"
        ], verbose=False, capture_output=True)

        ha_info = json.loads(result.stdout)
        if ha_info.get("data", {}).get("state") != "running":
            raise DeploymentError(
                "Home Assistant core is not running",
                error_type="HA_CORE_NOT_RUNNING",
                context={"state": ha_info.get("data", {}).get("state")},
                troubleshooting_steps=[
                    "Check Home Assistant status: ha core info",
                    "Start Home Assistant: ha core start",
                    "Check system logs: ha supervisor logs"
                ]
            )
        console.print("  ✓ Home Assistant core is running")
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        raise DeploymentError(
            "Cannot verify Home Assistant health",
            error_type="HA_HEALTH_CHECK_FAILED",
            troubleshooting_steps=[
                "Check Home Assistant status: ha core info",
                "Verify supervisor is running: ha supervisor info",
                "Check system logs for errors"
            ]
        )

    # Check disk space
    try:
        result = run_cmd([
            "ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}",
            "df -h / | tail -1 | awk '{print $4}'"
        ], verbose=False, capture_output=True)

        free_space = result.stdout.strip()
        console.print(f"  ✓ Disk space available: {free_space}")
    except subprocess.CalledProcessError:
        console.print("  ⚠️  Could not check disk space")

    console.print("✅ [green]Prerequisites validation passed[/green]\n")


def discover_addons() -> Dict[str, Any]:
    """Discover all addons by finding */addon.yaml files in the repo."""
    addons: Dict[str, Any] = {}
    for addon_yaml in REPO_ROOT.glob("*/addon.yaml"):
        addon_dir = addon_yaml.parent
        addon_key = addon_dir.name

        data = yaml.safe_load(addon_yaml.read_text(encoding="utf-8"))
        if not data:
            continue

        # Derive source_dir from addon location
        # If there's a source_subdir, use that as the working directory
        source_dir = addon_dir / data.get("source_subdir", "") if data.get("source_subdir") else addon_dir

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
    except ImportError:  # pragma: no cover - Py<3.11 fallback
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
    versions: Dict[str, str] = {}

    nvmrc_path = REPO_ROOT / ".nvmrc"
    if nvmrc_path.exists():
        node_version = nvmrc_path.read_text().strip()
        versions["node"] = node_version.lstrip("v")
        versions["node_major"] = node_version.lstrip("v").split(".")[0]
    else:
        versions["node"] = "20.18.2"
        versions["node_major"] = "20"

    python_version_path = REPO_ROOT / ".python-version"
    if python_version_path.exists():
        python_version = python_version_path.read_text().strip()
        versions["python"] = python_version
        versions["python_minor"] = ".".join(python_version.split(".")[:2])
    else:
        versions["python"] = "3.9.0"
        versions["python_minor"] = "3.9"

    return versions


def build_context(addon_key: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if addon_key not in manifest:
        raise click.ClickException(f"Addon '{addon_key}' not found in manifest")

    raw = manifest[addon_key]
    source_dir = REPO_ROOT / raw["source_dir"]

    runtime_versions = read_runtime_versions()

    if raw.get("python", False):
        version_from = source_dir / "pyproject.toml"
        version = read_pyproject_version(version_from) if version_from.exists() else "0.0.0"
    else:
        version_from = source_dir / "package.json"
        version = read_package_version(version_from) if version_from.exists() else "0.0.0"

    ports = raw.get("ports") or {}
    port = int(next(iter(ports.keys()))) if ports else None

    # Container paths (used in Dockerfile and run.sh templates)
    container_paths = {
        "venv": "/opt/venv",  # Python virtual environment location
        "tmp_overlay": "/tmp/app-overlay",  # Temporary overlay for git clone operations
        "ha_options": "/data/options.json",  # Home Assistant options file
        "ha_config": "/config",  # Home Assistant config mount point
        "ha_data": "/data",  # Home Assistant data mount point
    }

    # Deployment paths (used for remote Home Assistant operations)
    deploy_paths = {
        "remote_home": "/root",  # Home directory on Home Assistant host
        "remote_addons": "/addons",  # Add-ons directory on Home Assistant host
    }

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
            "custom_dockerfile": raw.get("custom_dockerfile", False),
            "node_version": runtime_versions["node"],
            "node_major": runtime_versions["node_major"],
            "python_version": runtime_versions["python"],
            "python_minor": runtime_versions["python_minor"],
        },
        "paths": {
            **container_paths,
            **deploy_paths,
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
        "iVBORw0KGgoAAAANSUhEUgAAAIwAAACMCAYAAAB1Hg1ZAAAABmJLR0QA/wD/AP+gvaeTAAABhUlEQVR4nO3aPW7CMBQG4M3lDAZhgXcwiAIwJgrAHRhBsENwDozBCnSlYB5iM5dfHpuO83I5ZrSX7/y3t59n9/PNHtq5VABERERERERERETkFy8A+gN1M1vHM/4O1Zhq6B3QK9jFrZqdd3kc1oAuY4ZrXtUa6PbUDrCOatbfRQuwN1kHtrTxBEcX3W6DBZR264yugPVkHYqVvRCuwR1kHarkgAV6HoUDLVKixj0J6gDtZB2Klb0QrsEdZB2rpJAFel6FAy1SosY9CeoA7WQdiqW0gZ6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZD0qVn0gY6BzUBoqVNRCewO6CDtZB2KpbSBnoHNAaKlT0QnsDugg7WQ9Kla9ICNUAZ7Bf0yu9oJvhYpoRERERERERERkd4TB5g2bgDW2lzQAAAABJRU5ErkJggg=="
    )
    for name in ("icon.png", "logo.png"):
        target = addon_root / name
        if not target.exists():
            target.write_bytes(placeholder)


def make_tarball(addon_root: Path, slug: str) -> Path:
    ADDON_BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    archive = ADDON_BUILD_ROOT / f"{slug}.tar.gz"
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(addon_root, arcname=slug)
    return archive


def build_addon(addon_key: str) -> Path:
    manifest = load_manifest()
    context = build_context(addon_key, manifest)
    addon = context["addon"]
    addon_root = ADDON_BUILD_ROOT / addon["slug"]
    app_root = addon_root / "app"
    translations_root = addon_root / "translations"

    if addon_root.exists():
        shutil.rmtree(addon_root)
    app_root.mkdir(parents=True, exist_ok=True)
    translations_root.mkdir(parents=True, exist_ok=True)

    copy_sources(addon, app_root)

    env = jinja_env()
    write_file(addon_root / "config.yaml", render_template(env, "config.yaml.j2", context))

    if addon.get("custom_dockerfile", False):
        custom_dockerfile = addon["source_dir"] / "Dockerfile"
        if not custom_dockerfile.exists():
            raise click.ClickException(f"custom_dockerfile is set but {custom_dockerfile} not found")
        shutil.copy2(custom_dockerfile, addon_root / "Dockerfile")
    else:
        write_file(addon_root / "Dockerfile", render_template(env, "Dockerfile.j2", context))

    custom_run_sh = addon["source_dir"] / "run.sh"
    if custom_run_sh.exists():
        shutil.copy2(custom_run_sh, addon_root / "run.sh")
    else:
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


def run_cmd(cmd: list[str], dry_run: bool = False, cwd: Optional[Path] = None, verbose: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run a command with improved error handling and output control."""
    # Only show commands in verbose mode, and make dry-run output much more concise
    if verbose and not dry_run:
        console.print(f"[cyan]$ {' '.join(cmd)}[/cyan]" + (f" (cwd={cwd})" if cwd else ""))

    if dry_run:
        # For dry run, only show high-level operations, not individual commands
        if verbose:
            console.print(f"[dim]Would run: {' '.join(cmd)}[/dim]")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=str(cwd) if cwd else None,
            capture_output=capture_output,
            text=True if capture_output else None
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed with exit code {e.returncode}[/red]")
        if capture_output and e.stdout:
            console.print(f"[red]stdout:[/red] {e.stdout}")
        if capture_output and e.stderr:
            console.print(f"[red]stderr:[/red] {e.stderr}")
        raise


def deploy_addon(addon_key: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool, verbose: bool = False) -> None:
    """Deploy an add-on with enhanced error handling and validation."""
    try:
        manifest = load_manifest()
        context = build_context(addon_key, manifest)
        addon = context["addon"]
        paths = context["paths"]
        slug = addon["slug"]
        port = addon.get("port")

        if dry_run:
            # Concise dry-run output showing deployment plan
            console.print(f"📋 [bold]Deployment Plan for {addon_key}:[/bold]")
            console.print(f"  • Add-on: {addon_key} (slug: {slug})")
            console.print(f"  • Target: {ha_user}@{ha_host}:{ha_port}")
            console.print(f"  • Version: {addon.get('version', 'unknown')}")
            if port:
                console.print(f"  • Port: {port}")
            if addon.get("ingress"):
                console.print(f"  • Ingress: enabled")

            console.print(f"\n[dim]Operations that would be performed:[/dim]")
            console.print(f"  1. Build add-on locally")
            console.print(f"  2. Upload to {ha_host}")
            console.print(f"  3. Stop existing add-on (if running)")
            console.print(f"  4. Install/rebuild add-on")
            console.print(f"  5. Configure add-on options")
            console.print(f"  6. Start add-on")
            console.print(f"  7. Verify add-on health")

            console.print(f"\n[yellow]This is a dry run - no changes would be made[/yellow]")
            return

        # Validate prerequisites for real deployments
        validate_deployment_prerequisites(ha_host, ha_port, ha_user)

        console.print(f"🔨 [bold]Building {addon_key}...[/bold]")
        archive = build_addon(addon_key)

        remote_tar = f"{paths['remote_home']}/{slug}.tar.gz"
        remote_addon_dir = f"{paths['remote_addons']}/{slug}"
        has_ingress = "true" if addon.get("ingress") else "false"

        console.print(f"📦 [bold]Deploying {addon_key} to {ha_host}...[/bold]")

        # Upload addon tarball
        scp_cmd = ["scp", "-P", str(ha_port), str(archive), f"{ha_user}@{ha_host}:{remote_tar}"]
        try:
            run_cmd(scp_cmd, dry_run=dry_run, verbose=verbose)
            console.print(f"  ✓ Uploaded {addon_key} tarball")
        except subprocess.CalledProcessError as e:
            raise DeploymentError(
                f"Failed to upload {addon_key} to {ha_host}",
                error_type="UPLOAD_FAILED",
                context={
                    "addon": addon_key,
                    "host": ha_host,
                    "exit_code": e.returncode
                },
                troubleshooting_steps=[
                    f"Check SSH connectivity: ssh -p {ha_port} {ha_user}@{ha_host}",
                    "Verify disk space on target system",
                    "Check file permissions"
                ]
            )

        # Create enhanced remote deployment script
        remote_script = f"""#!/bin/bash
set -euo pipefail

# Deployment variables
ADDON_SLUG="{slug}"
ADDON_ID="local_{slug}"
REMOTE_TAR="{remote_tar}"
REMOTE_ADDON_DIR="{remote_addon_dir}"

# Logging function
log_info() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
}}

log_error() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}}

# Stop addon if running
log_info "Stopping add-on $ADDON_ID if running..."
if ha addons info "$ADDON_ID" >/dev/null 2>&1; then
    if ! ha addons stop "$ADDON_ID"; then
        log_error "Failed to stop add-on $ADDON_ID"
        exit 1
    fi
    log_info "Add-on $ADDON_ID stopped successfully"
else
    log_info "Add-on $ADDON_ID not currently installed"
fi

# Extract addon files
log_info "Extracting add-on files..."
rm -rf "$REMOTE_ADDON_DIR"
mkdir -p "{paths['remote_addons']}"
if ! tar -xzf "$REMOTE_TAR" -C "{paths['remote_addons']}"; then
    log_error "Failed to extract add-on tarball"
    exit 1
fi
rm -f "$REMOTE_TAR"
log_info "Add-on files extracted successfully"

# Reload addon list
log_info "Reloading add-on list..."
if ! ha addons reload; then
    log_error "Failed to reload add-on list"
    exit 1
fi
sleep 2

# Install or rebuild addon
log_info "Installing/rebuilding add-on $ADDON_ID..."
if ha addons info "$ADDON_ID" >/dev/null 2>&1; then
    log_info "Add-on exists, attempting rebuild..."
    if ! ha addons rebuild "$ADDON_ID"; then
        log_info "Rebuild failed, attempting fresh install..."
        if ! ha addons install "$ADDON_ID"; then
            log_error "Failed to install add-on $ADDON_ID"
            exit 1
        fi
    fi
else
    log_info "Installing new add-on..."
    if ! ha addons install "$ADDON_ID"; then
        log_error "Failed to install add-on $ADDON_ID"
        exit 1
    fi
fi
"""

        # Add port mapping and options configuration
        if port:
            remote_script += f"""
# Check if port mapping is needed
log_info "Checking port configuration for port {port}..."
CURRENT_PORT="$(ha addons info "$ADDON_ID" --raw-json 2>/dev/null | jq -r '.network["{port}/tcp"] // empty' || true)"
need_port_mapping="false"
if [ -z "$CURRENT_PORT" ] || [ "$CURRENT_PORT" = "null" ]; then
    need_port_mapping="true"
    log_info "Port mapping needed for port {port}"
else
    log_info "Port {port} already configured"
fi
"""

        # Add options configuration
        remote_script += f"""
# Configure add-on options
log_info "Configuring add-on options..."
SUPERVISOR_TOKEN="${{SUPERVISOR_TOKEN:-}}"
if [ -n "$SUPERVISOR_TOKEN" ]; then
    OPTIONS_JSON='{{"watchdog": true'
    if [ "{has_ingress}" = "true" ]; then
        OPTIONS_JSON+=', "ingress_panel": true'
    fi
    if [ "{'true' if bool(port) else 'false'}" = "true" ] && [ "$need_port_mapping" = "true" ]; then
        OPTIONS_JSON+=', "network": {{"{port}/tcp": {port}}}'
    fi
    OPTIONS_JSON+='}}'

    if curl -sSf -H "Authorization: Bearer $SUPERVISOR_TOKEN" -H "Content-Type: application/json" \\
        -X POST -d "$OPTIONS_JSON" http://supervisor/addons/"$ADDON_ID"/options >/dev/null; then
        log_info "Add-on options configured successfully"
    else
        log_error "Failed to set add-on options for $ADDON_ID"
        exit 1
    fi
else
    log_info "SUPERVISOR_TOKEN not set; skipping add-on options configuration"
fi

# Start the add-on
log_info "Starting add-on $ADDON_ID..."
if ha addons start "$ADDON_ID"; then
    log_info "Add-on $ADDON_ID started successfully"

    # Wait a moment and verify it's running
    sleep 3
    if ha addons info "$ADDON_ID" --raw-json | jq -e '.state == "started"' >/dev/null; then
        log_info "Add-on $ADDON_ID is running and healthy"
    else
        log_error "Add-on $ADDON_ID failed to start properly"
        exit 1
    fi
else
    log_error "Failed to start add-on $ADDON_ID"
    exit 1
fi

log_info "Deployment of $ADDON_ID completed successfully"
"""

        # Execute remote deployment script
        ssh_cmd = ["ssh", "-p", str(ha_port), f"{ha_user}@{ha_host}", remote_script]
        try:
            run_cmd(ssh_cmd, dry_run=dry_run, verbose=verbose)
            if not dry_run:
                console.print(f"  ✅ [green]{addon_key} deployed successfully[/green]")
        except subprocess.CalledProcessError as e:
            raise DeploymentError(
                f"Failed to deploy {addon_key} on remote system",
                error_type="REMOTE_DEPLOYMENT_FAILED",
                context={
                    "addon": addon_key,
                    "host": ha_host,
                    "exit_code": e.returncode
                },
                troubleshooting_steps=[
                    f"Check add-on logs: ha addons logs local_{slug}",
                    f"Check add-on info: ha addons info local_{slug}",
                    "Check supervisor logs: ha supervisor logs",
                    f"Rebuild add-on: just ha-addon {addon_key}",
                    "Check Home Assistant system health"
                ]
            )

        console.print(f"✅ [green]Successfully deployed {addon_key} to {ha_host}[/green]")

    except DeploymentError:
        # Re-raise deployment errors to preserve context
        raise
    except Exception as e:
        # Wrap unexpected errors in DeploymentError
        raise DeploymentError(
            f"Unexpected error during {addon_key} deployment: {str(e)}",
            error_type="UNEXPECTED_ERROR",
            context={"addon": addon_key, "error": str(e)},
            troubleshooting_steps=[
                "Check system logs for more details",
                "Verify all prerequisites are met",
                "Try deploying with --verbose for more information"
            ]
        )


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


def list_addons() -> None:
    manifest = load_manifest()
    for key, cfg in manifest.items():
        console.print(f"- {key}: slug={cfg.get('slug')} port={list((cfg.get('ports') or {}).keys())}")


def addon_names(as_json: bool = False) -> None:
    names = list(load_manifest().keys())
    if as_json:
        console.print(json.dumps(names))
    else:
        console.print(" ".join(names))


def run_build(addon: str) -> None:
    build_addon(addon)


def run_deploy(addon: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool, verbose: bool = False) -> None:
    deploy_addon(addon, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=dry_run, verbose=verbose)


def run_test(addon: str) -> None:
    run_tests(addon)
