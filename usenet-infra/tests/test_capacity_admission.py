from __future__ import annotations

import copy
import fcntl
import hashlib
import importlib.util
import io
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
        value.require_resources = mock.Mock()
        value.require_dependencies = mock.Mock()
        value.preflight_cart = mock.Mock()
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

    def test_materialized_normal_priority_cart_is_admitted_from_provenance(self):
        sab = FakeSab()
        controller = self.controller(sab)
        controller.configure()
        armed = self.root / 'state/catalog/cart-import/armed.json'
        armed.write_text(json.dumps({'schema_version': 1, 'armed_at': 100,
                                     'excluded_ids': ['protected'], 'excluded_rss_hashes': ['old']}))
        job = self.job('new')
        job.update(priority='Normal', paused_intake={'feed': 'NZBGeek Cart',
                   'downloaded_at': 200, 'url_sha256': 'new'})
        sab.state['queue'].append(job)
        self.assertEqual(controller.run()['status'], 'admitted')
        self.assertEqual(controller.state()['admitted']['nzo_id'], 'new')

    def test_materialized_intake_preserves_activation_exclusions_and_holds(self):
        controller = self.controller(FakeSab())
        armed = self.root / 'state/catalog/cart-import/armed.json'
        armed.write_text(json.dumps({'schema_version': 1, 'armed_at': 100,
                                     'excluded_ids': ['protected'], 'excluded_rss_hashes': ['old']}))
        jobs=[]
        for identity, downloaded, url in [('protected',200,'new'), ('old-feed',200,'old'),
                                         ('too-old',99,'new'), ('held',200,'new'), ('eligible',200,'new')]:
            job=self.job(identity)
            job.update(priority='Normal',paused_intake={'feed':'NZBGeek Cart',
                       'downloaded_at':downloaded,'url_sha256':url})
            jobs.append(job)
        self.assertEqual(controller.intake_ids({'queue':jobs},{'held'}), {'eligible'})

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

    def test_recovered_admission_failure_preserves_payload_and_reservation(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        state = controller.state()
        state["admitted"]["preserve_failed_payload"] = True
        controller.save(state)
        reservation = copy.deepcopy(state["admitted"])
        identity = reservation["nzo_id"]
        sab.state["queue"] = [j for j in sab.state["queue"] if j["nzo_id"] != identity]
        sab.state["history"] = [{"nzo_id": identity, "status": "Failed", "category": "Default"}]
        with mock.patch.object(controller, "recycle_failed") as recycle:
            with self.assertRaisesRegex(admission.AdmissionError, "recovered_payload_failed_review"):
                controller.run()
        recycle.assert_not_called()
        self.assertTrue(sab.state["paused"])
        self.assertEqual(controller.state()["admitted"], reservation)
        self.assertTrue(all(j["status"] == "Paused" for j in sab.state["queue"]))

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

    def test_burst_drains_sequentially_across_restarts_and_duplicate_polls(self):
        sab = FakeSab([self.job(f"request-{index}") for index in range(12)])
        controller = self.controller(sab)
        controller.configure()
        completed = set()
        for index in range(12):
            # A new process reconstructs its reservation from the durable state.
            controller = self.controller(sab)
            self.assertEqual(controller.run()["status"], "admitted")
            identity = controller.state()["admitted"]["nzo_id"]
            self.assertNotIn(identity, completed)
            self.assertEqual(sum(j["status"] != "Paused" for j in sab.state["queue"]), 1)
            duplicate = self.job(f"poll-{index}")
            duplicate["filename"] = identity
            sab.state["queue"].append(duplicate)
            self.assertEqual(self.controller(sab).run()["status"], "active")
            self.assertNotIn(duplicate["nzo_id"], [j["nzo_id"] for j in sab.state["queue"]])
            sab.state["queue"] = [j for j in sab.state["queue"] if j["nzo_id"] != identity]
            sab.state["history"].append({"nzo_id": identity, "status": "Completed", "category": "Default"})
            # Repair/import/verification have not finished; no second acquisition.
            self.assertEqual(self.controller(sab).run()["status"], "awaiting_cart_cleanup")
            self.assertTrue(all(j["status"] == "Paused" for j in sab.state["queue"]))
            journal = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
            journal.write_text(json.dumps({"phase": "cleaned", "job": {"nzo_id": identity}}))
            completed.add(identity)
        self.assertEqual(self.controller(sab).run()["status"], "idle")
        self.assertEqual(len(sab.state["history"]), 12)

    def test_existing_allocations_and_retained_failures_reduce_admission_budget(self):
        sab = FakeSab([self.job("partial", size=4096)])
        sab.state["queue"][0].update(mbleft="1024", percentage="75")
        controller = self.controller(sab)
        controller.configure()
        peak = (1024 + 4096 * 1.25) * 1024 ** 2 + admission.MARGIN
        controller.available = lambda: admission.RESERVE + peak - 1
        self.assertEqual(controller.run()["status"], "awaiting_capacity_or_known_size")
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")
        controller.available = lambda: admission.RESERVE + peak
        self.assertEqual(controller.run()["status"], "admitted")

    def test_unpacking_blocks_next_job_even_when_free_bytes_are_high(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure(); controller.run()
        identity = controller.state()["admitted"]["nzo_id"]
        sab.state["queue"] = [j for j in sab.state["queue"] if j["nzo_id"] != identity]
        sab.state["history"] = [{"nzo_id": identity, "status": "Running", "category": "Default"}]
        sab.state["postprocessing"] = 1
        controller.clock = lambda: 10_000
        self.assertEqual(controller.run()["status"], "awaiting_sab_completion")
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")

    def test_reserve_breach_pauses_without_releasing_or_deleting_jobs(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure(); controller.run()
        before = copy.deepcopy(sab.state["queue"])
        controller.available = lambda: admission.RESERVE - 1
        with self.assertRaisesRegex(admission.AdmissionError, "reserve_breached"):
            controller.run()
        self.assertTrue(sab.state["paused"])
        self.assertEqual(sab.state["queue"], before)

    def test_user_pausing_admitted_job_survives_controller_restart(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure(); controller.run()
        for job in sab.state["queue"]:
            job["status"] = "Paused"
        with self.assertRaisesRegex(admission.AdmissionError, "admitted_job_pause_or_concurrency_changed"):
            self.controller(sab).run()
        self.assertTrue(all(j["status"] == "Paused" for j in sab.state["queue"]))

    def test_competing_controller_cannot_spend_same_reservation(self):
        sab = FakeSab([self.job("first")])
        controller = self.controller(sab)
        controller.configure()
        with controller.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.controller(sab).run()
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")

    def test_failed_reservation_write_never_resumes_acquisition(self):
        sab = FakeSab([self.job("first")])
        controller = self.controller(sab)
        controller.configure()
        with mock.patch.object(controller, "save", side_effect=OSError("fixture disk full")):
            with self.assertRaises(OSError):
                controller.run()
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")
        self.assertIsNone(controller.state()["admitted"])

    def test_lost_resume_response_reconstructs_without_second_admission(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        original = sab.api
        def lose_response(mode, **values):
            result = original(mode, **values)
            if mode == "queue" and values.get("name") == "resume":
                raise TimeoutError("fixture response lost")
            return result
        with mock.patch.object(sab, "api", side_effect=lose_response):
            with self.assertRaises(TimeoutError):
                controller.run()
        self.assertEqual(self.controller(sab).run()["status"], "active")
        self.assertEqual(sum(j["status"] != "Paused" for j in sab.state["queue"]), 1)

    def test_root_reserved_blocks_are_not_application_capacity(self):
        controller = admission.Controller(self.root, sab=FakeSab())
        with mock.patch.object(admission.os, "statvfs", return_value=mock.Mock(
                f_bavail=100, f_bfree=10000, f_frsize=4096)):
            self.assertEqual(controller.available(), 409600)

    def test_inode_pressure_preserves_jobs_and_durable_reservation(self):
        for admitted in (False, True):
            with self.subTest(admitted=admitted):
                sab = FakeSab([self.job("first"), self.job("second")])
                controller = self.controller(sab)
                controller.configure()
                if admitted:
                    controller.run()
                before = copy.deepcopy(sab.state["queue"])
                reservation = controller.state()["admitted"]
                controller.require_resources.side_effect = admission.AdmissionError("inode_reserve_unavailable")
                with self.assertRaisesRegex(admission.AdmissionError, "inode_reserve_unavailable"):
                    controller.run()
                self.assertTrue(sab.state["paused"])
                self.assertEqual(sab.state["queue"], before)
                self.assertEqual(controller.state()["admitted"], reservation)
                self.assertEqual(controller.state()["blocked"], "inode_reserve_unavailable")

    def test_inode_guard_uses_application_available_inodes(self):
        controller = self.controller(FakeSab())
        for relative in ("downloads/incomplete", "downloads/complete", "config"):
            (self.root / relative).mkdir(parents=True)
        for available in (0, admission.INODE_RESERVE - 1, admission.INODE_RESERVE):
            with self.subTest(available=available), mock.patch.object(admission.os, "statvfs",
                    return_value=mock.Mock(f_files=1_000_000, f_ffree=500_000, f_favail=available)):
                if available < admission.INODE_RESERVE:
                    with self.assertRaisesRegex(admission.AdmissionError, "inode_reserve_unavailable"):
                        admission.Controller.require_resources(controller)
                else:
                    admission.Controller.require_resources(controller)

    def test_unexpected_scratch_mount_fails_closed(self):
        controller = self.controller(FakeSab())
        controller.remote_scratch = mock.Mock(return_value=None)
        controller.repair_spool = mock.Mock(return_value=None)
        with mock.patch.object(Path, "stat", side_effect=[mock.Mock(st_dev=1), mock.Mock(st_mode=0o40700),
                mock.Mock(st_mode=0o40700), mock.Mock(st_dev=2)]):
            with self.assertRaisesRegex(admission.AdmissionError, "scratch_filesystem_layout_changed"):
                admission.Controller.require_resources(controller)

    def test_mount_outage_blocks_new_and_active_acquisitions(self):
        for active in (False, True):
            with self.subTest(active=active):
                sab = FakeSab([self.job("first"), self.job("second")])
                controller = self.controller(sab)
                controller.configure()
                if active:
                    controller.run()
                before = copy.deepcopy(sab.state)
                controller.require_dependencies = lambda: admission.Controller.require_dependencies(controller)
                with mock.patch.object(Path, "is_mount", return_value=False):
                    with self.assertRaisesRegex(admission.AdmissionError, "canonical_mount_unavailable"):
                        controller.run()
                self.assertTrue(sab.state["paused"])
                self.assertEqual(sab.state["queue"], before["queue"])
                self.assertEqual(sab.state["history"], before["history"])

    def test_application_outages_and_inaccessible_native_roots(self):
        for response in (TimeoutError(), [], [{"path": "/library", "accessible": False}]):
            with self.subTest(response=response):
                sab = FakeSab([self.job("first")])
                controller = self.controller(sab)
                controller.configure()
                api = mock.Mock()
                if isinstance(response, Exception):
                    api.call.side_effect = response
                else:
                    api.call.return_value = response
                controller.discovery_api = lambda: api
                controller.require_dependencies = lambda: admission.Controller.require_dependencies(controller)
                with mock.patch.object(Path, "is_mount", return_value=True), mock.patch.object(Path, "is_dir", return_value=True):
                    with self.assertRaises(admission.AdmissionError):
                        controller.run()
                self.assertTrue(sab.state["paused"])
                self.assertEqual(sab.state["queue"][0]["status"], "Paused")
                self.assertIsNone(controller.state()["admitted"])

    def test_both_native_roots_checked_with_bounded_timeout(self):
        controller = self.controller(FakeSab())
        api = mock.Mock()
        api.call.return_value = [{"path": "/library", "accessible": True}]
        controller.discovery_api = lambda: api
        with mock.patch.object(Path, "is_mount", return_value=True), mock.patch.object(Path, "is_dir", return_value=True):
            admission.Controller.require_dependencies(controller)
        self.assertEqual(api.call.call_args_list, [mock.call("radarr", "rootfolder", timeout=5),
                                                 mock.call("sonarr", "rootfolder", timeout=5)])

    def test_global_manual_pause_does_not_reserve_or_mutate_jobs(self):
        sab = FakeSab([self.job("first"), self.job("second")])
        controller = self.controller(sab)
        controller.configure()
        sab.state["paused"] = True
        before = copy.deepcopy(sab.state)
        self.assertEqual(controller.run()["status"], "globally_paused")
        self.assertIsNone(controller.state()["admitted"])
        self.assertEqual(sab.state, before)

    def test_configuration_refresh_preserves_manual_pause_and_ownership(self):
        sab = FakeSab([self.job("owned")])
        controller = self.controller(sab)
        controller.configure()
        manual = self.job("manual")
        manual["priority"] = "Normal"
        sab.state["queue"].append(manual)
        sab.state["paused"] = True
        controller.configure()
        self.assertTrue(sab.state["paused"])
        self.assertEqual(controller.state()["owned"], ["owned"])

    def test_configuration_refresh_preserves_admitted_user_pause(self):
        sab = FakeSab([self.job("owned")])
        controller = self.controller(sab)
        controller.configure()
        controller.run()
        reservation = controller.state()["admitted"]
        sab.state["queue"][0]["status"] = "Paused"
        controller.configure()
        self.assertEqual(controller.state()["admitted"], reservation)
        with self.assertRaisesRegex(admission.AdmissionError, "admitted_job_pause_or_concurrency_changed"):
            controller.run()
        self.assertEqual(sab.state["queue"][0]["status"], "Paused")

    def test_service_runs_guard_even_when_mount_service_is_down(self):
        unit = (SCRIPTS.parent / "ansible/roles/cloud_cart_import/templates/usenet-capacity-admission.service.j2").read_text()
        # A mount-dependent unit skips ExecStart entirely during an outage,
        # bypassing the Python guard that pauses an already active SAB job.
        self.assertNotIn("BindsTo=", unit)
        self.assertNotIn("Requires=", unit)
        self.assertNotIn("ExecStartPre=", unit)

    def test_cli_lock_contention_does_not_pause_owner(self):
        controller = mock.Mock()
        controller.run.side_effect = admission.AdmissionBusy()
        with mock.patch.object(admission, "Controller", return_value=controller), \
                mock.patch.object(sys, "argv", ["capacity-admission.py", "run"]), \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            self.assertEqual(admission.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {"status": "busy"})
        controller.pause_global.assert_not_called()

    def test_sab_outage_does_not_resume_or_delete_and_attempts_pause(self):
        sab = FakeSab([self.job("first")])
        controller = self.controller(sab)
        controller.configure()
        before = copy.deepcopy(sab.state["queue"])
        with mock.patch.object(sab, "snapshot", side_effect=TimeoutError()), \
                mock.patch.object(admission, "Controller", return_value=controller), \
                mock.patch.object(sys, "argv", ["capacity-admission.py", "run"]), \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(admission.main(), 1)
        self.assertTrue(sab.state["paused"])
        self.assertEqual(sab.state["queue"], before)
        self.assertIsNone(controller.state()["admitted"])

    def test_malformed_and_nonfinite_sizes_stay_held(self):
        for value in (None, "bad", "NaN", "Infinity", "-Infinity", "-1"):
            sab = FakeSab([self.job("invalid"), self.job("valid")])
            sab.state["queue"][0]["mb"] = value
            controller = self.controller(sab)
            controller.state_path.unlink(missing_ok=True)
            controller.configure()
            self.assertEqual(controller.run()["status"], "admitted")
            self.assertEqual(controller.state()["admitted"]["nzo_id"], "valid")

    def test_peak_allocation_trace_retains_state_and_blocks_second_job(self):
        # GiB-scale allocations are simulated; only the real journals use disk.
        # 40 GiB archive, 10 GiB already present, 40 GiB output, 10 GiB repair
        # workspace, and the explicit 5 GiB application margin coexist at peak.
        gib = 1024 ** 3
        sab = FakeSab([self.job("first", 40 * 1024), self.job("second", 60 * 1024)])
        sab.state["queue"][0].update(mbleft=str(30 * 1024), percentage="25")
        controller = self.controller(sab)
        controller.configure()
        free = admission.RESERVE + 85 * gib
        controller.available = lambda: free
        result = controller.run()
        self.assertEqual(result["estimate_bytes"], 85 * gib)
        for phase, allocation in (("download", 30), ("repair", 10), ("unpack", 40), ("state_margin", 5)):
            with self.subTest(phase=phase):
                free -= allocation * gib
                controller = self.controller(sab)
                controller.available = lambda: free
                self.assertEqual(controller.run()["status"], "active")
                self.assertGreaterEqual(free, admission.RESERVE)
                self.assertEqual(sab.state["queue"][1]["status"], "Paused")
                self.assertEqual(json.loads(controller.state_path.read_text())["admitted"]["nzo_id"], "first")
        free -= 1  # Unknown extra allocation triggers the runtime floor.
        with self.assertRaisesRegex(admission.AdmissionError, "reserve_breached"):
            controller.run()
        self.assertTrue(sab.state["paused"])

    def enable_remote(self, controller):
        marker = self.root / "config/catalog/remote-scratch.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"schema_version": 1, "mode": "storagebox"}))
        return controller.remote_scratch()

    def test_remote_budget_can_admit_80_gib_without_spending_local_scratch(self):
        sab = FakeSab([self.job("large", 80 * 1024), self.job("other", 81 * 1024)])
        controller = self.controller(sab)
        controller.configure()
        self.enable_remote(controller)
        controller.available = lambda: 75 * 1024**3
        controller.budget_available = lambda: 300 * 1024**3
        outcome = controller.run()
        self.assertEqual(outcome["status"], "admitted")
        self.assertEqual(outcome["estimate_bytes"], 205 * 1024**3)
        self.assertEqual(sum(j["status"] == "Downloading" for j in sab.state["queue"]), 1)

    def enable_hybrid(self, controller):
        self.enable_remote(controller)
        (self.root / 'config/catalog/remote-scratch.json').write_text(json.dumps(
            {'schema_version': 2, 'mode': 'hybrid', 'native_hardlinks': True}))

    def test_hybrid_budgets_each_filesystem_instead_of_three_remote_copies(self):
        controller = self.controller(FakeSab([self.job('large', 80 * 1024)]))
        controller.configure(); self.enable_hybrid(controller)
        controller.available = lambda: 195 * 1024**3
        controller.budget_available = lambda: 135 * 1024**3
        self.assertEqual(controller.run()['status'], 'admitted')
        self.assertEqual(controller.state()['admitted']['estimate_bytes'], 105 * 1024**3)
        self.assertEqual(controller.state()['admitted']['local_estimate_bytes'], 165 * 1024**3)

    def test_hybrid_requires_both_budgets_and_does_not_spend_reserves(self):
        for local, remote in [(195 * 1024**3 - 1, 1000 * 1024**3),
                              (1000 * 1024**3, 135 * 1024**3 - 1)]:
            controller = self.controller(FakeSab([self.job('large', 80 * 1024)]))
            controller.configure(); self.enable_hybrid(controller)
            controller.available = lambda: local
            controller.budget_available = lambda: remote
            self.assertEqual(controller.run()['status'], 'awaiting_capacity_or_known_size')
            self.assertIsNone(controller.state()['admitted'])

    def test_hybrid_serial_drain_accounts_only_final_library_growth_after_cleanup(self):
        sab = FakeSab([self.job(str(i), 64 * 1024) for i in range(3)])
        controller = self.controller(sab)
        controller.configure(); self.enable_hybrid(controller)
        remote_free = 230 * 1024**3
        controller.available = lambda: 170 * 1024**3
        controller.budget_available = lambda: remote_free
        for _ in range(3):
            self.assertEqual(controller.run()['status'], 'admitted')
            identity = controller.state()['admitted']['nzo_id']
            sab.state['queue'] = [j for j in sab.state['queue'] if j['nzo_id'] != identity]
            sab.state['history'].append({'nzo_id': identity, 'status': 'Completed', 'category': 'Default'})
            self.assertEqual(controller.run()['status'], 'awaiting_cart_cleanup')
            path = self.root / 'state/catalog/cart-import/jobs' / (hashlib.sha256(identity.encode()).hexdigest() + '.json')
            path.write_text(json.dumps({'phase': 'cleaned', 'job': {'nzo_id': identity}}))
            remote_free -= 54 * 1024**3
        self.assertEqual(controller.run()['status'], 'idle')
        self.assertFalse(sab.state['paused'])

    def test_hybrid_skips_job_whose_parity_repair_would_breach_local_floor(self):
        controller = self.controller(FakeSab([self.job('large', 80 * 1024), self.job('fitting', 12 * 1024)]))
        controller.configure(); self.enable_hybrid(controller)
        controller.available = lambda: 123 * 1024**3
        controller.budget_available = lambda: 131 * 1024**3
        self.assertEqual(controller.run()['status'], 'admitted')
        self.assertEqual(controller.state()['admitted']['nzo_id'], 'fitting')
        self.assertEqual(controller.state()['admitted']['local_estimate_bytes'], 29 * 1024**3)

    def test_remote_budget_reserves_source_and_canonical_copy_together(self):
        controller = self.controller(FakeSab([self.job("large", 80 * 1024)]))
        controller.configure()
        self.enable_remote(controller)
        controller.available = lambda: 1000 * 1024**3
        controller.budget_available = lambda: admission.RESERVE + 205 * 1024**3 - 1
        self.assertEqual(controller.run()["status"], "awaiting_capacity_or_known_size")
        self.assertIsNone(controller.state()["admitted"])

    def test_remote_mount_loss_cannot_fall_back_to_empty_local_directory(self):
        controller = self.controller(FakeSab())
        remote = self.enable_remote(controller)
        for relative in ("downloads/complete", "state/catalog", "downloads/incomplete"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        remote.mkdir()
        with mock.patch.object(admission.os, "statvfs", return_value=mock.Mock(
                f_files=1000000, f_favail=500000, f_bavail=100*1024**3, f_frsize=1)):
            with self.assertRaisesRegex(admission.AdmissionError, "remote_scratch_mount_unavailable"):
                admission.Controller.require_resources(controller)

    def test_remote_mode_still_requires_local_application_reserve(self):
        controller = self.controller(FakeSab())
        self.enable_remote(controller)
        for relative in ("downloads/complete", "state/catalog"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        controller.available = lambda: admission.RESERVE - 1
        with mock.patch.object(admission.os, "statvfs", return_value=mock.Mock(f_files=1000000, f_favail=500000)):
            with self.assertRaisesRegex(admission.AdmissionError, "reserve_breached"):
                admission.Controller.require_resources(controller)

    def test_remote_config_is_explicit_and_symlinks_are_rejected(self):
        controller = self.controller(FakeSab())
        self.assertIsNone(controller.remote_scratch())
        self.enable_remote(controller)
        marker = self.root / "config/catalog/remote-scratch.json"
        marker.write_text('{}')
        with self.assertRaisesRegex(admission.AdmissionError, "configuration_invalid"):
            controller.remote_scratch()
        marker.unlink(); marker.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(admission.AdmissionError, "configuration_invalid"):
            controller.remote_scratch()

    def test_remote_ambiguous_identity_is_held_before_allocating_payload(self):
        sab = FakeSab([self.job("ambiguous"), self.job("other", 2048)])
        controller = self.controller(sab)
        controller.configure()
        self.enable_remote(controller)
        controller.budget_available = lambda: 300 * 1024**3
        controller.preflight_cart.side_effect = admission.cart_import_arr.CartImportHold("catalog_identity_ambiguous")
        self.assertEqual(controller.run()["status"], "identity_held_before_download")
        self.assertIsNone(controller.state()["admitted"])
        self.assertTrue(all(j["status"] == "Paused" for j in sab.state["queue"]))
        self.assertEqual(controller.state()["held"][0]["reason"], "preflight_catalog_identity_ambiguous")
        controller.preflight_cart.side_effect = None
        self.assertEqual(controller.run()["status"], "admitted")
        self.assertEqual(controller.state()["admitted"]["nzo_id"], "other")

    def test_failed_remote_job_reclaims_only_its_payload_and_keeps_admin(self):
        controller = self.controller(FakeSab())
        self.enable_remote(controller)
        directory = self.root / "downloads/incomplete/Example.Failed"
        (directory / "__ADMIN__").mkdir(parents=True)
        (directory / "__ADMIN__/retry").write_bytes(b'request')
        (directory / "payload.rar").write_bytes(b'payload')
        controller.reclaim_failed({"path": "/data/incomplete/Example.Failed"})
        self.assertEqual((directory / "__ADMIN__/retry").read_bytes(), b'request')
        self.assertFalse((directory / "payload.rar").exists())
        with self.assertRaisesRegex(admission.AdmissionError, "path_requires_review"):
            controller.failed_paths({"path": "/data/complete/remote/complete"})

    def test_long_postprocessing_without_history_retains_reservation(self):
        sab = FakeSab([self.job("first"), self.job("next", 2048)])
        controller = self.controller(sab)
        controller.configure(); controller.run()
        state = controller.state(); state["admitted"]["admitted_at"] = 0; controller.save(state)
        sab.state["queue"] = [j for j in sab.state["queue"] if j["nzo_id"] != "first"]
        sab.state["postprocessing"] = 1
        for _ in range(3):
            self.assertEqual(controller.run()["status"], "awaiting_sab_completion")
            self.assertFalse(sab.state["paused"])
            self.assertEqual(controller.state()["admitted"]["nzo_id"], "first")
            self.assertEqual(sab.state["queue"][0]["status"], "Paused")
        sab.state["postprocessing"] = 0
        sab.state["history"].append({"nzo_id": "first", "status": "Completed", "category": "Default"})
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(b"first").hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "cleaned", "job": {"nzo_id": "first"}}))
        self.assertEqual(controller.run()["status"], "admitted")
        self.assertEqual(controller.state()["admitted"]["nzo_id"], "next")

    def test_explicit_resume_recomputes_old_missing_history_block(self):
        sab = FakeSab([self.job("first"), self.job("next", 2048)])
        controller = self.controller(sab)
        controller.configure(); controller.run()
        state = controller.state(); state["admitted"]["admitted_at"] = 0; controller.save(state)
        sab.state["queue"] = [j for j in sab.state["queue"] if j["nzo_id"] != "first"]
        with self.assertRaisesRegex(admission.AdmissionError, "admitted_history_missing_or_ambiguous"):
            controller.run()
        self.assertTrue(sab.state["paused"])
        sab.state["history"].append({"nzo_id": "first", "status": "Completed", "category": "Default"})
        path = self.root / "state/catalog/cart-import/jobs" / (hashlib.sha256(b"first").hexdigest() + ".json")
        path.write_text(json.dumps({"phase": "cleaned", "job": {"nzo_id": "first"}}))
        self.assertEqual(controller.run()["status"], "globally_paused")
        sab.api("resume")
        self.assertEqual(controller.run()["status"], "admitted")
        self.assertIsNone(controller.state()["blocked"])


if __name__ == "__main__":
    unittest.main()
