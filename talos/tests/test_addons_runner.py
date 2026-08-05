from pathlib import Path

import pytest

from talos import addons_runner


def test_dependency_waves_parallelize_only_independent_addons():
    names = (
        "grid-dashboard",
        "mongodb",
        "node-sonos-http-api",
        "printer",
        "snapshot-service",
        "sonos-api",
        "tinyurl-service",
    )
    waves = addons_runner._dependency_waves(
        [addons_runner.REPO_ROOT / name for name in names]
    )

    assert [[path.name for path in wave] for wave in waves] == [
        ["mongodb", "node-sonos-http-api", "snapshot-service"],
        ["printer", "sonos-api", "tinyurl-service"],
        ["grid-dashboard"],
    ]


def test_dependency_waves_reject_cycles(tmp_path: Path):
    for name, dependency in (("first", "second"), ("second", "first")):
        addon_dir = tmp_path / name
        addon_dir.mkdir()
        (addon_dir / "addon.yaml").write_text(
            f"slug: {name}\ndepends_on:\n  - {dependency}\n",
            encoding="utf-8",
        )

    with pytest.raises(Exception, match="Circular add-on deployment dependencies"):
        addons_runner._dependency_waves([tmp_path / "first", tmp_path / "second"])
