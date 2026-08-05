from __future__ import annotations

from rich.console import Console
import pytest

from talos.timing import DeployTimer


def test_disabled_timer_phase_is_noop():
    timer = DeployTimer(Console(), enabled=False)

    with timer.phase("ignored"):
        pass
    timer.record("also_ignored", 1.0)

    assert timer.events == []


def test_interrupted_phase_is_recorded_as_error():
    timer = DeployTimer(Console(), enabled=True)

    with pytest.raises(KeyboardInterrupt):
        with timer.phase("interrupted"):
            raise KeyboardInterrupt

    assert timer.events[0]["status"] == "error"
