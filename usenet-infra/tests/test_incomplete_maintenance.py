import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "incomplete_maintenance", Path(__file__).parents[1] / "scripts/incomplete-maintenance.py"
)
maintenance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(maintenance)


class FakeSab:
    def __init__(self, snapshot):
        self.value = snapshot

    def snapshot(self):
        return self.value


def snapshot(*, queue=(), postprocessing=0):
    return {"queue": list(queue), "history": [], "postprocessing": postprocessing}


class IncompleteMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "downloads/incomplete").mkdir(parents=True)
        (self.root / "state/catalog/locks").mkdir(parents=True)
        (self.root / "state/catalog/locks/cache.lock").touch()
        self.now = 2_000_000_000
        self.old = self.now - maintenance.MIN_AGE_SECONDS - 1
        self.mount = mock.patch.object(Path, "is_mount", return_value=True)
        self.mount.start(); self.addCleanup(self.mount.stop)

    def make_tree(self, name, *, mtime=None):
        path = self.root / "downloads/incomplete" / name
        path.mkdir()
        (path / "part").write_bytes(b"scratch")
        stamp = self.old if mtime is None else mtime
        import os
        for item in (path, path / "part"):
            os.utime(item, (stamp, stamp))
        return path

    def execute(self, sab=None):
        return maintenance.run(self.root, sab=sab or FakeSab(snapshot()), now=self.now)

    def test_deletes_only_stale_unowned_tree_and_records_receipt(self):
        path = self.make_tree("orphan")
        result = self.execute()
        self.assertEqual(result["status"], "deleted")
        self.assertFalse(path.exists())
        receipts = list((self.root / maintenance.RECEIPTS).glob("*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["directories"], 1)

    def test_preserves_queue_referenced_tree(self):
        path = self.make_tree("owned")
        result = self.execute(FakeSab(snapshot(queue=[{"status": "Paused", "storage": "/data/incomplete/owned"}])))
        self.assertEqual(result["directories"], 0)
        self.assertTrue(path.exists())
        self.assertEqual(result["skipped"]["referenced_by_queue_history_or_journal"], 1)

    def test_preserves_recent_hardlinked_and_symlinked_trees(self):
        recent = self.make_tree("recent", mtime=self.now)
        linked = self.make_tree("linked")
        (self.root / "downloads/incomplete/other").mkdir()
        (self.root / "downloads/incomplete/other/shared").hardlink_to(linked / "part")
        symlinked = self.make_tree("symlinked")
        (symlinked / "escape").symlink_to(linked / "part")
        result = self.execute()
        self.assertEqual(result["directories"], 0)
        for path in (recent, linked, symlinked):
            self.assertTrue(path.exists())
        self.assertGreaterEqual(len(result["skipped"]), 3)

    def test_refuses_when_sab_is_not_idle(self):
        path = self.make_tree("active")
        result = self.execute(FakeSab(snapshot(postprocessing=1)))
        self.assertEqual(result, {"status": "held", "reason": "sab_not_idle"})
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
