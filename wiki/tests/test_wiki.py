import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "wiki"))
import tool
from areas import render_rooms


class ContentTests(unittest.TestCase):
    def test_room_catalog_distinguishes_inheritance_controls_and_stale_verification(self):
        model = {"devices": [{"entity": "light.fixture", "areaId": "office"}], "scenes": [
            {"id": "fixture_high", "name": "Fixture high", "targets": [{"entity": "light.fixture"}]}],
            "rooms": {"areas": [{"id": "office", "name": "Office"}], "rooms": []},
            "placements": {"devices": [{"name": "Fixture", "entityId": "light.fixture", "areaId": "office", "status": "assigned", "note": "Confirmed"}],
                           "entities": [{"entityId": "script.fixture", "areaId": "office", "status": "assigned", "note": "Room control"}], "retired": []},
            "verification": {"verifiedAt": "2026-01-01T00:00:00Z", "coveredDevices": 1, "coveredEntities": 2,
                             "devicesWithoutEntities": 0, "catalogMatches": False, "areas": []}}
        rendered = render_rooms(model, tool.table)
        self.assertIn("every entity attached to that device inherits", rendered)
        self.assertIn("catalog has changed since this check", rendered)
        self.assertIn("scenes.md#fixture-high", rendered)
        self.assertIn("<details><summary>Room controls and helpers (1)", rendered)
        self.assertIn("script.fixture", rendered)
        model["speakerVerification"] = {"verifiedAt": "2026-01-01T00:00:00Z", "catalogMatches": False, "speakers": [
            {"expectedName": "Office", "sonosName": None, "homeAssistantName": "Office", "homeAssistantDeviceName": "Office", "areaName": "Office", "status": "speaker_unreachable"}]}
        rendered = render_rooms(model, tool.table)
        self.assertIn("Speaker unreachable; HA matches", rendered)
        self.assertIn("Not verified", rendered)
        self.assertIn("room or device catalog changed", rendered)

    def test_guide_and_runbook_changes_participate_in_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("source.ts", "guide.md", "runbook.md"):
                (root / name).write_text("initial")
            component = {"id": "fixture", "watch": ["source.ts"], "pages": ["guide.md"], "runbooks": ["runbook.md"]}
            with patch.object(tool.subprocess, "check_output", return_value="source.ts\n"):
                paths = tool.source_files(component, root)
            before = tool.fingerprint(paths, root)
            (root / "runbook.md").write_text("Changed recovery instructions")
            self.assertNotEqual(before, tool.fingerprint(paths, root))
            self.assertIn("guide.md", paths)

    def test_missing_watch_path_fails_instead_of_silently_losing_coverage(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool.subprocess, "check_output", return_value=""):
            with self.assertRaisesRegex(ValueError, "matches no files"):
                tool.source_files({"id": "fixture", "watch": ["missing/src/*"]}, Path(directory))

    def test_duplicate_and_unowned_guide_coverage_is_rejected(self):
        data = tool.catalog()
        data["components"].append(data["components"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate component"):
            tool.check_catalog(data)
        data = tool.catalog()
        data["components"][0]["pages"] = []
        with self.assertRaisesRegex(ValueError, "Guide coverage"):
            tool.check_catalog(data)

    def test_reference_links_work_from_nested_guides_and_reject_typos(self):
        text = tool.rewrite_links("[DNS](wiki-reference:network#local-records)", "wiki/content/media/access.md", "media/access.md", {}, "HEAD")
        self.assertEqual(text, "[DNS](../reference/network.md#local-records)")
        with self.assertRaisesRegex(ValueError, "Unknown generated reference"):
            tool.rewrite_links("[Bad](wiki-reference:typo)", "wiki/content/index.md", "index.md", {}, "HEAD")

    def test_generated_reference_preserves_mappings_states_and_runbook_navigation(self):
        model = {"devices": [], "controls": [], "scenes": [
            {"id": "fixture_high", "name": "Fixture high", "script": "script.fast_scene_fixture_high",
             "targets": [{"device": "fixture_light", "entity": "light.fixture", "state": {"state": "on", "brightness": 128}}],
             "omitted": ["fixture_excluded"]}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, "run"):
            root = Path(directory)
            (root / "model.json").write_text(json.dumps(model))
            stage = root / "docs"
            (stage / "runbooks").mkdir(parents=True)
            with patch.object(tool, "BUILD", root):
                tool.export_reference(stage, tool.catalog(), "HEAD")
            services = (stage / "reference/services.md").read_text()
            self.assertIn("27017 → 27017", services)
            self.assertIn("disabled / retained", services)
            scenes = (stage / "reference/scenes.md").read_text()
            self.assertIn("light.fixture", scenes)
            self.assertIn("128", scenes)
            self.assertIn("fixture_excluded", scenes)
            runbooks = (stage / "runbooks/index.md").read_text()
            for source in tool.catalog()["imports"]:
                self.assertIn(f"]({source})", runbooks)

    def test_changed_source_changes_review_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.ts").write_text("status=active")
            before = tool.fingerprint(["model.ts"], root)
            (root / "model.ts").write_text("status=temporarily_excluded")
            self.assertNotEqual(before, tool.fingerprint(["model.ts"], root))

    def test_private_and_remote_assets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "index.html"
            for html in ('<script src="https://example.org/a.js"></script>',
                         '<script>alert(1)</script>', '<a href="javascript:alert(1)">bad</a>',
                         '<a href="http://example.org/?api_key=secret">bad</a>',
                         '<a href="../private.env">bad</a>', '<a href="#missing">bad</a>'):
                page.write_text(html)
                with self.assertRaises(ValueError):
                    tool.validate_site(root)

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").write_text("private")
            (root / "b").symlink_to(root / "a")
            with self.assertRaises(ValueError):
                tool.safe_file("b", root)

    def test_all_legacy_fragments_survive_migration(self):
        old = tool.PageParser()
        old.feed((ROOT / "wiki/tests/fixtures/usenet-legacy.html").read_text())
        migrated = tool.PageParser()
        migrated.feed((ROOT / "wiki/content/media/usenet.md").read_text())
        self.assertFalse(old.ids - migrated.ids, old.ids - migrated.ids)

    def test_new_addon_requires_catalog_coverage(self):
        with patch.object(tool, "catalog", return_value={"components": []}):
            with self.assertRaisesRegex(ValueError, "coverage"):
                tool.check_reviews()

    def test_expired_review_is_rejected(self):
        with patch.object(tool, "fingerprint", return_value="unreviewed"):
            with self.assertRaisesRegex(ValueError, "review required"):
                tool.check_reviews()


class TransactionTests(unittest.TestCase):
    def test_unreachable_wiki_stops_before_services_change(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "manifest.json").write_text(json.dumps({"publication": {}}))
            with patch.dict(os.environ, {}, clear=True), patch.object(tool, "build", return_value=output), \
                 patch.object(tool, "existing_receipts", side_effect=OSError("No route to host")), \
                 patch.object(tool.subprocess, "call") as services, patch.object(tool, "deploy") as publish:
                self.assertEqual(tool.with_deployment("media", ["true"]), 3)
                services.assert_not_called()
                publish.assert_not_called()

    def test_receipt_survives_failure_to_fetch_previous_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            before = {"source_fingerprint": "abc", "revision": "a" * 40, "dirty": True}
            (output / "manifest.json").write_text(json.dumps({"publication": before}))
            with patch.dict(os.environ, {}, clear=True), patch.object(tool, "BUILD", output), \
                 patch.object(tool, "build", return_value=output), patch.object(tool.subprocess, "call", return_value=0), \
                 patch.object(tool, "publication_inputs", return_value="abc"), \
                 patch.object(tool, "existing_receipts", side_effect=[{}, OSError("NAS unreachable")]):
                self.assertEqual(tool.with_deployment("media", ["true"]), 3)
                self.assertIn("media", json.loads((output / "pending-receipts.json").read_text()))

    def test_failure_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "manifest.json").write_text(json.dumps({"publication": {}}))
            with patch.dict(os.environ, {"WIKI_CALLER_DIR": str(ROOT)}, clear=True), \
                 patch.object(tool, "build", return_value=output), \
                 patch.object(tool, "existing_receipts", return_value={}), \
                 patch.object(tool.subprocess, "call", return_value=7), patch.object(tool, "deploy") as publish:
                self.assertEqual(tool.with_deployment("media", ["false"]), 7)
                publish.assert_not_called()

    def test_nested_and_dry_runs_skip_build_and_publish(self):
        for environment, command in [({"SMARTHOME_WIKI_DEPLOY_ACTIVE": "1"}, ["true"]),
                                     ({}, ["deploy", "--dry-run"]),
                                     ({}, ["just", "talos-deploy", "dry-run", "all"]),
                                     ({}, ["just", "talos-deploy", "verbose", "--help"]),
                                     ({}, ["just", "talos-deploy", "normal", "--help"]),
                                     ({}, ["ansible-playbook", "qnap.yml", "--check"])]:
            with patch.dict(os.environ, environment, clear=True), patch.object(tool.subprocess, "call", return_value=0), \
                 patch.object(tool, "build") as build, patch.object(tool, "deploy") as publish:
                self.assertEqual(tool.with_deployment("media", command), 0)
                build.assert_not_called()
                publish.assert_not_called()

    def test_success_publishes_once_and_does_not_verify_disabled_addons(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            before = {"source_fingerprint": "abc", "revision": "a" * 40, "dirty": True}
            (output / "manifest.json").write_text(json.dumps({"publication": before}))
            with patch.dict(os.environ, {}, clear=True), patch.object(tool, "BUILD", output), \
                 patch.object(tool, "build", return_value=output) as build, \
                 patch.object(tool.subprocess, "call", return_value=0), \
                 patch.object(tool, "publication_inputs", return_value="abc"), \
                 patch.object(tool, "existing_receipts", return_value={}), patch.object(tool, "deploy") as publish:
                self.assertEqual(tool.with_deployment("home-assistant", ["just", "talos-deploy", "normal", "all"]), 0)
                publish.assert_called_once_with(output)
                receipts = build.call_args.args[0]
                self.assertIn("home-assistant-config", receipts)
                self.assertIn("sonos-api", receipts)
                self.assertNotIn("node-sonos-http-api", receipts)
                self.assertFalse((output / "pending-receipts.json").exists())

    def test_publication_failure_keeps_successful_deployment_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            before = {"source_fingerprint": "abc", "revision": "a" * 40, "dirty": True}
            (output / "manifest.json").write_text(json.dumps({"publication": before}))
            with patch.dict(os.environ, {}, clear=True), patch.object(tool, "BUILD", output), \
                 patch.object(tool, "build", return_value=output), patch.object(tool.subprocess, "call", return_value=0), \
                 patch.object(tool, "publication_inputs", return_value="abc"), \
                 patch.object(tool, "existing_receipts", return_value={"unrelated": {"completed_at": "old"}}), \
                 patch.object(tool, "deploy", side_effect=OSError("NAS unavailable")):
                self.assertEqual(tool.with_deployment("media", ["true"]), 3)
                receipts = json.loads((output / "pending-receipts.json").read_text())
                self.assertEqual(receipts["unrelated"]["completed_at"], "old")
                self.assertEqual(receipts["media"]["revision"], before["revision"])


class ReceiptFetchTests(unittest.TestCase):
    def test_direct_bounded_fetch_preserves_receipts(self):
        def respond(argv, **kwargs):
            self.assertEqual(argv[:2], ["/usr/bin/curl", "--disable"])
            self.assertEqual(argv[argv.index("--noproxy") + 1], "*")
            self.assertIn("--max-time", argv)
            self.assertIn("--max-filesize", argv)
            self.assertNotIn("--location", argv)
            Path(argv[argv.index("--output") + 1]).write_text('{"receipts":{"lighting":{"completed_at":"today"}}}')
            return subprocess.CompletedProcess(argv, 0, "200", "")
        with patch.object(tool.sys, "platform", "darwin"), patch.object(tool.subprocess, "run", side_effect=respond):
            self.assertEqual(tool.existing_receipts(), {"lighting": {"completed_at": "today"}})

    def test_network_failure_reports_both_urls(self):
        failure = subprocess.CompletedProcess([], 7, "000", "No route to host")
        with patch.object(tool.subprocess, "run", return_value=failure):
            with self.assertRaises(ValueError) as error:
                tool.existing_receipts()
        self.assertIn("http://192.168.1.66/publication.json", str(error.exception))
        self.assertIn("http://192.168.1.66:8090/", str(error.exception))
        self.assertIn("No route to host", str(error.exception))

    def test_missing_metadata_does_not_discard_history(self):
        with patch.object(tool.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "404", "")) as fetch:
            with self.assertRaisesRegex(ValueError, "do not discard"):
                tool.existing_receipts()
            self.assertEqual(fetch.call_count, 1)

    def test_only_original_guide_allows_empty_receipts(self):
        for body, allowed in [("Usenet field guide", True), ("Smarthome field guide Usenet field guide", False)]:
            with patch.object(tool, "fetch_wiki", side_effect=[ConnectionError("No route to host"), body]):
                if allowed:
                    self.assertEqual(tool.existing_receipts(), {})
                else:
                    with self.assertRaises(ValueError):
                        tool.existing_receipts()

    def test_http_redirect_is_rejected(self):
        with patch.object(tool.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "302", "")):
            with self.assertRaises(tool.WikiHTTPError):
                tool.existing_receipts()


class DeploymentLogTests(unittest.TestCase):
    def test_wrapper_saves_both_streams_and_preserves_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wiki").mkdir()
            (root / "wiki/run").write_bytes((ROOT / "wiki/run").read_bytes())
            (root / ".python-version").write_text("3.14.6")
            uv = root / "uv"
            uv.write_text("#!/bin/sh\necho service-output\necho wiki-error >&2\nexit 3\n")
            uv.chmod(0o755)
            result = subprocess.run(["bash", str(root / "wiki/run"), "deploy"], capture_output=True, text=True,
                                    env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                                         "SMARTHOME_WIKI_DEPLOY_ACTIVE": ""})
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            logs = list((root / "build/wiki/logs").iterdir())
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].stat().st_mode & 0o777, 0o600)
            self.assertIn("service-output", logs[0].read_text())
            self.assertIn("wiki-error", logs[0].read_text())
            self.assertIn("Deployment exited 3", logs[0].read_text())
            self.assertIn(str(logs[0]), result.stdout)


class RuntimeRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docker = self.root / "docker"
        self.docker.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
r=Path(os.environ['MOCK_WIKI_ROOT']); a=sys.argv[1:]; state=r/'active.json'
def env(p):return dict(l.split('=',1) for l in Path(p).read_text().splitlines() if '=' in l)
current=json.loads(state.read_text()) if state.exists() else {}
if a[0]=='compose':
 e=env(a[a.index('--env-file')+1])
 if 'up' in a:
  assert a[-1]=='wiki'
  state.write_text(json.dumps(e)); (r/'starts').open('a').write('start\\n')
 elif 'down' in a:state.unlink(missing_ok=True)
elif a[0]=='ps':print('wiki-id')
elif a[:2]==['image','inspect']:pass
elif a[0]=='inspect':
 print('healthy' if 'Health.Status' in a[2] else current.get('WIKI_RELEASE_DIR','')+'/site')
elif a[0]=='port':print('192.168.1.66:'+('80' if a[-1]=='8080/tcp' else '8090'))
elif a[0]=='exec':
 if a[-1].endswith('publication.json'):sys.stdout.write((Path(current['WIKI_RELEASE_DIR'])/'site/publication.json').read_text())
 else:print('Smarthome field guide')
else:raise SystemExit('unexpected Docker command')
''')
        self.docker.chmod(0o755)

    def release(self, name):
        target = self.root / "releases" / name
        (target / "site").mkdir(parents=True)
        (target / "runtime").mkdir()
        (target / "runtime/compose.yaml").write_text("name: usenet-wiki\n")
        (target / "site/publication.json").write_text(json.dumps({"release": name}))
        value = hashlib.sha256((target / "site/publication.json").read_bytes()).hexdigest()
        (target / "SHA256SUMS").write_text(value + "  site/publication.json\n")
        return target

    def apply(self, name, mode="publish", reject=False):
        return subprocess.run(["sh", str(ROOT / "wiki/apply.sh"), str(self.root), mode, name, "1000", "1000",
                               str(self.docker), "true" if reject else "false"], capture_output=True, text=True,
                              env={**os.environ, "MOCK_WIKI_ROOT": str(self.root)})

    def test_reject_restores_content_and_runtime_then_manual_rollback_works(self):
        for name in ("a" * 64, "b" * 64):self.release(name)
        first = self.apply("a" * 64)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = (self.root / ".env").read_text()
        failed = self.apply("b" * 64, reject=True)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertEqual((self.root / ".env").read_text(), before)
        self.assertIn("previous release restored", failed.stderr)
        good = self.apply("b" * 64)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        rolled = self.apply("unused", mode="rollback")
        self.assertEqual(rolled.returncode, 0, rolled.stdout + rolled.stderr)
        self.assertEqual((self.root / ".env").read_text(), before)

    def test_repeated_healthy_release_does_not_restart(self):
        self.release("a" * 64)
        self.assertEqual(self.apply("a" * 64).returncode, 0)
        again = self.apply("a" * 64)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual((self.root / "starts").read_text().splitlines(), ["start"])


if __name__ == "__main__":
    unittest.main()
