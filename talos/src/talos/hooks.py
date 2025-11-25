from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import REPO_ROOT

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


def run_hook(addon: str, hook: str, if_missing_ok: bool = False) -> bool:
    """Run a specific hook for an add-on."""
    addon_dir = REPO_ROOT / addon
    if not addon_dir.exists():
        if if_missing_ok:
            return False
        raise FileNotFoundError(f"Addon directory '{addon}' not found at {addon_dir}.")

    hook_path = _resolve_hook(addon_dir, hook)
    if hook_path is None or not hook_path.exists():
        return if_missing_ok

    if not os.access(hook_path, os.X_OK):
        if if_missing_ok:
            return False
        raise PermissionError(f"Hook '{hook_path}' exists but is not executable.")

    env = os.environ.copy()
    env.setdefault("REPO_ROOT", str(REPO_ROOT))

    result = subprocess.run([str(hook_path)], cwd=str(addon_dir), env=env, check=False)
    return result.returncode == 0
