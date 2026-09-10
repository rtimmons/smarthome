from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
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
