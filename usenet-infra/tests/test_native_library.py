from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import catalogctl as catalog
import native_library as native


class FakeRclone:
    def __init__(self, remote):
        self.remote = remote
        self.calls = []
        self.after_copy = None
        self.after_hash = None
        self.fail_copy = False

    def run(self, *args, capture=False):
        self.calls.append(args)
        path = self.remote / args[1].split(":", 1)[1] if args[0] != "hashsum" else self.remote / args[2].split(":", 1)[1]
        if args[0] == "lsjson":
            return json.dumps([{"Path": p.relative_to(path).as_posix(), "Size": p.stat().st_size,
                                "ModTime": str(p.stat().st_mtime_ns), "IsDir": p.is_dir()}
                               for p in sorted(path.rglob("*"))])
        if args[0] == "hashsum":
            result = "".join(f"{catalog.sha256_file(p)}  {p.relative_to(path).as_posix()}\n" for p in sorted(path.rglob("*")) if p.is_file())
            if self.after_hash:
                self.after_hash()
            return result
        if args[0] == "copy":
            shutil.copytree(path, args[2], dirs_exist_ok=True)
            if self.after_copy:
                self.after_copy(Path(args[2]))
            if self.fail_copy:
                raise catalog.CatalogError("test transfer interrupted")
            return ""
        raise AssertionError(f"not a permitted read/copy: {args}")


class NativeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = mock.patch.dict(os.environ, {"CATALOG_ROLE": "qnap", "NATIVE_TV_COPY_ENABLED": "true"}, clear=False)
        self.env.start()
        self.settings = catalog.Settings(remote="reader:catalog", local_root=self.root / "Movies",
                                         state_root=self.root / "state", staging_root=self.root / "Movies/.staging",
                                         promotion_root=self.root / "scratch", rclone="rclone", transfers=2,
                                         checkers=4, min_free_bytes=0)
        self.settings.local_root.mkdir()
        self.remote = self.root / "remote"
        (self.remote / "catalog/library").mkdir(parents=True)
        self.rclone = FakeRclone(self.remote)
        self.backend = native.NativeLibrary(self.settings, self.rclone, self.root / "TV Shows/library")
        self.movie = self.add_title("Movies", "Test Movie (2026)", {"Test Movie.mkv": b"video bytes"})
        self.tv = self.add_title("TV", "Test Series (2026)", {"Season 01/Episode S01E01.mkv": b"episode bytes"})

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def add_title(self, kind, title, files):
        root = self.remote / "catalog/library" / kind / title
        for relative, data in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return native.title_id(kind, title)

    def selected(self, ident=None):
        return self.backend.selected(ident or self.movie)

    def pull(self, ident=None):
        self.backend.pull(ident or self.movie)
        return self.backend.final_path(self.selected(ident))

    def test_snapshot_lists_only_titles_without_reading_media(self):
        data = self.backend.snapshot()
        self.assertEqual({i["id"] for i in data["items"]}, {self.movie, self.tv})
        self.assertEqual({c[0] for c in self.rclone.calls}, {"lsjson"})
        self.assertEqual(data["remote_bytes"], len(b"video bytesepisode bytes"))
        self.assertTrue(all(i["valid_action"] == "download" for i in data["items"]))

    def test_movie_copy_verified_and_published_outside_staging(self):
        final = self.pull()
        self.assertEqual((final / "Test Movie.mkv").read_bytes(), b"video bytes")
        self.assertEqual(final.parent.name, self.movie)
        record = self.backend.record(self.movie)
        self.assertEqual(record["status"], "published")
        self.assertTrue(self.backend.owns(final, record))
        self.assertFalse((self.settings.staging_root / (self.movie + ".partial")).exists())
        copies = [c for c in self.rclone.calls if c[0] == "copy"]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0][1], "reader:catalog/library/Movies/Test Movie (2026)")
        self.assertIn("--immutable", copies[0])
        self.assertIn("--sftp-skip-links", copies[0])
        self.assertEqual(self.backend.snapshot()["local_items"], 1)

    def test_tv_staging_is_same_bind_and_outside_plex_root(self):
        final = self.pull(self.tv)
        self.assertEqual(final, self.root / "TV Shows/library/Test Series (2026)")
        copy = next(c for c in self.rclone.calls if c[0] == "copy")
        self.assertEqual(Path(copy[2]).parent, self.root / "TV Shows/.staging")
        self.assertEqual((final / "Season 01/Episode S01E01.mkv").read_bytes(), b"episode bytes")

    def test_repeat_verifies_local_copy_without_remote_media_reads(self):
        final = self.pull()
        before = final.stat().st_ino
        self.rclone.calls.clear()
        self.backend.pull(self.movie)
        self.assertEqual(final.stat().st_ino, before)
        self.assertFalse(any(c[0] in {"copy", "hashsum"} for c in self.rclone.calls))

    def test_existing_unowned_title_even_identical_is_never_adopted(self):
        item = self.selected()
        final = self.backend.final_path(item)
        final.mkdir(parents=True)
        (final / "Test Movie.mkv").write_bytes(b"video bytes")
        with self.assertRaisesRegex(catalog.CatalogError, "ownership receipt"):
            self.backend.pull(self.movie)
        self.assertIsNone(self.backend.record(self.movie))
        self.assertEqual((final / "Test Movie.mkv").read_bytes(), b"video bytes")

    def test_atomic_publication_does_not_replace_empty_directory(self):
        source = self.root / "source"
        destination = self.root / "destination"
        source.mkdir()
        destination.mkdir()
        before = destination.stat().st_ino
        with self.assertRaisesRegex(catalog.CatalogError, "already exists"):
            native.exclusive_rename(source, destination)
        self.assertEqual(destination.stat().st_ino, before)
        self.assertTrue(source.exists())

    def test_collision_appearing_during_copy_is_preserved(self):
        final = self.backend.final_path(self.selected())
        self.rclone.after_copy = lambda stage: final.mkdir(parents=True)
        with self.assertRaisesRegex(catalog.CatalogError, "already exists"):
            self.backend.pull(self.movie)
        self.assertEqual(list(final.iterdir()), [])
        self.assertFalse(self.backend.owns(final, self.backend.record(self.movie)))

    def test_crash_after_rename_recovers_only_owned_inode(self):
        real_write = catalog.atomic_json
        def fail_published(path, payload):
            if path == self.backend.record_path(self.movie) and payload.get("status") == "published":
                raise OSError("simulated receipt failure")
            real_write(path, payload)
        with mock.patch.object(catalog, "atomic_json", side_effect=fail_published):
            with self.assertRaisesRegex(OSError, "simulated"):
                self.backend.pull(self.movie)
        self.assertEqual(self.backend.record(self.movie)["status"], "ready")
        self.backend.pull(self.movie)
        self.assertEqual(self.backend.record(self.movie)["status"], "published")
        self.assertEqual(len([c for c in self.rclone.calls if c[0] == "copy"]), 1)

    def test_modified_same_size_local_bytes_never_overwritten_or_removed(self):
        final = self.pull()
        target = final / "Test Movie.mkv"
        target.write_bytes(b"other bytes")
        for command in (self.backend.pull, self.backend.evict):
            with self.assertRaisesRegex(catalog.CatalogError, "SHA-256 mismatch"):
                command(self.movie)
        self.assertEqual(target.read_bytes(), b"other bytes")
        row = next(i for i in self.backend.snapshot()["items"] if i["id"] == self.movie)
        self.assertIsNone(row["valid_action"])

    def test_changed_remote_title_requires_explicit_eviction(self):
        final = self.pull()
        remote = self.remote / "catalog/library/Movies/Test Movie (2026)/Test Movie.mkv"
        remote.write_bytes(b"new canonical movie")
        with self.assertRaisesRegex(catalog.CatalogError, "canonical title changed"):
            self.backend.pull(self.movie)
        self.assertEqual((final / "Test Movie.mkv").read_bytes(), b"video bytes")
        self.backend.evict(self.movie)
        self.backend.pull(self.movie)
        self.assertEqual((final / "Test Movie.mkv").read_bytes(), b"new canonical movie")

    def test_source_mutation_after_hash_fails_before_copy(self):
        path = self.remote / "catalog/library/Movies/Test Movie (2026)/Test Movie.mkv"
        self.rclone.after_hash = lambda: path.write_bytes(b"changed")
        with self.assertRaisesRegex(catalog.CatalogError, "canonical title changed"):
            self.backend.pull(self.movie)
        self.assertFalse(any(c[0] == "copy" for c in self.rclone.calls))

    def test_source_addition_during_copy_prevents_publication(self):
        self.rclone.after_copy = lambda stage: self.add_title("Movies", "Test Movie (2026)", {"extra.mkv": b"new file"})
        with self.assertRaisesRegex(catalog.CatalogError, "canonical title changed"):
            self.backend.pull(self.movie)
        self.assertFalse(self.backend.final_path(self.selected()).exists())

    def test_damaged_copy_fails_hash_and_never_publishes(self):
        self.rclone.after_copy = lambda stage: (stage / "Test Movie.mkv").write_bytes(b"other bytes")
        with self.assertRaisesRegex(catalog.CatalogError, "SHA-256 mismatch"):
            self.backend.pull(self.movie)
        self.assertFalse(self.backend.final_path(self.selected()).exists())

    def test_partial_transfer_is_visible_failed_and_retry_verifies(self):
        self.rclone.fail_copy = True
        with self.assertRaisesRegex(catalog.CatalogError, "interrupted"):
            self.backend.pull(self.movie)
        row = next(i for i in self.backend.snapshot()["items"] if i["id"] == self.movie)
        self.assertEqual((row["state"], row["valid_action"]), ("failed", "retry"))
        self.rclone.fail_copy = False
        self.pull()
        self.assertEqual(self.backend.snapshot()["local_items"], 1)

    def test_capacity_rejected_before_hashing_or_copying(self):
        usage = shutil.disk_usage(self.root)._replace(free=1)
        with mock.patch.object(shutil, "disk_usage", return_value=usage):
            with self.assertRaisesRegex(catalog.CatalogError, "insufficient free space"):
                self.backend.pull(self.movie)
        self.assertFalse(any(c[0] in {"copy", "hashsum"} for c in self.rclone.calls))

    def test_only_owned_local_title_is_evicted_without_remote_calls(self):
        final = self.pull()
        self.rclone.calls.clear()
        self.backend.evict(self.movie)
        self.assertFalse(final.exists())
        self.assertEqual(self.rclone.calls, [])
        self.assertTrue((self.remote / "catalog/library/Movies/Test Movie (2026)/Test Movie.mkv").exists())

    def test_disappeared_remote_title_remains_explicitly_removable(self):
        final = self.pull()
        shutil.rmtree(self.remote / "catalog/library/Movies/Test Movie (2026)")
        row = next(i for i in self.backend.snapshot()["items"] if i["id"] == self.movie)
        self.assertTrue(row["remote_missing"])
        self.assertEqual(row["valid_action"], "evict")
        self.backend.evict(self.movie)
        self.assertFalse(final.exists())

    def test_role_and_arbitrary_path_selection_rejected(self):
        with mock.patch.dict(os.environ, {"CATALOG_ROLE": "cloud"}):
            with self.assertRaisesRegex(catalog.CatalogError, "qnap"):
                self.backend.pull(self.movie)
        for ident in ("Movies", "library", "../title", "all", ""):
            with self.assertRaises(catalog.CatalogError):
                self.backend.pull(ident)

    def test_paths_reject_traversal_and_symlink_parents(self):
        for path in ("../outside", "/outside", "a//b", "a/./b", "a\\b", "a\nb", ".staging/x"):
            with self.assertRaises(catalog.CatalogError):
                native.safe_relative(path)
        outside = self.root / "outside"
        outside.mkdir()
        (self.settings.local_root / "video").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(catalog.CatalogError, "symlink"):
            self.backend.pull(self.movie)
        self.assertEqual(list(outside.iterdir()), [])

    def test_staging_within_plex_is_rejected(self):
        self.backend.tv_staging_root = self.backend.tv_root / ".staging"
        with self.assertRaisesRegex(catalog.CatalogError, "outside every Plex"):
            self.backend.pull(self.tv)

    def test_hashes_are_server_side_and_fail_closed_if_unavailable(self):
        original = self.rclone.run
        def missing(*args, **kwargs):
            if args[0] == "hashsum":
                self.assertEqual(args[1], "sha256")
                self.assertNotIn("--download", args)
                self.assertIn("--sftp-disable-hashcheck=false", args)
                return "UNSUPPORTED  Test Movie.mkv\n"
            return original(*args, **kwargs)
        with mock.patch.object(self.rclone, "run", side_effect=missing):
            with self.assertRaisesRegex(catalog.CatalogError, "SHA-256 output"):
                self.backend.pull(self.movie)
        self.assertFalse(any(c[0] == "copy" for c in self.rclone.calls))

    def test_cross_bind_rename_fails_before_remote_hashing(self):
        with mock.patch.object(native, "exclusive_rename", side_effect=catalog.CatalogError("cross-device rename")):
            with self.assertRaisesRegex(catalog.CatalogError, "cross-device"):
                self.backend.pull(self.tv)
        self.assertFalse(any(c[0] in {"copy", "hashsum"} for c in self.rclone.calls))
        self.assertEqual(list(self.backend.tv_staging_root.iterdir()), [])

    def test_reserve_drop_prevents_publication(self):
        # Disk-space changes unrelated to our serialized cache can happen while
        # copying. Publication still refuses a violated reserve.
        from dataclasses import replace
        self.backend.settings = replace(self.settings, min_free_bytes=100)
        usage = shutil.disk_usage(self.root)
        with mock.patch.object(shutil, "disk_usage", side_effect=[usage, usage._replace(free=1)]):
            with self.assertRaisesRegex(catalog.CatalogError, "below the configured reserve"):
                self.backend.pull(self.movie)
        self.assertFalse(self.backend.final_path(self.selected()).exists())

    def test_partial_with_symlink_or_special_file_is_preserved_and_rejected(self):
        staging = self.settings.staging_root / (self.movie + ".partial")
        staging.mkdir(parents=True)
        link = staging / "external"
        link.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(catalog.CatalogError, "symlink or special"):
            self.backend.pull(self.movie)
        self.assertTrue(link.is_symlink())
        self.assertFalse(any(c[0] in {"copy", "hashsum"} for c in self.rclone.calls))

    def test_native_root_parent_symlink_is_rejected(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        parent = self.root / "TV Shows"
        parent.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(catalog.CatalogError, "symlink ancestor"):
            self.backend.pull(self.tv)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_tv_copy_default_disabled_until_plex_migration(self):
        with mock.patch.dict(os.environ, {"NATIVE_TV_COPY_ENABLED": "false"}):
            row = next(i for i in self.backend.snapshot()["items"] if i["id"] == self.tv)
            self.assertIsNone(row["valid_action"])
            self.assertIn("Plex TV source", row["error"])
            with self.assertRaisesRegex(catalog.CatalogError, "Plex TV source migration"):
                self.backend.pull(self.tv)
        self.assertFalse(any(c[0] in {"copy", "hashsum"} for c in self.rclone.calls))

    def test_local_byte_total_retains_copied_version_size(self):
        self.pull()
        target = self.remote / "catalog/library/Movies/Test Movie (2026)/Test Movie.mkv"
        target.write_bytes(b"a much bigger replacement movie version")
        snapshot = self.backend.snapshot()
        self.assertEqual(snapshot["local_bytes"], len(b"video bytes"))
        row = next(i for i in snapshot["items"] if i["id"] == self.movie)
        self.assertEqual(row["local_size_bytes"], len(b"video bytes"))
        self.assertEqual(row["size_bytes"], target.stat().st_size)

    def test_shared_legacy_lock_excludes_native_copy(self):
        with catalog.cache_lock(self.settings, self.rclone):
            with self.assertRaises(catalog.CatalogBusy):
                self.backend.pull(self.movie)
        self.assertEqual(self.rclone.calls, [])


if __name__ == "__main__":
    unittest.main()
