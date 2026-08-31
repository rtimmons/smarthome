from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import click

from .addon_manifest import dependency_order, discover_addons, installed_addon_id
from .paths import REPO_ROOT

SCHEMA_VERSION = 1
MIN_REMOTE_FREE_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "backups" / "addon-state"
DEFAULT_HA_SSH_IDENTITY = REPO_ROOT / ".ssh" / "id_ed25519_codex_smarthome"
NODE_SONOS_ADDON_ID = "local_node_sonos_http_api"


class Transport(Protocol):
    def ssh(self, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]: ...

    def scp_from(self, remote_path: str, local_path: Path) -> None: ...


def _common_repository_identity() -> Path | None:
    """Find the primary worktree's dedicated key when running from a linked worktree."""
    try:
        common_git_dir = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    if not common_git_dir:
        return None
    common_git_path = Path(common_git_dir)
    if not common_git_path.is_absolute():
        common_git_path = (REPO_ROOT / common_git_path).resolve()
    return common_git_path.parent / ".ssh" / "id_ed25519_codex_smarthome"


def ha_ssh_identity() -> Path:
    """Resolve the explicit override, current worktree key, or primary worktree key."""
    override = os.environ.get("HASS_SSH_IDENTITY")
    if override:
        return Path(override).expanduser()
    if DEFAULT_HA_SSH_IDENTITY.is_file():
        return DEFAULT_HA_SSH_IDENTITY
    common_identity = _common_repository_identity()
    if common_identity is not None and common_identity.is_file():
        return common_identity
    return DEFAULT_HA_SSH_IDENTITY


def classify_transport_failure(stderr: str | bytes | None) -> str:
    """Keep pre-auth hostname failures distinct from dedicated-key failures."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    message = (stderr or "").lower()
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
        return "hostname"
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
        return "authentication"
    return "connection"


def _transport_exception(operation: str, error: subprocess.CalledProcessError) -> click.ClickException:
    failure = classify_transport_failure(error.stderr)
    if failure == "authentication":
        return click.ClickException(
            f"{operation} could not authenticate with the repository Home Assistant SSH key. "
            "Stop and ask Ryan to rerun the human-only 'just ha-ssh-key-copy'. "
            "Do not retry with alternate credentials, hosts, or IP addresses."
        )
    if failure == "hostname":
        return click.ClickException(
            f"{operation} could not resolve the Home Assistant hostname (mDNS/network failure). "
            "Retry the same hostname once outside the Codex sandbox; do not substitute an IP address. "
            "If it still does not resolve, stop and report the mDNS/network failure."
        )
    return click.ClickException(f"{operation} failed on Home Assistant.")


def _raise_if_classified_transport_failure(
    result: subprocess.CompletedProcess[str], operation: str
) -> None:
    if result.returncode == 0:
        return
    failure = classify_transport_failure(result.stderr)
    if failure in {"authentication", "hostname"}:
        raise _transport_exception(
            operation,
            subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            ),
        )


@dataclass
class SshTransport:
    host: str
    port: int
    user: str
    identity_file: Path | None = None

    def _identity_args(self) -> list[str]:
        identity_file = self.identity_file or ha_ssh_identity()
        if not identity_file.is_file():
            raise click.ClickException(
                f"Repository Home Assistant SSH key is missing: {identity_file}. "
                "Run 'just ha-ssh-key-create', then ask Ryan to run the human-only "
                "'just ha-ssh-key-copy'."
            )
        return [
            "-i",
            str(identity_file),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
        ]

    def ssh(self, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "ssh",
                "-p",
                str(self.port),
                *self._identity_args(),
                f"{self.user}@{self.host}",
                command,
            ],
            check=check,
            capture_output=True,
            text=True,
        )

    def scp_from(self, remote_path: str, local_path: Path) -> None:
        subprocess.run(
            [
                "scp",
                "-P",
                str(self.port),
                *self._identity_args(),
                f"{self.user}@{self.host}:{remote_path}",
                str(local_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def _unwrap_ha_json(raw: str, operation: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise click.ClickException(f"{operation} returned malformed JSON.") from error
    if not isinstance(payload, dict) or payload.get("result") != "ok":
        raise click.ClickException(f"{operation} failed.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise click.ClickException(f"{operation} returned no data.")
    return data


def _ha_json(transport: Transport, arguments: Sequence[str], operation: str) -> dict[str, Any]:
    command = shlex.join(["ha", *arguments, "--no-progress", "--raw-json"])
    try:
        result = transport.ssh(command)
    except subprocess.CalledProcessError as error:
        raise _transport_exception(operation, error) from error
    return _unwrap_ha_json(result.stdout, operation)


def _git_metadata() -> dict[str, Any]:
    def run(*arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    try:
        revision = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain"))
    except subprocess.CalledProcessError as error:
        raise click.ClickException("Unable to record the repository revision.") from error
    return {"revision": revision, "dirty": dirty}


def _preflight_remote_storage(transport: Transport) -> int:
    command = (
        "test -d /backup && test -w /backup && "
        "df -Pk /backup | awk 'NR==2 {print $4 * 1024}'"
    )
    try:
        result = transport.ssh(command)
        free_bytes = int(float(result.stdout.strip()))
    except subprocess.CalledProcessError as error:
        raise _transport_exception("Inspecting remote backup storage", error) from error
    except ValueError as error:
        raise click.ClickException("Remote /backup is unavailable or its free space cannot be read.") from error
    if free_bytes < MIN_REMOTE_FREE_BYTES:
        raise click.ClickException(
            f"Remote /backup has insufficient free space ({free_bytes} bytes free; "
            f"at least {MIN_REMOTE_FREE_BYTES} required)."
        )
    return free_bytes


def _health_command(repo_key: str, hostname: str) -> str:
    host = shlex.quote(hostname)
    if repo_key == "mongodb":
        return f"nc -z -w 5 {host} 27017"
    if repo_key == "printer":
        return (
            f"payload=\"$(curl -fsS --max-time 5 http://{host}:8099/health/mongo)\" && "
            "printf '%s' \"$payload\" | jq -e '.configured == true and .ok == true' >/dev/null"
        )
    if repo_key == "tinyurl-service":
        return f"curl -fsS --max-time 5 http://{host}:4100/api/urls >/dev/null"
    endpoints = {
        "grid-dashboard": (3000, "/"),
        "sonos-api": (5006, "/sonos/zones"),
        "snapshot-service": (4010, "/healthz"),
    }
    if repo_key == "node-sonos-http-api":
        return f"curl -sS --max-time 5 -o /dev/null http://{host}:5005/"
    port, path = endpoints[repo_key]
    return f"curl -fsS --max-time 5 http://{host}:{port}{path} >/dev/null"


def _check_health_once(
    transport: Transport,
    app_records: Sequence[dict[str, Any]],
) -> list[str]:
    failures: list[str] = []
    for record in app_records:
        if record["original_state"] != "started":
            continue
        result = transport.ssh(
            _health_command(record["repo_key"], record["hostname"]), check=False
        )
        _raise_if_classified_transport_failure(result, "Running Home Assistant add-on health checks")
        if result.returncode != 0:
            failures.append(record["repo_key"])
    return failures


def wait_for_health(
    transport: Transport,
    app_records: Sequence[dict[str, Any]],
    *,
    attempts: int = 1,
    interval_seconds: float = 5.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    failures: list[str] = []
    for attempt in range(attempts):
        failures = _check_health_once(transport, app_records)
        if not failures:
            return
        if attempt + 1 < attempts:
            sleeper(interval_seconds)
    raise click.ClickException(
        "Application health checks failed for: " + ", ".join(sorted(failures))
    )


def _collect_app_records(
    transport: Transport,
    manifests: dict[str, dict[str, Any]],
    ordered_keys: Sequence[str],
    installed: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for repo_key in ordered_keys:
        manifest = manifests[repo_key]
        app_id = installed_addon_id(manifest)
        if app_id not in installed:
            missing.append(app_id)
            continue
        info = _ha_json(transport, ["apps", "info", app_id], f"Inspecting {repo_key}")
        hostname = info.get("hostname")
        if not isinstance(hostname, str) or not hostname:
            raise click.ClickException(f"Installed add-on '{app_id}' has no hostname.")
        records.append(
            {
                "repo_key": repo_key,
                "manifest_slug": manifest["slug"],
                "installed_id": app_id,
                "version": str(info.get("version") or installed[app_id].get("version") or "unknown"),
                "original_state": str(info.get("state") or installed[app_id].get("state") or "unknown"),
                "hostname": hostname,
                "startup": info.get("startup"),
                "backup": info.get("backup"),
            }
        )
    if missing:
        raise click.ClickException("Required local add-ons are not installed: " + ", ".join(missing))
    return records


def _validate_mongodb_deployment(
    transport: Transport, app_records: Sequence[dict[str, Any]]
) -> None:
    mongo = next(record for record in app_records if record["repo_key"] == "mongodb")
    backup_is_cold = mongo["backup"] == "cold"
    if not backup_is_cold:
        manifest_path = f"/addons/{mongo['manifest_slug']}/config.yaml"
        deployed_manifest = transport.ssh(
            "grep -Eq '^backup:[[:space:]]+\"?cold\"?[[:space:]]*$' "
            + shlex.quote(manifest_path),
            check=False,
        )
        _raise_if_classified_transport_failure(
            deployed_manifest, "Inspecting deployed MongoDB backup metadata"
        )
        backup_is_cold = deployed_manifest.returncode == 0
    if mongo["startup"] != "system" or not backup_is_cold:
        raise click.ClickException(
            "Deployed MongoDB must use startup: system and backup: cold before backup."
        )
    required_running = {"mongodb", "printer", "tinyurl-service"}
    stopped = sorted(
        record["repo_key"]
        for record in app_records
        if record["repo_key"] in required_running and record["original_state"] != "started"
    )
    if stopped:
        raise click.ClickException(
            "Database health cannot be validated because required add-on(s) are not started: "
            + ", ".join(stopped)
        )


def validate_backup_metadata(
    metadata: dict[str, Any], expected_ids: Sequence[str], expected_name: str
) -> None:
    addons = metadata.get("addons", metadata.get("content", {}).get("addons", []))
    addon_ids = {
        item.get("slug") if isinstance(item, dict) else item
        for item in addons
    }
    folders = metadata.get("folders", metadata.get("content", {}).get("folders", []))
    homeassistant = metadata.get(
        "homeassistant", metadata.get("content", {}).get("homeassistant", False)
    )
    if addon_ids != set(expected_ids):
        raise click.ClickException("Supervisor backup metadata has unexpected add-on membership.")
    if set(folders or []) != {"share"}:
        raise click.ClickException("Supervisor backup metadata must contain only the share folder.")
    if homeassistant not in (False, None):
        raise click.ClickException("Supervisor backup unexpectedly contains Home Assistant Core.")
    if metadata.get("protected") is not False:
        raise click.ClickException("Supervisor backup is protected; an unencrypted backup was requested.")
    if metadata.get("compressed") is not True:
        raise click.ClickException("Supervisor backup is not compressed.")
    if metadata.get("name") != expected_name:
        raise click.ClickException("Supervisor backup name does not match the requested name.")


def _normalized_member_names(archive: tarfile.TarFile) -> set[str]:
    return {member.name.removeprefix("./") for member in archive.getmembers()}


def _nested_tar_members(stream: Any, *, depth: int = 0) -> dict[str, bool]:
    """List nested add-on paths and regular-file status without extracting contents."""
    members: dict[str, bool] = {}
    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            members[name] = member.isfile()
            if depth >= 2 or not member.isfile() or not name.endswith((".tar", ".tar.gz")):
                continue
            nested_stream = archive.extractfile(member)
            if nested_stream is None:
                continue
            nested_members = _nested_tar_members(nested_stream, depth=depth + 1)
            members.update(
                (f"{name}/{nested_name}", is_file)
                for nested_name, is_file in nested_members.items()
            )
    return members


def _validate_node_sonos_state(archive: tarfile.TarFile) -> None:
    member_name = f"{NODE_SONOS_ADDON_ID}.tar.gz"
    member = next(
        (item for item in archive.getmembers() if item.name.removeprefix("./") == member_name),
        None,
    )
    if member is None:
        raise click.ClickException("Downloaded archive is missing the Node Sonos add-on state.")
    stream = archive.extractfile(member)
    if stream is None:
        raise click.ClickException("Node Sonos add-on state cannot be read from the archive.")
    members = _nested_tar_members(stream)
    has_presets_json = members.get("data.tar.gz/presets.json") is True
    has_settings_json = members.get("data.tar.gz/settings.json") is True
    has_preset_content = any(
        name.startswith("data.tar.gz/presets/") and is_file
        for name, is_file in members.items()
    )
    missing: list[str] = []
    if not has_presets_json:
        missing.append("presets.json")
    if not has_preset_content:
        missing.append("presets/ contents")
    if not has_settings_json:
        missing.append("settings.json")
    if missing:
        raise click.ClickException(
            "Node Sonos add-on backup is missing required /data/node-sonos-http-api state: "
            + ", ".join(missing)
        )


def inspect_archive(
    archive_path: Path,
    *,
    expected_ids: Sequence[str],
    expected_slug: str,
    expected_name: str,
) -> dict[str, Any]:
    expected_members = {
        "backup.json",
        "supervisor.tar.gz",
        "share.tar.gz",
        *(f"{app_id}.tar.gz" for app_id in expected_ids),
    }
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            names = _normalized_member_names(archive)
            if names != expected_members:
                raise click.ClickException("Downloaded archive has unexpected tar members.")
            member = next(
                item for item in archive.getmembers() if item.name.removeprefix("./") == "backup.json"
            )
            if member.size > 1024 * 1024:
                raise click.ClickException("Archive backup.json is unexpectedly large.")
            stream = archive.extractfile(member)
            if stream is None:
                raise click.ClickException("Archive backup.json cannot be read.")
            metadata = json.loads(stream.read().decode("utf-8"))
            _validate_node_sonos_state(archive)
    except (tarfile.TarError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise click.ClickException("Downloaded backup archive is malformed or truncated.") from error
    if not isinstance(metadata, dict) or metadata.get("slug") != expected_slug:
        raise click.ClickException("Archive backup.json has an unexpected backup slug.")
    validate_backup_metadata(metadata, expected_ids, expected_name)
    return metadata


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_manifest_records(app_records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = ("repo_key", "manifest_slug", "installed_id", "version", "original_state")
    return [{key: record[key] for key in allowed} for record in app_records]


def _write_artifacts(
    staging: Path,
    archive_path: Path,
    manifest: dict[str, Any],
    sha256: str,
) -> None:
    manifest_path = staging / "manifest.json"
    sums_path = staging / "SHA256SUMS"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sums_path.write_text(f"{sha256}  {archive_path.name}\n", encoding="utf-8")
    for path in (archive_path, manifest_path, sums_path):
        path.chmod(0o600)


def create_addon_state_backup(
    *,
    ha_host: str,
    ha_port: int,
    ha_user: str,
    output_root: Path | None = None,
    transport: Transport | None = None,
    now: datetime | None = None,
    post_health_attempts: int = 12,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    manifests = discover_addons()
    ordered_paths = dependency_order(
        [REPO_ROOT / key for key in manifests], manifests=manifests
    )
    ordered_keys = [path.name for path in ordered_paths]
    expected_ids = [installed_addon_id(manifests[key]) for key in ordered_keys]
    transport = transport or SshTransport(ha_host, ha_port, ha_user)

    timestamp_dt = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = timestamp_dt.strftime("%Y%m%dT%H%M%SZ")
    created_at = timestamp_dt.isoformat().replace("+00:00", "Z")
    backup_name = f"Smarthome add-on state {timestamp}"
    filename = f"smarthome_addon_state_{timestamp}.tar"
    remote_path = f"/backup/{filename}"
    output_root = Path(output_root or DEFAULT_OUTPUT_ROOT)
    final_dir = output_root / timestamp
    if final_dir.exists():
        raise click.ClickException(f"Backup destination already exists: {final_dir}")

    click.echo(
        "Warning: this backup is intentionally unencrypted and contains sensitive add-on state."
    )
    click.echo("Preflighting Home Assistant and add-on health...")
    core = _ha_json(transport, ["core", "info"], "Inspecting Home Assistant Core")
    supervisor = _ha_json(transport, ["supervisor", "info"], "Inspecting Supervisor")
    if not core.get("version"):
        raise click.ClickException("Home Assistant Core did not report a running version.")
    if supervisor.get("healthy") is not True or supervisor.get("supported") is not True:
        raise click.ClickException("Home Assistant Supervisor is not healthy and supported.")
    installed_list = supervisor.get("addons")
    if not isinstance(installed_list, list):
        raise click.ClickException("Supervisor did not report the installed add-on set.")
    installed = {
        str(item.get("slug")): item
        for item in installed_list
        if isinstance(item, dict) and item.get("slug")
    }
    app_records = _collect_app_records(transport, manifests, ordered_keys, installed)
    _validate_mongodb_deployment(transport, app_records)
    _preflight_remote_storage(transport)
    remote_path_check = transport.ssh(f"test ! -e {shlex.quote(remote_path)}", check=False)
    _raise_if_classified_transport_failure(remote_path_check, "Checking the remote backup path")
    if remote_path_check.returncode != 0:
        raise click.ClickException(f"Remote backup path already exists: {remote_path}")
    wait_for_health(transport, app_records)

    arguments = [
        "backups",
        "new",
        "--name",
        backup_name,
        "--filename",
        filename,
    ]
    for app_id in expected_ids:
        arguments.extend(["--app", app_id])
    arguments.extend(["--folders", "share"])

    click.echo("Creating Supervisor partial backup (MongoDB will restart briefly)...")
    created: dict[str, Any] | None = None
    try:
        created = _ha_json(transport, arguments, "Creating Supervisor backup")
    finally:
        # A failed Supervisor command may still have stopped/restarted a cold-backed-up app.
        wait_for_health(
            transport,
            app_records,
            attempts=post_health_attempts,
            sleeper=sleeper,
        )

    backup_slug = created.get("slug") if created else None
    if not isinstance(backup_slug, str) or not backup_slug:
        raise click.ClickException("Supervisor did not return the created backup slug.")
    metadata = _ha_json(
        transport, ["backups", "info", backup_slug], "Inspecting Supervisor backup"
    )
    validate_backup_metadata(metadata, expected_ids, backup_name)

    try:
        remote_size_result = transport.ssh(
            f"chmod 600 {shlex.quote(remote_path)} && "
            f"stat -c '%s %a' {shlex.quote(remote_path)} && "
            f"sha256sum {shlex.quote(remote_path)} | awk '{{print $1}}'"
        )
        remote_lines = remote_size_result.stdout.splitlines()
        remote_stat = remote_lines[0].split()
        remote_size = int(remote_stat[0])
        if remote_stat[1] != "600":
            raise ValueError("invalid remote mode")
        remote_sha256 = remote_lines[1].strip()
        if len(remote_sha256) != 64:
            raise ValueError("invalid remote digest")
    except subprocess.CalledProcessError as error:
        raise _transport_exception("Securing the remote backup archive", error) from error
    except ValueError as error:
        raise click.ClickException("Unable to secure or size the remote backup archive.") from error
    metadata_size = metadata.get("size_bytes")
    if isinstance(metadata_size, int) and metadata_size != remote_size:
        raise click.ClickException("Remote archive size does not match Supervisor metadata.")

    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(output_root).free < remote_size:
        raise click.ClickException("Insufficient local free space for the backup archive.")

    staging = Path(tempfile.mkdtemp(prefix=f".{timestamp}.", dir=output_root))
    staging.chmod(0o700)
    archive_path = staging / filename
    try:
        click.echo("Downloading and verifying backup archive...")
        try:
            transport.scp_from(remote_path, archive_path)
        except subprocess.CalledProcessError as error:
            failure = classify_transport_failure(error.stderr)
            if failure in {"authentication", "hostname"}:
                raise _transport_exception("Downloading the backup archive", error) from error
            raise click.ClickException("Backup archive download was interrupted or failed.") from error
        archive_path.chmod(0o600)
        if archive_path.stat().st_size != remote_size:
            raise click.ClickException("Downloaded archive size does not match the remote archive.")
        inspect_archive(
            archive_path,
            expected_ids=expected_ids,
            expected_slug=backup_slug,
            expected_name=backup_name,
        )
        digest = _sha256(archive_path)
        if digest != remote_sha256:
            raise click.ClickException("Downloaded archive checksum does not match the remote archive.")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "git": _git_metadata(),
            "home_assistant": {
                "core_version": core.get("version"),
                "supervisor_version": supervisor.get("version"),
            },
            "addons": _safe_manifest_records(app_records),
            "backup": {
                "slug": backup_slug,
                "name": backup_name,
                "filename": filename,
                "components": {
                    "addons": expected_ids,
                    "folders": ["share"],
                    "homeassistant": False,
                },
                "size_bytes": remote_size,
                "compressed": True,
                "protected": False,
                "sha256": digest,
                "remote_path": remote_path,
            },
        }
        _write_artifacts(staging, archive_path, manifest, digest)
        os.replace(staging, final_dir)
        final_dir.chmod(0o700)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    click.echo(f"Backup retained remotely at {remote_path}")
    return final_dir
