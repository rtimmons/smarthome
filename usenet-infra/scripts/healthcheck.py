#!/usr/bin/env python3
"""Small, dependency-free health check for the cloud and QNAP roles."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from catalogctl import CatalogError, Settings, read_json_records


@dataclass
class Check:
    name: str
    status: str
    detail: str


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    # Authenticated local requests must not forward keys to a redirect or an
    # environment-configured proxy. Never include requests/exceptions in output.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
    return opener.open(request, timeout=10)


def get_json(url: str, *, headers: dict[str, str] | None = None, form: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(
        url, headers=headers or {},
        data=urllib.parse.urlencode(form).encode() if form is not None else None,
    )
    with open_request(request) as response:
        return json.load(response)


def request_failure(exc: Exception) -> str:
    """Only fixed categories and a validated status code may leave this helper."""
    if isinstance(exc, urllib.error.HTTPError) and isinstance(exc.code, int) and 100 <= exc.code <= 599:
        return f"API request rejected (HTTP {exc.code})"
    if isinstance(exc, TimeoutError):
        return "API request timed out"
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
        return "API returned an invalid response"
    return "API request failed; inspect the application privately"


def app_checks() -> list[Check]:
    checks: list[Check] = []
    sab_url = os.environ.get("SABNZBD_URL", "http://127.0.0.1:8080").rstrip("/")
    sab_key = os.environ.get("SABNZBD_API_KEY", "")
    if sab_key:
        try:
            payload = get_json(f"{sab_url}/api", form={"mode": "fullstatus", "output": "json", "apikey": sab_key})
            if not isinstance(payload, dict) or not isinstance(payload.get("status"), dict):
                raise ValueError("invalid response")
            warnings = get_json(f"{sab_url}/api", form={"mode": "warnings", "output": "json", "apikey": sab_key}).get("warnings")
            if not isinstance(warnings, list) or any(not isinstance(item, dict) for item in warnings):
                raise ValueError("invalid response")
            errors = [item for item in warnings if str(item.get("type", "")).upper() in {"ERROR", "CRITICAL", "FATAL"}]
            lesser = [item for item in warnings if item not in errors]
            if errors:
                detail = f"{len(errors)} error(s), {len(lesser)} other warning(s); inspect SABnzbd privately"
                checks.append(Check("sabnzbd", "fail", detail))
            elif lesser:
                detail = f"{len(lesser)} warning(s); inspect SABnzbd privately"
                checks.append(Check("sabnzbd", "warn", detail))
            else:
                checks.append(Check("sabnzbd", "ok", "authenticated API reachable; no warnings"))
        except Exception as exc:
            checks.append(Check("sabnzbd", "fail", request_failure(exc)))
    else:
        checks.append(Check("sabnzbd", "warn", "SABNZBD_API_KEY is not configured"))

    prowlarr_url = os.environ.get("PROWLARR_URL", "http://127.0.0.1:9696").rstrip("/")
    prowlarr_key = os.environ.get("PROWLARR_API_KEY", "")
    if prowlarr_key:
        headers = {"X-Api-Key": prowlarr_key}
        try:
            system = get_json(f"{prowlarr_url}/api/v1/system/status", headers=headers)
            health = get_json(f"{prowlarr_url}/api/v1/health", headers=headers)
            if (not isinstance(system, dict) or not isinstance(system.get("version"), str)
                    or not isinstance(health, list) or any(not isinstance(item, dict) for item in health)):
                raise ValueError("invalid response")
            issues = [
                item
                for item in health
                if str(item.get("type", "")).lower() in {"warning", "error"}
            ]
            if issues:
                detail = f"{len(issues)} health issue(s); inspect Prowlarr privately"
                checks.append(Check("prowlarr", "fail", detail))
            else:
                checks.append(Check("prowlarr", "ok", "authenticated API reachable; no health issues"))
        except Exception as exc:
            checks.append(Check("prowlarr", "fail", request_failure(exc)))
    else:
        checks.append(Check("prowlarr", "warn", "PROWLARR_API_KEY is not configured"))
    return checks


def disk_check(name: str, path: Path, minimum_free: int) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(path)
    except OSError:
        return Check(name, "fail", "disk capacity check failed")
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
            timeout=60,
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
    except OSError:
        return Check("storage_box", "fail", "rclone could not be started")
    except (subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        try:
            subprocess.run(
                [rclone, "lsf", f"{remote}/manifests", "--max-depth", "1"],
                check=True,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            return Check(
                "storage_box",
                "warn",
                "reachable, but capacity is unavailable from rclone about",
            )
        except (OSError, subprocess.SubprocessError):
            return Check("storage_box", "fail", "remote metadata check failed")


def failure_check() -> Check:
    state_root = Path(os.environ.get("CATALOG_STATE_ROOT", "/data/state"))
    try:
        failures = [item for item in read_json_records(state_root / "failures") if not item.get("resolved_at")]
    except (CatalogError, OSError, ValueError, TypeError, AttributeError):
        return Check("catalog_failures", "fail", "catalog failure records could not be read")
    if failures:
        return Check("catalog_failures", "fail", f"{len(failures)} unresolved failure(s); inspect the catalog dashboard privately")
    return Check("catalog_failures", "ok", "none")


def qnap_transfer_check() -> Check:
    try:
        # Only QNAP uses operation records. Cloud installations may still run
        # the earlier catalog implementation and need no migration for health.
        from catalogctl import operation_records

        settings = Settings.from_env()
        operations = operation_records(settings)
        failed = [item for item in operations if item["status"] in {"failed", "stalled"}]
        handled = {item["item"] for item in operations if item["active"] or item["status"] in {"failed", "stalled"}}
        abandoned = [path.name for path in settings.staging_root.glob("*.partial") if path.name.removesuffix(".partial") not in handled]
        if failed or abandoned:
            return Check("qnap_transfers", "fail", f"{len(failed)} failed or stalled operation(s); {len(abandoned)} interrupted staging item(s); inspect the catalog dashboard privately")
        active = [item for item in operations if item["active"] and item["operation"] == "pull"]
        return Check("qnap_transfers", "ok", f"{len(active)} active pull(s); no failed or interrupted pulls")
    except ImportError:
        return Check("qnap_transfers", "fail", "catalog implementation must be updated to check transfer state")
    except (CatalogError, OSError, ValueError, TypeError, KeyError):
        return Check("qnap_transfers", "fail", "transfer state could not be read")


def dashboard_check() -> Check:
    url = os.environ.get("QNAP_DASHBOARD_HEALTH_URL", "")
    if not url:
        return Check("catalog_dashboard", "warn", "QNAP_DASHBOARD_HEALTH_URL is not configured")
    try:
        with open_request(urllib.request.Request(url)) as response:
            if response.status != 200:
                return Check("catalog_dashboard", "fail", "readiness endpoint returned an unsuccessful status")
        return Check("catalog_dashboard", "ok", "readiness endpoint reachable; authentication requires a separate acceptance test")
    except Exception as exc:
        return Check("catalog_dashboard", "fail", request_failure(exc))


def dashboard_data_check() -> Check:
    path = Path(os.environ.get("CATALOG_DASHBOARD_STATUS_PATH", "/data/dashboard/status.json"))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        refresh_seconds = int(os.environ.get("CATALOG_DASHBOARD_REFRESH_SECONDS", "60"))
        age = time.time() - float(payload["updated_at"])
        if not math.isfinite(age):
            raise ValueError("invalid heartbeat")
        if payload.get("error"):
            return Check("catalog_dashboard_data", "fail", "catalog refresh failed; inspect the dashboard privately")
        if age < -30 or age > max(180, 3 * refresh_seconds + 300):
            return Check("catalog_dashboard_data", "fail", f"catalog refresh heartbeat is stale ({age:.0f} seconds old)")
        if not isinstance(payload.get("snapshot"), dict):
            return Check("catalog_dashboard_data", "fail", "refresh has no catalog snapshot")
        return Check("catalog_dashboard_data", "ok", f"catalog refreshed {max(0, age):.0f} seconds ago")
    except (OSError, ValueError, KeyError, TypeError):
        return Check("catalog_dashboard_data", "fail", "catalog refresh heartbeat could not be read")


def collect_checks() -> list[Check]:
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
        checks.extend([qnap_transfer_check(), dashboard_check(), dashboard_data_check()])
        checks.append(
            disk_check(
                "qnap_cache",
                Path(os.environ.get("CATALOG_LOCAL_ROOT", "/data/library")),
                int(os.environ.get("CATALOG_MIN_FREE_BYTES", str(10 * 1024**3))),
            )
        )
    else:
        checks.append(Check("role", "fail", "unsupported CATALOG_ROLE"))
    return checks


def main() -> int:
    try:
        checks = collect_checks()
    except Exception:
        # Malformed environment values and unexpected response shapes must not
        # escape as tracebacks, which may embed requests or secret-bearing paths.
        checks = [Check("healthcheck", "fail", "health check configuration or response is invalid")]

    if "--json" in sys.argv[1:]:
        print(json.dumps([asdict(check) for check in checks], indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"{check.status.upper():4} {check.name:20} {check.detail}")
    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
