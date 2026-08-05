from pathlib import Path
import threading
import time

import pytest
from rich.console import Console

from talos import addons_runner
from talos.timing import DeployTimer


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


def test_ready_queue_does_not_wait_for_unrelated_wave_members(monkeypatch):
    names = (
        "grid-dashboard",
        "mongodb",
        "node-sonos-http-api",
        "printer",
        "snapshot-service",
        "sonos-api",
        "tinyurl-service",
    )
    durations = {
        "mongodb": 0.02,
        "node-sonos-http-api": 0.08,
        "snapshot-service": 0.20,
        "printer": 0.25,
        "sonos-api": 0.02,
        "tinyurl-service": 0.02,
        "grid-dashboard": 0.02,
    }
    timestamps: dict[str, dict[str, float]] = {}
    timestamp_lock = threading.Lock()

    def fake_prerequisites(*_args, **_kwargs):
        return None

    def fake_deploy(addon_name: str, *_args, **_kwargs):
        with timestamp_lock:
            timestamps[addon_name] = {"start": time.perf_counter()}
        time.sleep(durations[addon_name])
        with timestamp_lock:
            timestamps[addon_name]["finish"] = time.perf_counter()

    monkeypatch.setattr(
        addons_runner, "validate_deployment_prerequisites", fake_prerequisites
    )
    monkeypatch.setattr(addons_runner, "deploy_addon", fake_deploy)

    timer = DeployTimer(Console(), enabled=True)
    addons_runner.run_enhanced_deployment(
        names,
        "example.invalid",
        22,
        "root",
        jobs=4,
        timer=timer,
    )

    assert timestamps["printer"]["start"] < timestamps["snapshot-service"]["finish"]
    assert timestamps["tinyurl-service"]["start"] < timestamps["snapshot-service"]["finish"]
    assert timestamps["grid-dashboard"]["start"] < timestamps["printer"]["finish"]
    dispatches = [
        event["addon"] for event in timer.events if event["name"] == "addons.dispatch"
    ]
    assert set(dispatches) == set(names)


def test_ready_queue_blocks_only_failed_dependency_chain(monkeypatch):
    names = (
        "grid-dashboard",
        "mongodb",
        "node-sonos-http-api",
        "printer",
        "snapshot-service",
        "sonos-api",
        "tinyurl-service",
    )
    called: set[str] = set()
    called_lock = threading.Lock()

    monkeypatch.setattr(
        addons_runner,
        "validate_deployment_prerequisites",
        lambda *_args, **_kwargs: None,
    )

    def fake_deploy(addon_name: str, *_args, **_kwargs):
        with called_lock:
            called.add(addon_name)
        if addon_name == "mongodb":
            raise RuntimeError("database deploy failed")

    monkeypatch.setattr(addons_runner, "deploy_addon", fake_deploy)

    with pytest.raises(Exception, match="Deployment failed for 3 add-on"):
        addons_runner.run_enhanced_deployment(
            names,
            "example.invalid",
            22,
            "root",
            jobs=4,
        )

    assert "printer" not in called
    assert "tinyurl-service" not in called
    assert "grid-dashboard" in called
