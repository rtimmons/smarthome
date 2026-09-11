#!/usr/bin/env python3
"""Safe catalog promotion and selective-cache operations.

The remote object bytes are canonical.  Manifests are published only after a
verified upload, and eviction never invokes an rclone mutation command.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
CATEGORIES = ("video", "audio", "books", "software", "archives", "other")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


class CatalogError(RuntimeError):
    pass


class CatalogBusy(CatalogError):
    """A cache mutation is already running; this is not a transfer failure."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser().resolve()


def remote_join(remote: str, *parts: str) -> str:
    base = remote.rstrip("/")
    clean = [str(PurePosixPath(part)).strip("/") for part in parts]
    # SFTP remote:path is relative to the login directory; remote:/path is
    # absolute. Preserve that distinction for a subaccount rooted at catalog.
    separator = "" if base.endswith(":") and not remote.endswith("/") else "/"
    return base + separator + "/".join(clean)


def safe_id(value: str) -> str:
    value = value.strip().lower()
    if not ID_RE.fullmatch(value):
        raise CatalogError(
            "item id must be 3-128 lowercase letters, digits, dots, underscores, or hyphens"
        )
    return value


def default_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    slug = slug or "item"
    return f"{slug}-{uuid.uuid4().hex[:12]}"


def confined(path: Path, root: Path, *, allow_root: bool = False) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CatalogError(f"path escapes configured root {root}: {path}") from exc
    if not allow_root and resolved == root.resolve():
        raise CatalogError(f"refusing to operate on root path {root}")
    return resolved


def human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if amount < 1024 or unit == "PiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


@dataclass(frozen=True)
class Settings:
    remote: str
    local_root: Path
    state_root: Path
    staging_root: Path
    promotion_root: Path
    rclone: str
    transfers: int
    checkers: int
    min_free_bytes: int
    bwlimit: str = "off"

    @classmethod
    def from_env(cls) -> "Settings":
        remote = os.environ.get("CATALOG_REMOTE", "").strip()
        if not remote or ":" not in remote:
            raise CatalogError("CATALOG_REMOTE must name an rclone path such as storage:catalog")
        settings = cls(
            remote=remote,
            local_root=env_path("CATALOG_LOCAL_ROOT", "/data/library"),
            state_root=env_path("CATALOG_STATE_ROOT", "/data/state"),
            staging_root=env_path("CATALOG_STAGING_ROOT", "/data/staging"),
            promotion_root=env_path(
                "CATALOG_PROMOTION_ROOT", "/srv/usenet/downloads/complete"
            ),
            rclone=os.environ.get("RCLONE_BIN", "rclone"),
            transfers=int(os.environ.get("RCLONE_TRANSFERS", "2")),
            checkers=int(os.environ.get("RCLONE_CHECKERS", "4")),
            min_free_bytes=int(
                os.environ.get("CATALOG_MIN_FREE_BYTES", str(10 * 1024**3))
            ),
            bwlimit=os.environ.get("RCLONE_BWLIMIT", "off").strip() or "off",
        )
        if settings.min_free_bytes < 0 or settings.transfers < 1 or settings.checkers < 1:
            raise CatalogError("reserve must be nonnegative and rclone concurrency must be positive")
        if not re.fullmatch(r"(?:off|\d+(?:\.\d+)?[kKmMgGtT]?)", settings.bwlimit):
            raise CatalogError("RCLONE_BWLIMIT must be off or a bytes/second limit such as 10M")
        return settings


class Rclone:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock_fds: tuple[int, ...] = ()

    def run(self, *args: str, capture: bool = False) -> str:
        command = [self.settings.rclone, *args]
        try:
            if not capture:
                tail: deque[str] = deque(maxlen=30)
                with subprocess.Popen(
                    command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    pass_fds=self.lock_fds,
                ) as process:
                    assert process.stdout is not None
                    try:
                        for line in process.stdout:
                            print(line, end="", file=sys.stderr, flush=True)
                            tail.append(line)
                        code = process.wait()
                    except BaseException:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise
                if code:
                    raise CatalogError(f"rclone {args[0]} failed (exit {code}): {''.join(tail).strip()}")
                return ""
            result = subprocess.run(
                command,
                check=True,
                text=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                # Keep the cache locked if this process dies before its transfer
                # child exits. A retry must never race an orphaned rclone copy.
                pass_fds=self.lock_fds,
            )
        except FileNotFoundError as exc:
            raise CatalogError(f"rclone executable not found: {self.settings.rclone}") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise CatalogError(f"rclone failed ({' '.join(command)}): {detail}") from exc
        return result.stdout if capture else ""

    def read_json(self, path: str) -> dict[str, Any]:
        raw = self.run("cat", path, capture=True)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"invalid JSON at {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise CatalogError(f"manifest at {path} is not an object")
        return value

    def succeeds(self, *args: str) -> bool:
        try:
            result = subprocess.run(
                [self.settings.rclone, *args],
                check=False,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise CatalogError(f"rclone executable not found: {self.settings.rclone}") from exc
        return result.returncode == 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_files(root: Path) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CatalogError(f"symlinks are not allowed in catalog objects: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        entries.append({"path": relative, "size_bytes": size, "sha256": sha256_file(path)})
        total += size
    if not entries:
        raise CatalogError(f"no files found beneath {root}")
    return entries, total


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "id",
        "title",
        "category",
        "source",
        "authorization",
        "acquired_at",
        "remote_path",
        "size_bytes",
        "files",
        "integrity",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise CatalogError(f"manifest missing fields: {', '.join(missing)}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise CatalogError(f"unsupported schema_version {manifest['schema_version']}")
    item_id = safe_id(str(manifest["id"]))
    if manifest["id"] != item_id:
        raise CatalogError("manifest id must use its canonical lowercase spelling")
    if not str(manifest["title"]).strip():
        raise CatalogError("manifest title may not be empty")
    if manifest["category"] not in CATEGORIES:
        raise CatalogError(f"unsupported category {manifest['category']}")
    if not isinstance(manifest["source"], dict) or not str(
        manifest["source"].get("description", "")
    ).strip():
        raise CatalogError("manifest source.description may not be empty")
    if not isinstance(manifest["authorization"], dict) or not str(
        manifest["authorization"].get("basis", "")
    ).strip():
        raise CatalogError("manifest authorization.basis may not be empty")
    try:
        dt.datetime.fromisoformat(str(manifest["acquired_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogError("manifest acquired_at must be an ISO-8601 timestamp") from exc
    remote_path = PurePosixPath(str(manifest["remote_path"]))
    if remote_path.is_absolute() or ".." in remote_path.parts:
        raise CatalogError("manifest remote_path must be relative and may not contain '..'")
    expected_remote_path = f"objects/{manifest['category']}/{item_id}"
    if remote_path.as_posix() != expected_remote_path:
        raise CatalogError(f"manifest remote_path must be {expected_remote_path}")
    if not isinstance(manifest["files"], list) or not manifest["files"]:
        raise CatalogError("manifest files must be a non-empty list")
    calculated_size = 0
    seen: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise CatalogError("manifest file entries must be objects")
        relative = PurePosixPath(str(entry.get("path", "")))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise CatalogError(f"unsafe file path in manifest: {relative}")
        if relative.as_posix() in seen:
            raise CatalogError(f"duplicate file path in manifest: {relative}")
        seen.add(relative.as_posix())
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            raise CatalogError(f"invalid SHA-256 for {relative}")
        entry_size = int(entry.get("size_bytes", -1))
        if entry_size < 0:
            raise CatalogError(f"invalid file size for {relative}")
        calculated_size += entry_size
    if calculated_size != int(manifest["size_bytes"]):
        raise CatalogError("manifest size_bytes does not match file entries")
    integrity = manifest["integrity"]
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        raise CatalogError("manifest integrity.algorithm must be sha256")
    if integrity.get("verified_at") is not None:
        try:
            dt.datetime.fromisoformat(str(integrity["verified_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise CatalogError("manifest integrity.verified_at is invalid") from exc


def manifests(rclone: Rclone, settings: Settings) -> list[dict[str, Any]]:
    root = remote_join(settings.remote, "manifests")
    listing = rclone.run("lsf", root, "--files-only", "--include", "*.json", capture=True)
    result = []
    seen: set[str] = set()
    for filename in sorted(line.strip() for line in listing.splitlines() if line.strip()):
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}\.json", filename):
            raise CatalogError(f"unsafe manifest filename: {filename}")
        manifest = rclone.read_json(remote_join(root, filename))
        validate_manifest(manifest)
        if filename != f"{manifest['id']}.json" or manifest["id"] in seen:
            raise CatalogError(f"manifest filename/id mismatch or duplicate: {filename}")
        seen.add(manifest["id"])
        if manifest["integrity"]["verified_at"] is None:
            raise CatalogError(f"published manifest is not marked verified: {filename}")
        result.append(manifest)
    return result


def resolve(items: Iterable[dict[str, Any]], query: str) -> dict[str, Any]:
    exact = [
        item
        for item in items
        if query in (item["id"], item["title"], item["remote_path"])
    ]
    if not exact:
        raise CatalogError(f"catalog item not found: {query}")
    if len(exact) > 1:
        ids = ", ".join(item["id"] for item in exact)
        raise CatalogError(f"catalog query is ambiguous; use an id: {ids}")
    return exact[0]


def local_record_path(settings: Settings, item_id: str) -> Path:
    return settings.state_root / "items" / f"{safe_id(item_id)}.json"


def local_object_path(settings: Settings, manifest: dict[str, Any]) -> Path:
    raw = settings.local_root / manifest["category"] / manifest["id"]
    if raw.is_symlink() or raw.parent.is_symlink():
        raise CatalogError(f"local object path contains a symlink: {raw}")
    return confined(
        raw,
        settings.local_root,
    )


def verify_local(root: Path, manifest: dict[str, Any]) -> None:
    expected = {entry["path"] for entry in manifest["files"]}
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CatalogError(f"symlinks are not allowed in local objects: {path}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise CatalogError("local files do not match the manifest; unexpected or missing files")
    for entry in manifest["files"]:
        path = confined(root / entry["path"], root)
        if not path.is_file():
            raise CatalogError(f"missing local file: {entry['path']}")
        if path.stat().st_size != entry["size_bytes"]:
            raise CatalogError(f"size mismatch: {entry['path']}")
        if sha256_file(path) != entry["sha256"]:
            raise CatalogError(f"SHA-256 mismatch: {entry['path']}")


def atomic_json(destination: Path, payload: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=destination.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, destination)


def write_state(settings: Settings, manifest: dict[str, Any], object_path: Path) -> None:
    record = dict(manifest)
    record["local_path"] = str(object_path)
    record["local_verified_at"] = utc_now()
    atomic_json(local_record_path(settings, manifest["id"]), record)


def record_failure(settings: Settings, operation: str, item: str, error: Exception) -> None:
    destination = settings.state_root / "failures"
    destination.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "operation": operation,
        "item": item,
        "failed_at": utc_now(),
        "error": str(error),
    }
    atomic_json(destination / f"{stamp}-{uuid.uuid4().hex[:8]}.json", payload)


def read_json_records(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("expected an object")
        except (ValueError, OSError) as exc:
            raise CatalogError(f"invalid catalog state {path}: {exc}") from exc
        result.append(value)
    return result


def resolve_failures(settings: Settings, item_id: str) -> None:
    for path in (settings.state_root / "failures").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("item") == item_id and not payload.get("resolved_at"):
            payload["resolved_at"] = utc_now()
            atomic_json(path, payload)


@contextmanager
def cache_lock(settings: Settings, rclone: Rclone):
    """Serialize pulls and evictions, including the free-space admission check."""
    root = settings.state_root / "locks"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "cache.lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CatalogBusy("another cache operation is running; wait for it to finish") from exc
        previous = getattr(rclone, "lock_fds", ())
        rclone.lock_fds = (*previous, handle.fileno())
        try:
            yield handle
        finally:
            rclone.lock_fds = previous
            # Closing (rather than LOCK_UN) retains a shared inherited lock
            # until any orphaned transfer child also closes its descriptor.


@contextmanager
def cache_operation(settings: Settings, operation: str, item_id: str, lock):
    destination = settings.state_root / "operations" / f"{safe_id(item_id)}.json"
    payload = {
        "id": uuid.uuid4().hex,
        "item": item_id,
        "operation": operation,
        "status": "running",
        "phase": "preparing",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "error": None,
    }
    lock.seek(0)
    lock.truncate()
    json.dump({"id": payload["id"], "item": item_id}, lock)
    lock.flush()

    def update(phase: str) -> None:
        payload["phase"] = phase
        payload["updated_at"] = utc_now()
        atomic_json(destination, payload)
        print(f"{operation} {item_id}: {phase}", flush=True)

    update("preparing")
    try:
        yield update
    except (Exception, KeyboardInterrupt) as exc:
        payload.update(status="failed", error=str(exc) or "operation interrupted")
        record_failure(settings, operation, item_id, CatalogError(payload["error"]))
        raise
    else:
        payload.update(status="succeeded", error=None)
        resolve_failures(settings, item_id)
    finally:
        payload["updated_at"] = utc_now()
        if payload["status"] != "running":
            payload["finished_at"] = payload["updated_at"]
        atomic_json(destination, payload)


def active_operation_id(settings: Settings) -> str | None:
    path = settings.state_root / "locks" / "cache.lock"
    try:
        with path.open("r") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                try:
                    return str(json.load(handle)["id"])
                except (ValueError, KeyError):
                    return None  # The owner has not published its operation yet.
    except FileNotFoundError:
        pass
    return None


def operation_records(settings: Settings) -> list[dict[str, Any]]:
    active_ids = {active_operation_id(settings)}
    result = read_json_records(settings.state_root / "operations")
    # A retry can publish its record during the read; sample both sides to
    # avoid calling that newly started operation interrupted for one refresh.
    active_ids.add(active_operation_id(settings))
    active_ids.discard(None)
    for operation in result:
        operation["active"] = operation.get("id") in active_ids
        operation["stalled"] = (
            operation.get("status") == "running" and not operation["active"]
        )
        if operation["stalled"]:
            operation["status"] = "stalled"
            operation["error"] = "Operation interrupted; its process is no longer running. Retry to resume verified staging."
    return result


def catalog_snapshot(settings: Settings, rclone: Rclone) -> dict[str, Any]:
    """One structured view shared by the dashboard and recovery commands.

    Local means a matching successful verification record still has its files,
    sizes and paths. Re-hashing terabytes on every UI refresh is deliberately
    avoided; pull always performs the full SHA-256 verification.
    """
    items = manifests(rclone, settings)
    records = {record["id"]: record for record in load_local_records(settings)}
    operations = {record["item"]: record for record in operation_records(settings)}
    failures = read_json_records(settings.state_root / "failures")
    enriched = []
    for item in items:
        item = dict(item)
        item_id = item["id"]
        final = local_object_path(settings, item)
        record = records.get(item_id)
        operation = operations.get(item_id)
        item_failures = [failure for failure in failures if failure.get("item") == item_id and not failure.get("resolved_at")]
        latest_failure = max(item_failures, key=lambda failure: failure.get("failed_at", ""), default=None)
        local = bool(
            record and record.get("local_verified_at") and final.is_dir()
            and record["files"] == item["files"]
            and record["remote_path"] == item["remote_path"]
            and local_metadata_matches(final, item)
        )
        error = None
        stalled = bool(operation and operation.get("stalled"))
        if operation and operation["active"]:
            state, action = "downloading", None
        elif operation and operation["status"] in {"failed", "stalled"}:
            state = "failed"
            error = operation["error"]
            action = "evict" if final.exists() and record else "retry"
        elif local:
            state, action = "local", "evict"
        elif latest_failure:
            state, action, error = "failed", "retry", latest_failure["error"]
        elif final.exists():
            state, action = "failed", "evict" if record else "retry"
            error = "Local files have no matching verification record; retry will verify them before marking local."
        elif (settings.staging_root / f"{item_id}.partial").exists():
            state, action, stalled = "failed", "retry", True
            error = "Interrupted staging is present with no active transfer. Retry to resume."
        else:
            state, action = "remote_only", "download"
        item.update(local=local, state=state, valid_action=action, error=error,
                    operation=operation, stalled=stalled,
                    local_verified_at=record.get("local_verified_at") if record else None)
        enriched.append(item)
    settings.local_root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.local_root)
    local_items = [item for item in enriched if item["local"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "remote_items": len(items),
        "remote_bytes": sum(int(item["size_bytes"]) for item in items),
        "local_items": len(local_items),
        "local_bytes": sum(int(item["size_bytes"]) for item in local_items),
        "local_free_bytes": usage.free,
        "local_total_bytes": usage.total,
        "local_reserve_bytes": settings.min_free_bytes,
        "transfers_in_progress": sum(bool(op["active"] and op["operation"] == "pull") for op in operations.values()),
        "stalled_transfers": sum(bool(item["stalled"]) for item in enriched),
        "recorded_failures": len(failures),
        "unresolved_failures": sum(not failure.get("resolved_at") for failure in failures),
        "failed_transfers": sum(item["state"] == "failed" for item in enriched),
        "items": enriched,
    }


def local_metadata_matches(root: Path, manifest: dict[str, Any]) -> bool:
    expected = {entry["path"]: entry["size_bytes"] for entry in manifest["files"]}
    actual = {}
    try:
        for path in root.rglob("*"):
            if path.is_symlink():
                return False
            if path.is_file():
                actual[path.relative_to(root).as_posix()] = path.stat().st_size
    except OSError:
        return False
    return actual == expected


def cmd_list(args: argparse.Namespace, settings: Settings, rclone: Rclone) -> None:
    items = catalog_snapshot(settings, rclone)["items"]
    if args.json:
        print(json.dumps(items, indent=2, sort_keys=True))
        return
    print(f"{'ID':36} {'CATEGORY':10} {'SIZE':>10}  {'STATE':12}  TITLE")
    for item in items:
        print(
            f"{item['id'][:36]:36} {item['category'][:10]:10} "
            f"{human_bytes(item['size_bytes']):>10}  {item['state']:12}  {item['title']}"
        )
        if item["error"]:
            print(f"  {item['error']}")


def cmd_status(args: argparse.Namespace, settings: Settings, rclone: Rclone) -> None:
    status = catalog_snapshot(settings, rclone)
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return
    for key, value in status.items():
        if key == "items":
            continue
        if key.endswith("_bytes"):
            print(f"{key.replace('_', ' '):24} {human_bytes(value)}")
        else:
            print(f"{key.replace('_', ' '):24} {value}")


def cmd_pull(args: argparse.Namespace, settings: Settings, rclone: Rclone) -> None:
    with cache_lock(settings, rclone) as lock:
        manifest = resolve(manifests(rclone, settings), args.item)
        with cache_operation(settings, "pull", manifest["id"], lock) as update:
            final = local_object_path(settings, manifest)
            if final.exists():
                update("verifying existing local copy")
                verify_local(final, manifest)
                write_state(settings, manifest, final)
                remove_staging(settings, manifest["id"])
                print(f"already local and verified: {manifest['id']}", flush=True)
                return
            settings.staging_root.mkdir(parents=True, exist_ok=True)
            settings.local_root.mkdir(parents=True, exist_ok=True)
            if settings.staging_root.stat().st_dev != settings.local_root.stat().st_dev:
                raise CatalogError("staging and local library must share a filesystem for atomic publication")
            staging_path = settings.staging_root / f"{manifest['id']}.partial"
            if staging_path.is_symlink():
                raise CatalogError("staging object path is a symlink; refusing to alter it")
            staging = confined(staging_path, settings.staging_root)
            staging.mkdir(parents=True, exist_ok=True)
            update("checking resumable staging")
            reusable = prepare_staging(staging, manifest)
            free = shutil.disk_usage(settings.local_root).free
            required = int(manifest["size_bytes"]) - reusable + settings.min_free_bytes
            if free < required:
                raise CatalogError(
                    f"insufficient free space: need {human_bytes(required)}, have {human_bytes(free)}"
                )
            source = remote_join(settings.remote, manifest["remote_path"])
            update("downloading; transfer output appears in execution history")
            rclone.run(
                "copy", source, str(staging), "--immutable",
                "--transfers", str(settings.transfers),
                "--checkers", str(settings.checkers),
                "--bwlimit", settings.bwlimit,
                "--partial-suffix", ".rclone-partial",
                "--stats", "10s", "--stats-one-line", "--stats-log-level", "NOTICE",
                "--contimeout", "30s", "--timeout", "5m",
            )
            update("verifying SHA-256")
            verify_local(staging, manifest)
            update("publishing verified local copy")
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, final)
            write_state(settings, manifest, final)
            print(f"pulled and verified: {manifest['id']} -> {final}", flush=True)


def prepare_staging(staging: Path, manifest: dict[str, Any]) -> int:
    """Keep verified files, remove damaged/unlisted local remnants for safe retry."""
    expected = {entry["path"]: entry for entry in manifest["files"]}
    reusable = 0
    paths = list(staging.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise CatalogError("staging contains a symlink; refusing to follow or alter it")
    for path in paths:
        if not path.is_file():
            continue
        entry = expected.get(path.relative_to(staging).as_posix())
        if entry and path.stat().st_size == entry["size_bytes"] and sha256_file(path) == entry["sha256"]:
            reusable += entry["size_bytes"]
        else:
            confined(path, staging).unlink()
    return reusable


def remove_staging(settings: Settings, item_id: str) -> None:
    staging = settings.staging_root / f"{safe_id(item_id)}.partial"
    if staging.is_symlink():
        raise CatalogError("staging object path is a symlink; refusing to alter it")
    if staging.exists():
        shutil.rmtree(confined(staging, settings.staging_root))


def load_local_records(settings: Settings) -> list[dict[str, Any]]:
    root = settings.state_root / "items"
    result: list[dict[str, Any]] = []
    if not root.exists():
        return result
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue  # A concurrent eviction removed this record after listing.
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"invalid local state file {path}: {exc}") from exc
        validate_manifest(value)
        result.append(value)
    return result


def cmd_evict(args: argparse.Namespace, settings: Settings, rclone: Rclone) -> None:
    with cache_lock(settings, rclone) as lock:
        manifest = resolve(load_local_records(settings), args.item)
        with cache_operation(settings, "evict", manifest["id"], lock) as update:
            final = local_object_path(settings, manifest)
            update("removing local copy; canonical remote copy remains")
            if final.exists():
                confined(final, settings.local_root)
                shutil.rmtree(final)
            remove_staging(settings, manifest["id"])
            record = local_record_path(settings, manifest["id"])
            if record.exists():
                record.unlink()
            print(f"evicted local copy only: {manifest['id']}", flush=True)


def cmd_promote(args: argparse.Namespace, settings: Settings, rclone: Rclone) -> None:
    if os.environ.get("CATALOG_ROLE", "").lower() != "cloud":
        raise CatalogError("promotion requires CATALOG_ROLE=cloud")
    source = confined(Path(args.path), settings.promotion_root)
    if not source.is_dir():
        raise CatalogError(f"promotion source is not a directory: {source}")
    item_id = safe_id(args.id or default_id(args.title))
    category = args.category
    files, total = inventory_files(source)
    remote_path = f"objects/{category}/{item_id}"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "id": item_id,
        "title": args.title,
        "category": category,
        "source": {"description": args.source},
        "authorization": {"basis": args.authorization},
        "acquired_at": args.acquired_at or utc_now(),
        "remote_path": remote_path,
        "size_bytes": total,
        "files": files,
        "integrity": {"algorithm": "sha256", "verified_at": None},
        "notes": args.notes or "",
    }
    validate_manifest(manifest)
    suffix = uuid.uuid4().hex
    incoming = remote_join(settings.remote, ".incoming", f"{item_id}.{suffix}")
    incoming_data = remote_join(incoming, "data")
    final_data = remote_join(settings.remote, remote_path)
    final_manifest = remote_join(settings.remote, "manifests", f"{item_id}.json")
    try:
        # A prior run may have completed the remote rename and then stopped
        # before publishing its manifest. Re-verify that exact immutable object
        # and finish the transaction instead of creating a duplicate.
        final_already_verified = rclone.succeeds(
            "check", str(source), final_data, "--download", "--one-way"
        )
        if not final_already_verified:
            rclone.run(
                "copy",
                str(source),
                incoming_data,
                "--immutable",
                "--transfers",
                str(settings.transfers),
                "--checkers",
                str(settings.checkers),
                "--bwlimit",
                settings.bwlimit,
            )
            rclone.run("check", str(source), incoming_data, "--download", "--one-way")
            rclone.run("moveto", incoming_data, final_data, "--immutable")
        manifest["integrity"]["verified_at"] = utc_now()
        with tempfile.TemporaryDirectory() as directory:
            local_manifest = Path(directory) / f"{item_id}.json"
            local_manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            rclone.run("copyto", str(local_manifest), final_manifest, "--immutable")
        if args.delete_local:
            shutil.rmtree(source)
        resolve_failures(settings, item_id)
    except Exception as exc:
        record_failure(settings, "promote", item_id, exc)
        raise
    print(f"promoted and verified: {item_id} -> {final_data}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    list_parser = commands.add_parser("list", help="list canonical remote catalog items")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)
    status = commands.add_parser("status", help="summarize remote and local state")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)
    pull = commands.add_parser("pull", help="copy and verify one item into the local cache")
    pull.add_argument("item")
    pull.set_defaults(func=cmd_pull)
    evict = commands.add_parser("evict", help="remove only one local cached item")
    evict.add_argument("item")
    evict.set_defaults(func=cmd_evict)
    promote = commands.add_parser("promote", help="publish a verified staged item")
    promote.add_argument("path")
    promote.add_argument("--title", required=True)
    promote.add_argument("--category", required=True, choices=CATEGORIES)
    promote.add_argument("--source", required=True)
    promote.add_argument("--authorization", required=True)
    promote.add_argument("--notes")
    promote.add_argument("--id")
    promote.add_argument("--acquired-at")
    promote.add_argument("--delete-local", action="store_true")
    promote.set_defaults(func=cmd_promote)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        args.func(args, settings, Rclone(settings))
    except (CatalogError, ValueError, OSError) as exc:
        print(f"catalog: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
