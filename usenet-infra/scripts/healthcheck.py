#!/usr/bin/env python3
"""Small, dependency-free health check for the cloud and QNAP roles."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Check:
    name: str
    status: str
    detail: str


def get_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def app_checks() -> list[Check]:
    checks: list[Check] = []
    sab_url = os.environ.get("SABNZBD_URL", "http://127.0.0.1:8080").rstrip("/")
    sab_key = os.environ.get("SABNZBD_API_KEY", "")
    if sab_key:
        status_query = urllib.parse.urlencode(
            {"mode": "fullstatus", "output": "json", "apikey": sab_key}
        )
        warnings_query = urllib.parse.urlencode(
            {"mode": "warnings", "output": "json", "apikey": sab_key}
        )
        try:
            payload = get_json(f"{sab_url}/api?{status_query}")
            warnings = get_json(f"{sab_url}/api?{warnings_query}").get("warnings", [])
            state = payload.get("status", {}).get("status", "reachable")
            errors = [item for item in warnings if str(item.get("type", "")).upper() == "ERROR"]
            lesser = [item for item in warnings if item not in errors]
            if errors:
                detail = "; ".join(str(item.get("text", item)) for item in errors[-3:])
                checks.append(Check("sabnzbd", "fail", detail))
            elif lesser:
                detail = "; ".join(str(item.get("text", item)) for item in lesser[-3:])
                checks.append(Check("sabnzbd", "warn", detail))
            else:
                checks.append(Check("sabnzbd", "ok", str(state)))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            checks.append(Check("sabnzbd", "fail", str(exc)))
    else:
        checks.append(Check("sabnzbd", "warn", "SABNZBD_API_KEY is not configured"))

    prowlarr_url = os.environ.get("PROWLARR_URL", "http://127.0.0.1:9696").rstrip("/")
    prowlarr_key = os.environ.get("PROWLARR_API_KEY", "")
    if prowlarr_key:
        headers = {"X-Api-Key": prowlarr_key}
        try:
            system = get_json(f"{prowlarr_url}/api/v1/system/status", headers=headers)
            health = get_json(f"{prowlarr_url}/api/v1/health", headers=headers)
            issues = [
                item
                for item in health
                if str(item.get("type", "")).lower() in {"warning", "error"}
            ]
            if issues:
                detail = "; ".join(str(item.get("message", item)) for item in issues)
                checks.append(Check("prowlarr", "fail", detail))
            else:
                checks.append(Check("prowlarr", "ok", str(system.get("version", "reachable"))))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            checks.append(Check("prowlarr", "fail", str(exc)))
    else:
        checks.append(Check("prowlarr", "warn", "PROWLARR_API_KEY is not configured"))
    return checks


def disk_check(name: str, path: Path, minimum_free: int) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return Check(name, "fail", str(exc))
    status = "ok" if usage.free >= minimum_free else "fail"
    return Check(
        name,
        status,
        f"{usage.free} bytes free of {usage.total}; minimum is {minimum_free}",
    )


def storage_check() -> Check:
    remote = os.environ.get("CATALOG_REMOTE", "").rstrip("/")
    if not remote:
        return Check("storage_box", "warn", "CATALOG_REMOTE is not configured")
    rclone = os.environ.get("RCLONE_BIN", "rclone")
    try:
        result = subprocess.run(
            [rclone, "about", remote, "--json"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        payload = json.loads(result.stdout)
        total = int(payload.get("total", 0))
        used = int(payload.get("used", 0))
        if total > 0:
            fraction = used / total
            threshold = float(os.environ.get("STORAGE_WARN_FRACTION", "0.80"))
            status = "warn" if fraction >= threshold else "ok"
            return Check(
                "storage_box",
                status,
                f"reachable; {used} of {total} bytes used ({fraction:.1%})",
            )
        return Check("storage_box", "ok", "reachable; capacity was not reported")
    except FileNotFoundError as exc:
        return Check("storage_box", "fail", str(exc))
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as about_exc:
        try:
            subprocess.run(
                [rclone, "lsf", f"{remote}/manifests", "--max-depth", "1"],
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            return Check(
                "storage_box",
                "warn",
                f"reachable, but capacity is unavailable from rclone about: {about_exc}",
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            return Check("storage_box", "fail", str(exc))


def failure_check() -> Check:
    state_root = Path(os.environ.get("CATALOG_STATE_ROOT", "/data/state"))
    failures = list((state_root / "failures").glob("*.json"))
    if failures:
        return Check("catalog_failures", "fail", f"{len(failures)} recorded failure(s)")
    return Check("catalog_failures", "ok", "none")


def main() -> int:
    role = os.environ.get("CATALOG_ROLE", "cloud").lower()
    checks = [storage_check(), failure_check()]
    if role == "cloud":
        checks.extend(app_checks())
        checks.append(
            disk_check(
                "vm_scratch",
                Path(os.environ.get("CATALOG_PROMOTION_ROOT", "/srv/usenet/downloads/complete")),
                int(os.environ.get("SCRATCH_MIN_FREE_BYTES", str(30 * 1024**3))),
            )
        )
    elif role == "qnap":
        checks.append(
            disk_check(
                "qnap_cache",
                Path(os.environ.get("CATALOG_LOCAL_ROOT", "/data/library")),
                int(os.environ.get("CATALOG_MIN_FREE_BYTES", str(10 * 1024**3))),
            )
        )
    else:
        checks.append(Check("role", "fail", f"unsupported CATALOG_ROLE={role}"))

    if "--json" in sys.argv[1:]:
        print(json.dumps([asdict(check) for check in checks], indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"{check.status.upper():4} {check.name:20} {check.detail}")
    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
