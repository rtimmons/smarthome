from __future__ import annotations

from pathlib import Path


def test_printer_setup_runs_script():
    printer_root = Path(__file__).resolve().parents[1] / ".." / "printer"
    justfile = printer_root / "Justfile"
    contents = justfile.read_text(encoding="utf-8")
    assert "scripts/setup.sh" in contents

    setup_script = printer_root / "scripts" / "setup.sh"
    setup_text = setup_script.read_text(encoding="utf-8")
    assert "talos/scripts/python_use.sh" in setup_text
