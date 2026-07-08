from __future__ import annotations

import subprocess
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
        capture_output=not verbose,
    )


def precheck(verbose: bool = False, timer: DeployTimer | None = None) -> None:
    timer = timer or DeployTimer(console, enabled=False)
    with timer.phase("config.precheck"):
        _run_config_script("precheck", verbose=verbose)


def deploy_needed(verbose: bool = False, timer: DeployTimer | None = None) -> bool:
    timer = timer or DeployTimer(console, enabled=False)
    with timer.phase("config.deploy_needed"):
        result = _run_config_script("needed", verbose=False)

    needed = result.stdout.strip()
    if needed not in {"true", "false"}:
        raise click.ClickException(f"Unexpected config deploy-needed output: {needed!r}")
    if verbose:
        console.print(f"Home Assistant config deploy needed: {needed}")
    return needed == "true"


def apply(verbose: bool = False, timer: DeployTimer | None = None) -> None:
    timer = timer or DeployTimer(console, enabled=False)
    with timer.phase("config.apply"):
        _run_config_script("apply", verbose=verbose)


def deploy(verbose: bool = False, timer: DeployTimer | None = None) -> bool:
    precheck(verbose=verbose, timer=timer)
    if deploy_needed(verbose=verbose, timer=timer):
        console.print("\n🏠 Deploying Home Assistant configs...")
        apply(verbose=verbose, timer=timer)
        return True

    console.print("\n🏠 Home Assistant configs unchanged; skipping config deploy and restart.")
    return False
