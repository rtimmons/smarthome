from __future__ import annotations

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
