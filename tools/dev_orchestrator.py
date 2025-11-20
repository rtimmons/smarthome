#!/usr/bin/env python3
"""
Development orchestrator for running all Home Assistant add-ons locally.

This tool discovers add-ons from */addon.yaml files, resolves dependencies,
and launches services with appropriate environment variables and log multiplexing.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import signal
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parents[1]
console = Console()

# Color palette for service logs
SERVICE_COLORS = [
    "cyan",
    "green",
    "yellow",
    "magenta",
    "blue",
    "bright_cyan",
    "bright_green",
    "bright_yellow",
]


class AddonConfig:
    """Represents a single addon's configuration."""

    def __init__(self, key: str, yaml_path: Path, data: Dict[str, Any]):
        self.key = key
        self.yaml_path = yaml_path
        self.addon_dir = yaml_path.parent
        self.data = data

        # Derive source directory
        if "source_subdir" in data:
            self.source_dir = self.addon_dir / data["source_subdir"]
        else:
            self.source_dir = self.addon_dir

        self.slug = data.get("slug", key)
        self.name = data.get("name", key)
        self.port = self._get_port()
        self.is_python = data.get("python", False)
        self.run_env = data.get("run_env", [])
        self.tests = data.get("tests", [])

    def _get_port(self) -> Optional[int]:
        """Extract the primary port from the ports config."""
        ports = self.data.get("ports", {})
        if ports:
            return int(next(iter(ports.keys())))
        return None

    def get_dependencies(self) -> Set[str]:
        """
        Determine which other addons this one depends on based on URLs in run_env.

        For example, if SONOS_BASE_URL references node-sonos-http-api, this addon
        depends on node-sonos-http-api.
        """
        deps = set()
        for env_spec in self.run_env:
            default_val = env_spec.get("default", "")
            # Look for references to other addons in URLs
            # e.g., "http://local-node-sonos-http-api:5005"
            if "local-node-sonos-http-api" in default_val:
                deps.add("node-sonos-http-api")
            if "local-sonos-api" in default_val:
                deps.add("sonos-api")
            if "local-grid-dashboard" in default_val:
                deps.add("grid-dashboard")
        return deps

    def build_env_vars(self) -> Dict[str, str]:
        """Build environment variables for local development."""
        env = os.environ.copy()

        # For Python services, help cairocffi find cairo library on macOS
        if self.is_python:
            # Add Homebrew library paths for cairo
            if shutil.which("brew"):
                try:
import subprocess
                    brew_prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
                    cairo_lib = f"{brew_prefix}/lib"

                    # Set library path for cairocffi
                    if "DYLD_LIBRARY_PATH" in env:
                        env["DYLD_LIBRARY_PATH"] = f"{cairo_lib}:{env['DYLD_LIBRARY_PATH']}"
                    else:
                        env["DYLD_LIBRARY_PATH"] = cairo_lib
                except:
                    pass  # If brew command fails, continue without setting paths

        # Add base NODE_OPTIONS if needed
        if not self.is_python:
            node_opts = self.data.get("environment", {}).get("NODE_OPTIONS", "")
            if node_opts:
                env["NODE_OPTIONS"] = node_opts

        # Process run_env specifications
        for env_spec in self.run_env:
            env_name = env_spec["env"]

            if "value" in env_spec:
                # Static value
                env[env_name] = str(env_spec["value"])
            elif "from_option" in env_spec:
                # Use default value, localizing URLs
                default = env_spec.get("default", "")
                # Convert production URLs to localhost
                default = default.replace("http://local-node-sonos-http-api:5005", "http://localhost:5005")
                default = default.replace("http://local-sonos-api:5006", "http://localhost:5006")
                default = default.replace("http://local-grid-dashboard:3000", "http://localhost:3000")
                default = default.replace("/share/printer-labels", "/tmp/printer-labels")

                if default or not env_spec.get("optional", False):
                    env[env_name] = default

        return env

    def get_working_dir(self) -> Path:
        """Get the working directory for running this service."""
        # Special case for node-sonos-http-api - run from cloned upstream
        if self.key == "node-sonos-http-api":
            upstream_dir = self.source_dir / "node-sonos-http-api"
            if upstream_dir.exists():
                return upstream_dir
        return self.source_dir

    def get_start_command(self) -> List[str]:
        """Determine the command to start this addon in dev mode."""
        if self.is_python:
            # Python service - check for script in pyproject.toml
            pyproject_path = self.source_dir / "pyproject.toml"
            if pyproject_path.exists():
                import tomli
                data = tomli.loads(pyproject_path.read_text())
                scripts = data.get("project", {}).get("scripts", {})
                if scripts:
                    # Use the first script (usually the main one)
                    script_name = next(iter(scripts.keys()))
                    if shutil.which("uv"):
                        return ["uv", "run", script_name]
                    else:
                        return ["python", "-m", scripts[script_name].replace(":", ".")]

            # Fallback to python_module
            module = self.data.get("python_module", "")
            if module:
                return ["python", "-m", module.replace(":", ".")]

            raise ValueError(f"Python addon {self.key} has no runnable script")
        else:
            # Node service - prefer dev script if available
            package_json = self.source_dir / "package.json"
            if package_json.exists():
                # Check if there's a dev script
                import json
                pkg_data = json.loads(package_json.read_text())
                scripts = pkg_data.get("scripts", {})
                if "dev" in scripts:
                    return ["npm", "run", "dev"]
                elif "start:dev" in scripts:
                    return ["npm", "run", "start:dev"]
                elif "start" in scripts:
                    return ["npm", "start"]

            # Special case for node-sonos-http-api - needs upstream repo
            if self.key == "node-sonos-http-api":
                # Check if upstream is cloned
                upstream_dir = self.source_dir / "node-sonos-http-api"
                if not upstream_dir.exists():
                    raise ValueError(
                        f"Upstream repo not found. See docs/dev-setup.md for instructions.\n"
                        f"   Quick fix: cd {self.source_dir} && "
                        f"git clone https://github.com/jishi/node-sonos-http-api.git"
                    )
                # Run from the cloned repo directory
                return ["npm", "start"]

            return ["npm", "start"]

    def __repr__(self) -> str:
        return f"AddonConfig({self.key}, port={self.port})"


class AddonDiscovery:
    """Discovers and manages addon configurations."""

    @staticmethod
    def discover() -> Dict[str, AddonConfig]:
        """Discover all addons from */addon.yaml files."""
        addons = {}
        for yaml_path in REPO_ROOT.glob("*/addon.yaml"):
            addon_dir = yaml_path.parent
            key = addon_dir.name

            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if data:
                    addons[key] = AddonConfig(key, yaml_path, data)
            except Exception as e:
                console.print(f"[red]Error loading {yaml_path}:[/red] {e}")
                continue

        return addons

    @staticmethod
    def resolve_startup_order(addons: Dict[str, AddonConfig]) -> List[str]:
        """
        Resolve startup order based on dependencies.
        Returns a list of addon keys in the order they should start.
        """
        # Build dependency graph
        graph = {key: addon.get_dependencies() for key, addon in addons.items()}

        # Topological sort
        ordered = []
        visited = set()
        temp_visited = set()

        def visit(key: str):
            if key in temp_visited:
                raise ValueError(f"Circular dependency detected involving {key}")
            if key in visited:
                return

            temp_visited.add(key)
            for dep in graph.get(key, set()):
                if dep in addons:  # Only visit if dependency exists
                    visit(dep)
            temp_visited.remove(key)
            visited.add(key)
            ordered.append(key)

        for key in addons.keys():
            if key not in visited:
                visit(key)

        return ordered


def port_is_available(port: int) -> bool:
    """Return True if nothing is listening on the given TCP port."""
    if not port or port <= 0:
        return True

    def _can_connect(host: str) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            return False

    # If we can connect, something is already bound.
    if _can_connect("127.0.0.1") or _can_connect("::1"):
        return False

    # Final sanity check: attempt to bind temporarily to detect wildcard listeners.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False

    return True


class ServiceProcess:
    """Manages a single service process with log capture."""

    def __init__(self, addon: AddonConfig, color: str):
        self.addon = addon
        self.color = color
        self.process: Optional[asyncio.subprocess.Process] = None
        self.stdout_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        self.started: bool = False
        self.failure_reason: Optional[str] = None

    def _check_prerequisites(self) -> bool:
        """Check if prerequisites are met to start this service."""
        # Check for node_modules if Node.js service
        if not self.addon.is_python:
            # Check in the working directory (might be different from source_dir for upstream clones)
            working_dir = self.addon.get_working_dir()
            node_modules = working_dir / "node_modules"
            if not node_modules.exists():
                self._log("[yellow]⚠️  node_modules not found. Run 'npm install' first.[/yellow]")
                self._log(f"[yellow]   cd {working_dir} && npm install[/yellow]")
                self.failure_reason = "Missing node_modules (run npm install)"
                return False

        # Check for venv/uv setup if Python service
        if self.addon.is_python:
            pyproject = self.addon.source_dir / "pyproject.toml"
            if pyproject.exists():
                # Check if uv lock file exists
                uv_lock = self.addon.source_dir / "uv.lock"
                if not uv_lock.exists():
                    self._log("[yellow]⚠️  uv.lock not found. Run 'uv sync' first.[/yellow]")
                    self.failure_reason = "Missing uv.lock (run uv sync)"
                    return False

        # Allow add-ons to run custom logic before starting (e.g., network checks)
        if not self._run_addon_hook("pre_start"):
            self.failure_reason = "Pre-start hook failed"
            return False

        return True

    async def start(self):
        """Start the service process."""
        self.started = False
        self.failure_reason = None

        # Check prerequisites
        if not self._check_prerequisites():
            self._log("[yellow]Skipping due to missing prerequisites[/yellow]")
            return

        try:
            cmd = self.addon.get_start_command()
        except ValueError as e:
            self._log(f"[red]Cannot start: {e}[/red]")
            self.failure_reason = str(e)
            return

        if self.addon.port and not port_is_available(self.addon.port):
            reason = f"Port {self.addon.port} is already in use. Stop the other service or change the port."
            self._log(f"[red]{reason}[/red]")
            self.failure_reason = reason
            return

        env = self.addon.build_env_vars()
        cwd = self.addon.get_working_dir()

        self._log(f"Starting: {' '.join(cmd)}")
        self._log(f"Working directory: {cwd}")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(cwd),
            )

            # Start log capture tasks
            self.stdout_task = asyncio.create_task(self._capture_output(self.process.stdout, "stdout"))
            self.stderr_task = asyncio.create_task(self._capture_output(self.process.stderr, "stderr"))
            self.started = True

        except Exception as e:
            self._log(f"[red]Failed to start: {e}[/red]")
            self.failure_reason = str(e)

    async def _capture_output(self, stream, stream_name: str):
        """Capture and display output from a stream."""
        while True:
            line = await stream.readline()
            if not line:
                break

            try:
                text = line.decode("utf-8").rstrip()
                self._log(text)
            except UnicodeDecodeError:
                # Handle binary output gracefully
                self._log(f"[Binary output on {stream_name}]")

    def _log(self, message: str):
        """Log a message with service prefix and timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{self.color}][{self.addon.key} {timestamp}][/{self.color}]"
        console.print(f"{prefix} {message}")

    def _run_addon_hook(self, hook: str) -> bool:
        """Run a local-dev hook for this add-on if it exists."""
        hooks_runner = REPO_ROOT / "tools" / "addon_hooks.py"
        if not hooks_runner.exists():
            return True

        cmd = [sys.executable, str(hooks_runner), "run", self.addon.key, hook, "--if-missing-ok"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            return True

        for stream in (result.stdout, result.stderr):
            if not stream:
                continue
            for line in stream.strip().splitlines():
                if line:
                    self._log(f"[yellow]{line}[/yellow]")

        self._log(f"[red]{hook} hook failed with exit code {result.returncode}[/red]")
        return False

    async def stop(self):
        """Stop the service process gracefully."""
        if not self.process:
            return

        self._log("Stopping...")

        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._log("[yellow]Force killing...[/yellow]")
            self.process.kill()
            await self.process.wait()

        # Cancel log tasks
        if self.stdout_task:
            self.stdout_task.cancel()
        if self.stderr_task:
            self.stderr_task.cancel()

        self._log("Stopped")


class DevOrchestrator:
    """Main orchestrator for running services."""

    def __init__(self):
        self.addons: Dict[str, AddonConfig] = {}
        self.processes: Dict[str, ServiceProcess] = {}
        self.shutdown_event = asyncio.Event()

    async def run(self) -> int:
        """Main entry point for running all services. Returns exit code."""
        # Discover addons
        console.print(Panel("[bold]🚀 Starting smart home development environment...[/bold]"))

        self.addons = AddonDiscovery.discover()
        if not self.addons:
            console.print("[red]No addons found![/red]")
            return

        console.print(f"[green]Discovered {len(self.addons)} addon(s)[/green]")

        # Show addon table
        table = Table(title="Add-ons")
        table.add_column("Name", style="cyan")
        table.add_column("Port", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Directory", style="blue")

        for addon in self.addons.values():
            addon_type = "Python" if addon.is_python else "Node.js"
            table.add_row(addon.name, str(addon.port or "N/A"), addon_type, str(addon.source_dir))

        console.print(table)

        # Resolve startup order
        try:
            startup_order = AddonDiscovery.resolve_startup_order(self.addons)
            console.print(f"[cyan]Startup order:[/cyan] {' → '.join(startup_order)}")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            return

        # Check for port conflicts before starting any process
        conflicts = self._find_port_conflicts()
        if conflicts:
            console.print("[red]Cannot start dev environment: port conflicts detected.[/red]")
            conflict_table = Table(show_header=True, header_style="bold red")
            conflict_table.add_column("Service", style="cyan")
            conflict_table.add_column("Port", style="magenta")
            for addon, port in conflicts:
                conflict_table.add_row(addon.name, str(port))
            console.print(conflict_table)
            console.print("[yellow]Run 'just kill' to terminate background processes using these ports, then retry 'just dev'.[/yellow]")
            return 1

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start services
        console.print("\n[bold green]Starting services...[/bold green]\n")

        for i, key in enumerate(startup_order):
            addon = self.addons[key]
            color = SERVICE_COLORS[i % len(SERVICE_COLORS)]

            service = ServiceProcess(addon, color)
            self.processes[key] = service

            await service.start()
            # Small delay between starts to let services initialize
            await asyncio.sleep(2)

        running_services = [self.processes[k] for k in startup_order if self.processes[k].started]
        failed_services = [self.processes[k] for k in startup_order if not self.processes[k].started]

        console.print("\n" + "=" * 60)

        if failed_services:
            console.print("[yellow]⚠ Some services failed to launch:[/yellow]")
            failure_table = Table(show_header=True, header_style="bold red")
            failure_table.add_column("Service", style="cyan")
            failure_table.add_column("Reason", style="magenta")
            for service in failed_services:
                reason = service.failure_reason or "See logs above for details"
                failure_table.add_row(service.addon.name, reason)
            console.print(failure_table)

        exit_code = 1 if failed_services else 0

        if running_services:
            console.print("[bold green]✨ Running services[/bold green]\n")
            for service in running_services:
                addon = service.addon
                if addon.port:
                    console.print(f"   • [cyan]{addon.name:20}[/cyan] http://localhost:{addon.port}")
                else:
                    console.print(f"   • [cyan]{addon.name}[/cyan]")

            console.print("\n[yellow]Press Ctrl+C to stop all services.[/yellow]")
            console.print("=" * 60 + "\n")

            # Wait for shutdown
            await self.shutdown_event.wait()
            return exit_code
        else:
            console.print("[red]No services are running. Fix the issues above and rerun 'just dev'.[/red]")
            console.print("=" * 60 + "\n")
            return 1

    async def shutdown(self):
        """Shutdown all services gracefully."""
        if self.shutdown_event.is_set():
            return  # Already shutting down

        self.shutdown_event.set()
        console.print("\n[yellow]Shutting down all services...[/yellow]")

        # Stop in reverse order
        for key in reversed(list(self.processes.keys())):
            await self.processes[key].stop()

        console.print("[green]All services stopped.[/green]")

    def _find_port_conflicts(self) -> List[Tuple[AddonConfig, int]]:
        conflicts: List[Tuple[AddonConfig, int]] = []
        for addon in self.addons.values():
            if addon.port and not port_is_available(addon.port):
                conflicts.append((addon, addon.port))
        return conflicts


@click.command()
def main():
    """Run all Home Assistant add-ons locally for development."""
    orchestrator = DevOrchestrator()

    try:
        exit_code = asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        exit_code = 0
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
