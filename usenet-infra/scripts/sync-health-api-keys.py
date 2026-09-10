#!/usr/bin/env python3
"""Copy locally generated application API keys into the protected health env."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET


def sabnzbd_api_key(path: Path) -> str:
    # SABnzbd writes metadata such as ``__version__`` before its first INI
    # section, which strict INI parsers reject. Its settings remain simple
    # key/value lines, so find the exact api_key entry without interpreting
    # unrelated values.
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "api_key" and value.strip():
            return value.strip()
    raise ValueError("SABnzbd api_key is missing")


def prowlarr_api_key(path: Path) -> str:
    value = (ET.parse(path).getroot().findtext("ApiKey") or "").strip()
    if not value:
        raise ValueError("Prowlarr ApiKey is missing")
    return value


def render_env(source: Path, destination: Path, values: dict[str, str]) -> bool:
    original = destination.read_text(encoding="utf-8") if destination.exists() else ""
    baseline = source.read_text(encoding="utf-8")
    emitted: set[str] = set()
    output: list[str] = []
    for line in baseline.splitlines():
        key, separator, _ = line.partition("=")
        if separator and key in values:
            if key not in emitted:
                output.append(f"{key}={values[key]}")
                emitted.add(key)
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in values.items() if key not in emitted)
    rendered = "\n".join(output) + "\n"
    if rendered == original:
        current_mode = os.stat(destination).st_mode & 0o777
        if current_mode == 0o640:
            return False
        os.chmod(destination, 0o640)
        return True

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: sync-health-api-keys.py SAB_INI PROWLARR_XML DEFAULTS_ENV CATALOG_ENV",
            file=sys.stderr,
        )
        return 2
    sab_path, prowlarr_path, defaults_path, env_path = map(Path, argv[1:])
    changed = render_env(
        defaults_path,
        env_path,
        {
            "SABNZBD_API_KEY": sabnzbd_api_key(sab_path),
            "PROWLARR_API_KEY": prowlarr_api_key(prowlarr_path),
        },
    )
    print("updated health API keys" if changed else "health API keys already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
