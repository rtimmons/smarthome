from __future__ import annotations

import json

from click.testing import CliRunner

from talos import cli


def test_dev_command_invokes_run_dev(monkeypatch):
    called = {"count": 0}

    def fake_run_dev() -> int:
        called["count"] += 1
        return 0

    monkeypatch.setattr(cli.dev_mod, "run_dev", fake_run_dev)

    result = CliRunner().invoke(cli.app, ["dev"])

    assert result.exit_code == 0
    assert called["count"] == 1


def test_addon_names_json_outputs_manifest():
    result = CliRunner().invoke(cli.app, ["addon", "names", "--json"])

    assert result.exit_code == 0
    names = json.loads(result.output.strip())
    assert isinstance(names, list)
    for expected in ("grid-dashboard", "sonos-api", "printer"):
        assert expected in names
