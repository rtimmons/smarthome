from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .addon_builder import discover_addons, DeploymentError, deploy_addon, validate_deployment_prerequisites
from .paths import REPO_ROOT

console = Console()


def _tail_lines(text: str, limit: int = 12) -> List[str]:
    if not text:
        return []
    lines = text.rstrip("\n").splitlines()
    if len(lines) > limit:
        return lines[-limit:]
    return lines


def _print_command_output(stdout: str, stderr: str) -> None:
    stderr_lines = _tail_lines(stderr)
    stdout_lines = _tail_lines(stdout)

    if stderr_lines:
        console.print(f"  stderr (last {len(stderr_lines)} lines):")
        for line in stderr_lines:
            console.print(f"    {line}", style="dim", markup=False)

    if stdout_lines:
        console.print(f"  stdout (last {len(stdout_lines)} lines):")
        for line in stdout_lines:
            console.print(f"    {line}", style="dim", markup=False)


def _has_recipe(addon_dir: Path, target: str) -> bool:
    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(addon_dir / "Justfile"),
            "--working-directory",
            str(addon_dir),
            "--color",
            "never",
            "--list",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False

    lines = result.stdout.splitlines()
    for line in lines[1:]:
        parts = line.split()
        if not parts:  # Skip empty lines
            continue
        recipe = parts[0]
        if recipe == target:
            return True
    return False


def _run_just(addon_dir: Path, recipe: str, verbose: bool = True) -> None:
    cmd = ["just", "--justfile", str(addon_dir / "Justfile"), "--working-directory", str(addon_dir), recipe]

    if verbose:
        subprocess.run(cmd, check=True)
    else:
        # Suppress output in non-verbose mode
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def _resolve_addons(explicit: Iterable[str]) -> List[Path]:
    if explicit:
        addon_dirs = []
        for name in explicit:
            path = REPO_ROOT / name
            if not (path.exists() and (path / "addon.yaml").exists()):
                raise click.ClickException(f"Unknown add-on '{name}' (no addon.yaml in {path}).")
            addon_dirs.append(path)
        return addon_dirs

    addons = discover_addons()
    if not addons:
        raise click.ClickException("No add-on manifests found (expected */addon.yaml).")
    return [REPO_ROOT / name for name in sorted(addons.keys())]


def run_enhanced_deployment(addons: Iterable[str], ha_host: str, ha_port: int, ha_user: str,
                          dry_run: bool = False, verbose: bool = False) -> None:
    """Enhanced deployment with better error handling and progress tracking."""
    addon_dirs = _resolve_addons(addons)
    addon_names = [addon_dir.name for addon_dir in addon_dirs]

    if not addon_names:
        console.print("[yellow]No add-ons to deploy[/yellow]")
        return

    if dry_run:
        # Concise dry-run summary for batch deployment
        console.print(f"📋 [bold]Batch Deployment Plan[/bold]")
        console.print(f"  • Target: {ha_host}:{ha_port}")
        console.print(f"  • Add-ons to deploy: {len(addon_names)}")
        console.print(f"  • Add-ons: {', '.join(addon_names)}")
        console.print(f"\n[dim]Each add-on would be:[/dim]")
        console.print(f"  1. Built locally with pre-deployment tests")
        console.print(f"  2. Uploaded and deployed to {ha_host}")
        console.print(f"  3. Health checked after deployment")
        console.print(f"\n[yellow]This is a dry run - no changes would be made[/yellow]")

        # Still call individual dry-runs if verbose mode is requested
        if verbose:
            console.print(f"\n[dim]Individual add-on plans:[/dim]")
            for addon_name in addon_names:
                try:
                    deploy_addon(addon_name, ha_host, ha_port, ha_user, dry_run=True, verbose=False)
                    console.print("")  # Add spacing between add-ons
                except Exception as e:
                    console.print(f"  ❌ [red]Would fail to deploy {addon_name}: {str(e)}[/red]")
        return

    console.print(f"🚀 [bold]Deploying {len(addon_names)} add-on(s)[/bold]")
    validate_deployment_prerequisites(ha_host, ha_port, ha_user, verbose=verbose)

    deployment_errors = []
    successful_deployments = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=not verbose,
        disable=not console.is_terminal or not console.is_interactive
    ) as progress:

        # Phase 1: Pre-deployment validation and build
        build_task = progress.add_task("Building add-ons...", total=len(addon_names))

        for addon_dir in addon_dirs:
            addon_name = addon_dir.name
            progress.update(build_task, description=f"Building {addon_name}...")

            failed_pre = False
            if (addon_dir / "Justfile").exists():
                for pre in ("generate", "build", "test", "ha-addon", "container-test"):
                    if _has_recipe(addon_dir, pre):
                        if verbose:
                            console.print(f"  Running {pre} for {addon_name}")
                        try:
                            _run_just(addon_dir, pre, verbose=verbose)
                        except subprocess.CalledProcessError as e:
                            failed_pre = True
                            error_msg = (
                                f"Pre-deployment step failed for {addon_name}: "
                                f"just {pre} (exit {e.returncode})"
                            )
                            deployment_errors.append((addon_name, error_msg))
                            progress.stop()
                            console.print(f"  ❌ [red]{error_msg}[/red]")
                            if not verbose:
                                _print_command_output(e.stdout or "", e.stderr or "")
                            console.print(f"  Hint: run `just {pre}` in `{addon_name}/` to reproduce.")
                            progress.start()
                            break

            progress.advance(build_task)
            if failed_pre:
                continue

        progress.remove_task(build_task)

        # Phase 2: Deployment
        if not deployment_errors:  # Only deploy if all builds succeeded
            deploy_task = progress.add_task("Deploying add-ons...", total=len(addon_names))

            for addon_dir in addon_dirs:
                addon_name = addon_dir.name
                progress.update(deploy_task, description=f"Deploying {addon_name}...")

                try:
                    deploy_addon(
                        addon_name,
                        ha_host,
                        ha_port,
                        ha_user,
                        dry_run,
                        verbose,
                        validate_prereqs=False,
                        show_success=verbose
                    )
                    successful_deployments.append(addon_name)
                    progress.advance(deploy_task)

                except DeploymentError as e:
                    deployment_errors.append((addon_name, str(e)))
                    # Stop progress bar before displaying error to avoid interference
                    progress.stop()
                    e.display_error()
                    progress.start()
                    progress.advance(deploy_task)
                    continue
                except Exception as e:
                    error_msg = f"Unexpected error deploying {addon_name}: {str(e)}"
                    deployment_errors.append((addon_name, error_msg))
                    # Stop progress bar before displaying error to avoid interference
                    progress.stop()
                    console.print(f"  ❌ [red]{error_msg}[/red]")
                    progress.start()
                    progress.advance(deploy_task)
                    continue

            progress.remove_task(deploy_task)

    # Summary
    console.print("\n📊 [bold]Deployment Summary[/bold]")
    if successful_deployments:
        console.print(f"✅ [green]Successfully deployed ({len(successful_deployments)}):[/green]")
        for addon in successful_deployments:
            console.print(f"  • {addon}")

    if deployment_errors:
        console.print(f"\n❌ [red]Failed deployments ({len(deployment_errors)}):[/red]")
        for addon, error in deployment_errors:
            console.print(f"  • {addon}: {error}")

        console.print(f"\n💡 [yellow]Troubleshooting tips:[/yellow]")
        console.print("  • Run with --verbose for detailed output")
        console.print("  • Check individual add-on logs: ha addons logs <addon>")
        console.print("  • Verify system health: ha supervisor info")

        raise click.ClickException(f"Deployment failed for {len(deployment_errors)} add-on(s)")

    console.print(f"\n🎉 [green]All {len(successful_deployments)} add-on(s) deployed successfully![/green]")


def run_recipes(recipe: str, addons: Iterable[str]) -> None:
    addon_dirs = _resolve_addons(addons)

    for addon_dir in addon_dirs:
        addon_name = addon_dir.name
        if not (addon_dir / "Justfile").exists():
            click.echo(f"==> {addon_name}: skipping, no Justfile")
            continue

        if recipe == "deploy":
            for pre in ("generate", "build", "test", "ha-addon", "container-test"):
                if _has_recipe(addon_dir, pre):
                    click.echo(f"==> {addon_name}: just {pre} (pre-deploy)")
                    _run_just(addon_dir, pre, verbose=True)

        if _has_recipe(addon_dir, recipe):
            click.echo(f"==> {addon_name}: just {recipe}")
            _run_just(addon_dir, recipe, verbose=True)
        else:
            click.echo(f"==> {addon_name}: skipping, no '{recipe}' recipe")
