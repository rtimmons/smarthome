from __future__ import annotations

import pathlib
import subprocess
import sys
import tomllib


def pip(*args: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", *args])


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    lock = tomllib.load((root / "uv.lock").open("rb"))
    # Filter out the local 'printer' package - it will be installed in editable mode below
    requirements = [
        f"{pkg['name']}=={pkg['version']}" for pkg in lock["package"] if pkg["name"] != "printer"
    ]

    pip("install", "--upgrade", "pip", "wheel", "setuptools")
    pip("install", *requirements)
    pip("install", "--no-cache-dir", "--force-reinstall", "cairocffi==1.7.1")
    pip("install", "ruff", "mypy")
    pip("install", "-e", str(root))


if __name__ == "__main__":
    main()
