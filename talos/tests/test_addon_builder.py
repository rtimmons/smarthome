from __future__ import annotations

import pytest

from talos import addon_builder


def test_discover_addons_finds_known_services():
    addons = addon_builder.discover_addons()
    # Expect our core add-ons to be present; this guards against path mistakes.
    for name in ("grid-dashboard", "sonos-api", "mongodb", "printer"):
        assert name in addons


def test_build_context_reads_runtime_versions():
    addons = addon_builder.discover_addons()
    first = next(iter(addons.keys()))
    ctx = addon_builder.build_context(first, addons)
    addon = ctx["addon"]
    assert "node_version" in addon and addon["node_version"]
    assert "python_version" in addon and addon["python_version"]


def test_build_context_supports_per_addon_node_version():
    addons = addon_builder.discover_addons()
    ctx = addon_builder.build_context("node-sonos-http-api", addons)
    assert ctx["addon"]["node_version"] == "22.21.1"
    assert ctx["addon"]["node_major"] == "22"


def test_generated_mongodb_configuration_is_system_cold_backup():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("mongodb", addons)
    rendered = addon_builder.render_template(
        addon_builder.jinja_env(), "config.yaml.j2", context
    )
    assert "startup: system" in rendered
    assert "backup: cold" in rendered


def test_generated_configuration_supports_backup_hooks_and_excludes():
    addons = addon_builder.discover_addons()
    addons["printer"] = {
        **addons["printer"],
        "backup": "hot",
        "backup_pre": "echo pre",
        "backup_post": "echo post",
        "backup_exclude": ["cache", "tmp/*"],
    }
    context = addon_builder.build_context("printer", addons)
    rendered = addon_builder.render_template(
        addon_builder.jinja_env(), "config.yaml.j2", context
    )
    assert "backup: hot" in rendered
    assert 'backup_pre: "echo pre"' in rendered
    assert 'backup_post: "echo post"' in rendered
    assert "- cache" in rendered
    assert "- tmp/*" in rendered


def test_cold_backup_rejects_hot_backup_hooks():
    addons = addon_builder.discover_addons()
    addons["mongodb"] = {**addons["mongodb"], "backup_pre": "unsafe"}
    with pytest.raises(Exception, match="cannot combine"):
        addon_builder.build_context("mongodb", addons)


def test_remote_deploy_script_uses_quiet_wrapper_without_fixed_reload_sleep():
    script = addon_builder.render_remote_deploy_script(
        slug="grid_dashboard",
        remote_tar="/root/grid_dashboard.tar.gz",
        remote_addon_dir="/addons/grid_dashboard",
        remote_addons_dir="/addons",
        verbose=False,
    )

    assert 'VERBOSE="false"' in script
    assert "run_quiet ha addons reload" in script
    assert "sleep 2" not in script
    assert "need_port_mapping" not in script
