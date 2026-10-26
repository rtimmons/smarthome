from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_printer_setup_runs_script():
    printer_root = Path(__file__).resolve().parents[1] / ".." / "printer"
    justfile = printer_root / "Justfile"
    contents = justfile.read_text(encoding="utf-8")
    assert "scripts/setup.sh" in contents
    assert "setup: setup-printer" in contents
    assert "ensure-current-venv" in contents

    setup_script = printer_root / "scripts" / "setup.sh"
    setup_text = setup_script.read_text(encoding="utf-8")
    assert "talos/scripts/python_use.sh" in setup_text


@pytest.mark.parametrize("caller", [".", "printer", "printer/src"])
def test_nested_printer_justfile_uses_enclosing_workspace(tmp_path, caller):
    """An independent Git root must not redirect shared tooling into printer/."""
    workspace = tmp_path / "workspace with spaces"
    printer = workspace / "printer"
    (printer / "src").mkdir(parents=True)
    shared = workspace / "talos/just"
    shared.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    shutil.copy(source / "talos/just/common.just", shared / "common.just")
    shutil.copy(source / "printer/Justfile", printer / "Justfile")
    subprocess.run(["git", "init", "-q", str(printer)], check=True)
    result = subprocess.run(
        ["just", "--justfile", str(printer / "Justfile"), "--evaluate", "repo_root"],
        cwd=workspace / caller, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == str(workspace)
    dry_run = subprocess.run(
        ["just", "--justfile", str(printer / "Justfile"), "--dry-run", "build"],
        cwd=workspace / caller, capture_output=True, text=True, check=True,
    )
    assert f'REPO_ROOT="{workspace}"' in dry_run.stderr
    assert "git rev-parse" not in dry_run.stderr
