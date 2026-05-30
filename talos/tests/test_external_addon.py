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

