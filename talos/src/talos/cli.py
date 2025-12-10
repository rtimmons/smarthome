from __future__ import annotations

import click

from . import addon_builder, addons_runner, dev as dev_mod, hooks, manage_ports


@click.group()
def app() -> None:
    """Talos smarthome build tool."""


@app.group()
def addon() -> None:
    """Add-on build and deploy helpers."""


@addon.command("list")
def addon_list() -> None:
    addon_builder.list_addons()


@addon.command("names")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON array.")
def addon_names(as_json: bool) -> None:
    addon_builder.addon_names(as_json=as_json)


@addon.command("build")
@click.argument("addon")
def addon_build(addon: str) -> None:
    addon_builder.run_build(addon)


@addon.command("deploy")
@click.argument("addon")
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print commands without executing.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
def addon_deploy(addon: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool, verbose: bool) -> None:
    """Deploy a single add-on with enhanced error handling."""
    try:
        addon_builder.deploy_addon(addon, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=dry_run, verbose=verbose)
    except addon_builder.DeploymentError as e:
        e.display_error()
        raise click.ClickException("Deployment failed")


@addon.command("test")
@click.argument("addon")
def addon_test(addon: str) -> None:
    addon_builder.run_test(addon)


@app.group()
def ports() -> None:
    """Inspect or free add-on ports."""


@ports.command("list")
def ports_list() -> None:
    manage_ports.list_ports()


@ports.command("kill")
@click.option("--force", "force_kill", is_flag=True, help="Use SIGKILL instead of SIGTERM.")
def ports_kill(force_kill: bool) -> None:
    manage_ports.kill_ports(force_kill)


@app.group()
def addons() -> None:
    """Run per-add-on just recipes."""


@addons.command("run")
@click.argument("recipe")
@click.argument("addons", nargs=-1)
def addons_run(recipe: str, addons: tuple[str, ...]) -> None:
    addons_runner.run_recipes(recipe, addons)


@addons.command("deploy")
@click.argument("addons", nargs=-1)
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
@click.option("--dry-run", is_flag=True, help="Print commands without executing.")
def addons_deploy(addons: tuple[str, ...], ha_host: str, ha_port: int, ha_user: str, verbose: bool, dry_run: bool) -> None:
    """Deploy multiple add-ons with enhanced error handling and progress tracking."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.console import Console

    console = Console()

    # Resolve addons to deploy
    addon_dirs = addons_runner._resolve_addons(addons)
    addon_names = [addon_dir.name for addon_dir in addon_dirs]

    if not addon_names:
        console.print("[yellow]No add-ons to deploy[/yellow]")
        return

    if dry_run:
        console.print(f"[bold]🔍 Dry Run: Would deploy {len(addon_names)} add-on(s):[/bold]")
        for name in addon_names:
            console.print(f"  • {name}")
        console.print(f"\n[yellow]This is a dry run - no changes would be made[/yellow]")

        # Show what each addon would do
        for name in addon_names:
            try:
                addon_builder.deploy_addon(name, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=True, verbose=verbose)
                console.print()
            except Exception as e:
                console.print(f"[red]Error planning deployment for {name}: {e}[/red]")
        return

    # Real deployment with progress tracking
    console.print(f"[bold]🚀 Deploying {len(addon_names)} add-on(s) to {ha_host}...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    ) as progress:

        deploy_task = progress.add_task("Deploying add-ons...", total=len(addon_names))

        for i, name in enumerate(addon_names):
            progress.update(deploy_task, description=f"Deploying {name}...")

            try:
                addon_builder.deploy_addon(name, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=False, verbose=verbose)
                progress.update(deploy_task, advance=1)
                if verbose:
                    console.print(f"  ✅ {name} deployed successfully")
            except Exception as e:
                progress.update(deploy_task, advance=1)
                console.print(f"  ❌ {name} failed: {e}")
                if not verbose:
                    console.print(f"     Run with --verbose for more details")
                # Continue with other addons instead of failing completely

    console.print(f"[green]✅ Batch deployment completed[/green]")


@addons.command("deploy")
@click.argument("addons", nargs=-1)
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print commands without executing.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
def addons_deploy(addons: tuple[str, ...], ha_host: str, ha_port: int, ha_user: str, dry_run: bool, verbose: bool) -> None:
    """Deploy multiple add-ons with enhanced error handling and progress tracking."""
    addons_runner.run_enhanced_deployment(addons, ha_host, ha_port, ha_user, dry_run, verbose)


@app.command(name="dev")
def dev_cmd() -> None:
    """Run all add-ons locally for development."""
    exit_code = dev_mod.run_dev()
    raise SystemExit(exit_code)


@app.group()
def hook() -> None:
    """Run per-add-on hooks."""


@hook.command("run")
@click.argument("addon")
@click.argument("hook")
@click.option("--if-missing-ok", is_flag=True, help="Exit 0 if the hook is missing.")
def hook_run(addon: str, hook: str, if_missing_ok: bool) -> None:
    ok = hooks.run_hook(addon, hook, if_missing_ok=if_missing_ok)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    app()
