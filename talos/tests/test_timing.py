from __future__ import annotations

from rich.console import Console

from talos.timing import DeployTimer


def test_disabled_timer_phase_is_noop():
    timer = DeployTimer(Console(), enabled=False)

    with timer.phase("ignored"):
        pass
    timer.record("also_ignored", 1.0)

    assert timer.events == []
