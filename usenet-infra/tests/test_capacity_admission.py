from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("capacity_admission", SCRIPTS / "capacity-admission.py")
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)


class FakeSab:
    def __init__(self, queue=None, history=None):
        self.state = {"queue": queue or [], "history": history or [], "rss_hashes": [],
                      "paused": False, "postprocessing": 0}
        self.feeds = [{"name": "NZBGeek Cart", "enable": 0}, {"name": "NZBFinder Cart", "enable": 0}]
        self.categories = [{"name": "*", "priority": 0}, {"name": "prowlarr", "priority": 0}]

    def snapshot(self):
        return copy.deepcopy(self.state)

    def api(self, mode, **values):
        if mode == "pause":
            self.state["paused"] = True
        elif mode == "resume":
            self.state["paused"] = False
        elif mode == "queue":
            ids = set(values["value"].split(","))
            if values["name"] == "delete":
                self.state["queue"] = [job for job in self.state["queue"] if job["nzo_id"] not in ids]
                return {"status": True}
            for job in self.state["queue"]:
                if job["nzo_id"] in ids:
                    job["status"] = "Paused" if values["name"] == "pause" else "Downloading"
        elif mode == "get_config":
            key = values["section"]
            return {"config": {key: self.feeds if key == "rss" else self.categories}}
        elif mode == "set_config" and values["section"] == "rss":
            feed = next(item for item in self.feeds if item["name"] == values["keyword"])
            feed.update({key: value for key, value in values.items() if key not in {"section", "keyword"}})
        elif mode == "set_config" and values["section"] == "categories":
            category = next(item for item in self.categories if item["name"] == values["keyword"])
            category.update({key: value for key, value in values.items() if key not in {"section", "keyword"}})
        elif mode == "retry":
            failed = next(job for job in self.state["history"] if job["nzo_id"] == values["value"])
            self.state["history"].remove(failed)
            replacement = {"nzo_id": failed["nzo_id"] + "-retry", "filename": failed["name"],
                           "status": "Paused", "cat": failed["category"], "mb": "1024",
                           "mbleft": "1024", "percentage": "0"}
            self.state["queue"].append(replacement)
        return {"status": True}


class CapacityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "state/catalog/cart-import/jobs").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def job(self, identity, size=1024, status="Paused", category="Default"):
        return {"nzo_id": identity, "filename": identity, "status": status, "cat": category,
                "priority": "Paused", "mb": str(size), "mbleft": str(size), "percentage": "0"}

    def controller(self, sab):
        value = admission.Controller(self.root, sab=sab, clock=lambda: 1000)
        value.available = lambda: 100 * 1024 ** 3
        return value

    def test_configure_pauses_intake_and_owns_existing_queue(self):
        sab = FakeSab([self.job("one", status="Queued"), self.job("two", status="Queued")])
        result = self.controller(sab).configure()
        self.assertEqual(result["owned_jobs"], 2)
        self.assertFalse(sab.state["paused"])
        self.assertTrue(all(job["status"] == "Paused" for job in sab.state["queue"]))
        self.assertTrue(all(feed["enable"] == 1 and feed["priority"] == -2 for feed in sab.feeds))
        self.assertTrue(all(category["priority"] == -2 for category in sab.categories))

    def test_configure_preserves_admitted_history_for_restart_reconstruction(self):
        sab = FakeSab(history=[{"nzo_id": "done", "status": "Completed", "category": "Default"}])
        controller = self.controller(sab)
        controller.base.mkdir(parents=True)
        controller.save({"schema_version": admission.SCHEMA, "owned": ["done"],
                         "admitted": {"nzo_id": "done", "filename": "done", "admitted_at": 900},
                         "held": [], "failure_retries": {}, "blocked": None})
        controller.configure()
        self.assertEqual(controller.state()["admitted"]["nzo_id"], "done")

    def test_configure_returns_paused_admitted_queue_item_to_owned_backlog(self):
        sab = FakeSab([self.job("queued")])
        controller = self.controller(sab)
        controller.base.mkdir(parents=True)
        controller.save({"schema_version": admission.SCHEMA, "owned": ["queued"],
                         "admitted": {"nzo_id": "queued", "filename": "queued", "admitted_at": 900},
                         "held": [], "failure_retries": {}, "blocked": None})
        controller.configure()
        self.assertIsNone(controller.state()["admitted"])
        self.assertIn("queued", controller.state()["owned"])

    def test_admits_exactly_one_fitting_job(self):
        sab = FakeSab([self.job("small", 1000), self.job("large", 2000)])
        controller = self.controller(sab)
        result = controller.configure()
        self.assertEqual(result["owned_jobs"], 2)
        result = controller.run()
        self.assertEqual(result["active_jobs"], 1)
        self.assertEqual([job["status"] for job in sab.state["queue"]].count("Downloading"), 1)

    def test_unknown_or_oversized_jobs_remain_paused(self):
        sab = FakeSab([self.job("unknown", 0), self.job("huge", 100000)])
        controller = self.controller(sab)
        controller.configure()
        controller.available = lambda: admission.RESERVE + 1024
        self.assertEqual(controller.run()["status"], "awaiting_capacity_or_known_size")
        self.assertTrue(all(job["status"] == "Paused" for job in sab.state["queue"]))

    def test_unmanaged_concurrency_fails_closed(self):
        sab = FakeSab([self.job("one", status="Downloading"), self.job("two", status="Downloading")])
        controller = self.controller(sab)
        with self.assertRaisesRegex(admission.AdmissionError, "unmanaged_active_acquisition"):
            controller.run()
        self.assertTrue(sab.state["paused"])

    def test_zero_progress_duplicates_are_collapsed_before_admission(self):
        first = self.job("one"); second = self.job("two"); second["filename"] = first["filename"]
        sab = FakeSab([first, second])
        controller = self.controller(sab)
        controller.configure()
        self.assertEqual(controller.run()["active_jobs"], 1)
        self.assertEqual(len(sab.state["queue"]), 1)
        self.assertEqual(len(controller.state()["owned"]), 1)

    def test_later_manual_pause_is_not_adopted_or_deduplicated(self):
        sab = FakeSab([self.job("owned")])
        controller = self.controller(sab)
        controller.configure()
        manual = self.job("manual")
        manual.update(filename="owned", priority="Normal")
        sab.state["queue"].append(manual)
        controller.run()
        self.assertEqual(len(sab.state["queue"]), 2)
        self.assertNotIn("manual", controller.state()["owned"])

    def test_new_paused_priority_job_is_adopted(self):
        sab = FakeSab()
        controller = self.controller(sab)
        controller.configure()
        sab.state["queue"].append(self.job("new"))
        self.assertEqual(controller.run()["status"], "admitted")
        self.assertIn("new", controller.state()["owned"])

    def test_orphaned_nonterminal_cart_journal_blocks_new_admission(self):
        sab = FakeSab([self.job("next")])
        controller = self.controller(sab)
        controller.configure()
        path = self.root / "state/catalog/cart-import/jobs/orphan.json"
        path.write_text(json.dumps({"phase": "source_verified", "job": {"nzo_id": "orphan"}}))
        self.assertEqual(controller.run()["status"], "awaiting_cart_reconciliation")
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")

    def test_orphaned_held_cart_journal_does_not_block_unrelated_work(self):
        sab = FakeSab([self.job("next")])
        controller = self.controller(sab)
        controller.configure()
        path = self.root / "state/catalog/cart-import/jobs/held.json"
        path.write_text(json.dumps({"phase": "source_verified", "hold": "identity_ambiguous",
                                    "job": {"nzo_id": "held"}}))
        self.assertEqual(controller.run()["status"], "admitted")

    def test_resolved_controller_hold_is_removed_from_durable_state(self):
        sab = FakeSab()
        controller = self.controller(sab)
        controller.configure()
        state = controller.state()
        state["held"] = [{"nzo_id": "resolved", "reason": "old", "held_at": 900}]
        controller.save(state)
        path = self.root / "state/catalog/cart-import/jobs" / (
            hashlib.sha256(b"resolved").hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "cleaned", "job": {"nzo_id": "resolved"}}))
        self.assertEqual(controller.run()["status"], "idle")
        self.assertEqual(controller.state()["held"], [])

    def test_cleaned_cart_completion_allows_next_job(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        state = controller.state()
        identity = state["admitted"]["nzo_id"]
        sab.state["queue"] = [job for job in sab.state["queue"] if job["nzo_id"] != identity]
        sab.state["history"] = [{"nzo_id": identity, "status": "Completed", "category": "Default"}]
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "cleaned"}))
        self.assertEqual(controller.run()["status"], "admitted")

    def test_legacy_provenance_hold_is_recovered_before_cleanup_wait(self):
        controller = self.controller(FakeSab())
        identity = "legacy"
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "admitted", "hold": "cart_provenance_unproven", "job": {"nzo_id": identity}}))
        with mock.patch.object(controller, "recover_cart_provenance") as recover:
            self.assertEqual(controller.cart_completion(identity), ("waiting", None))
        recover.assert_called_once()

    def test_cart_cleanup_hold_isolated_while_next_job_advances(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        state = controller.state()
        identity = state["admitted"]["nzo_id"]
        sab.state["queue"] = [job for job in sab.state["queue"] if job["nzo_id"] != identity]
        sab.state["history"] = [{"nzo_id": identity, "status": "Completed", "category": "Default"}]
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "source_verified", "hold": "native_target_has_file",
                                    "job": {"nzo_id": identity}}))
        result = controller.run()
        state = controller.state()
        self.assertEqual(result["status"], "admitted")
        self.assertEqual(len(state["held"]), 1)
        self.assertEqual(state["held"][0]["reason"], "native_target_has_file")
        self.assertFalse(sab.state["paused"])

    def test_failed_download_payload_is_removed_and_exact_job_retried(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        state = controller.state()
        identity = state["admitted"]["nzo_id"]
        sab.state["queue"] = [job for job in sab.state["queue"] if job["nzo_id"] != identity]
        failed = self.root / "downloads/incomplete/failed"
        failed.mkdir(parents=True)
        (failed / "__ADMIN__").mkdir()
        (failed / "partial").write_bytes(b"partial")
        sab.state["history"] = [{"nzo_id": identity, "name": identity, "status": "Failed",
                                 "category": "Default", "path": str(failed), "storage": None}]
        result = controller.run()
        state = controller.state()
        self.assertEqual(result["status"], "admitted")
        self.assertEqual([path.name for path in failed.iterdir()], ["__ADMIN__"])
        self.assertEqual(sum(state["failure_retries"].values()), 1)
        self.assertEqual(state["held"], [])
        self.assertFalse(sab.state["paused"])

    def test_nonterminal_history_never_reclaims_payload(self):
        sab = FakeSab([self.job("first")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        identity = controller.state()["admitted"]["nzo_id"]
        sab.state["queue"] = []
        payload = self.root / "downloads/incomplete/running"
        payload.mkdir(parents=True)
        (payload / "partial").write_bytes(b"partial")
        sab.state["history"] = [{"nzo_id": identity, "name": identity, "status": "Running",
                                 "category": "Default", "path": str(payload), "storage": None}]
        self.assertEqual(controller.run()["status"], "awaiting_sab_completion")
        self.assertTrue((payload / "partial").exists())

    def test_failed_download_retry_limit_reclaims_and_quarantines(self):
        sab = FakeSab([self.job("first")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        state = controller.state()
        identity = state["admitted"]["nzo_id"]
        failed = self.root / "downloads/complete/failed"
        failed.mkdir(parents=True)
        (failed / "payload").write_bytes(b"payload")
        sab.state["queue"] = []
        sab.state["history"] = [{"nzo_id": identity, "name": identity, "status": "Failed",
                                 "category": "Default", "path": None, "storage": str(failed)}]
        key = hashlib.sha256(identity.encode()).hexdigest()
        state["failure_retries"][key] = admission.MAX_FAILURE_RETRIES
        controller.save(state)
        self.assertEqual(controller.run()["status"], "idle")
        state = controller.state()
        self.assertFalse(failed.exists())
        self.assertEqual(state["held"][0]["reason"], "download_failed_retry_limit")


if __name__ == "__main__":
    unittest.main()
