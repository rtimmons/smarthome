from __future__ import annotations

import os

import click

from . import addon_builder, addons_runner, dev as dev_mod, external_addon, hass_config, hooks, manage_ports
from .timing import DeployTimer

DEFAULT_JOBS = max(1, os.cpu_count() or 1)


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


@addon.command("package-external")
@click.option("--app-dir", default=".", type=click.Path(file_okay=False, dir_okay=True), show_default=True, help="External app repository root.")
@click.option("--addon-dir", default="ha-addon", type=click.Path(file_okay=False, dir_okay=True), show_default=True, help="Directory containing config.yaml, Dockerfile, and run.sh.")
@click.option("--output-dir", default=None, type=click.Path(file_okay=False, dir_okay=True), help="Directory for the packaged tarball.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
def addon_package_external(app_dir: str, addon_dir: str, output_dir: str | None, verbose: bool) -> None:
    """Package an external app repository as a Home Assistant local add-on."""
    archive = external_addon.package_external_addon(app_dir, addon_dir, output_dir=output_dir, verbose=verbose)
    click.echo(str(archive))


@addon.command("deploy-external")
@click.option("--app-dir", default=".", type=click.Path(file_okay=False, dir_okay=True), show_default=True, help="External app repository root.")
@click.option("--addon-dir", default="ha-addon", type=click.Path(file_okay=False, dir_okay=True), show_default=True, help="Directory containing config.yaml, Dockerfile, and run.sh.")
@click.option("--output-dir", default=None, type=click.Path(file_okay=False, dir_okay=True), help="Directory for the packaged tarball.")
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print operations without executing.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
def addon_deploy_external(
    app_dir: str,
    addon_dir: str,
    output_dir: str | None,
    ha_host: str,
    ha_port: int,
    ha_user: str,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Deploy an external app repository as a Home Assistant local add-on."""
    try:
        external_addon.deploy_external_addon(
            app_dir,
            addon_dir,
            ha_host=ha_host,
            ha_port=ha_port,
            ha_user=ha_user,
            output_dir=output_dir,
            dry_run=dry_run,
            verbose=verbose,
        )
    except external_addon.DeploymentError as e:
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
@click.option("--dry-run", is_flag=True, help="Print commands without executing.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
@click.option("--verify", is_flag=True, help="Run optional local add-on build/test/container recipes before deploying.")
@click.option("--jobs", type=int, default=DEFAULT_JOBS, show_default=True, help="Max parallel build jobs.")
@click.option("--metrics-json", type=click.Path(dir_okay=False), default=None, help="Write deploy timing events as JSON.")
@click.option("--no-timings", is_flag=True, help="Suppress deploy timing summary.")
def addons_deploy(
    addons: tuple[str, ...],
    ha_host: str,
    ha_port: int,
    ha_user: str,
    dry_run: bool,
    verbose: bool,
    verify: bool,
    jobs: int,
    metrics_json: str | None,
    no_timings: bool
) -> None:
    """Deploy multiple add-ons with enhanced error handling and progress tracking."""
    timer = DeployTimer(addons_runner.console, enabled=not no_timings)
    addons_runner.run_enhanced_deployment(addons, ha_host, ha_port, ha_user, dry_run, verbose, jobs=jobs, verify=verify, timer=timer)
    timer.print_summary()
    timer.write_json(metrics_json)


@app.group(name="config")
def config_cmd() -> None:
    """Home Assistant config deploy helpers."""


@config_cmd.command("precheck")
@click.option("--verbose", "-v", is_flag=True, help="Show command output.")
def config_precheck(verbose: bool) -> None:
    hass_config.precheck(verbose=verbose)


@config_cmd.command("needed")
@click.option("--verbose", "-v", is_flag=True, help="Show decision details.")
def config_needed(verbose: bool) -> None:
    click.echo("true" if hass_config.deploy_needed(verbose=verbose) else "false")


@config_cmd.command("apply")
@click.option("--verbose", "-v", is_flag=True, help="Show command output.")
def config_apply(verbose: bool) -> None:
    hass_config.apply(verbose=verbose)


@app.command("deploy")
@click.argument("addons", nargs=-1)
@click.option("--ha-host", envvar="HA_HOST", default="homeassistant.local", show_default=True)
@click.option("--ha-port", envvar="HA_PORT", default=22, type=int, show_default=True)
@click.option("--ha-user", envvar="HA_USER", default="root", show_default=True)
@click.option("--dry-run", is_flag=True, help="Print operations without executing.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
@click.option("--verify", is_flag=True, help="Run optional local add-on build/test/container recipes before deploying.")
@click.option("--jobs", type=int, default=DEFAULT_JOBS, show_default=True, help="Max parallel build jobs.")
@click.option("--skip-config", is_flag=True, help="Skip Home Assistant config precheck/apply.")
@click.option("--metrics-json", type=click.Path(dir_okay=False), default=None, help="Write deploy timing events as JSON.")
@click.option("--no-timings", is_flag=True, help="Suppress deploy timing summary.")
def deploy_cmd(
    addons: tuple[str, ...],
    ha_host: str,
    ha_port: int,
    ha_user: str,
    dry_run: bool,
    verbose: bool,
    verify: bool,
    jobs: int,
    skip_config: bool,
    metrics_json: str | None,
    no_timings: bool,
) -> None:
    """Deploy Home Assistant configs and add-ons."""
    timer = DeployTimer(addons_runner.console, enabled=not no_timings)

    if dry_run:
        if not skip_config:
            click.echo("Home Assistant configs would be prechecked and deployed if changed.")
        addons_runner.run_enhanced_deployment(addons, ha_host, ha_port, ha_user, dry_run=True, verbose=verbose, jobs=jobs, verify=verify, timer=timer)
        timer.print_summary()
        timer.write_json(metrics_json)
        return

    if not skip_config:
        hass_config.precheck(verbose=verbose, timer=timer)

    addons_runner.run_enhanced_deployment(addons, ha_host, ha_port, ha_user, dry_run=False, verbose=verbose, jobs=jobs, verify=verify, timer=timer)

    if not skip_config:
        if hass_config.deploy_needed(verbose=verbose, timer=timer):
            hass_config.console.print("\n🏠 Deploying Home Assistant configs...")
            hass_config.apply(verbose=verbose, timer=timer)
        else:
            hass_config.console.print("\n🏠 Home Assistant configs unchanged; skipping config deploy and restart.")

    timer.print_summary()
    timer.write_json(metrics_json)


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
