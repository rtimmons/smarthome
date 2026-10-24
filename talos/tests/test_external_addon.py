from __future__ import annotations

import tarfile
from pathlib import Path

from click.testing import CliRunner

from talos.cli import app
from talos.external_addon import package_external_addon


def _write_minimal_app(root: Path) -> None:
    (root / "package.json").write_text(
        '{"scripts":{"start":"node server.js"},"dependencies":{}}\n',
        encoding="utf-8",
    )
    (root / "server.js").write_text('console.log("ok")\n', encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "ignored.js").write_text("ignored\n", encoding="utf-8")

    addon_dir = root / "ha-addon"
    addon_dir.mkdir()
    (addon_dir / "config.yaml").write_text(
        "\n".join(
            [
                'name: "Test App"',
                'version: "0.1.0"',
                'slug: "test_app"',
                'description: "Test app"',
                'arch: ["amd64"]',
                'startup: services',
                'boot: auto',
                'init: false',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (addon_dir / "Dockerfile").write_text("FROM node:22-alpine\n", encoding="utf-8")
    (addon_dir / "run.sh").write_text("#!/usr/bin/env bash\nexec npm start\n", encoding="utf-8")
    (addon_dir / "package-excludes.txt").write_text("node_modules/\nha-addon/\n", encoding="utf-8")


def test_package_external_addon_shapes_tarball(tmp_path: Path):
    _write_minimal_app(tmp_path)

    archive = package_external_addon(tmp_path, tmp_path / "ha-addon", output_dir=tmp_path / "out")

    assert archive.name == "test_app.tar.gz"
    with tarfile.open(archive, "r:gz") as tar:
        names = set(tar.getnames())

    assert "test_app/config.yaml" in names
    assert "test_app/Dockerfile" in names
    assert "test_app/run.sh" in names
    assert "test_app/app/package.json" in names
    assert "test_app/app/server.js" in names
    assert "test_app/app/node_modules/ignored.js" not in names
    assert "test_app/app/ha-addon/config.yaml" not in names


def test_package_external_cli(tmp_path: Path):
    _write_minimal_app(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "addon",
            "package-external",
            "--app-dir",
            str(tmp_path),
            "--addon-dir",
            str(tmp_path / "ha-addon"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "test_app.tar.gz").exists()



def test_external_deploy_uses_shared_transport_and_preserves_watchdog(tmp_path, monkeypatch):
    import subprocess
    from talos import addon_builder, external_addon

    _write_minimal_app(tmp_path)
    calls = []
    monkeypatch.setenv("HASS_SSH_IDENTITY", "/tmp/fixture-ha-key")
    monkeypatch.setattr(external_addon, "validate_deployment_prerequisites", lambda *a, **k: None)
    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
    monkeypatch.setattr(addon_builder, "run_cmd", run)
    external_addon.deploy_external_addon(tmp_path, tmp_path / "ha-addon", "fixture.local", 2222, "root")
    assert [c[0] for c in calls] == ["scp", "ssh"]
    for command in calls:
        assert command[1:5] == ["-i", "/tmp/fixture-ha-key", "-o", "IdentitiesOnly=yes"]
        assert "2222" in command
    script = calls[-1][-1]
    assert 'resolve_addons_dir' in script and 'wait_for_started' in script
    # Execute only the option-update section: external deployments must not enable watchdog.
    section = script.split('log_info "Configuring add-on options..."')[1].split('log_info "Starting add-on')[0]
    result = subprocess.run(["bash", "-c", 'SUPERVISOR_TOKEN=fixture\nrun_metric() { exit 99; }\nmonotonic_ms() { echo 1; }\nemit_metric() { :; }\n' + section], capture_output=True)
    assert result.returncode == 0


def test_external_dry_run_never_packages_or_connects(tmp_path, monkeypatch):
    from talos import external_addon
    _write_minimal_app(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("dry run attempted deployment")
    for name in ("validate_deployment_prerequisites", "package_external_addon", "deploy_artifact"):
        monkeypatch.setattr(external_addon, name, forbidden)
    external_addon.deploy_external_addon(tmp_path, tmp_path / "ha-addon", "fixture.local", 22, "root", dry_run=True)


def test_external_cli_reports_shared_deployment_error(monkeypatch):
    from talos import addon_builder, external_addon
    def fail(*args, **kwargs):
        raise addon_builder.DeploymentError("fixture upload failed", error_type="UPLOAD_FAILED")
    monkeypatch.setattr(external_addon, "deploy_external_addon", fail)
    result = CliRunner().invoke(app, ["addon", "deploy-external"])
    assert result.exit_code == 1
    assert "UPLOAD_FAILED" in result.output and "Deployment failed" in result.output
