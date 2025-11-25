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
