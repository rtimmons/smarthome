from __future__ import annotations

import subprocess
import time
from pathlib import Path

import click
from rich.console import Console

from .paths import REPO_ROOT
from .timing import DeployTimer

console = Console()
SCRIPT = REPO_ROOT / "new-hass-configs" / "sync-tools" / "deploy-config.sh"


def _run_config_script(action: str, verbose: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [str(SCRIPT), action]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT / "new-hass-configs"),
        check=True,
        text=True,
        capture_output=True,
    )


def _record_script_metrics(
    result: subprocess.CompletedProcess[str],
    timer: DeployTimer,
    verbose: bool,
) -> None:
    visible_stderr: list[str] = []
    metrics: list[tuple[str, int, int, str]] = []
    for line in result.stderr.splitlines():
        if not line.startswith("__TALOS_CONFIG_METRIC__\t"):
            visible_stderr.append(line)
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            visible_stderr.append(line)
            continue
        _, phase, started_raw, finished_raw, status = parts
        try:
            started_ms = int(started_raw)
            finished_ms = int(finished_raw)
        except ValueError:
            visible_stderr.append(line)
            continue
        metrics.append((phase, started_ms, finished_ms, status))

    script_finish_ms = max((metric[2] for metric in metrics), default=0)
    local_finish_offset = time.perf_counter() - timer.started_at
    for phase, started_ms, finished_ms, status in metrics:
        timer.record(
            phase,
            max(0, finished_ms - started_ms) / 1000,
            status=status,
            source="config-script",
            script_started_ms=started_ms,
            script_finished_ms=finished_ms,
            started_offset_seconds=round(
                local_finish_offset - (script_finish_ms - started_ms) / 1000, 3
            ),
            finished_offset_seconds=round(
                local_finish_offset - (script_finish_ms - finished_ms) / 1000, 3
            ),
        )

    if verbose:
        if result.stdout:
            console.print(result.stdout.rstrip(), markup=False)
        if visible_stderr:
            console.print("\n".join(visible_stderr), style="dim", markup=False)


def _run_timed_config_script(
    action: str,
    phase: str,
    timer: DeployTimer,
    verbose: bool,
) -> subprocess.CompletedProcess[str]:
    """Run one config action and retain its inner timings even when it fails."""
    try:
        with timer.phase(phase):
            result = _run_config_script(action, verbose=verbose)
    except subprocess.CalledProcessError as error:
        failed_result = subprocess.CompletedProcess(
            args=error.cmd,
            returncode=error.returncode,
            stdout=error.stdout or "",
            stderr=error.stderr or "",
        )
        _record_script_metrics(failed_result, timer, verbose)
        raise
    _record_script_metrics(result, timer, verbose)
    return result


def precheck(verbose: bool = False, timer: DeployTimer | None = None) -> None:
    timer = timer or DeployTimer(console, enabled=False)
    _run_timed_config_script("precheck", "config.precheck", timer, verbose)


def deploy_needed(verbose: bool = False, timer: DeployTimer | None = None) -> bool:
    timer = timer or DeployTimer(console, enabled=False)
    result = _run_timed_config_script(
        "needed", "config.deploy_needed", timer, verbose
    )

    needed = result.stdout.strip()
    if needed not in {"true", "false"}:
        raise click.ClickException(f"Unexpected config deploy-needed output: {needed!r}")
    if verbose:
        console.print(f"Home Assistant config deploy needed: {needed}")
    return needed == "true"


def apply(verbose: bool = False, timer: DeployTimer | None = None) -> None:
    timer = timer or DeployTimer(console, enabled=False)
    _run_timed_config_script("apply", "config.apply", timer, verbose)


def deploy(verbose: bool = False, timer: DeployTimer | None = None) -> bool:
    precheck(verbose=verbose, timer=timer)
    if deploy_needed(verbose=verbose, timer=timer):
        console.print("\n🏠 Deploying Home Assistant configs...")
        apply(verbose=verbose, timer=timer)
        return True

    console.print("\n🏠 Home Assistant configs unchanged; skipping config deploy and restart.")
    return False
