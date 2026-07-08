from __future__ import annotations

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
