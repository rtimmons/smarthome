from __future__ import annotations

import subprocess

import pytest
from rich.console import Console

from talos import hass_config
from talos.timing import DeployTimer


def test_failed_config_action_retains_inner_metrics(monkeypatch: pytest.MonkeyPatch):
    error = subprocess.CalledProcessError(
        1,
        ["deploy-config.sh", "precheck"],
        output="",
        stderr="__TALOS_CONFIG_METRIC__\tconfig.generate\t1000\t1750\terror\n",
    )

    def fail(_action: str, verbose: bool = False):
        raise error

    monkeypatch.setattr(hass_config, "_run_config_script", fail)
    timer = DeployTimer(Console(), enabled=True)

    with pytest.raises(subprocess.CalledProcessError):
        hass_config.precheck(timer=timer)

    events = {event["name"]: event for event in timer.events}
    assert events["config.precheck"]["status"] == "error"
    assert events["config.generate"]["seconds"] == 0.75
    assert events["config.generate"]["status"] == "error"
