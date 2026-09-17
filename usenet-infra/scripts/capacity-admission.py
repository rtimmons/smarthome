#!/usr/bin/env python3
"""Serialize SAB acquisition against conservative scratch-capacity reservations."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ElementTree

import cart_import_sab


SCHEMA = 1
RESERVE = 30 * 1024 ** 3
MARGIN = 5 * 1024 ** 3
INODE_RESERVE = 100_000
CATEGORIES = {"", "*", "Default", "prowlarr"}
FEEDS = {"NZBGeek Cart", "NZBFinder Cart"}
MAX_FAILURE_RETRIES = 2
MAX_CART_JOURNALS = 100_000
TERMINAL_CART_PHASES = {"cleaned", "cleaned_with_retained_files"}


class AdmissionError(RuntimeError):
    pass


class AdmissionBusy(BlockingIOError):
    pass


def atomic(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def count(value) -> int:
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        raise AdmissionError("queue_size_invalid") from None
    if number < 0:
        raise AdmissionError("queue_size_invalid")
    return number


class Controller:
    def __init__(self, root=Path("/srv/usenet"), sab=None, clock=time.time):
        self.root = Path(root)
        self.sab = sab or cart_import_sab.SabSource(self.root)
        self.clock = clock
        self.base = self.root / "state/catalog/capacity-admission"
        self.state_path = self.base / "state.json"
        self.lock_path = self.base / "lock"

    def api(self, mode, **values):
        result = self.sab.api(mode, **values)
        if not isinstance(result, dict) or result.get("status") is False or result.get("error"):
            raise AdmissionError("sab_request_rejected")
        return result

    def state(self) -> dict:
        if not self.state_path.exists():
            return {"schema_version": SCHEMA, "owned": [], "admitted": None, "held": [],
                    "failure_retries": {}, "blocked": None}
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != SCHEMA or not isinstance(value.get("owned"), list):
            raise AdmissionError("admission_state_invalid")
        value.setdefault("held", [])
        value.setdefault("failure_retries", {})
        if not isinstance(value["held"], list) or not isinstance(value["failure_retries"], dict):
            raise AdmissionError("admission_state_invalid")
        return value

    def save(self, state: dict) -> None:
        state["updated_at"] = self.clock()
        atomic(self.state_path, state)

    def available(self) -> int:
        stats = os.statvfs(self.root)
        return stats.f_bavail * stats.f_frsize

    def require_resources(self) -> None:
        # All current scratch/application paths share one filesystem. Refuse a
        # changed layout instead of budgeting an unrelated filesystem's space.
        device = self.root.stat().st_dev
        for relative in ("downloads/incomplete", "downloads/complete", "config", "state/catalog"):
            path = self.root / relative
            if path.is_symlink() or not path.is_dir() or path.stat().st_dev != device:
                raise AdmissionError("scratch_filesystem_layout_changed")
        stats = os.statvfs(self.root)
        if stats.f_files <= 0 or stats.f_favail < INODE_RESERVE:
            raise AdmissionError("inode_reserve_unavailable")
        if self.available() < RESERVE:
            raise AdmissionError("reserve_breached")

    def discovery_api(self):
        spec = importlib.util.spec_from_file_location(
            "capacity_discovery", Path(__file__).with_name("discovery-config.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.API(self.root / "config")

    def require_dependencies(self) -> None:
        library = self.root / "library"
        if not library.is_mount():
            raise AdmissionError("canonical_mount_unavailable")
        try:
            # Touch the mounted directories too: a stale FUSE mount is not
            # established as usable merely by being present in the mount table.
            if not all((library / name).is_dir() for name in ("Movies", "TV")):
                raise AdmissionError("canonical_mount_unavailable")
            api = self.discovery_api()
            for app in ("radarr", "sonarr"):
                roots = api.call(app, "rootfolder", timeout=5)
                if not isinstance(roots, list) or len([
                        row for row in roots if row.get("path") == "/library"
                        and row.get("accessible") is True]) != 1:
                    raise AdmissionError("native_library_unavailable")
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("native_application_unavailable") from None

    def estimate(self, job: dict) -> int | None:
        try:
            total = math.ceil(float(job.get("mb", 0)) * 1024 * 1024)
            left = math.ceil(float(job.get("mbleft", 0)) * 1024 * 1024)
        except (TypeError, ValueError, OverflowError):
            return None
        if total <= 0 or left < 0 or left > total:
            return None
        return left + math.ceil(total * 1.25) + MARGIN

    def pause_global(self) -> None:
        self.api("pause")

    def configure(self) -> dict:
        self.base.mkdir(parents=True, exist_ok=True, mode=0o700)
        before = self.sab.snapshot()
        self.pause_global()
        snapshot = self.sab.snapshot()
        ids = [job["nzo_id"] for job in snapshot["queue"]]
        if ids:
            self.api("queue", name="pause", value=",".join(ids))
        for name in ("download_free", "complete_free"):
            self.api("set_config", section="misc", keyword=name, value="30G")
        feeds = self.api("get_config", section="rss")["config"].get("rss", [])
        if {feed.get("name") for feed in feeds} != FEEDS:
            raise AdmissionError("cart_feed_set_requires_review")
        for feed in feeds:
            self.api("set_config", section="rss", keyword=feed["name"], priority=-2, enable=1)
        categories = self.api("get_config", section="categories")["config"].get("categories", [])
        names = {category.get("name") for category in categories}
        if not {"*", "prowlarr"}.issubset(names):
            raise AdmissionError("acquisition_categories_require_review")
        for name in ("*", "prowlarr"):
            self.api("set_config", section="categories", keyword=name, priority=-2)
        after = self.sab.snapshot()
        if any(job.get("status") != "Paused" for job in after["queue"]):
            raise AdmissionError("queue_pause_readback_failed")
        state = self.state()
        refreshing = bool(state.get("configured_at"))
        held = {item.get("nzo_id") for item in state.get("held", []) if isinstance(item, dict)}
        if not refreshing:
            state["owned"] = sorted({job["nzo_id"] for job in after["queue"]} - held)
        admitted = state.get("admitted")
        if admitted and not refreshing:
            identity = admitted.get("nzo_id") if isinstance(admitted, dict) else None
            queued = [job for job in after["queue"] if job.get("nzo_id") == identity]
            histories = [job for job in after["history"] if job.get("nzo_id") == identity]
            if isinstance(identity, str) and len(queued) == 1:
                state["admitted"] = None
            elif not isinstance(identity, str) or len(histories) != 1:
                raise AdmissionError("configured_admission_cannot_be_reconstructed")
            else:
                state["owned"] = sorted(set(state["owned"]) | {identity})
        state["configured_at"] = self.clock()
        if not refreshing:
            state["blocked"] = None
        self.save(state)
        if not before["paused"]:
            self.api("resume")
        final = self.sab.snapshot()
        if final["paused"] != before["paused"] or any(job.get("status") != "Paused" for job in final["queue"]):
            self.pause_global()
            raise AdmissionError("serialized_queue_readback_failed")
        return {"status": "configured", "owned_jobs": len(state["owned"]), "feeds_enabled_paused": 2,
                "reserve_bytes": RESERVE}

    def cart_completion(self, identity: str) -> tuple[str, str | None]:
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
        if not path.exists():
            return "waiting", None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("hold") == "cart_provenance_unproven" and record.get("phase") == "admitted":
            self.recover_cart_provenance(identity, path, record)
            return "waiting", None
        reason = record.get("hold") or record.get("last_error")
        if reason or record.get("phase") == "cleaned_with_retained_files":
            return "held", str(reason or "cleaned_with_retained_files")
        if record.get("phase") == "cleaned":
            return "cleaned", None
        return "waiting", None

    def isolate(self, state: dict, owned: set[str], admitted: dict, reason: str) -> None:
        identity = admitted["nzo_id"]
        held = [item for item in state.get("held", [])
                if isinstance(item, dict) and item.get("nzo_id") != identity]
        held.append({"nzo_id": identity, "reason": reason, "held_at": self.clock()})
        owned.discard(identity)
        state.update(admitted=None, owned=sorted(owned), held=held, blocked=None)

    def failed_paths(self, history: dict) -> list[Path]:
        roots = (self.root / "downloads/incomplete", self.root / "downloads/complete")
        result = []
        for value in (history.get("path"), history.get("storage")):
            if not value:
                continue
            path = Path(str(value))
            matches = [root for root in roots if path.parent == root]
            if len(matches) != 1 or path.is_symlink() or not path.is_dir():
                raise AdmissionError("failed_payload_path_requires_review")
            if path not in result:
                result.append(path)
        if not result:
            raise AdmissionError("failed_payload_missing")
        return result

    def reclaim_failed(self, history: dict) -> None:
        for path in self.failed_paths(history):
            if path.parent == self.root / "downloads/incomplete":
                admin = path / "__ADMIN__"
                if admin.is_symlink() or not admin.is_dir():
                    raise AdmissionError("failed_retry_admin_missing")
                for child in path.iterdir():
                    if child == admin:
                        continue
                    if child.is_symlink() or child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        shutil.rmtree(child)
                    else:
                        raise AdmissionError("failed_payload_entry_requires_review")
            else:
                shutil.rmtree(path)

    def recycle_failed(self, state: dict, owned: set[str], admitted: dict, history: dict) -> bool:
        filename = admitted.get("filename")
        if not isinstance(filename, str) or not filename:
            raise AdmissionError("failed_retry_filename_missing")
        key = hashlib.sha256(filename.encode()).hexdigest()
        attempts = int(state["failure_retries"].get(key, 0))
        self.reclaim_failed(history)
        if attempts >= MAX_FAILURE_RETRIES:
            self.isolate(state, owned, admitted, "download_failed_retry_limit")
            return False
        self.api("retry", value=admitted["nzo_id"])
        after = self.sab.snapshot()
        replacements = [job for job in after["queue"] if job.get("filename") == admitted.get("filename")]
        if len(replacements) != 1:
            raise AdmissionError("failed_retry_queue_readback_invalid")
        replacement = replacements[0]
        if replacement.get("status") != "Paused":
            self.api("queue", name="pause", value=replacement["nzo_id"])
            after = self.sab.snapshot()
            current = [job for job in after["queue"] if job["nzo_id"] == replacement["nzo_id"]]
            if len(current) != 1 or current[0].get("status") != "Paused":
                raise AdmissionError("failed_retry_pause_readback_failed")
        owned.discard(admitted["nzo_id"])
        owned.add(replacement["nzo_id"])
        state["failure_retries"][key] = attempts + 1
        state.update(admitted=None, owned=sorted(owned), blocked=None)
        return True

    def recover_cart_provenance(self, identity: str, path: Path, record: dict) -> None:
        import sqlite3
        database = sqlite3.connect(f"file:{self.root / 'config/sabnzbd/admin/history1.db'}?mode=ro", uri=True)
        database.row_factory = sqlite3.Row
        try:
            rows = list(database.execute(
                "SELECT status,category,archive,time_added,completed,url FROM history WHERE nzo_id = ?", (identity,)
            ))
        finally:
            database.close()
        if len(rows) != 1:
            raise AdmissionError("provenance_history_identity_invalid")
        row = rows[0]
        if (row["status"] != "Completed" or row["category"] not in (None, "", "*", "Default")
                or row["archive"] not in (None, 0) or not row["url"]):
            raise AdmissionError("provenance_history_not_recoverable")
        feeds = self.api("get_config", section="rss")["config"].get("rss", [])
        if {feed.get("name") for feed in feeds} != FEEDS:
            raise AdmissionError("cart_feed_set_requires_review")
        matches = []
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), cart_import_sab.NoRedirects())
        for feed in feeds:
            uris = feed.get("uri")
            if not isinstance(uris, list) or len(uris) != 1:
                raise AdmissionError("cart_feed_uri_invalid")
            request = urllib.request.Request(uris[0], headers={"User-Agent": "SABnzbd/5.1.3"})
            with opener.open(request, timeout=30) as response:
                body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise AdmissionError("cart_feed_too_large")
            urls = []
            for item in ElementTree.fromstring(body).iter():
                tag = item.tag.rsplit("}", 1)[-1]
                if tag == "enclosure" and item.get("url"):
                    urls.append(item.get("url"))
                elif tag in {"link", "guid"} and item.text:
                    urls.append(item.text.strip())
            if row["url"] in urls:
                matches.append(feed["name"])
        if len(matches) != 1:
            raise AdmissionError("live_cart_exact_url_match_not_unique")
        armed = json.loads((self.root / "state/catalog/cart-import/armed.json").read_text(encoding="utf-8"))
        if float(row["time_added"] or 0) < float(armed["armed_at"]):
            raise AdmissionError("completed_history_precedes_activation")
        record["job"]["provenance"] = {"feed": matches[0], "url_sha256": hashlib.sha256(row["url"].encode()).hexdigest(),
            "downloaded_at": float(row["time_added"]), "unique": True,
            "recovered_from_live_exact_cart_url_at": self.clock()}
        record.pop("hold", None)
        record["updated_at"] = self.clock()
        atomic(path, record)

    def pending_cart_reconciliation(self, admitted_identity: str | None) -> int:
        directory = self.root / "state/catalog/cart-import/jobs"
        paths = list(directory.glob("*.json"))
        if len(paths) > MAX_CART_JOURNALS:
            raise AdmissionError("cart_journal_count_exceeds_bound")
        pending = 0
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise AdmissionError("cart_journal_path_invalid")
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("phase") in TERMINAL_CART_PHASES:
                continue
            identity = (record.get("job") or {}).get("nzo_id")
            if not isinstance(identity, str) or not identity:
                raise AdmissionError("cart_journal_identity_invalid")
            if identity == admitted_identity:
                continue
            if record.get("hold") == "cart_provenance_unproven" and record.get("phase") == "admitted":
                self.recover_cart_provenance(identity, path, record)
            if not record.get("hold"):
                pending += 1
        return pending

    def reconcile_held(self, state: dict) -> None:
        directory = self.root / "state/catalog/cart-import/jobs"
        retained = []
        for item in state.get("held", []):
            if not isinstance(item, dict) or not isinstance(item.get("nzo_id"), str):
                raise AdmissionError("held_state_invalid")
            path = directory / (hashlib.sha256(item["nzo_id"].encode()).hexdigest() + ".json")
            if not path.exists():
                retained.append(item)
                continue
            if path.is_symlink() or not path.is_file():
                raise AdmissionError("cart_journal_path_invalid")
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("phase") in TERMINAL_CART_PHASES or not record.get("hold"):
                continue
            item["reason"] = str(record["hold"])
            retained.append(item)
        state["held"] = retained

    def run(self) -> dict:
        self.base.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.lock_path.open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AdmissionBusy() from None
            state = self.state()
            try:
                self.require_resources()
                self.require_dependencies()
            except Exception as error:
                state["blocked"] = (str(error) if isinstance(error, AdmissionError)
                                    else "capacity_resource_check_failed")
                self.pause_global()
                self.save(state)
                raise
            self.reconcile_held(state)
            snapshot = self.sab.snapshot()
            if snapshot["paused"]:
                # Global pauses may be deliberate or a previous fail-closed
                # response. Never change individual jobs or auto-resume them.
                self.save(state)
                return {"status": "globally_paused", "active_jobs": 0,
                        "paused_jobs": len(snapshot["queue"])}
            held_ids = {item.get("nzo_id") for item in state.get("held", []) if isinstance(item, dict)}
            intake_ids = {job["nzo_id"] for job in snapshot["queue"]
                          if job.get("status") == "Paused" and job.get("priority") == "Paused"
                          and job.get("cat") in CATEGORIES and job["nzo_id"] not in held_ids}
            eligible_ids = set(state["owned"]) | intake_ids
            groups = {}
            for job in snapshot["queue"]:
                if job["nzo_id"] in eligible_ids:
                    groups.setdefault(job.get("filename"), []).append(job)
            remove = []
            for name, members in groups.items():
                if not name or len(members) < 2:
                    continue
                ranked = sorted(members, key=lambda job: float(job.get("percentage", 0)), reverse=True)
                for job in ranked[1:]:
                    if job.get("status") != "Paused" or float(job.get("percentage", 0)) != 0:
                        raise AdmissionError("duplicate_queue_progress_requires_review")
                    remove.append(job["nzo_id"])
            if remove:
                self.api("queue", name="delete", value=",".join(remove), del_files=0)
                snapshot = self.sab.snapshot()
            queue = {job["nzo_id"]: job for job in snapshot["queue"]}
            admitted_identity = (state.get("admitted") or {}).get("nzo_id")
            owned = {identity for identity in state["owned"]
                     if identity in queue or identity == admitted_identity}
            owned.update(job["nzo_id"] for job in snapshot["queue"]
                         if job.get("status") == "Paused" and job.get("priority") == "Paused"
                         and job.get("cat") in CATEGORIES
                         and job["nzo_id"] not in held_ids)
            state["owned"] = sorted(owned)
            admitted = state.get("admitted")
            active = [job for job in snapshot["queue"] if job.get("status") != "Paused"]
            if admitted:
                identity = admitted["nzo_id"]
                if identity in queue:
                    if len(active) != 1 or active[0]["nzo_id"] != identity:
                        state["blocked"] = "admitted_job_pause_or_concurrency_changed"
                        self.pause_global(); self.save(state)
                        raise AdmissionError(state["blocked"])
                    if self.available() < RESERVE:
                        state["blocked"] = "reserve_breached"
                        self.pause_global(); self.save(state)
                        raise AdmissionError(state["blocked"])
                    state["blocked"] = None
                    self.save(state)
                    return {"status": "active", "active_jobs": 1, "paused_jobs": len(queue) - 1}
                replacements = [job for job in snapshot["queue"]
                                if job.get("filename") == admitted.get("filename")]
                if len(replacements) == 1:
                    replacement = replacements[0]
                    owned.discard(identity)
                    owned.add(replacement["nzo_id"])
                    admitted["nzo_id"] = replacement["nzo_id"]
                    state["owned"] = sorted(owned)
                    self.save(state)
                    return {"status": "materialized", "active_jobs": int(replacement.get("status") != "Paused"),
                            "paused_jobs": len(queue) - int(replacement.get("status") != "Paused")}
                histories = [job for job in snapshot["history"] if job["nzo_id"] == identity]
                if len(histories) != 1:
                    if self.clock() - float(admitted.get("admitted_at", 0)) <= 300:
                        self.save(state)
                        return {"status": "materializing", "active_jobs": 0, "paused_jobs": len(queue)}
                    state["blocked"] = "admitted_history_missing_or_ambiguous"
                elif histories[0]["status"] == "Failed":
                    self.recycle_failed(state, owned, admitted, histories[0])
                elif histories[0]["status"] != "Completed":
                    age = self.clock() - float(admitted.get("admitted_at", 0))
                    if snapshot.get("postprocessing", 0) or age <= 300:
                        self.save(state)
                        return {"status": "awaiting_sab_completion", "active_jobs": 0,
                                "paused_jobs": len(queue)}
                    state["blocked"] = "admitted_history_not_terminal"
                elif histories[0].get("category") in (None, "", "*", "Default"):
                    outcome, reason = self.cart_completion(identity)
                    if outcome == "waiting":
                        self.save(state)
                        return {"status": "awaiting_cart_cleanup", "active_jobs": 0, "paused_jobs": len(queue)}
                    if outcome == "held":
                        self.isolate(state, owned, admitted, reason or "cart_cleanup_held")
                else:
                    storage = Path(str(histories[0].get("storage") or ""))
                    if storage.exists():
                        self.save(state)
                        return {"status": "awaiting_arr_cleanup", "active_jobs": 0, "paused_jobs": len(queue)}
                if state.get("blocked"):
                    self.pause_global(); self.save(state)
                    raise AdmissionError(state["blocked"])
                if state.get("admitted"):
                    owned.discard(identity)
                    state.update(admitted=None, owned=sorted(owned), blocked=None)
            if active:
                state["blocked"] = "unmanaged_active_acquisition"
                self.pause_global(); self.save(state)
                raise AdmissionError(state["blocked"])
            pending = self.pending_cart_reconciliation(
                (state.get("admitted") or {}).get("nzo_id"))
            if pending:
                state["blocked"] = "awaiting_cart_reconciliation"
                self.save(state)
                return {"status": state["blocked"], "active_jobs": 0,
                        "paused_jobs": len(queue), "pending_cart_jobs": pending}
            candidates = []
            available = self.available()
            for identity in sorted(owned):
                job = queue.get(identity)
                estimate = self.estimate(job) if job and job.get("status") == "Paused" else None
                if estimate is not None and available - RESERVE >= estimate:
                    candidates.append((estimate, identity))
            if not candidates:
                state["blocked"] = ("awaiting_capacity_or_known_size"
                                    if any(identity in queue for identity in owned) else None)
                self.save(state)
                return {"status": state["blocked"] or "idle", "active_jobs": 0, "paused_jobs": len(queue)}
            estimate, identity = min(candidates)
            state.update(admitted={"nzo_id": identity, "filename": queue[identity].get("filename"),
                                   "estimate_bytes": estimate, "admitted_at": self.clock()}, blocked=None)
            self.save(state)
            self.api("queue", name="resume", value=identity)
            after = self.sab.snapshot()
            active = [job for job in after["queue"] if job.get("status") != "Paused"]
            if len(active) != 1 or active[0]["nzo_id"] != identity:
                self.pause_global()
                raise AdmissionError("single_admission_readback_failed")
            return {"status": "admitted", "active_jobs": 1, "paused_jobs": len(after["queue"]) - 1,
                    "estimate_bytes": estimate, "available_bytes": available, "reserve_bytes": RESERVE}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "run", "status"))
    args = parser.parse_args()
    controller = Controller()
    try:
        if args.action == "configure":
            result = controller.configure()
        elif args.action == "status":
            state = controller.state()
            result = {"status": "blocked" if state.get("blocked") else "active" if state.get("admitted") else "idle",
                      "blocked_reason": state.get("blocked"), "owned_jobs": len(state.get("owned", [])),
                      "admitted_jobs": int(bool(state.get("admitted"))),
                      "held_jobs": len(state.get("held", [])), "updated_at": state.get("updated_at")}
        else:
            result = controller.run()
        print(json.dumps(result, sort_keys=True))
        return 0
    except AdmissionBusy:
        # A second invocation must not pause the controller holding the lock.
        print(json.dumps({"status": "busy"}))
        return 0
    except Exception as error:
        try:
            controller.pause_global()
        except Exception:
            pass
        reason = str(error) if isinstance(error, AdmissionError) else "capacity_admission_failed"
        print(json.dumps({"status": "blocked", "reason": reason}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
