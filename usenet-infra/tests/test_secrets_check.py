"""Offline recovery-inventory tests; every private path contains synthetic data."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/secrets-check.py"
SPEC = importlib.util.spec_from_file_location("secrets_check", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def manifest():
    return {
        "schema_version": 1,
        "scope": "smarthome",
        "deletion_safe": False,
        "files": [{
            "id": "fixture-secret", "path": "private/key",
            "restore_path": "private/key", "owner": "fixture service",
            "sensitivity": "secret", "mode": "0600", "format": "opaque",
            "consumers": ["fixture consumer"], "backup_dependency": ["unverified"],
            "rotation": "replace fixture", "category": "vault", "required": True,
            "path_policy": "exact-bytes", "evidence": ["synthetic fixture"],
        }],
        "scan_roots": ["private"], "exclusions": [],
        "external_dependencies": [{
            "id": "fixture-master", "owner": "fixture operator", "source": "external",
            "restore_destinations": ["operator-held"], "sensitivity": "secret",
            "format": "opaque", "consumers": ["fixture restore"],
            "backup_dependency": ["second copy unverified"], "rotation": "replace fixture",
            "status": "unverified", "evidence": ["synthetic fixture"],
        }],
    }


class SecretsCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="secrets-check-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir(mode=0o700)
        # Keep fixture Git configuration independent of the operator's machine.
        self.env = mock.patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "0", "GIT_OPTIONAL_LOCKS": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.git("init", "--quiet")
        self.ignore = self.root / ".gitignore"
        self.ignore.write_text("/private/\n")
        self.git("add", ".gitignore")
        self.commit_fixture()
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.secret = self.private / "key"
        self.secret.write_bytes(b"SYNTHETIC_PRIVATE_BYTES_NEVER_PRINT\n")
        self.secret.chmod(0o600)
        self.data = manifest()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, check=True)

    def commit_fixture(self):
        self.git("-c", "user.name=Recovery Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "--no-verify", "-m", "fixture rules")

    def result(self):
        return checker.check(self.root, self.data)

    def codes(self):
        return {item["code"] for item in self.result()["issues"]}

    def save_manifest(self, data=None):
        path = self.root / "public-inventory.json"
        path.write_text(json.dumps(self.data if data is None else data))
        return path

    def test_success_never_claims_recovery_ready(self):
        result = self.result()
        self.assertTrue(result["inventory_ok"])
        self.assertFalse(result["deletion_safe"])
        self.assertEqual(result["external_dependencies"][0]["status"], "unverified")
        self.assertNotIn("SYNTHETIC_PRIVATE_BYTES", json.dumps(result))

    def test_private_contents_are_never_opened(self):
        real_open = os.open

        def directories_only(path, flags, *args, **kwargs):
            self.assertTrue(flags & os.O_DIRECTORY, "checker attempted a file open")
            return real_open(path, flags, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=AssertionError("file bytes opened")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("file bytes opened")), \
                mock.patch.object(checker.os, "open", side_effect=directories_only):
            self.assertTrue(self.result()["inventory_ok"])

    def test_schema_rejects_unsafe_paths(self):
        for path in ("../key", "/key", "private/../key", "private//key", "private/./key",
                     "private/key/", "private\\key", "private/*", "private/[key]", "private/key\n"):
            with self.subTest(path=path):
                data = manifest()
                data["files"][0]["path"] = path
                data["files"][0]["restore_path"] = path
                with self.assertRaises(checker.InventoryError):
                    checker.validate_manifest(data)

    def test_schema_rejects_distinct_restore_destination(self):
        self.data["files"][0]["restore_path"] = "private/other"
        with self.assertRaises(checker.InventoryError):
            checker.validate_manifest(self.data)

    def test_schema_rejects_duplicate_identity_and_path(self):
        for field, value in (("id", "fixture-secret"), ("path", "private/key")):
            with self.subTest(field=field):
                data = manifest()
                extra = copy.deepcopy(data["files"][0])
                extra.update(id="another-secret", path="private/other", restore_path="private/other")
                extra[field] = value
                if field == "path":
                    extra["restore_path"] = value
                data["files"].append(extra)
                with self.assertRaises(checker.InventoryError):
                    checker.validate_manifest(data)

    def test_schema_rejects_external_identity_collision(self):
        self.data["external_dependencies"][0]["id"] = "fixture-secret"
        with self.assertRaises(checker.InventoryError):
            checker.validate_manifest(self.data)

    def test_schema_rejects_readiness_claim(self):
        self.data["deletion_safe"] = True
        with self.assertRaises(checker.InventoryError):
            checker.validate_manifest(self.data)

    def test_duplicate_json_keys_are_rejected(self):
        path = self.save_manifest()
        path.write_text(json.dumps(self.data).replace('"schema_version": 1',
                                                     '"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(checker.InventoryError):
            checker.load_manifest(path)

    def test_manifest_symlink_leaf_rejected_without_reading(self):
        path = self.root / "public-inventory.json"
        path.symlink_to(self.secret)
        with mock.patch.object(checker.os, "fdopen", side_effect=AssertionError("symlink read")):
            with self.assertRaises(checker.InventoryError):
                checker.load_manifest(path)

    def test_manifest_symlink_parent_rejected(self):
        self.save_manifest()
        alias = self.base / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(checker.InventoryError):
            checker.load_manifest(alias / "public-inventory.json")

    def test_manifest_fifo_rejected_without_hanging(self):
        path = self.root / "public-inventory.json"
        os.mkfifo(path)
        with self.assertRaises(checker.InventoryError):
            checker.load_manifest(path)

    def test_manifest_size_is_bounded(self):
        path = self.root / "public-inventory.json"
        with path.open("wb") as stream:
            stream.truncate(2_000_001)
        with self.assertRaises(checker.InventoryError):
            checker.load_manifest(path)

    def test_missing_required_fails(self):
        self.secret.unlink()
        self.assertIn("missing-required-file", self.codes())
        self.assertEqual(self.result()["files"][0]["status"], "missing")

    def test_missing_optional_passes_with_explicit_status(self):
        self.secret.unlink()
        self.private.rmdir()
        self.data["files"][0]["required"] = False
        result = self.result()
        self.assertTrue(result["inventory_ok"])
        self.assertEqual(result["files"][0]["status"], "optional-absent")
        self.assertFalse(result["deletion_safe"])

    def test_symlink_leaf_rejected(self):
        self.secret.unlink()
        self.secret.symlink_to(self.ignore)
        self.assertIn("not-regular-file", self.codes())

    def test_symlink_parent_rejected_without_discovery_following(self):
        outside = self.base / "outside"
        self.private.rename(outside)
        self.private.symlink_to(outside, target_is_directory=True)
        # Git also refuses paths under a symlink; isolate metadata/discovery to
        # ensure they retain their own independent no-follow protection.
        with mock.patch.object(checker, "git_paths", return_value=(set(), {"private/key"})):
            codes = self.codes()
        self.assertIn("unsafe-or-inaccessible-path", codes)
        self.assertIn("discovery-root-unsafe", codes)
        path = self.save_manifest()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertNotEqual(checker.main(["--root", str(self.root), "--manifest", str(path)]), 0)

    def test_symlink_repository_root_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            checker.check(alias, self.data)

    def test_hard_link_rejected(self):
        os.link(self.secret, self.base / "other-link")
        self.assertIn("hard-linked-file", self.codes())

    def test_fifo_private_file_rejected_without_open(self):
        self.secret.unlink()
        os.mkfifo(self.secret, mode=0o600)
        self.assertIn("not-regular-file", self.codes())

    def test_directory_instead_of_file_rejected(self):
        self.secret.unlink()
        self.secret.mkdir(mode=0o700)
        self.assertIn("not-regular-file", self.codes())

    def test_parent_group_or_other_write_permissions_rejected(self):
        for mode in (0o720, 0o702, 0o777):
            with self.subTest(mode=oct(mode)):
                self.private.chmod(mode)
                self.assertIn("unsafe-parent-permissions", self.codes())

    def test_repository_root_write_permissions_rejected(self):
        self.root.chmod(0o777)
        path = self.save_manifest()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertNotEqual(checker.main(["--root", str(self.root), "--manifest", str(path)]), 0)

    def test_excess_file_permissions_and_empty_file_rejected(self):
        self.secret.chmod(0o644)
        self.assertIn("excess-permissions", self.codes())
        self.secret.chmod(0o600)
        self.secret.write_bytes(b"")
        self.assertIn("empty-file", self.codes())

    def test_tracked_private_material_rejected_even_with_ignore(self):
        self.git("add", "-f", "private/key")
        self.assertIn("tracked-recovery-material", self.codes())

    def test_untracked_gitignore_is_not_portable(self):
        self.git("rm", "--cached", "--quiet", ".gitignore")
        self.assertIn("not-repository-ignored", self.codes())

    def test_worktree_only_ignore_rule_is_not_portable(self):
        self.ignore.write_text("")
        self.git("add", ".gitignore")
        self.commit_fixture()
        self.ignore.write_text("/private/\n")
        self.assertIn("not-repository-ignored", self.codes())

    def test_staged_only_ignore_rule_is_not_portable(self):
        self.ignore.write_text("")
        self.git("add", ".gitignore")
        self.commit_fixture()
        self.ignore.write_text("/private/\n")
        self.git("add", ".gitignore")
        self.assertIn("not-repository-ignored", self.codes())

    def test_unborn_repository_cannot_certify_ignore_portability(self):
        self.git("update-ref", "-d", "HEAD")
        path = self.save_manifest()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertNotEqual(checker.main(["--root", str(self.root), "--manifest", str(path)]), 0)

    def test_local_info_exclude_is_not_portable(self):
        self.ignore.write_text("")
        self.git("add", ".gitignore")
        (self.root / ".git/info/exclude").write_text("/private/\n")
        self.assertIn("not-repository-ignored", self.codes())

    def test_global_exclude_is_not_portable(self):
        self.ignore.write_text("")
        self.git("add", ".gitignore")
        external = self.base / "global-ignore"
        external.write_text("private/\n")
        self.git("config", "core.excludesFile", str(external))
        self.assertIn("not-repository-ignored", self.codes())

    def test_effective_negation_does_not_count_as_ignore(self):
        self.ignore.write_text("/private/*\n!/private/key\n")
        self.git("add", ".gitignore")
        self.assertIn("not-repository-ignored", self.codes())

    def test_nested_tracked_ignore_is_portable(self):
        self.ignore.write_text("/private/\n")
        nested = self.root / "nested"
        nested.mkdir()
        (nested / ".gitignore").write_text("/private/\n")
        self.git("add", "nested/.gitignore")
        self.commit_fixture()
        nested_private = nested / "private"
        nested_private.mkdir(mode=0o700)
        self.secret.rename(nested_private / "key")
        self.data["files"][0].update(path="nested/private/key", restore_path="nested/private/key")
        self.data["scan_roots"] = ["nested/private"]
        self.assertTrue(self.result()["inventory_ok"])

    def test_unknown_file_needs_classification(self):
        (self.private / "unreviewed").write_bytes(b"fixture")
        self.assertIn("unclassified-file", self.codes())

    def test_excluded_tree_is_not_entered(self):
        excluded = self.private / "cache"
        excluded.mkdir()
        (excluded / "unreviewed").write_bytes(b"fixture")
        self.data["exclusions"] = [{"path": "private/cache", "kind": "tree", "reason": "fixture cache"}]
        real_open = os.open

        def reject_cache(path, flags, *args, **kwargs):
            self.assertNotEqual(os.fspath(path), "cache", "excluded directory entered")
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(checker.os, "open", side_effect=reject_cache):
            self.assertTrue(self.result()["inventory_ok"])

    def test_excluded_regular_file_passes(self):
        (self.private / "generated").write_bytes(b"fixture")
        self.data["exclusions"] = [{"path": "private/generated", "kind": "file", "reason": "regenerated"}]
        self.assertTrue(self.result()["inventory_ok"])

    def test_excluded_symlinks_do_not_bypass_discovery(self):
        for kind in ("file", "tree"):
            with self.subTest(kind=kind):
                path = self.private / "excluded"
                path.symlink_to(self.base, target_is_directory=True)
                self.data["exclusions"] = [{"path": "private/excluded", "kind": kind, "reason": "fixture"}]
                self.assertIn("unclassified-file", self.codes())
                path.unlink()

    def test_schema_rejects_exclusion_hiding_required_file(self):
        self.data["exclusions"] = [{"path": "private", "kind": "tree", "reason": "invalid"}]
        with self.assertRaises(checker.InventoryError):
            checker.validate_manifest(self.data)

    def test_schema_rejects_scan_root_within_excluded_tree(self):
        self.data["scan_roots"].append("cache/nested")
        self.data["exclusions"] = [{"path": "cache", "kind": "tree", "reason": "excluded"}]
        with self.assertRaises(checker.InventoryError):
            checker.validate_manifest(self.data)

    def test_cli_exit_status_and_output_are_sanitized(self):
        path = self.save_manifest()
        args = ["--root", str(self.root), "--manifest", str(path), "--json"]
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(checker.main(args), 0)
        self.assertFalse(json.loads(out.getvalue())["deletion_safe"])
        self.secret.unlink()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(args), 1)
        path.write_text('invalid SYNTHETIC_PRIVATE_BYTES_NEVER_PRINT')
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(checker.main(args), 2)
        self.assertNotIn("SYNTHETIC_PRIVATE_BYTES", err.getvalue())

    def test_manifest_only_does_not_claim_deletion_safety(self):
        path = self.save_manifest()
        self.secret.unlink()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(checker.main(["--manifest", str(path), "--manifest-only"]), 0)
        self.assertIn("deletion safety NOT verified", out.getvalue())


if __name__ == "__main__":
    unittest.main()
