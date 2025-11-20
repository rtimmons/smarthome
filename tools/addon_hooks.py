#!/usr/bin/env python3
"""Utility for running local development lifecycle hooks for add-ons."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_SUBDIR = Path("local-dev") / "hooks"


def _resolve_hook(addon_dir: Path, hook: str) -> Path | None:
    base = addon_dir / HOOKS_SUBDIR
    candidates = [
        base / hook,
        base / f"{hook}.sh",
        base / f"{hook}.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_hook(addon: str, hook: str, if_missing_ok: bool) -> int:
    """Run a specific hook for an add-on."""
    addon_dir = REPO_ROOT / addon
    if not addon_dir.exists():
        message = f"Addon directory '{addon}' not found at {addon_dir}."
        if if_missing_ok:
            return 0
        print(message, file=sys.stderr)
        return 1

    hook_path = _resolve_hook(addon_dir, hook)
    if not hook_path.exists():
        if if_missing_ok:
            return 0
        print(f"Hook '{hook}' not found for addon '{addon}'. Expected at {hook_path}.", file=sys.stderr)
        return 1

    if not os.access(hook_path, os.X_OK):
        print(f"Hook '{hook_path}' exists but is not executable.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("REPO_ROOT", str(REPO_ROOT))

    result = subprocess.run([str(hook_path)], cwd=str(addon_dir), env=env, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local-dev hooks for add-ons.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a hook for a specific add-on.")
    run_parser.add_argument("addon", help="Addon directory name (e.g., node-sonos-http-api).")
    run_parser.add_argument("hook", help="Hook name (e.g., pre_setup, pre_start).")
    run_parser.add_argument(
        "--if-missing-ok",
        action="store_true",
        help="Exit success if the add-on or hook is missing.",
    )

    args = parser.parse_args()

    if args.command == "run":
        return run_hook(args.addon, args.hook, args.if_missing_ok)

    return 0


if __name__ == "__main__":
    sys.exit(main())
