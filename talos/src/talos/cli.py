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
def addon_deploy(addon: str, ha_host: str, ha_port: int, ha_user: str, dry_run: bool) -> None:
    addon_builder.run_deploy(addon, ha_host=ha_host, ha_port=ha_port, ha_user=ha_user, dry_run=dry_run)


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
