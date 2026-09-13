#!/usr/bin/env python3
"""Selective NAS copies of canonical native Arr title directories.

Only remote reads are permitted here. A selected title is inventoried, SHA-256
hashed through rclone's configured remote SHA-256 reader, copied to private staging, verified and
published with an exclusive same-filesystem rename. No Arr scratch is accessed.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import uuid

import catalogctl as catalog

KINDS = ("Movies", "TV")
READ_FLAGS = ("--sftp-skip-links", "--sftp-disable-hashcheck", "--contimeout", "30s", "--timeout", "5m")


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise catalog.CatalogError("unsafe native-library relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} or p.startswith(".") for p in value.split("/")):
        raise catalog.CatalogError("unsafe native-library relative path")
    if path.as_posix() != value:
        raise catalog.CatalogError("native-library path is not canonical")
    return value


def title_id(kind: str, title: str) -> str:
    if kind not in KINDS or "/" in safe_relative(title):
        raise catalog.CatalogError("native selection must identify exactly one Movies or TV title")
    return "native-" + hashlib.sha256(f"{kind}/{title}".encode()).hexdigest()


def exclusive_rename(source: Path, destination: Path) -> None:
    """Never fall back to rename/replace: they can clobber an empty directory."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        func = libc.renameat2
        func.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        func.restype = ctypes.c_int
        result = func(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        func = libc.renamex_np
        func.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        func.restype = ctypes.c_int
        result = func(os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
    else:
        raise catalog.CatalogError("exclusive atomic rename is unavailable; refusing publication")
    if result:
        number = ctypes.get_errno()
        if number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise catalog.CatalogError("destination already exists; refusing to overwrite it")
        raise catalog.CatalogError(f"exclusive atomic publication failed: {os.strerror(number)}")


def reject_symlink_ancestors(path: Path) -> None:
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise catalog.CatalogError("native path contains a symlink ancestor")


def guarded_path(root: Path, relative: str) -> Path:
    """Reject symlinks below configured roots, including intermediate parents."""
    safe_relative(relative)
    current = root
    reject_symlink_ancestors(root)
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise catalog.CatalogError("native local path contains a symlink")
    return catalog.confined(current, root)


def local_signature(root: Path) -> list[dict]:
    result = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise catalog.CatalogError("native local copy contains a symlink or special file")
        result.append({"path": path.relative_to(root).as_posix(), "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns})
    return result


class NativeLibrary:
    def __init__(self, settings: catalog.Settings, rclone: catalog.Rclone, tv_root: Path | None = None):
        self.settings = settings
        self.rclone = rclone
        # Do not resolve away a symlink at the supplied root before validating it.
        self.tv_root = tv_root or Path(os.environ.get("NATIVE_TV_ROOT", "/data/tv/library"))
        self.tv_staging_root = Path(os.environ.get("NATIVE_TV_STAGING_ROOT", str(self.tv_root.parent / ".staging")))
        self.record_root = settings.state_root / "native-items"

    def require_nas(self) -> None:
        if os.environ.get("CATALOG_ROLE", "").lower() != "qnap":
            raise catalog.CatalogError("native NAS operations require CATALOG_ROLE=qnap")

    def tv_enabled(self) -> bool:
        return os.environ.get("NATIVE_TV_COPY_ENABLED", "false").lower() == "true"

    def listing(self, relative: str) -> list[dict]:
        rows = json.loads(self.rclone.run("lsjson", catalog.remote_join(self.settings.remote, relative),
                                         "--recursive", *READ_FLAGS, capture=True))
        if not isinstance(rows, list):
            raise catalog.CatalogError("invalid native remote listing")
        result = []
        seen = set()
        for row in rows:
            path = safe_relative(row["Path"])
            if path in seen:
                raise catalog.CatalogError("duplicate path in native remote listing")
            seen.add(path)
            if row.get("IsDir"):
                continue
            size = row.get("Size")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0 or not row.get("ModTime"):
                raise catalog.CatalogError("native listing is missing size or modification time")
            result.append({"path": path, "size_bytes": size, "modtime": row["ModTime"]})
        return sorted(result, key=lambda entry: entry["path"])

    def titles(self) -> list[dict]:
        grouped = {}
        for entry in self.listing("library"):
            parts = entry["path"].split("/")
            if len(parts) < 3 or parts[0] not in KINDS:
                continue
            kind, title = parts[:2]
            item_id = title_id(kind, title)
            item = grouped.setdefault(item_id, {
                "id": item_id, "title": title, "category": kind, "library_kind": kind,
                "source": "native", "relative_path": f"library/{kind}/{title}", "files": [], "size_bytes": 0,
            })
            item["files"].append({**entry, "path": "/".join(parts[2:])})
            item["size_bytes"] += entry["size_bytes"]
        return sorted(grouped.values(), key=lambda item: (item["title"].casefold(), item["id"]))

    def selected(self, item_id: str) -> dict:
        # Never accept a path or a search string as an action target.
        if not re.fullmatch(r"native-[0-9a-f]{64}", item_id):
            raise catalog.CatalogError("select exactly one native title ID from native-list")
        matches = [item for item in self.titles() if item["id"] == item_id]
        if len(matches) != 1:
            raise catalog.CatalogError("native title is no longer available; refresh the catalog")
        return matches[0]

    def final_path(self, item: dict) -> Path:
        if title_id(item["library_kind"], item["title"]) != item["id"]:
            raise catalog.CatalogError("native record identity does not match its title")
        if item["library_kind"] == "Movies":
            return guarded_path(self.settings.local_root, f"video/{item['id']}/{item['title']}")
        return guarded_path(self.tv_root, item["title"])

    def record_path(self, item_id: str) -> Path:
        return self.record_root / f"{catalog.safe_id(item_id)}.json"

    def record(self, item_id: str) -> dict | None:
        path = self.record_path(item_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return None
        if not isinstance(value, dict) or value.get("id") != item_id or value.get("source") != "native":
            raise catalog.CatalogError("invalid native copy receipt")
        return value

    def owns(self, final: Path, record: dict | None) -> bool:
        if not record or not final.is_dir():
            return False
        info = final.stat()
        return record.get("local_path") == str(final) and record.get("directory_identity") == [info.st_dev, info.st_ino]

    def snapshot(self) -> dict:
        self.require_nas()
        items = self.titles()
        records = {r["id"]: r for r in catalog.read_json_records(self.record_root)}
        # Keep removed/renamed remote titles visible so their verified local copy
        # remains removable without reading or mutating the canonical library.
        current_ids = {item["id"] for item in items}
        items += [{**r, "remote_missing": True} for ident, r in records.items() if ident not in current_ids]
        operations = {r["item"]: r for r in catalog.operation_records(self.settings) if r["item"].startswith("native-")}
        failures = [r for r in catalog.read_json_records(self.settings.state_root / "failures") if str(r.get("item", "")).startswith("native-")]
        for item in items:
            record = records.get(item["id"])
            operation = operations.get(item["id"])
            local = False
            error = None
            try:
                final = self.final_path(item)
                local = bool(self.owns(final, record) and record.get("local_verified_at") and
                             record.get("local_signature") == local_signature(final))
                exists = final.exists()
            except (OSError, catalog.CatalogError) as exc:
                error, exists = str(exc), True
            stalled = bool(operation and operation.get("stalled"))
            if operation and operation["active"]:
                state, action = "downloading", None
            elif local:
                state, action = "local", "evict"
                if item.get("remote_missing") or record["files"] != item["files"]:
                    error = "Canonical title changed or was removed; this NAS copy retains its verified version. Remove it explicitly before copying the current version."
            elif exists:
                state, action = "failed", None
                error = error or "Destination collision or modified local copy; preserved for manual review."
            elif operation and operation["status"] in {"failed", "stalled"}:
                state, action = "failed", None if item.get("remote_missing") else "retry"
                error = operation.get("error")
            else:
                state, action = "remote_only", None if item.get("remote_missing") else "download"
            if item["library_kind"] == "TV" and not self.tv_enabled() and action in {"download", "retry"}:
                action = None
                error = "TV copying is disabled until the Plex TV source is migrated to TV Shows/library; private staging must be outside Plex."
            item.update(local=local, state=state, valid_action=action, error=error, operation=operation, stalled=stalled,
                        local_size_bytes=record["size_bytes"] if local else 0,
                        local_verified_at=record.get("local_verified_at") if record else None)
        usage = shutil.disk_usage(self.settings.local_root)
        remote = [item for item in items if not item.get("remote_missing")]
        local = [item for item in items if item["local"]]
        return {
            "schema_version": 1, "generated_at": catalog.utc_now(), "items": items,
            "remote_items": len(remote), "remote_bytes": sum(i["size_bytes"] for i in remote),
            "local_items": len(local), "local_bytes": sum(i["local_size_bytes"] for i in local),
            "local_free_bytes": usage.free, "local_total_bytes": usage.total, "local_reserve_bytes": self.settings.min_free_bytes,
            "transfers_in_progress": sum(bool(o["active"] and o["operation"] == "native-pull") for o in operations.values()),
            "stalled_transfers": sum(bool(i["stalled"]) for i in items), "recorded_failures": len(failures),
            "unresolved_failures": sum(not f.get("resolved_at") for f in failures),
            "failed_transfers": sum(i["state"] == "failed" for i in items),
        }

    def assert_unchanged(self, item: dict) -> None:
        if self.listing(item["relative_path"]) != item["files"]:
            raise catalog.CatalogError("canonical title changed during the copy; nothing was published; refresh and retry")

    def remote_hashes(self, item: dict) -> list[dict]:
        # The NAS reader config explicitly enables server-side sha256sum.
        # Fail closed on unsupported/missing hashes; never silently download
        # the title a second time or weaken verification to size/modtime.
        output = self.rclone.run("hashsum", "sha256", catalog.remote_join(self.settings.remote, item["relative_path"]),
                                 "--checkers", str(self.settings.checkers),
                                 *READ_FLAGS, "--sftp-disable-hashcheck=false", capture=True)
        hashes = {}
        for line in output.splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if not match or match[2] in hashes:
                raise catalog.CatalogError("invalid or duplicate SHA-256 output for native title")
            hashes[safe_relative(match[2])] = match[1]
        if set(hashes) != {entry["path"] for entry in item["files"]}:
            raise catalog.CatalogError("remote SHA-256 inventory does not match the selected title")
        return [{**entry, "sha256": hashes[entry["path"]]} for entry in item["files"]]

    def prepare_roots(self, final: Path, kind: str) -> Path:
        staging_root = self.tv_staging_root if kind == "TV" else self.settings.staging_root
        for root in (self.settings.local_root, self.tv_root, staging_root):
            reject_symlink_ancestors(root)
        # A typo must not stage partial bytes inside either Plex source.
        for plex in (self.settings.local_root / "video", self.tv_root):
            if staging_root.resolve() == plex.resolve() or plex.resolve() in staging_root.resolve().parents:
                raise catalog.CatalogError("native staging must be outside every Plex source")
        staging_root.mkdir(parents=True, exist_ok=True)
        final.parent.mkdir(parents=True, exist_ok=True)
        if staging_root.stat().st_dev != final.parent.stat().st_dev:
            raise catalog.CatalogError("native staging and final title must share a filesystem")
        # Distinct Docker bind mounts can report the same device but reject
        # cross-mount renames with EXDEV. Probe with an empty owned directory
        # before reading any media, and never touch an existing destination.
        probe = Path(tempfile.mkdtemp(prefix=".native-rename-", dir=staging_root))
        published_probe = final.parent / (".native-rename-" + uuid.uuid4().hex)
        moved = False
        try:
            exclusive_rename(probe, published_probe)
            moved = True
        finally:
            (published_probe if moved else probe).rmdir()
        return staging_root

    def pull(self, item_id: str) -> None:
        self.require_nas()
        with catalog.cache_lock(self.settings, self.rclone) as lock:
            item = self.selected(item_id)
            with catalog.cache_operation(self.settings, "native-pull", item_id, lock) as update:
                if item["library_kind"] == "TV" and not self.tv_enabled():
                    raise catalog.CatalogError("TV copying requires the Plex TV source migration and NATIVE_TV_COPY_ENABLED=true")
                final = self.final_path(item)
                record = self.record(item_id)
                if final.exists():
                    if not self.owns(final, record):
                        raise catalog.CatalogError("destination already exists without this copy's ownership receipt; preserved")
                    update("verifying existing native NAS copy")
                    local_signature(final)
                    catalog.verify_local(final, {"files": record["verified_files"]})
                    if record["files"] != item["files"]:
                        raise catalog.CatalogError("canonical title changed; remove this verified NAS copy explicitly before copying the new version")
                    # A ready receipt belongs to the exact staging inode, which
                    # survives publication. Recover a crash after rename safely.
                    record.update(local_verified_at=catalog.utc_now(), local_signature=local_signature(final), status="published")
                    catalog.atomic_json(self.record_path(item_id), record)
                    print(f"already local and verified: {item_id}")
                    return
                staging_root = self.prepare_roots(final, item["library_kind"])
                staging = guarded_path(staging_root, item_id + ".partial")
                staging.mkdir(exist_ok=True)
                local_signature(staging)  # Reject links/special files before cleanup.
                # Budget for a full fresh copy before reading remote media. Space
                # already occupied by a partial is deliberately not counted free.
                free = shutil.disk_usage(staging_root).free
                required = item["size_bytes"] + self.settings.min_free_bytes
                if free < required:
                    raise catalog.CatalogError(f"insufficient free space: need {catalog.human_bytes(required)}, have {catalog.human_bytes(free)}")
                self.assert_unchanged(item)
                update("reading selected title SHA-256 checksums")
                verified_files = self.remote_hashes(item)
                self.assert_unchanged(item)
                catalog.prepare_staging(staging, {"files": verified_files})
                update("copying selected title to private NAS staging")
                self.rclone.run("copy", catalog.remote_join(self.settings.remote, item["relative_path"]), str(staging),
                                "--immutable", "--transfers", str(self.settings.transfers), "--checkers", str(self.settings.checkers),
                                "--bwlimit", self.settings.bwlimit, "--partial-suffix", ".rclone-partial",
                                "--max-transfer", str(item["size_bytes"] + 1), "--cutoff-mode", "HARD",
                                "--stats", "10s", "--use-json-log", "--stats-log-level", "NOTICE", *READ_FLAGS,
                                progress=lambda stats: update(None, stats))
                update("verifying selected NAS bytes and unchanged canonical title")
                local_signature(staging)
                catalog.verify_local(staging, {"files": verified_files})
                self.assert_unchanged(item)
                if shutil.disk_usage(staging_root).free < self.settings.min_free_bytes:
                    raise catalog.CatalogError("NAS free space fell below the configured reserve; title remains in private staging")
                info = staging.stat()
                record = {**item, "verified_files": verified_files, "local_path": str(final),
                          "directory_identity": [info.st_dev, info.st_ino], "status": "ready",
                          "local_signature": local_signature(staging), "local_verified_at": catalog.utc_now()}
                # Receipt first: a crash after rename can only adopt our exact
                # inode plus matching hashes, never an unrelated directory.
                catalog.atomic_json(self.record_path(item_id), record)
                update("publishing verified native NAS copy")
                if self.final_path(item) != final:
                    raise catalog.CatalogError("native destination changed during transfer")
                exclusive_rename(staging, final)
                record["status"] = "published"
                catalog.atomic_json(self.record_path(item_id), record)
                print(f"pulled and verified native title: {item_id} -> {final}")

    def evict(self, item_id: str) -> None:
        self.require_nas()
        with catalog.cache_lock(self.settings, self.rclone) as lock:
            record = self.record(item_id)
            if not record:
                raise catalog.CatalogError("no owned native NAS copy receipt; nothing removed")
            with catalog.cache_operation(self.settings, "native-evict", item_id, lock) as update:
                final = self.final_path(record)
                if final.exists():
                    if not self.owns(final, record):
                        raise catalog.CatalogError("native destination ownership changed; nothing removed")
                    update("verifying local ownership and unchanged bytes before removal")
                    local_signature(final)
                    catalog.verify_local(final, {"files": record["verified_files"]})
                    update("removing only this verified native NAS copy")
                    shutil.rmtree(final)
                self.record_path(item_id).unlink()
                print(f"removed native NAS copy only: {item_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "status"):
        sub.add_parser(command).add_argument("--json", action="store_true")
    for command in ("pull", "evict"):
        sub.add_parser(command).add_argument("item")
    args = parser.parse_args()
    try:
        settings = catalog.Settings.from_env()
        backend = NativeLibrary(settings, catalog.Rclone(settings))
        if args.command in {"list", "status"}:
            snapshot = backend.snapshot()
            if args.json:
                print(json.dumps(snapshot["items"] if args.command == "list" else snapshot, indent=2, sort_keys=True))
            else:
                for item in snapshot["items"]:
                    print(f"{item['id']}  {item['category']:6}  {catalog.human_bytes(item['size_bytes']):>10}  {item['state']:12}  {item['title']}")
        else:
            getattr(backend, args.command)(args.item)
    except catalog.CatalogBusy as exc:
        print(f"native library busy: {exc}", file=sys.stderr)
        return 75
    except (catalog.CatalogError, OSError, ValueError, KeyError) as exc:
        print(f"native library error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
