from __future__ import annotations

import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import time
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

import click
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .paths import ADDON_BUILD_ROOT, REPO_ROOT, TEMPLATE_DIR
from .addon_manifest import discover_addons
from .timing import DeployTimer

console = Console()

DEFAULT_HA_SSH_IDENTITY = REPO_ROOT / ".ssh" / "id_ed25519_codex_smarthome"


def ha_ssh_identity() -> Path:
    """Return the explicit repository-local Home Assistant SSH identity."""
    return Path(
        os.environ.get("HASS_SSH_IDENTITY", str(DEFAULT_HA_SSH_IDENTITY))
    ).expanduser()


def ssh_transport_args(port: int) -> list[str]:
    return [
        "-i", str(ha_ssh_identity()),
        "-o", "IdentitiesOnly=yes",
        "-p", str(port),
    ]


def scp_transport_args(port: int) -> list[str]:
    return [
        "-i", str(ha_ssh_identity()),
        "-o", "IdentitiesOnly=yes",
        "-P", str(port),
    ]


def ssh_command(host: str, port: int, user: str) -> str:
    return shlex.join(["ssh", *ssh_transport_args(port), f"{user}@{host}"])


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
                if key == "recent_logs" and value and value.strip():
                    console.print(f"  • {key}:")
                    # Display logs with proper formatting
                    log_lines = value.strip().split('\n')
                    for line in log_lines[-10:]:  # Show last 10 lines
                        if line.strip():
                            console.print(f"    [dim]{line}[/dim]")
                else:
                    console.print(f"  • {key}: {value}")

        if self.troubleshooting_steps:
            console.print(f"\n[bold]Troubleshooting Steps:[/bold]")
            for i, step in enumerate(self.troubleshooting_steps, 1):
                console.print(f"  {i}. {step}")

        console.print(f"\n[dim]Timestamp: {self.timestamp.isoformat()}[/dim]")


def get_addon_logs(ha_host: str, ha_port: int, ha_user: str, addon_id: str, lines: int = 10) -> str:
    """Get the last N lines of logs for an add-on."""
    try:
        result = run_cmd([
            "ssh", *ssh_transport_args(ha_port), f"{ha_user}@{ha_host}",
            f"ha addons logs {addon_id} --lines {lines}"
        ], verbose=False, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return f"Could not retrieve logs for {addon_id}"


def check_ha_core_status(ha_host: str, ha_port: int, ha_user: str) -> dict:
    """Check Home Assistant core status and return detailed information."""
    try:
        result = run_cmd([
            "ssh", *ssh_transport_args(ha_port), f"{ha_user}@{ha_host}",
            "ha core info --raw-json"
        ], verbose=False, capture_output=True)

        ha_info = json.loads(result.stdout)
        if ha_info.get("result") != "ok":
            return {"status": "error", "data": ha_info}

        core_data = ha_info.get("data", {})
        return {
            "status": "ok",
            "version": core_data.get("version"),
            "update_available": core_data.get("update_available", False),
            "arch": core_data.get("arch"),
            "port": core_data.get("port", 8123)
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        return {"status": "error", "error": str(e)}


def classify_ssh_failure(stderr: str) -> str:
    """Classify the failure stage without treating pre-auth DNS as an auth error."""
    message = stderr.lower()
    if any(
        marker in message
        for marker in (
            "could not resolve hostname",
            "name or service not known",
            "nodename nor servname provided",
            "temporary failure in name resolution",
            "no address associated with hostname",
        )
    ):
        return "SSH_HOSTNAME_RESOLUTION_FAILED"
    if any(
        marker in message
        for marker in (
            "permission denied",
            "agent refused operation",
            "sign_and_send_pubkey",
            "too many authentication failures",
            "identity file",
            "no such identity",
        )
    ):
        return "SSH_AUTHENTICATION_FAILED"
    return "SSH_CONNECTION_FAILED"


def ssh_failure_troubleshooting(error_type: str, host: str, port: int, user: str) -> list[str]:
    command = ssh_command(host, port, user)
    if error_type == "SSH_HOSTNAME_RESOLUTION_FAILED":
        return [
            f"Retry the exact hostname-based command once outside the Codex sandbox: {command}",
            "Do not substitute an IP address; this failure happened before authentication",
            "If the hostname still does not resolve, stop and report the mDNS/network failure",
        ]
    if error_type == "SSH_AUTHENTICATION_FAILED":
        return [
            "Stop the deployment and ask Ryan to run the human-only `just ha-ssh-key-copy`",
            "Retry only after Ryan confirms the repository-local key is installed",
            "Do not retry repeatedly or fall back to 1Password, another host, an IP address, or alternate credentials",
        ]
    return [
        f"Inspect the exact failure with: {command}",
        "Stop the deployment until the SSH transport problem is understood",
        "Do not fall back to another host, IP address, or authentication path",
    ]


def validate_deployment_prerequisites(
    ha_host: str,
    ha_port: int,
    ha_user: str,
    verbose: bool = False,
    timer: DeployTimer | None = None,
) -> None:
    """
    Validate that deployment prerequisites are met.

    This function performs comprehensive validation to ensure the deployment
    environment is ready and safe for deployment operations.

    Args:
        ha_host: Target Home Assistant host
        ha_port: SSH port for connection
        ha_user: SSH user for authentication

    Raises:
        DeploymentError: If any prerequisite validation fails

    Validation Steps:
        1. Input parameter validation
        2. SSH connectivity test with timeout
        3. Home Assistant core status check
        4. Disk space availability check
        5. System resource validation
    """
    if verbose:
        console.print("🔍 [bold]Validating deployment prerequisites...[/bold]")
    else:
        console.print("🔍 Validating deployment prerequisites...")

    # Input validation with detailed error messages
    if not ha_host or not isinstance(ha_host, str) or ha_host.strip() == "":
        raise DeploymentError(
            "Invalid or empty host parameter",
            error_type="INVALID_PARAMETER",
            context={"parameter": "ha_host", "value": ha_host, "type": type(ha_host).__name__},
            troubleshooting_steps=[
                "Provide a valid hostname or IP address",
                "Check environment variable HA_HOST",
                "Verify network configuration"
            ]
        )

    if not isinstance(ha_port, int) or ha_port <= 0 or ha_port > 65535:
        raise DeploymentError(
            "Invalid port parameter",
            error_type="INVALID_PARAMETER",
            context={"parameter": "ha_port", "value": ha_port, "valid_range": "1-65535"},
            troubleshooting_steps=[
                "Use a valid port number (1-65535)",
                "Check environment variable HA_PORT",
                "Verify SSH service configuration"
            ]
        )

    if not ha_user or not isinstance(ha_user, str) or ha_user.strip() == "":
        raise DeploymentError(
            "Invalid or empty user parameter",
            error_type="INVALID_PARAMETER",
            context={"parameter": "ha_user", "value": ha_user, "type": type(ha_user).__name__},
            troubleshooting_steps=[
                "Provide a valid SSH username",
                "Check environment variable HA_USER",
                "Verify SSH user permissions"
            ]
        )

    # Test SSH connectivity with enhanced error handling
    if verbose:
        console.print("  🔗 Testing SSH connectivity...")
    timer = timer or DeployTimer(console, enabled=False)
    try:
        with timer.phase("prerequisites.ssh"):
            result = run_cmd([
                "ssh", *ssh_transport_args(ha_port), f"{ha_user}@{ha_host}",
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",  # For automated deployments
                "echo 'SSH connection successful'"
            ], verbose=False, capture_output=True)
        if verbose:
            console.print("  ✓ SSH connection established")
    except subprocess.CalledProcessError as e:
        stderr = getattr(e, "stderr", "") or ""
        error_type = classify_ssh_failure(stderr)
        error_details = {
            "host": ha_host,
            "port": ha_port,
            "user": ha_user,
            "exit_code": e.returncode,
            "stderr": stderr,
            "command": ssh_command(ha_host, ha_port, ha_user)
        }

        raise DeploymentError(
            f"Cannot establish SSH connection to {ha_host}:{ha_port}",
            error_type=error_type,
            context=error_details,
            troubleshooting_steps=ssh_failure_troubleshooting(
                error_type, ha_host, ha_port, ha_user
            )
        )

    # Check Home Assistant core status
    with timer.phase("prerequisites.core_info"):
        core_status = check_ha_core_status(ha_host, ha_port, ha_user)
    if core_status["status"] != "ok":
        raise DeploymentError(
            "Home Assistant core is not responding properly",
            error_type="HA_CORE_NOT_RUNNING",
            context=core_status,
            troubleshooting_steps=[
                "Check Home Assistant status: ha core info",
                "Start Home Assistant: ha core start",
                "Check system logs: ha supervisor logs"
            ]
        )

    if verbose:
        console.print(f"  ✓ Home Assistant core is running (v{core_status['version']})")

    # Check disk space
    try:
        with timer.phase("prerequisites.disk"):
            result = run_cmd([
                "ssh", *ssh_transport_args(ha_port), f"{ha_user}@{ha_host}",
                "df -h / | tail -1 | awk '{print $4}'"
            ], verbose=False, capture_output=True)

        free_space = result.stdout.strip()
        if verbose:
            console.print(f"  ✓ Disk space available: {free_space}")
    except subprocess.CalledProcessError:
        if verbose:
            console.print("  ⚠️  Could not check disk space")

    if verbose:
        console.print("✅ [green]Prerequisites validation passed[/green]\n")
    else:
        console.print("✅ Prerequisites validation passed")


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
    if not data:
        return "{}"
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False).strip()


def _validated_backup_config(raw: Dict[str, Any], addon_key: str) -> Dict[str, Any]:
    startup = raw.get("startup", "services")
    if startup not in {"initialize", "system", "services", "application", "once"}:
        raise click.ClickException(f"Invalid startup mode for add-on '{addon_key}': {startup}")

    backup = raw.get("backup")
    if backup is not None and backup not in {"hot", "cold"}:
        raise click.ClickException(f"Invalid backup mode for add-on '{addon_key}': {backup}")

    backup_pre = raw.get("backup_pre")
    backup_post = raw.get("backup_post")
    for field, value in (("backup_pre", backup_pre), ("backup_post", backup_post)):
        if value is not None and not isinstance(value, str):
            raise click.ClickException(f"Invalid {field} for add-on '{addon_key}'; expected a string.")
    if backup == "cold" and (backup_pre or backup_post):
        raise click.ClickException(
            f"Add-on '{addon_key}' cannot combine backup: cold with backup_pre or backup_post."
        )

    backup_exclude = raw.get("backup_exclude", [])
    if not isinstance(backup_exclude, list) or not all(
        isinstance(item, str) and item for item in backup_exclude
    ):
        raise click.ClickException(
            f"Invalid backup_exclude for add-on '{addon_key}'; expected a list of paths."
        )
    return {
        "startup": startup,
        "backup": backup,
        "backup_pre": backup_pre,
        "backup_post": backup_post,
        "backup_exclude": backup_exclude,
    }


def _validated_git_clone_config(
    raw: Dict[str, Any], addon_key: str
) -> Dict[str, str] | None:
    config = raw.get("git_clone")
    if config is None:
        return None
    if not isinstance(config, dict):
        raise click.ClickException(
            f"Invalid git_clone for add-on '{addon_key}'; expected a mapping."
        )

    repo = config.get("repo")
    target = config.get("target")
    ref = config.get("ref")
    if not isinstance(repo, str) or not repo.startswith("https://"):
        raise click.ClickException(
            f"Invalid git_clone.repo for add-on '{addon_key}'; expected an HTTPS URL."
        )
    target_path = PurePosixPath(target) if isinstance(target, str) else None
    if (
        target_path is None
        or not target_path.is_absolute()
        or target_path == PurePosixPath("/")
        or ".." in target_path.parts
    ):
        raise click.ClickException(
            f"Invalid git_clone.target for add-on '{addon_key}'; expected a safe absolute path."
        )
    if not isinstance(ref, str) or re.fullmatch(r"[0-9a-fA-F]{40}", ref) is None:
        raise click.ClickException(
            f"Invalid git_clone.ref for add-on '{addon_key}'; expected a full 40-character commit SHA."
        )

    return {"repo": repo, "target": str(target_path), "ref": ref.lower()}


def read_runtime_versions() -> Dict[str, str]:
    """Read runtime versions from .nvmrc and .python-version files."""
    versions: Dict[str, str] = {}

    nvmrc_path = REPO_ROOT / ".nvmrc"
    if nvmrc_path.exists():
        node_version = nvmrc_path.read_text().strip()
        versions["node"] = node_version.lstrip("v")
        versions["node_major"] = node_version.lstrip("v").split(".")[0]
    else:
        versions["node"] = "24.18.0"
        versions["node_major"] = "24"

    python_version_path = REPO_ROOT / ".python-version"
    if python_version_path.exists():
        python_version = python_version_path.read_text().strip()
        versions["python"] = python_version
        versions["python_minor"] = ".".join(python_version.split(".")[:2])
    else:
        versions["python"] = "3.14.6"
        versions["python_minor"] = "3.14"

    return versions


def build_context(addon_key: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    if addon_key not in manifest:
        raise click.ClickException(f"Addon '{addon_key}' not found in manifest")

    raw = manifest[addon_key]
    source_dir = REPO_ROOT / raw["source_dir"]
    backup_config = _validated_backup_config(raw, addon_key)
    git_clone_config = _validated_git_clone_config(raw, addon_key)

    runtime_versions = read_runtime_versions()

    python_dependencies: list[str] = []
    python_build_dependencies: list[str] = []
    if raw.get("python", False):
        version_from = source_dir / "pyproject.toml"
        version = read_pyproject_version(version_from) if version_from.exists() else "0.0.0"
        if version_from.exists():
            try:
                import tomllib

                pyproject = tomllib.loads(version_from.read_text(encoding="utf-8"))
                python_dependencies = list(pyproject.get("project", {}).get("dependencies", []))
                python_build_dependencies = list(
                    pyproject.get("build-system", {}).get("requires", [])
                )
            except Exception as error:
                raise click.ClickException(f"Unable to read Python dependencies from {version_from}: {error}")
    else:
        version_from = source_dir / "package.json"
        version = read_package_version(version_from) if version_from.exists() else "0.0.0"

    ports = raw.get("ports") or {}
    port = int(next(iter(ports.keys()))) if ports else None
    deploy_health_path = raw.get("deploy_health_path")
    if deploy_health_path is not None:
        if not isinstance(deploy_health_path, str) or not deploy_health_path.startswith("/"):
            raise click.ClickException(
                f"Invalid deploy_health_path for '{addon_key}'; expected an absolute HTTP path."
            )
        if port is None:
            raise click.ClickException(
                f"Add-on '{addon_key}' declares deploy_health_path without a port."
            )

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
            "deploy_health_path": deploy_health_path,
            "run_env": raw.get("run_env", []),
            "git_clone": git_clone_config,
            "tests": raw.get("tests", []),
            "map": raw.get("map", []),
            "usb": raw.get("usb", False),
            "audio": raw.get("audio", False),
            "gpio": raw.get("gpio", False),
            "custom_dockerfile": raw.get("custom_dockerfile", False),
            **backup_config,
            "node_version": str(raw.get("node_version", runtime_versions["node"])).lstrip("v"),
            "node_major": str(raw.get("node_version", runtime_versions["node_major"]))
            .lstrip("v")
            .split(".")[0],
            "python_version": runtime_versions["python"],
            "python_minor": runtime_versions["python_minor"],
            "python_dependencies": python_dependencies,
            "python_build_dependencies": python_build_dependencies,
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
        "backup_exclude_yaml": default_yaml(backup_config["backup_exclude"]),
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


def export_python_requirements(addon: Dict[str, Any], app_root: Path) -> None:
    """Export frozen uv application and build graphs as hash-locked requirements."""
    source_dir: Path = addon["source_dir"]
    lockfile = source_dir / "uv.lock"
    if not lockfile.exists():
        raise click.ClickException(
            f"Python add-on '{addon['key']}' must include uv.lock for reproducible builds."
        )

    exports = (
        (app_root / "requirements.lock", ["--no-dev"]),
        (app_root / "build-requirements.lock", ["--only-group", "build"]),
    )
    for output, selection in exports:
        command = [
            "uv",
            "export",
            "--frozen",
            "--offline",
            "--no-cache",
            *selection,
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--quiet",
            "--output-file",
            str(output),
        ]
        try:
            subprocess.run(
                command,
                cwd=source_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise click.ClickException(
                "uv is required to export locked Python dependencies; run 'just setup'."
            ) from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or error.stdout.strip() or str(error)
            raise click.ClickException(
                f"Unable to export locked dependencies for '{addon['key']}': {detail}"
            ) from error

        exported = output.read_text(encoding="utf-8") if output.exists() else ""
        if "--hash=sha256:" not in exported:
            raise click.ClickException(
                f"Locked dependency export for '{addon['key']}' did not contain package hashes."
            )


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


def build_addon(
    addon_key: str,
    verbose: bool = False,
    timer: DeployTimer | None = None,
) -> Path:
    timer = timer or DeployTimer(console, enabled=False)
    with timer.phase("addon.local.context", addon=addon_key):
        manifest = load_manifest()
        context = build_context(addon_key, manifest)
    addon = context["addon"]
    addon_root = ADDON_BUILD_ROOT / addon["slug"]
    app_root = addon_root / "app"
    translations_root = addon_root / "translations"

    with timer.phase("addon.local.stage", addon=addon_key):
        if addon_root.exists():
            shutil.rmtree(addon_root)
        app_root.mkdir(parents=True, exist_ok=True)
        translations_root.mkdir(parents=True, exist_ok=True)
        copy_sources(addon, app_root)
        if addon.get("python", False):
            export_python_requirements(addon, app_root)

    with timer.phase("addon.local.render", addon=addon_key):
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

    with timer.phase("addon.local.archive", addon=addon_key):
        archive = make_tarball(addon_root, addon["slug"])
    if verbose:
        console.print(f"[green]Built[/green] {addon_key} -> {addon_root}")
        console.print(f"[green]Tarball[/green] {archive}")
    return archive


def run_cmd(
    cmd: list[str],
    dry_run: bool = False,
    cwd: Optional[Path] = None,
    verbose: bool = True,
    capture_output: bool = False,
    report_failure: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command with improved error handling and output control."""
    display_cmd = cmd
    if cmd and cmd[0] == "ssh" and cmd[-1].startswith("#!/bin/bash\n"):
        display_cmd = [*cmd[:-1], "<remote-script>"]

    # Only show commands in verbose mode, and make dry-run output much more concise
    if verbose and not dry_run:
        console.print(f"[cyan]$ {' '.join(display_cmd)}[/cyan]" + (f" (cwd={cwd})" if cwd else ""))

    if dry_run:
        # For dry run, only show high-level operations, not individual commands
        if verbose:
            console.print(f"[dim]Would run: {' '.join(display_cmd)}[/dim]")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    try:
        # In non-verbose mode, suppress output unless explicitly capturing it
        if not verbose and not capture_output:
            result = subprocess.run(
                cmd,
                check=True,
                cwd=str(cwd) if cwd else None,
                capture_output=True,  # Suppress output in non-verbose mode
                text=True
            )
        else:
            result = subprocess.run(
                cmd,
                check=True,
                cwd=str(cwd) if cwd else None,
                capture_output=capture_output,
                text=True if capture_output else None
            )
        return result
    except subprocess.CalledProcessError as e:
        if report_failure:
            console.print(f"[red]Command failed with exit code {e.returncode}[/red]")
            if e.stdout:
                console.print(f"[red]stdout:[/red] {e.stdout}")
            if e.stderr:
                console.print(f"[red]stderr:[/red] {e.stderr}")
        raise


def render_remote_deploy_script(
    slug: str,
    remote_tar: str,
    remote_addon_dir: str,
    remote_addons_dir: str,
    verbose: bool,
    health_port: int | None = None,
    health_path: str | None = None,
) -> str:
    verbose_flag = "true" if verbose else "false"
    health_port_value = shlex.quote(str(health_port)) if health_port is not None else "''"
    health_path_value = shlex.quote(health_path or "")
    return f"""#!/bin/bash
set -euo pipefail

ADDON_SLUG="{slug}"
ADDON_ID="local_{slug}"
REMOTE_TAR="{remote_tar}"
REMOTE_ADDON_DIR="{remote_addon_dir}"
VERBOSE="{verbose_flag}"
HEALTH_PORT={health_port_value}
HEALTH_PATH={health_path_value}
READINESS_ATTEMPTS=60
LAST_HEALTH_TARGET="not-resolved"

monotonic_ms() {{ awk '{{printf "%.0f", $1 * 1000}}' /proc/uptime; }}
REMOTE_TOTAL_START_MS="$(monotonic_ms)"
REMOTE_TOTAL_STATUS="error"
RELOAD_LOCK_HELD="false"

log_info() {{
    if [ "$VERBOSE" = "true" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
    fi
}}

log_error() {{ echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2; }}

run_quiet() {{
    if [ "$VERBOSE" = "true" ]; then "$@"; else "$@" >/dev/null 2>&1; fi
}}

emit_metric() {{
    printf '__TALOS_METRIC__\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4"
}}

run_metric() {{
    local phase="$1" started_ms finished_ms exit_code
    shift
    started_ms="$(monotonic_ms)"
    set +e
    "$@"
    exit_code=$?
    set -e
    finished_ms="$(monotonic_ms)"
    if [ "$exit_code" -eq 0 ]; then
        emit_metric "$phase" "$started_ms" "$finished_ms" "ok"
    else
        emit_metric "$phase" "$started_ms" "$finished_ms" "error"
    fi
    return "$exit_code"
}}

emit_total_metric() {{
    if [ "$RELOAD_LOCK_HELD" = "true" ]; then
        rmdir /tmp/talos-addon-reload.lock 2>/dev/null || true
    fi
    emit_metric "remote.total" "$REMOTE_TOTAL_START_MS" "$(monotonic_ms)" "$REMOTE_TOTAL_STATUS"
}}
trap emit_total_metric EXIT

extract_addon() {{
    rm -rf "$REMOTE_ADDON_DIR"
    mkdir -p "{remote_addons_dir}"
    tar -xzf "$REMOTE_TAR" -C "{remote_addons_dir}"
    rm -f "$REMOTE_TAR"
}}

read_addon_info() {{ ha --raw-json apps info "$ADDON_ID"; }}

read_addon_ip() {{
    read_addon_info | jq -er '.data.ip_address | strings | select(length > 0)'
}}

reload_addons() {{
    local attempt exit_code
    for attempt in $(seq 1 100); do
        if mkdir /tmp/talos-addon-reload.lock 2>/dev/null; then
            RELOAD_LOCK_HELD="true"
            run_quiet ha apps reload
            exit_code=$?
            rmdir /tmp/talos-addon-reload.lock 2>/dev/null || true
            RELOAD_LOCK_HELD="false"
            return "$exit_code"
        fi
        sleep 0.1
    done
    return 1
}}

wait_for_started() {{
    local attempt
    for attempt in $(seq 1 20); do
        if read_addon_info | jq -e '.data.state == "started"' >/dev/null; then return 0; fi
        if [ "$attempt" = "20" ]; then return 1; fi
        sleep 1
    done
}}

probe_service() {{
    local addon_ip curl_host
    if [ -z "$HEALTH_PORT" ]; then return 0; fi
    if ! addon_ip="$(read_addon_ip)"; then
        LAST_HEALTH_TARGET="Supervisor IP unavailable"
        return 1
    fi
    LAST_HEALTH_TARGET="${{addon_ip}}:${{HEALTH_PORT}}${{HEALTH_PATH}}"
    if [ -n "$HEALTH_PATH" ]; then
        curl_host="$addon_ip"
        case "$curl_host" in *:*) curl_host="[${{curl_host}}]" ;; esac
        curl -fsS -o /dev/null --connect-timeout 1 --max-time 2 \
            "http://${{curl_host}}:${{HEALTH_PORT}}${{HEALTH_PATH}}" 2>/dev/null
    else
        nc -z -w 2 "$addon_ip" "$HEALTH_PORT" >/dev/null 2>&1
    fi
}}

wait_for_readiness() {{
    local attempt
    for attempt in $(seq 1 "$READINESS_ATTEMPTS"); do
        if probe_service; then return 0; fi
        if [ "$attempt" = "$READINESS_ATTEMPTS" ]; then
            log_error "Readiness probe exhausted retries at $LAST_HEALTH_TARGET"
            return 1
        fi
        sleep 1
    done
}}

log_info "Stopping add-on $ADDON_ID if running..."
INSPECT_STARTED_MS="$(monotonic_ms)"
if ADDON_INFO="$(read_addon_info 2>/dev/null)"; then
    ADDON_STATE="$(printf '%s' "$ADDON_INFO" | jq -r '.data.state // "unknown"')"
    emit_metric "remote.inspect" "$INSPECT_STARTED_MS" "$(monotonic_ms)" "ok"
    if [ "$ADDON_STATE" = "started" ]; then
        if ! run_metric "remote.stop" run_quiet ha apps stop "$ADDON_ID"; then
            log_error "Failed to stop add-on $ADDON_ID"
            exit 1
        fi
        log_info "Add-on $ADDON_ID stopped successfully"
    else
        NOW_MS="$(monotonic_ms)"
        emit_metric "remote.stop" "$NOW_MS" "$NOW_MS" "skipped"
        log_info "Add-on $ADDON_ID is not running (state: $ADDON_STATE)"
    fi
else
    emit_metric "remote.inspect" "$INSPECT_STARTED_MS" "$(monotonic_ms)" "not_found"
    NOW_MS="$(monotonic_ms)"
    emit_metric "remote.stop" "$NOW_MS" "$NOW_MS" "skipped"
    log_info "Add-on $ADDON_ID not currently installed"
fi

log_info "Extracting add-on files..."
if ! run_metric "remote.extract" extract_addon; then
    log_error "Failed to extract add-on tarball"
    exit 1
fi

log_info "Reloading add-on list..."
if ! run_metric "remote.reload" reload_addons; then
    log_error "Failed to reload add-on list"
    exit 1
fi

log_info "Installing/rebuilding add-on $ADDON_ID..."
if read_addon_info >/dev/null 2>&1; then
    if ! run_metric "remote.rebuild" run_quiet ha apps rebuild "$ADDON_ID"; then
        log_info "Rebuild failed, attempting fresh install..."
        if ! run_metric "remote.install_fallback" run_quiet ha apps install "$ADDON_ID"; then
            log_error "Failed to install add-on $ADDON_ID"
            exit 1
        fi
    fi
else
    if ! run_metric "remote.install" run_quiet ha apps install "$ADDON_ID"; then
        log_error "Failed to install add-on $ADDON_ID"
        exit 1
    fi
fi

log_info "Configuring add-on options..."
SUPERVISOR_TOKEN="${{SUPERVISOR_TOKEN:-}}"
if [ -n "$SUPERVISOR_TOKEN" ]; then
    OPTIONS_JSON='{{"watchdog": true}}'
    if ! run_metric "remote.configure" curl -sSf \\
        -o /dev/null \\
        -H "Authorization: Bearer $SUPERVISOR_TOKEN" \\
        -H "Content-Type: application/json" \\
        -X POST -d "$OPTIONS_JSON" \\
        http://supervisor/addons/"$ADDON_ID"/options; then
        log_info "Warning: could not update add-on options for $ADDON_ID; continuing"
    fi
else
    NOW_MS="$(monotonic_ms)"
    emit_metric "remote.configure" "$NOW_MS" "$NOW_MS" "skipped"
fi

log_info "Starting add-on $ADDON_ID..."
if ! run_metric "remote.start" run_quiet ha apps start "$ADDON_ID"; then
    log_error "Failed to start add-on $ADDON_ID"
    exit 1
fi

if ! run_metric "remote.state" wait_for_started; then
    log_error "Add-on $ADDON_ID never reached Supervisor state 'started'"
    exit 1
fi

if ! run_metric "remote.readiness" wait_for_readiness; then
    log_error "Add-on $ADDON_ID did not pass its service readiness probe"
    exit 1
fi

log_info "Deployment of $ADDON_ID completed successfully"
REMOTE_TOTAL_STATUS="ok"
"""


def _record_remote_metrics(output: str, addon_key: str, timer: DeployTimer) -> str:
    """Record structured remote metrics and return output without marker lines."""
    visible_lines: list[str] = []
    metrics: list[tuple[str, int, int, str]] = []
    for line in output.splitlines():
        if not line.startswith("__TALOS_METRIC__\t"):
            visible_lines.append(line)
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            visible_lines.append(line)
            continue
        _, phase, started_raw, finished_raw, status = parts
        try:
            started_ms = int(started_raw)
            finished_ms = int(finished_raw)
        except ValueError:
            visible_lines.append(line)
            continue
        metrics.append((phase, started_ms, finished_ms, status))

    remote_finish_ms = max((metric[2] for metric in metrics), default=0)
    local_finish_offset = time.perf_counter() - timer.started_at
    for phase, started_ms, finished_ms, status in metrics:
        timer.record(
            f"addon.{phase}",
            max(0, finished_ms - started_ms) / 1000,
            status=status,
            addon=addon_key,
            source="remote",
            remote_started_ms=started_ms,
            remote_finished_ms=finished_ms,
            started_offset_seconds=round(
                local_finish_offset - (remote_finish_ms - started_ms) / 1000, 3
            ),
            finished_offset_seconds=round(
                local_finish_offset - (remote_finish_ms - finished_ms) / 1000, 3
            ),
        )
    return "\n".join(visible_lines)


def deploy_addon(addon_key: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool,
                 verbose: bool = False, validate_prereqs: bool = True, show_success: bool = True,
                 timer: DeployTimer | None = None) -> None:
    """Deploy an add-on with enhanced error handling and validation."""
    timer = timer or DeployTimer(console, enabled=False)
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
        if validate_prereqs:
            with timer.phase("addon.prerequisites", addon=addon_key):
                validate_deployment_prerequisites(
                    ha_host, ha_port, ha_user, verbose=verbose, timer=timer
                )

        if verbose:
            console.print(f"🔨 [bold]Building {addon_key}...[/bold]")
        with timer.phase("addon.build", addon=addon_key):
            archive = build_addon(addon_key, verbose=verbose, timer=timer)

        remote_tar = f"{paths['remote_home']}/{slug}.tar.gz"
        remote_addon_dir = f"{paths['remote_addons']}/{slug}"

        if verbose:
            console.print(f"📦 [bold]Deploying {addon_key} to {ha_host}...[/bold]")

        # Upload addon tarball
        scp_cmd = [
            "scp", *scp_transport_args(ha_port), str(archive),
            f"{ha_user}@{ha_host}:{remote_tar}",
        ]
        try:
            with timer.phase("addon.upload", addon=addon_key):
                run_cmd(scp_cmd, dry_run=dry_run, verbose=verbose)
            if verbose:
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
                    f"Check SSH connectivity: {ssh_command(ha_host, ha_port, ha_user)}",
                    "Verify disk space on target system",
                    "Check file permissions"
                ]
            )

        remote_script = render_remote_deploy_script(
            slug=slug,
            remote_tar=remote_tar,
            remote_addon_dir=remote_addon_dir,
            remote_addons_dir=paths["remote_addons"],
            verbose=verbose,
            health_port=port,
            health_path=addon.get("deploy_health_path"),
        )

        # Execute remote deployment script
        ssh_cmd = [
            "ssh", *ssh_transport_args(ha_port), f"{ha_user}@{ha_host}", remote_script,
        ]
        try:
            with timer.phase("addon.remote_deploy", addon=addon_key):
                remote_result = run_cmd(
                    ssh_cmd,
                    dry_run=dry_run,
                    verbose=verbose,
                    capture_output=True,
                    report_failure=False,
                )
            visible_output = _record_remote_metrics(
                remote_result.stdout or "", addon_key, timer
            )
            if verbose and visible_output:
                console.print(visible_output, markup=False)
            if verbose and remote_result.stderr:
                console.print(remote_result.stderr.rstrip(), style="dim", markup=False)
            if not dry_run and verbose:
                console.print(f"  ✅ [green]{addon_key} deployed successfully[/green]")
        except subprocess.CalledProcessError as e:
            _record_remote_metrics(e.stdout or "", addon_key, timer)
            # Capture logs for troubleshooting
            with timer.phase("addon.fetch_logs", addon=addon_key):
                addon_logs = get_addon_logs(ha_host, ha_port, ha_user, f"local_{slug}", lines=20)

            raise DeploymentError(
                f"Failed to deploy {addon_key} on remote system",
                error_type="REMOTE_DEPLOYMENT_FAILED",
                context={
                    "addon": addon_key,
                    "host": ha_host,
                    "exit_code": e.returncode,
                    "recent_logs": addon_logs
                },
                troubleshooting_steps=[
                    f"Check add-on logs: ha addons logs local_{slug}",
                    f"Check add-on info: ha addons info local_{slug}",
                    "Check supervisor logs: ha supervisor logs",
                    f"Rebuild add-on: just ha-addon {addon_key}",
                    "Check Home Assistant system health"
                ]
            )

        # Always show deployment success, but with different detail levels
        if show_success:
            if verbose:
                console.print(f"✅ [green]Successfully deployed {addon_key} to {ha_host}[/green]")
            else:
                console.print(f"✅ [green]{addon_key} deployed successfully[/green]")

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
    build_addon(addon, verbose=True)


def run_test(addon: str) -> None:
    run_tests(addon)
