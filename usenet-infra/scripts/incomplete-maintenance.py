#!/usr/bin/env python3
"""Guarded cleanup of stale, unowned SAB incomplete-download scratch trees."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import time

import cart_import_sab

MIN_AGE_SECONDS = 7 * 24 * 60 * 60
INCOMPLETE = Path("downloads/incomplete")
RECEIPTS = Path("state/catalog/maintenance/incomplete-cleanup")


def confined(value, root):
    """Resolve a SAB path into the host root without permitting escape."""
    path = Path(str(value))
    if path.is_absolute() and path.parts[:2] == ("/", "data"):
        path = Path("downloads", *path.parts[2:])
    elif path.is_absolute() and path.parts[:2] == ("/", "library"):
        path = Path("library", *path.parts[2:])
    candidate = (root / path).resolve()
    base = root.resolve()
    if candidate != base and base not in candidate.parents:
        return None
    return candidate


def protected_paths(snapshot, root, journal_root):
    paths = []
    for item in snapshot["queue"] + snapshot["history"]:
        for key in ("path", "storage"):
            if item.get(key):
                path = confined(item[key], root)
                if path is not None:
                    paths.append(path)
    for journal in journal_root.glob("**/*.json"):
        try:
            data = json.loads(journal.read_text())
        except (OSError, ValueError):
            paths.append(journal_root)
            continue
        if isinstance(data, dict) and data.get("source_dir"):
            path = confined(data["source_dir"], root)
            paths.append(path or journal_root)
    return paths


def under(candidate, protected):
    return candidate == protected or protected in candidate.parents or candidate in protected.parents


def inspect_candidates(base, protected, now):
    candidates, reasons = [], {}
    for entry in sorted(base.iterdir(), key=lambda p: p.name):
        def reject(reason):
            reasons[reason] = reasons.get(reason, 0) + 1
        try:
            info = entry.lstat()
        except OSError:
            reject("stat_failed"); continue
        if not stat.S_ISDIR(info.st_mode) or entry.is_symlink():
            reject("not_plain_directory"); continue
        if now - info.st_mtime < MIN_AGE_SECONDS:
            reject("younger_than_grace_period"); continue
        if any(under(entry, path) for path in protected):
            reject("referenced_by_queue_history_or_journal"); continue
        total = 0; safe = True
        for path in entry.rglob("*"):
            try:
                child = path.lstat()
            except OSError:
                reject("stat_failed"); safe = False; break
            if stat.S_ISLNK(child.st_mode):
                reject("symlink_present"); safe = False; break
            if not stat.S_ISREG(child.st_mode):
                reject("nonregular_file_present"); safe = False; break
            if child.st_nlink != 1:
                reject("hardlink_present"); safe = False; break
            total += child.st_size
        if safe:
            candidates.append((entry, total, info.st_mtime))
    return candidates, reasons


def receipt(root, payload):
    directory = root / RECEIPTS
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = f"{int(payload['finished_at'])}.json"
    target = directory / name
    temporary = directory / f".{name}.tmp-{os.getpid()}"
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, target)


def run(root=Path("/srv/usenet"), *, sab=None, now=None):
    root = Path(root).resolve(); now = time.time() if now is None else now
    base = root / INCOMPLETE
    if not base.is_dir() or base.is_symlink() or not base.is_mount():
        return {"status": "held", "reason": "incomplete_mount_unavailable"}
    lock_path = root / "state/catalog/locks/cache.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "held", "reason": "cache_operation_active"}
        snapshot = (sab or cart_import_sab.SabSource(root)).snapshot()
        if snapshot["postprocessing"] or any(j.get("status") != "Paused" for j in snapshot["queue"]):
            return {"status": "held", "reason": "sab_not_idle"}
        protected = protected_paths(snapshot, root, root / "state/catalog/cart-import/jobs")
        candidates, reasons = inspect_candidates(base, protected, now)
        # Re-check every candidate immediately before deletion; a changed tree is held.
        for path, size, mtime in candidates:
            try:
                info = path.lstat()
                if info.st_mtime != mtime or not path.is_dir() or path.is_symlink():
                    return {"status": "held", "reason": "candidate_changed_before_delete"}
            except OSError:
                return {"status": "held", "reason": "candidate_changed_before_delete"}
        reclaimed = 0
        for path, size, _ in candidates:
            shutil.rmtree(path)
            reclaimed += size
        payload = {"schema_version": 1, "status": "deleted", "finished_at": now,
                   "directories": len(candidates), "files_bytes": reclaimed,
                   "skipped": reasons, "protected_path_count": len(protected)}
        receipt(root, payload)
        return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run",))
    args = parser.parse_args()
    if Path('/srv/usenet/config/catalog/native-ownership.json').exists():
        print(json.dumps({'status': 'retired', 'reason': 'native_ownership_active'}))
        return 0
    try:
        print(json.dumps(run(), sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"status": "held", "reason": "maintenance_error", "error_type": type(error).__name__}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
