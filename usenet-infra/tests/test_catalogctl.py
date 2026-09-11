from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "catalogctl.py"
SPEC = importlib.util.spec_from_file_location("catalogctl", MODULE_PATH)
assert SPEC and SPEC.loader
catalogctl = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = catalogctl
SPEC.loader.exec_module(catalogctl)


class RemotePathTests(unittest.TestCase):
    def test_sftp_home_relative_root_does_not_become_absolute(self):
        self.assertEqual(catalogctl.remote_join('catalog:', 'manifests'), 'catalog:manifests')
        self.assertEqual(catalogctl.remote_join('catalog:', 'objects', 'other/test'),
                         'catalog:objects/other/test')

    def test_explicit_absolute_root_and_nested_root_are_preserved(self):
        self.assertEqual(catalogctl.remote_join('storage:/', 'manifests'), 'storage:/manifests')
        self.assertEqual(catalogctl.remote_join('storage:catalog/', 'manifests'),
                         'storage:catalog/manifests')
        with mock.patch.dict(os.environ, {'CATALOG_REMOTE': 'storage:/'}, clear=False):
            self.assertEqual(catalogctl.Settings.from_env().remote, 'storage:/')


def manifest(item_id: str = "authorized-test") -> dict:
    payload = b"authorized integration fixture\n"
    return {
        "schema_version": 1,
        "id": item_id,
        "title": "Authorized test",
        "category": "other",
        "source": {"description": "generated fixture"},
        "authorization": {"basis": "generated for this test"},
        "acquired_at": "2026-09-10T12:00:00+00:00",
        "remote_path": f"objects/other/{item_id}",
        "size_bytes": len(payload),
        "files": [
            {
                "path": "fixture.txt",
                "size_bytes": len(payload),
                "sha256": catalogctl.hashlib.sha256(payload).hexdigest(),
            }
        ],
        "integrity": {
            "algorithm": "sha256",
            "verified_at": "2026-09-10T12:01:00+00:00",
        },
        "notes": "",
    }


class FakeRclone:
    def __init__(self, remote_root: Path):
        self.remote_root = remote_root
        self.calls: list[tuple[str, ...]] = []

    def _remote(self, value: str) -> Path:
        _, path = value.split(":", 1)
        return self.remote_root / path

    def run(self, *args: str, capture: bool = False) -> str:
        self.calls.append(args)
        if args[0] == "lsf":
            path = self._remote(args[1])
            return "".join(f"{entry.name}\n" for entry in sorted(path.glob("*.json")))
        if args[0] == "cat":
            return self._remote(args[1]).read_text(encoding="utf-8")
        if args[0] == "copy":
            source = self._remote(args[1])
            destination = Path(args[2])
            destination.mkdir(parents=True, exist_ok=True)
            for entry in source.rglob("*"):
                if entry.is_file():
                    target = destination / entry.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(entry, target)
            return ""
        raise AssertionError(f"unexpected fake rclone call: {args}")

    def read_json(self, path: str) -> dict:
        return json.loads(self.run("cat", path, capture=True))


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.settings = catalogctl.Settings(
            remote="storage:catalog",
            local_root=base / "library",
            state_root=base / "state",
            staging_root=base / "staging",
            promotion_root=base / "complete",
            rclone="rclone",
            transfers=2,
            checkers=4,
            min_free_bytes=0,
        )
        self.remote = base / "remote"
        (self.remote / "catalog" / "manifests").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def put_remote_item(self, item: dict) -> None:
        catalogctl.validate_manifest(item)
        manifest_path = self.remote / "catalog" / "manifests" / f"{item['id']}.json"
        manifest_path.write_text(json.dumps(item), encoding="utf-8")
        object_path = self.remote / "catalog" / item["remote_path"]
        object_path.mkdir(parents=True)
        (object_path / "fixture.txt").write_bytes(b"authorized integration fixture\n")

    def test_manifest_rejects_parent_traversal(self) -> None:
        item = manifest()
        item["files"][0]["path"] = "../outside"
        with self.assertRaises(catalogctl.CatalogError):
            catalogctl.validate_manifest(item)

    def test_pull_verifies_and_atomically_publishes(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        final = self.settings.local_root / "other" / item["id"]
        self.assertEqual(
            (final / "fixture.txt").read_bytes(), b"authorized integration fixture\n"
        )
        self.assertFalse((self.settings.staging_root / f"{item['id']}.partial").exists())
        self.assertTrue(catalogctl.local_record_path(self.settings, item["id"]).is_file())
        copy_calls = [call for call in fake.calls if call[0] == "copy"]
        self.assertEqual(len(copy_calls), 1)
        self.assertIn("--immutable", copy_calls[0])

    def test_evict_only_deletes_local_tree_and_never_calls_rclone(self) -> None:
        item = manifest()
        local = self.settings.local_root / "other" / item["id"]
        local.mkdir(parents=True)
        (local / "fixture.txt").write_bytes(b"authorized integration fixture\n")
        catalogctl.write_state(self.settings, item, local)

        class NoRemoteMutation:
            def run(self, *args: str, **kwargs: object) -> str:
                raise AssertionError(f"eviction called rclone: {args}")

        catalogctl.cmd_evict(SimpleNamespace(item=item["id"]), self.settings, NoRemoteMutation())
        self.assertFalse(local.exists())
        self.assertFalse(catalogctl.local_record_path(self.settings, item["id"]).exists())

    def test_confined_refuses_root_and_escape(self) -> None:
        root = self.settings.local_root
        root.mkdir(parents=True)
        with self.assertRaises(catalogctl.CatalogError):
            catalogctl.confined(root, root)
        with self.assertRaises(catalogctl.CatalogError):
            catalogctl.confined(root.parent / "outside", root)

    def test_snapshot_requires_verified_record_and_exposes_summary_and_actions(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        snapshot = catalogctl.catalog_snapshot(self.settings, fake)
        self.assertEqual(snapshot["remote_items"], 1)
        self.assertEqual(snapshot["remote_bytes"], item["size_bytes"])
        self.assertEqual(snapshot["local_reserve_bytes"], 0)
        self.assertGreater(snapshot["local_total_bytes"], 0)
        self.assertEqual(snapshot["items"][0]["state"], "remote_only")
        self.assertEqual(snapshot["items"][0]["valid_action"], "download")
        local = self.settings.local_root / "other" / item["id"]
        local.mkdir(parents=True)
        (local / "fixture.txt").write_bytes(b"authorized integration fixture\n")
        self.assertFalse(catalogctl.catalog_snapshot(self.settings, fake)["items"][0]["local"])
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        snapshot = catalogctl.catalog_snapshot(self.settings, fake)
        self.assertEqual(snapshot["items"][0]["state"], "local")
        self.assertEqual(snapshot["items"][0]["valid_action"], "evict")
        self.assertEqual(snapshot["local_items"], 1)
        self.assertEqual(snapshot["local_bytes"], item["size_bytes"])

    def test_snapshot_reports_live_transfer_then_abandoned_operation(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        with self.assertRaises(SystemExit):
            with catalogctl.cache_lock(self.settings, fake) as lock:
                with catalogctl.cache_operation(self.settings, "pull", item["id"], lock):
                    snapshot = catalogctl.catalog_snapshot(self.settings, fake)
                    self.assertEqual(snapshot["transfers_in_progress"], 1)
                    self.assertEqual(snapshot["items"][0]["state"], "downloading")
                    self.assertIsNone(snapshot["items"][0]["valid_action"])
                    raise SystemExit("simulated process termination")
        snapshot = catalogctl.catalog_snapshot(self.settings, fake)
        self.assertEqual(snapshot["transfers_in_progress"], 0)
        self.assertEqual(snapshot["stalled_transfers"], 1)
        self.assertEqual(snapshot["items"][0]["state"], "failed")
        self.assertEqual(snapshot["items"][0]["valid_action"], "retry")
        self.assertIn("no longer running", snapshot["items"][0]["error"])

    def test_cache_mutations_are_locked_across_processes(self) -> None:
        fake = FakeRclone(self.remote)
        code = "import fcntl,sys; f=open(sys.argv[1], 'a+'); fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)"
        lock_path = self.settings.state_root / "locks" / "cache.lock"
        with catalogctl.cache_lock(self.settings, fake):
            result = subprocess.run([sys.executable, "-c", code, str(lock_path)], capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"BlockingIOError", result.stderr)
            with self.assertRaises(catalogctl.CatalogBusy):
                catalogctl.cmd_evict(SimpleNamespace(item="authorized-test"), self.settings, fake)
        result = subprocess.run([sys.executable, "-c", code, str(lock_path)], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.settings.state_root / "failures").exists())

    def test_rclone_inherits_lock_until_orphaned_child_exits(self) -> None:
        rclone = catalogctl.Rclone(self.settings)
        with catalogctl.cache_lock(self.settings, rclone):
            with mock.patch.object(catalogctl.subprocess, "run") as run:
                rclone.run("lsf", "storage:catalog", capture=True)
                self.assertEqual(len(run.call_args.kwargs["pass_fds"]), 1)
                self.assertGreaterEqual(run.call_args.kwargs["pass_fds"][0], 0)
        self.assertEqual(rclone.lock_fds, ())

    def test_child_retains_active_lock_after_parent_operation_is_interrupted(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        child = None
        try:
            with self.assertRaises(SystemExit):
                with catalogctl.cache_lock(self.settings, fake) as lock:
                    with catalogctl.cache_operation(self.settings, "pull", item["id"], lock):
                        child = subprocess.Popen(
                            [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.readline()"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                            pass_fds=fake.lock_fds,
                        )
                        self.assertEqual(child.stdout.readline().strip(), "ready")
                        raise SystemExit("simulate abrupt parent termination")
            self.assertEqual(catalogctl.catalog_snapshot(self.settings, fake)["transfers_in_progress"], 1)
            with self.assertRaises(catalogctl.CatalogBusy):
                with catalogctl.cache_lock(self.settings, fake):
                    self.fail("orphaned transfer child must retain the lock")
            child.communicate("\n", timeout=5)
            snapshot = catalogctl.catalog_snapshot(self.settings, fake)
            self.assertEqual(snapshot["transfers_in_progress"], 0)
            self.assertEqual(snapshot["stalled_transfers"], 1)
        finally:
            if child is not None and child.poll() is None:
                child.kill()
                child.communicate(timeout=5)

    def test_checksum_failure_is_not_published_and_retry_repairs_staging(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        remote_file = self.remote / "catalog" / item["remote_path"] / "fixture.txt"
        remote_file.write_bytes(b"x" * item["size_bytes"])
        fake = FakeRclone(self.remote)
        with self.assertRaisesRegex(catalogctl.CatalogError, "SHA-256"):
            catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        self.assertFalse((self.settings.local_root / "other" / item["id"]).exists())
        snapshot = catalogctl.catalog_snapshot(self.settings, fake)
        self.assertEqual(snapshot["failed_transfers"], 1)
        self.assertEqual(snapshot["transfers_in_progress"], 0)
        self.assertIn("SHA-256", snapshot["items"][0]["error"])
        remote_file.write_bytes(b"authorized integration fixture\n")
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        snapshot = catalogctl.catalog_snapshot(self.settings, fake)
        self.assertEqual(snapshot["failed_transfers"], 0)
        self.assertEqual(snapshot["recorded_failures"], 1)
        failures = catalogctl.read_json_records(self.settings.state_root / "failures")
        self.assertIn("resolved_at", failures[0])

    def test_resumable_verified_files_reduce_required_free_space(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        staging = self.settings.staging_root / f"{item['id']}.partial"
        staging.mkdir(parents=True)
        (staging / "fixture.txt").write_bytes(b"authorized integration fixture\n")
        fake = FakeRclone(self.remote)
        with mock.patch.object(catalogctl.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        self.assertTrue(catalogctl.local_record_path(self.settings, item["id"]).exists())

    def test_capacity_failure_is_recorded_before_copy(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        with mock.patch.object(catalogctl.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(catalogctl.CatalogError, "insufficient free space"):
                catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        self.assertFalse(any(call[0] == "copy" for call in fake.calls))
        operation = catalogctl.operation_records(self.settings)[0]
        self.assertEqual(operation["status"], "failed")
        self.assertIn("insufficient free space", operation["error"])

    def test_retry_keeps_only_verified_expected_staging_files(self) -> None:
        staging = self.settings.staging_root / "authorized-test.partial"
        staging.mkdir(parents=True)
        (staging / "fixture.txt").write_bytes(b"authorized integration fixture\n")
        (staging / "unlisted.txt").write_text("old debris")
        self.assertEqual(catalogctl.prepare_staging(staging, manifest()), manifest()["size_bytes"])
        self.assertFalse((staging / "unlisted.txt").exists())

    def test_evict_rejects_symlink_even_within_library(self) -> None:
        item = manifest()
        victim = self.settings.local_root / "other" / "other-item"
        victim.mkdir(parents=True)
        (victim / "fixture.txt").write_text("must survive")
        local = victim.parent / item["id"]
        local.symlink_to(victim, target_is_directory=True)
        catalogctl.write_state(self.settings, item, local)
        with self.assertRaisesRegex(catalogctl.CatalogError, "symlink"):
            catalogctl.cmd_evict(SimpleNamespace(item=item["id"]), self.settings, FakeRclone(self.remote))
        self.assertEqual((victim / "fixture.txt").read_text(), "must survive")

    def test_evict_then_snapshot_preserves_canonical_bytes_and_returns_remote_only(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        # A restored state backup may contain redundant staging from an old run.
        old_staging = self.settings.staging_root / f"{item['id']}.partial"
        old_staging.mkdir()
        (old_staging / "fixture.txt").write_text("old staging")
        fake.calls.clear()
        catalogctl.cmd_evict(SimpleNamespace(item=item["id"]), self.settings, fake)
        self.assertEqual(fake.calls, [])
        self.assertFalse(old_staging.exists())
        remote = self.remote / "catalog" / item["remote_path"] / "fixture.txt"
        self.assertEqual(remote.read_bytes(), b"authorized integration fixture\n")
        self.assertEqual(catalogctl.catalog_snapshot(self.settings, fake)["items"][0]["state"], "remote_only")

    def test_json_commands_share_snapshot_items(self) -> None:
        self.put_remote_item(manifest())
        fake = FakeRclone(self.remote)
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            catalogctl.cmd_status(SimpleNamespace(json=True), self.settings, fake)
            status = json.loads(output.getvalue())
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            catalogctl.cmd_list(SimpleNamespace(json=True), self.settings, fake)
            items = json.loads(output.getvalue())
        self.assertEqual(status["items"], items)

    def test_staging_directory_alone_is_interrupted_not_active(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        (self.settings.staging_root / f"{item['id']}.partial").mkdir(parents=True)
        snapshot = catalogctl.catalog_snapshot(self.settings, FakeRclone(self.remote))
        self.assertEqual(snapshot["transfers_in_progress"], 0)
        self.assertEqual(snapshot["stalled_transfers"], 1)
        self.assertEqual(snapshot["items"][0]["valid_action"], "retry")

    def test_snapshot_rejects_extra_local_files_and_symlinked_subdirectories(self) -> None:
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        local = self.settings.local_root / "other" / item["id"]
        (local / "unexpected").write_text("extra")
        self.assertFalse(catalogctl.catalog_snapshot(self.settings, fake)["items"][0]["local"])
        (local / "unexpected").unlink()
        (local / "alias").symlink_to(local, target_is_directory=True)
        self.assertFalse(catalogctl.catalog_snapshot(self.settings, fake)["items"][0]["local"])

    def test_manifest_requires_canonical_id(self) -> None:
        item = manifest()
        item["id"] = " Authorized-Test "
        with self.assertRaisesRegex(catalogctl.CatalogError, "canonical lowercase"):
            catalogctl.validate_manifest(item)

    def test_bandwidth_limit_is_validated_and_applied_to_pull(self) -> None:
        with mock.patch.dict(os.environ, {"CATALOG_REMOTE": "storage:catalog", "RCLONE_BWLIMIT": "20M"}):
            self.assertEqual(catalogctl.Settings.from_env().bwlimit, "20M")
        with mock.patch.dict(os.environ, {"CATALOG_REMOTE": "storage:catalog", "RCLONE_BWLIMIT": "invalid limit"}):
            with self.assertRaisesRegex(catalogctl.CatalogError, "RCLONE_BWLIMIT"):
                catalogctl.Settings.from_env()
        item = manifest()
        self.put_remote_item(item)
        fake = FakeRclone(self.remote)
        catalogctl.cmd_pull(SimpleNamespace(item=item["id"]), self.settings, fake)
        copy = next(call for call in fake.calls if call[0] == "copy")
        self.assertEqual(copy[copy.index("--bwlimit") + 1], "off")

    def test_transfer_errors_retain_output_tail(self) -> None:
        # Exercise the actual child process path without a network or rclone.
        from dataclasses import replace
        settings = replace(self.settings, rclone=sys.executable)
        with mock.patch("sys.stderr", new_callable=io.StringIO) as output:
            with self.assertRaisesRegex(catalogctl.CatalogError, "fixture permission denied"):
                catalogctl.Rclone(settings).run("-c", "import sys; print('fixture permission denied', file=sys.stderr); sys.exit(3)")
            self.assertIn("fixture permission denied", output.getvalue())

    def test_promote_recovers_after_object_publish_before_manifest(self) -> None:
        source = self.settings.promotion_root / "completed-item"
        source.mkdir(parents=True)
        (source / "fixture.txt").write_bytes(b"authorized integration fixture\n")

        class PublishedObjectRclone:
            def __init__(self) -> None:
                self.calls: list[tuple[str, ...]] = []

            def succeeds(self, *args: str) -> bool:
                self.calls.append(("succeeds", *args))
                return True

            def run(self, *args: str, **kwargs: object) -> str:
                self.calls.append(args)
                if args[0] != "copyto":
                    raise AssertionError(f"unexpected operation after recovery: {args}")
                return ""

        fake = PublishedObjectRclone()
        args = SimpleNamespace(
            path=str(source),
            title="Authorized test",
            category="other",
            source="generated fixture",
            authorization="generated for this test",
            notes=None,
            id="authorized-test",
            acquired_at=None,
            delete_local=False,
        )
        with mock.patch.dict(os.environ, {"CATALOG_ROLE": "cloud"}):
            catalogctl.cmd_promote(args, self.settings, fake)
        operations = [call[0] for call in fake.calls]
        self.assertEqual(operations, ["succeeds", "copyto"])
        self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
