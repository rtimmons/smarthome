from __future__ import annotations

import os
import subprocess
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .addon_builder import DeploymentError, deploy_addon, validate_deployment_prerequisites
from .addon_manifest import addon_dependencies, dependency_waves, resolve_addon_dirs
from .paths import REPO_ROOT
from .timing import DeployTimer

console = Console()
PRE_DEPLOY_RECIPES = ("generate", "build", "test", "ha-addon", "container-test")


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


def _run_pre_deploy_steps(
    addon_dir: Path,
    verbose: bool,
) -> Tuple[str, Optional[str], Optional[str], Optional[subprocess.CalledProcessError]]:
    addon_name = addon_dir.name
    if not (addon_dir / "Justfile").exists():
        return addon_name, None, None, None

    for pre in PRE_DEPLOY_RECIPES:
        if _has_recipe(addon_dir, pre):
            if verbose:
                console.print(f"  Running {pre} for {addon_name}")
            try:
                _run_just(addon_dir, pre, verbose=verbose)
            except subprocess.CalledProcessError as e:
                error_msg = (
                    f"Pre-deployment step failed for {addon_name}: "
                    f"just {pre} (exit {e.returncode})"
                )
                return addon_name, pre, error_msg, e

    return addon_name, None, None, None


def _run_just(addon_dir: Path, recipe: str, verbose: bool = True) -> None:
    cmd = ["just", "--justfile", str(addon_dir / "Justfile"), "--working-directory", str(addon_dir), recipe]

    if verbose:
        subprocess.run(cmd, check=True)
    else:
        # Suppress output in non-verbose mode
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _resolve_addons(explicit: Iterable[str]) -> List[Path]:
    return resolve_addon_dirs(explicit)


def _deploy_dependencies(addon_dir: Path) -> set[str]:
    """Return explicit deployment dependencies declared by an add-on."""
    return addon_dependencies(addon_dir)


def _dependency_waves(addon_dirs: Iterable[Path]) -> list[list[Path]]:
    """Group add-ons into parallel waves while preserving dependency order."""
    try:
        return dependency_waves(addon_dirs)
    except click.ClickException as error:
        if "Circular add-on dependencies" in str(error):
            raise click.ClickException(str(error).replace("Circular add-on dependencies", "Circular add-on deployment dependencies")) from error
        raise


def run_enhanced_deployment(addons: Iterable[str], ha_host: str, ha_port: int, ha_user: str,
                          dry_run: bool = False, verbose: bool = False, jobs: int | None = None,
                          verify: bool = False, timer: DeployTimer | None = None) -> None:
    """Enhanced deployment with better error handling and progress tracking."""
    timer = timer or DeployTimer(console, enabled=False)
    addon_dirs = _resolve_addons(addons)
    addon_names = [addon_dir.name for addon_dir in addon_dirs]
    dependency_waves = _dependency_waves(addon_dirs)
    dependencies = {addon_dir.name: _deploy_dependencies(addon_dir) for addon_dir in addon_dirs}
    verify = verify or _is_truthy(os.environ.get("TALOS_DEPLOY_VERIFY"))
    if jobs is None:
        jobs = os.cpu_count() or 1
    if jobs < 1:
        jobs = 1
    jobs = min(jobs, len(addon_names))

    timer.record(
        "addons.schedule",
        0.0,
        waves=[[path.name for path in wave] for wave in dependency_waves],
        strategy="dependency-ready-queue",
        jobs=jobs,
    )

    if not addon_names:
        console.print("[yellow]No add-ons to deploy[/yellow]")
        return

    if dry_run:
        # Concise dry-run summary for batch deployment
        console.print(f"📋 [bold]Batch Deployment Plan[/bold]")
        console.print(f"  • Target: {ha_host}:{ha_port}")
        console.print(f"  • Add-ons to deploy: {len(addon_names)}")
        console.print(f"  • Add-ons: {', '.join(addon_names)}")
        console.print(f"  • Mode: {'verified' if verify else 'fast'}")
        console.print(
            "  • Dependency levels (dispatched as soon as ready): "
            + " → ".join(
                f"wave {number} ({', '.join(path.name for path in wave)})"
                for number, wave in enumerate(dependency_waves, 1)
            )
        )
        console.print(f"\n[dim]Each add-on would be:[/dim]")
        if verify:
            console.print(f"  1. Validated locally via optional Just recipes")
            console.print(f"  2. Built, uploaded, and deployed to {ha_host}")
            console.print(f"  3. Health checked after deployment")
        else:
            console.print(f"  1. Built, uploaded, and deployed to {ha_host}")
            console.print(f"  2. Health checked after deployment")
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
    if verify:
        console.print("🧪 [bold]Verified deploy mode:[/bold] running optional local pre-deploy recipes first.")
    else:
        console.print("⚡ [bold]Fast deploy mode:[/bold] skipping optional local build/test/container validation. Use `--verify` to restore it.")
    with timer.phase("addons.prerequisites"):
        validate_deployment_prerequisites(
            ha_host, ha_port, ha_user, verbose=verbose, timer=timer
        )
    deployment_errors = []
    successful_deployments = []
    failed_deployments: set[str] = set()
    live_progress = console.is_terminal and console.is_interactive

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=not verbose,
        disable=not live_progress
    ) as progress:
        if verify:
            build_task = progress.add_task("Running local pre-deploy checks...", total=len(addon_names))

            def record_pre_deploy_failure(
                addon_name: str,
                pre: Optional[str],
                error_msg: str,
                error: Optional[subprocess.CalledProcessError]
            ) -> None:
                deployment_errors.append((addon_name, error_msg))
                progress.stop()
                console.print(f"  ❌ [red]{error_msg}[/red]")
                if not verbose and error is not None:
                    _print_command_output(error.stdout or "", error.stderr or "")
                if pre:
                    console.print(f"  Hint: run `just {pre}` in `{addon_name}/` to reproduce.")
                else:
                    console.print(f"  Hint: run the add-on build steps in `{addon_name}/` to reproduce.")
                progress.start()

            if jobs == 1:
                for addon_dir in addon_dirs:
                    addon_name = addon_dir.name
                    progress.update(build_task, description=f"Checking {addon_name}...")

                    with timer.phase("addons.verify", addon=addon_name):
                        addon_name, failed_pre, error_msg, error = _run_pre_deploy_steps(addon_dir, verbose)
                    if error_msg:
                        record_pre_deploy_failure(addon_name, failed_pre, error_msg, error)

                    progress.advance(build_task)
            else:
                with ThreadPoolExecutor(max_workers=jobs) as executor:
                    futures = {
                        executor.submit(_run_pre_deploy_steps, addon_dir, verbose): addon_dir
                        for addon_dir in addon_dirs
                    }

                    for future in as_completed(futures):
                        addon_dir = futures[future]
                        addon_name = addon_dir.name
                        progress.update(build_task, description=f"Checking {addon_name}...")
                        try:
                            addon_name, failed_pre, error_msg, error = future.result()
                        except Exception as e:
                            failed_pre = None
                            error = None
                            error_msg = f"Pre-deployment step failed for {addon_name}: {str(e)}"

                        if error_msg:
                            record_pre_deploy_failure(addon_name, failed_pre, error_msg, error)

                        progress.advance(build_task)

            progress.remove_task(build_task)

        # Phase 2: dependency-aware ready queue. Dependents launch as soon as
        # their own prerequisites finish; unrelated slow add-ons do not create
        # a wave-wide barrier.
        if not deployment_errors:  # Only deploy if all builds succeeded
            deploy_task = progress.add_task("Deploying add-ons...", total=len(addon_names))

            def deploy_one(addon_dir: Path) -> tuple[str, Exception | None]:
                addon_name = addon_dir.name
                try:
                    deploy_addon(
                        addon_name,
                        ha_host,
                        ha_port,
                        ha_user,
                        dry_run,
                        verbose,
                        validate_prereqs=False,
                        show_success=verbose,
                        timer=timer,
                    )
                    return addon_name, None
                except Exception as error:  # surfaced by the coordinator thread below
                    return addon_name, error

            addon_by_name = {addon_dir.name: addon_dir for addon_dir in addon_dirs}
            selected_names = set(addon_by_name)
            selected_dependencies = {
                name: declared & selected_names for name, declared in dependencies.items()
            }
            pending = set(selected_names)
            completed_deployments: set[str] = set()
            running: dict[Future[tuple[str, Exception | None]], str] = {}

            def record_deployment_result(addon_name: str, error: Exception | None) -> None:
                if error is None:
                    completed_deployments.add(addon_name)
                    successful_deployments.append(addon_name)
                    if not live_progress:
                        console.print(f"  ✅ {addon_name} deployment finished")
                else:
                    failed_deployments.add(addon_name)
                    deployment_errors.append((addon_name, str(error)))
                    progress.stop()
                    if isinstance(error, DeploymentError):
                        error.display_error()
                    else:
                        console.print(
                            f"  ❌ [red]Unexpected error deploying {addon_name}: {error}[/red]"
                        )
                    if running:
                        console.print(
                            "  ⏳ Allowing "
                            f"{len(running)} in-flight deployment(s) to finish safely; "
                            "their output may remain quiet until completion."
                        )
                    progress.start()
                progress.advance(deploy_task)

            with timer.phase(
                "addons.execution",
                strategy="dependency-ready-queue",
                jobs=jobs,
            ):
                with ThreadPoolExecutor(max_workers=jobs) as executor:
                    while pending or running:
                        # A failed dependency blocks its entire downstream chain.
                        blocked = sorted(
                            name
                            for name in pending
                            if selected_dependencies[name] & failed_deployments
                        )
                        for addon_name in blocked:
                            blocked_by = sorted(
                                selected_dependencies[addon_name] & failed_deployments
                            )
                            pending.remove(addon_name)
                            error_message = (
                                f"Blocked by failed dependency: {', '.join(blocked_by)}"
                            )
                            failed_deployments.add(addon_name)
                            deployment_errors.append((addon_name, error_message))
                            timer.record(
                                "addons.blocked",
                                0.0,
                                status="blocked",
                                addon=addon_name,
                                blocked_by=blocked_by,
                            )
                            progress.advance(deploy_task)
                        if blocked:
                            # Re-evaluate immediately so failure propagation can
                            # block deeper dependents before declaring a deadlock.
                            continue

                        available_slots = jobs - len(running)
                        ready = sorted(
                            name
                            for name in pending
                            if selected_dependencies[name] <= completed_deployments
                        )
                        for addon_name in ready[:available_slots]:
                            pending.remove(addon_name)
                            timer.record(
                                "addons.dispatch",
                                0.0,
                                addon=addon_name,
                                dependencies=sorted(selected_dependencies[addon_name]),
                                active=len(running) + 1,
                            )
                            progress.update(
                                deploy_task,
                                description=f"Deploying {addon_name} ({len(running) + 1} active)...",
                            )
                            if not live_progress:
                                dependency_label = ", ".join(
                                    sorted(selected_dependencies[addon_name])
                                ) or "none"
                                console.print(
                                    f"  → {addon_name} deployment started "
                                    f"(dependencies: {dependency_label})"
                                )
                            future = executor.submit(deploy_one, addon_by_name[addon_name])
                            running[future] = addon_name

                        if not running:
                            if pending:
                                unresolved = ", ".join(sorted(pending))
                                raise click.ClickException(
                                    f"Unable to schedule add-on deployments: {unresolved}"
                                )
                            continue

                        finished, _ = wait(running, return_when=FIRST_COMPLETED)
                        for future in finished:
                            expected_name = running.pop(future)
                            try:
                                addon_name, error = future.result()
                            except Exception as unexpected_error:
                                addon_name, error = expected_name, unexpected_error
                            record_deployment_result(addon_name, error)

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
