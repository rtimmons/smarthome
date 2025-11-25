from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set

import click
import yaml

from .paths import REPO_ROOT


def _load_addon_ports() -> Dict[str, Set[int]]:
    ports: Dict[str, Set[int]] = {}
    for yaml_path in REPO_ROOT.glob("*/addon.yaml"):
        addon_name = yaml_path.parent.name
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise click.ClickException(f"Failed to read {yaml_path}: {exc}") from exc

        raw_ports = data.get("ports") or {}
        for raw_key in raw_ports.keys():
            port = _parse_port(raw_key)
            if port:
                ports.setdefault(addon_name, set()).add(port)
    return ports


def _parse_port(value: object) -> Optional[int]:
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value)
    if "/" in text:
        text = text.split("/", 1)[0]
    text = text.strip()
    try:
        port = int(text)
    except ValueError:
        return None
    return port if port > 0 else None


def _collect_unique_ports(port_map: Dict[str, Set[int]]) -> List[int]:
    unique: Set[int] = set()
    for values in port_map.values():
        unique.update(values)
    return sorted(unique)


def _pids_using_port(port: int) -> Set[int]:
    pids: Set[int] = set()
    for proto in ("TCP", "UDP"):
        try:
            result = subprocess.run(
                ["lsof", "-ti", f"{proto}:{port}"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise click.ClickException("'lsof' not found on PATH. Install it via Homebrew (brew install lsof).") from exc

        if result.returncode != 0:
            continue

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                pids.add(int(line))
            except ValueError:
                continue
    return pids


def _describe_pid(pid: int) -> str:
    try:
        output = subprocess.check_output(["ps", "-p", str(pid), "-o", "comm="], text=True)
        description = output.strip()
        return description or "unknown"
    except Exception:
        return "unknown"


def list_ports() -> None:
    port_map = _load_addon_ports()
    if not port_map:
        click.echo("No add-on ports discovered.")
        return

    click.echo("Add-on ports:")
    for addon in sorted(port_map.keys()):
        ports = ", ".join(str(port) for port in sorted(port_map[addon]))
        click.echo(f"  • {addon}: {ports}")


def kill_ports(force_kill: bool) -> None:
    port_map = _load_addon_ports()
    unique_ports = _collect_unique_ports(port_map)

    if not unique_ports:
        click.echo("No add-on ports discovered.")
        return

    click.echo("Scanning for processes on add-on ports...")
    killed_any = False
    found_any = False
    signal_to_send = signal.SIGKILL if force_kill else signal.SIGTERM

    for port in unique_ports:
        pids = _pids_using_port(port)
        if not pids:
            continue

        found_any = True
        click.echo(f"Port {port} is in use by: {', '.join(str(pid) for pid in sorted(pids))}")
        for pid in sorted(pids):
            try:
                os.kill(pid, signal_to_send)
                killed_any = True
                click.echo(f"  → Sent {'SIGKILL' if force_kill else 'SIGTERM'} to PID {pid} ({_describe_pid(pid)})")
            except ProcessLookupError:
                click.echo(f"  → PID {pid} no longer exists")
            except PermissionError:
                click.echo(f"  → Permission denied when trying to kill PID {pid}")
            except Exception as exc:
                click.echo(f"  → Failed to kill PID {pid}: {exc}")

    if killed_any:
        click.echo("Finished stopping processes. Rerun 'just dev' when ready.")
    elif found_any:
        click.echo("Some processes could not be terminated. Try rerunning with elevated permissions or kill them manually.")
    else:
        click.echo("No running processes were using the configured ports.")
