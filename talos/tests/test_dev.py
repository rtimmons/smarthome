from __future__ import annotations

import asyncio
from pathlib import Path

from talos.dev import AddonConfig, ServiceProcess


def _make_addon(key: str, port: int) -> AddonConfig:
    return AddonConfig(
        key=key,
        yaml_path=Path(f"{key}/addon.yaml"),
        data={
            "name": key,
            "ports": {str(port): port},
        },
    )


def test_wait_for_port_listener_succeeds_when_port_becomes_ready(monkeypatch):
    service = ServiceProcess(_make_addon("mongodb", 27017), "cyan")

    class RunningProcess:
        returncode = None

    service.process = RunningProcess()

    checks = iter([False, False, True])
    monkeypatch.setattr("talos.dev.port_is_listening", lambda _port: next(checks))

    async def _run() -> bool:
        return await service._wait_for_port_listener(
            27017,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
        )

    assert asyncio.run(_run()) is True


def test_wait_for_port_listener_fails_when_process_exits(monkeypatch):
    service = ServiceProcess(_make_addon("mongodb", 27017), "cyan")

    class ExitedProcess:
        returncode = 1

    service.process = ExitedProcess()
    monkeypatch.setattr("talos.dev.port_is_listening", lambda _port: False)

    async def _run() -> bool:
        return await service._wait_for_port_listener(
            27017,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
        )

    assert asyncio.run(_run()) is False


def test_canonical_mongodb_hostname_is_a_dependency_and_rewrites_for_local_dev():
    addon = AddonConfig(
        key="printer",
        yaml_path=Path("printer/addon.yaml"),
        data={
            "name": "printer",
            "ports": {"8099": 8099},
            "run_env": [
                {
                    "env": "MONGODB_URL",
                    "from_option": "mongodb_url",
                    "default": "mongodb://local-mongodb.local.hass.io:27017/smarthome",
                }
            ],
        },
    )

    assert addon.get_dependencies() == {"mongodb"}
    assert addon.build_env_vars()["MONGODB_URL"] == "mongodb://localhost:27017/smarthome"
