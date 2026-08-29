from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from talos import addon_backup
from talos.addon_manifest import dependency_order, discover_addons, installed_addon_id
from talos.cli import app


NOW = datetime(2026, 8, 5, 12, 34, 56, tzinfo=timezone.utc)
TIMESTAMP = "20260805T123456Z"
BACKUP_NAME = f"Smarthome add-on state {TIMESTAMP}"
BACKUP_SLUG = "abc12345"


def expected_ids() -> list[str]:
    manifests = discover_addons()
    paths = dependency_order(
        [addon_backup.REPO_ROOT / key for key in manifests], manifests=manifests
    )
    return [installed_addon_id(manifests[path.name]) for path in paths]


def backup_metadata() -> dict[str, object]:
    return {
        "slug": BACKUP_SLUG,
        "name": BACKUP_NAME,
        "protected": False,
        "compressed": True,
        "homeassistant": None,
        "folders": ["share"],
        "addons": [{"slug": app_id, "version": "1.0.0"} for app_id in expected_ids()],
    }


def make_node_sonos_archive(state: dict[str, bytes | None] | None = None) -> bytes:
    state = state or {
        "presets.json": b"{}\n",
        "presets/favorite.json": b"{}\n",
        "settings.json": b"{}\n",
    }
    data_stream = io.BytesIO()
    with tarfile.open(fileobj=data_stream, mode="w:gz") as data_archive:
        for name, content in state.items():
            info = tarfile.TarInfo(name)
            if content is None:
                info.type = tarfile.DIRTYPE
                data_archive.addfile(info)
            else:
                info.size = len(content)
                data_archive.addfile(info, io.BytesIO(content))

    addon_stream = io.BytesIO()
    data = data_stream.getvalue()
    with tarfile.open(fileobj=addon_stream, mode="w:gz") as addon_archive:
        info = tarfile.TarInfo("data.tar.gz")
        info.size = len(data)
        addon_archive.addfile(info, io.BytesIO(data))
    return addon_stream.getvalue()


def make_archive(
    path: Path,
    metadata: dict[str, object] | None = None,
    node_state: dict[str, bytes | None] | None = None,
) -> None:
    payload = json.dumps(metadata or backup_metadata()).encode()
    members = {
        "backup.json": payload,
        "supervisor.tar.gz": b"supervisor",
        "share.tar.gz": b"share",
        **{f"{app_id}.tar.gz": app_id.encode() for app_id in expected_ids()},
    }
    members[f"{addon_backup.NODE_SONOS_ADDON_ID}.tar.gz"] = make_node_sonos_archive(node_state)
    with tarfile.open(path, "w") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


class FakeTransport:
    def __init__(self, archive: Path):
        self.archive = archive
        self.fail_contains: str | None = None
        self.failure_stderr: str | None = None
        self.health_failure: str | None = None
        self.scp_failure = False
        self.remote_free = addon_backup.MIN_REMOTE_FREE_BYTES + 1
        self.remote_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.commands: list[str] = []

    @staticmethod
    def _result(command: str, stdout: str = "", returncode: int = 0):
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    def ssh(self, command: str, *, check: bool = True):
        self.commands.append(command)
        if self.fail_contains and self.fail_contains in command:
            if check:
                raise subprocess.CalledProcessError(1, command, stderr=self.failure_stderr)
            return self._result(command, returncode=1)
        if command.startswith("ha core info"):
            data = {"version": "2026.8.0"}
        elif command.startswith("ha supervisor info"):
            data = {
                "version": "2026.07.5",
                "healthy": True,
                "supported": True,
                "addons": [
                    {"slug": app_id, "version": "1.0.0", "state": "started"}
                    for app_id in expected_ids()
                ],
            }
        elif command.startswith("ha apps info"):
            app_id = command.split()[3]
            data = {
                "slug": app_id,
                "hostname": app_id.replace("_", "-"),
                "version": "1.0.0",
                "state": "started",
                "startup": "system" if app_id == "local_mongodb" else "services",
                "backup": "cold" if app_id == "local_mongodb" else None,
                "options": {"password": "never-serialize-me", "mongodb_url": "mongodb://secret"},
            }
        elif command.startswith("ha backups new"):
            data = {"slug": BACKUP_SLUG}
        elif command.startswith("ha backups info"):
            data = backup_metadata()
            data["size_bytes"] = self.archive.stat().st_size
        elif command.startswith("test -d /backup"):
            return self._result(command, f"{self.remote_free}\n")
        elif command.startswith("test ! -e"):
            return self._result(command)
        elif command.startswith("chmod 600"):
            return self._result(
                command, f"{self.archive.stat().st_size} 600\n{self.remote_sha}\n"
            )
        else:
            failed = bool(self.health_failure and self.health_failure in command)
            result = self._result(command, returncode=1 if failed else 0)
            if check and failed:
                raise subprocess.CalledProcessError(1, command)
            return result
        return self._result(command, json.dumps({"result": "ok", "data": data}))

    def scp_from(self, remote_path: str, local_path: Path) -> None:
        if self.scp_failure:
            raise subprocess.CalledProcessError(1, ["scp"], stderr=self.failure_stderr)
        shutil.copyfile(self.archive, local_path)


def create_with_fake(tmp_path: Path, fake: FakeTransport) -> Path:
    return addon_backup.create_addon_state_backup(
        ha_host="example",
        ha_port=22,
        ha_user="root",
        output_root=tmp_path / "out",
        transport=fake,
        now=NOW,
        post_health_attempts=1,
        sleeper=lambda _: None,
    )


def test_backup_publishes_verified_private_artifacts_without_secrets(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    destination = create_with_fake(tmp_path, fake)

    assert destination.name == TIMESTAMP
    assert destination.stat().st_mode & 0o777 == 0o700
    for filename in (
        f"smarthome_addon_state_{TIMESTAMP}.tar",
        "manifest.json",
        "SHA256SUMS",
    ):
        assert (destination / filename).stat().st_mode & 0o777 == 0o600
    manifest_text = (destination / "manifest.json").read_text()
    manifest = json.loads(manifest_text)
    assert manifest["schema_version"] == 1
    assert manifest["backup"]["components"]["addons"] == expected_ids()
    assert manifest["backup"]["protected"] is False
    assert "never-serialize-me" not in manifest_text
    assert "mongodb://" not in manifest_text
    create_command = next(command for command in fake.commands if command.startswith("ha backups new"))
    assert create_command.count("--app") == 7
    assert "--folders share" in create_command
    assert "--password" not in create_command
    assert "--uncompressed" not in create_command


def test_backup_rejects_old_deployed_mongodb_configuration_before_creation(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    original = fake.ssh

    def old_mongo(command: str, *, check: bool = True):
        result = original(command, check=check)
        if command.startswith("ha apps info local_mongodb"):
            payload = json.loads(result.stdout)
            payload["data"]["startup"] = "services"
            payload["data"]["backup"] = None
            result.stdout = json.dumps(payload)
        return result

    fake.ssh = old_mongo  # type: ignore[method-assign]
    with pytest.raises(Exception, match="startup: system and backup: cold"):
        create_with_fake(tmp_path, fake)
    assert not any(command.startswith("ha backups new") for command in fake.commands)


def test_backup_accepts_cold_manifest_when_supervisor_omits_backup_field(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    original = fake.ssh

    def missing_api_field(command: str, *, check: bool = True):
        result = original(command, check=check)
        if command.startswith("ha apps info local_mongodb"):
            payload = json.loads(result.stdout)
            payload["data"]["backup"] = None
            result.stdout = json.dumps(payload)
        return result

    fake.ssh = missing_api_field  # type: ignore[method-assign]
    destination = create_with_fake(tmp_path, fake)

    assert destination.exists()
    assert any(
        command.startswith("grep -Eq") and "/addons/mongodb/config.yaml" in command
        for command in fake.commands
    )


def test_backup_rejects_missing_api_field_and_non_cold_manifest(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    original = fake.ssh

    def missing_both(command: str, *, check: bool = True):
        result = original(command, check=check)
        if command.startswith("ha apps info local_mongodb"):
            payload = json.loads(result.stdout)
            payload["data"]["backup"] = None
            result.stdout = json.dumps(payload)
        if command.startswith("grep -Eq"):
            return fake._result(command, returncode=1)
        return result

    fake.ssh = missing_both  # type: ignore[method-assign]
    with pytest.raises(Exception, match="startup: system and backup: cold"):
        create_with_fake(tmp_path, fake)


def test_backup_requires_database_dependents_running_for_preflight(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    original = fake.ssh

    def stopped_printer(command: str, *, check: bool = True):
        result = original(command, check=check)
        if command.startswith("ha apps info local_printer_service"):
            payload = json.loads(result.stdout)
            payload["data"]["state"] = "stopped"
            result.stdout = json.dumps(payload)
        return result

    fake.ssh = stopped_printer  # type: ignore[method-assign]
    with pytest.raises(Exception, match="printer"):
        create_with_fake(tmp_path, fake)
    assert not any(command.startswith("ha backups new") for command in fake.commands)


@pytest.mark.parametrize("failure", ["ha core info", "ha supervisor info", "ha backups new"])
def test_transport_and_supervisor_failures_are_reported(tmp_path: Path, failure: str):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.fail_contains = failure
    with pytest.raises(Exception, match="failed on Home Assistant"):
        create_with_fake(tmp_path, fake)


def test_remote_space_failure_prevents_archive_creation(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.remote_free = 1
    with pytest.raises(Exception, match="insufficient free space"):
        create_with_fake(tmp_path, fake)
    assert not any(command.startswith("ha backups new") for command in fake.commands)


@pytest.mark.parametrize(
    ("health_fragment", "expected"),
    [("local-printer-service", "printer"), ("local-tinyurl-service", "tinyurl-service")],
)
def test_database_dependent_health_gates_fail_before_backup(
    tmp_path: Path, health_fragment: str, expected: str
):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.health_failure = health_fragment
    with pytest.raises(Exception, match=expected):
        create_with_fake(tmp_path, fake)
    assert not any(command.startswith("ha backups new") for command in fake.commands)


def test_scp_interruption_cleans_staging_and_retains_no_local_publish(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.scp_failure = True
    with pytest.raises(Exception, match="download was interrupted"):
        create_with_fake(tmp_path, fake)
    output = tmp_path / "out"
    assert output.exists()
    assert list(output.iterdir()) == []


def test_checksum_mismatch_cleans_staging(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.remote_sha = "0" * 64
    with pytest.raises(Exception, match="checksum does not match"):
        create_with_fake(tmp_path, fake)
    assert list((tmp_path / "out").iterdir()) == []


def test_truncated_download_cleans_staging(tmp_path: Path):
    source = tmp_path / "source.tar"
    source.write_bytes(b"not a valid tar archive")
    fake = FakeTransport(source)
    with pytest.raises(Exception, match="malformed or truncated"):
        create_with_fake(tmp_path, fake)
    assert list((tmp_path / "out").iterdir()) == []


def test_post_backup_health_failure_is_reported_after_archive_creation(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    original = fake.ssh
    tiny_health_calls = 0

    def fail_after_backup(command: str, *, check: bool = True):
        nonlocal tiny_health_calls
        if "local-tinyurl-service" in command and "/api/urls" in command:
            tiny_health_calls += 1
            if tiny_health_calls > 1:
                return subprocess.CompletedProcess(command, 1, "", "")
        return original(command, check=check)

    fake.ssh = fail_after_backup  # type: ignore[method-assign]
    with pytest.raises(Exception, match="tinyurl-service"):
        create_with_fake(tmp_path, fake)
    assert any(command.startswith("ha backups new") for command in fake.commands)


def test_archive_inspection_rejects_truncated_and_unexpected_archives(tmp_path: Path):
    truncated = tmp_path / "truncated.tar"
    truncated.write_bytes(b"not a tar")
    with pytest.raises(Exception, match="malformed or truncated"):
        addon_backup.inspect_archive(
            truncated,
            expected_ids=expected_ids(),
            expected_slug=BACKUP_SLUG,
            expected_name=BACKUP_NAME,
        )

    malformed = tmp_path / "unexpected.tar"
    make_archive(malformed)
    with tarfile.open(malformed, "a") as archive:
        info = tarfile.TarInfo("unexpected")
        info.size = 0
        archive.addfile(info)
    with pytest.raises(Exception, match="unexpected tar members"):
        addon_backup.inspect_archive(
            malformed,
            expected_ids=expected_ids(),
            expected_slug=BACKUP_SLUG,
            expected_name=BACKUP_NAME,
        )


@pytest.mark.parametrize(
    ("node_state", "missing"),
    [
        (
            {"presets/favorite.json": b"{}\n", "settings.json": b"{}\n"},
            "presets.json",
        ),
        (
            {"presets.json": b"{}\n", "settings.json": b"{}\n"},
            "presets/ contents",
        ),
        (
            {"presets.json": b"{}\n", "presets/favorite.json": b"{}\n"},
            "settings.json",
        ),
    ],
)
def test_archive_inspection_requires_node_sonos_preset_and_settings_state(
    tmp_path: Path, node_state: dict[str, bytes | None], missing: str
):
    archive = tmp_path / "missing-node-state.tar"
    make_archive(archive, node_state=node_state)

    with pytest.raises(Exception, match=missing):
        addon_backup.inspect_archive(
            archive,
            expected_ids=expected_ids(),
            expected_slug=BACKUP_SLUG,
            expected_name=BACKUP_NAME,
        )


@pytest.mark.parametrize(
    "node_state",
    [
        {
            "other/presets.json": b"{}\n",
            "other/presets/favorite.json": b"{}\n",
            "other/settings.json": b"{}\n",
        },
        {
            "presets.json": b"{}\n",
            "presets/": None,
            "settings.json": b"{}\n",
        },
    ],
)
def test_archive_inspection_rejects_wrong_directory_and_empty_preset_lookalikes(
    tmp_path: Path, node_state: dict[str, bytes | None]
):
    archive = tmp_path / "lookalike-node-state.tar"
    make_archive(archive, node_state=node_state)

    with pytest.raises(Exception, match="presets"):
        addon_backup.inspect_archive(
            archive,
            expected_ids=expected_ids(),
            expected_slug=BACKUP_SLUG,
            expected_name=BACKUP_NAME,
        )


def test_cli_renders_addon_state_command(monkeypatch, tmp_path: Path):
    destination = tmp_path / "published"
    monkeypatch.setattr(
        addon_backup,
        "create_addon_state_backup",
        lambda **kwargs: destination,
    )
    result = CliRunner().invoke(
        app,
        [
            "backup",
            "addon-state",
            "--ha-host",
            "ha.example",
            "--ha-port",
            "2222",
            "--ha-user",
            "operator",
            "--output-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert str(destination) in result.output


def test_ssh_transport_requires_and_selects_repository_identity(monkeypatch, tmp_path: Path):
    identity = tmp_path / "id_ed25519_codex_smarthome"
    identity.write_text("synthetic", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transport = addon_backup.SshTransport(
        "homeassistant.local", 22, "root", identity_file=identity
    )
    transport.ssh("ha core info")
    transport.scp_from("/backup/example.tar", tmp_path / "example.tar")

    assert len(calls) == 2
    for command in calls:
        assert ["-i", str(identity)] == command[3:5]
        assert "IdentitiesOnly=yes" in command
        assert any(part.startswith("root@homeassistant.local") for part in command)


def test_ssh_transport_stops_when_repository_identity_is_missing(tmp_path: Path):
    transport = addon_backup.SshTransport(
        "homeassistant.local", 22, "root", identity_file=tmp_path / "missing"
    )

    with pytest.raises(Exception, match="ha-ssh-key-copy"):
        transport.ssh("ha core info")


def test_ssh_transport_uses_explicit_identity_override(monkeypatch, tmp_path: Path):
    override = tmp_path / "explicit-identity"
    override.write_text("synthetic", encoding="utf-8")
    monkeypatch.setenv("HASS_SSH_IDENTITY", str(override))

    assert addon_backup.ha_ssh_identity() == override


def test_ssh_transport_uses_primary_worktree_key_when_linked_worktree_has_none(
    monkeypatch, tmp_path: Path
):
    missing_current = tmp_path / "linked-worktree" / ".ssh" / "id_ed25519_codex_smarthome"
    primary_identity = tmp_path / "primary-worktree" / ".ssh" / "id_ed25519_codex_smarthome"
    primary_identity.parent.mkdir(parents=True)
    primary_identity.write_text("synthetic", encoding="utf-8")
    monkeypatch.delenv("HASS_SSH_IDENTITY", raising=False)
    monkeypatch.setattr(addon_backup, "DEFAULT_HA_SSH_IDENTITY", missing_current)
    monkeypatch.setattr(addon_backup, "_common_repository_identity", lambda: primary_identity)

    assert addon_backup.ha_ssh_identity() == primary_identity


def test_ssh_authentication_failure_stops_and_requires_human_key_copy(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.fail_contains = "ha core info"
    fake.failure_stderr = "Permission denied (publickey)."

    with pytest.raises(Exception, match="just ha-ssh-key-copy") as error:
        create_with_fake(tmp_path, fake)

    assert "alternate credentials" in str(error.value)
    assert len(fake.commands) == 1


def test_ssh_hostname_failure_preserves_mdns_hostname_workflow(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.fail_contains = "ha core info"
    fake.failure_stderr = "ssh: Could not resolve hostname homeassistant.local"

    with pytest.raises(Exception, match="mDNS/network failure") as error:
        create_with_fake(tmp_path, fake)

    assert "do not substitute an IP address" in str(error.value)
    assert len(fake.commands) == 1


def test_scp_authentication_failure_stops_and_requires_human_key_copy(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.scp_failure = True
    fake.failure_stderr = "Permission denied (publickey)."

    with pytest.raises(Exception, match="just ha-ssh-key-copy"):
        create_with_fake(tmp_path, fake)


def test_scp_hostname_failure_preserves_mdns_hostname_workflow(tmp_path: Path):
    source = tmp_path / "source.tar"
    make_archive(source)
    fake = FakeTransport(source)
    fake.scp_failure = True
    fake.failure_stderr = "scp: Could not resolve hostname homeassistant.local"

    with pytest.raises(Exception, match="mDNS/network failure") as error:
        create_with_fake(tmp_path, fake)

    assert "do not substitute an IP address" in str(error.value)
