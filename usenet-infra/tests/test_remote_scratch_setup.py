from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('remote_setup', SCRIPTS / 'remote-scratch-setup.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


class RemoteScratchSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'downloads/incomplete'
        (self.source / 'Example.Release/__ADMIN__').mkdir(parents=True)
        (self.source / 'Example.Release/__ADMIN__/queue').write_bytes(b'original queue metadata')
        self.target = self.root / 'library/.acquisition-staging/incomplete'
        self.target.mkdir(parents=True)
        (self.root / 'config/sabnzbd').mkdir(parents=True)
        (self.root / 'config/sabnzbd/sabnzbd.ini').write_text(
            '[misc]\ncomplete_dir = /data/complete\ndownload_dir = /data/incomplete\napi_key = fixture\n')
        (self.root / 'state/catalog').mkdir(parents=True)
        self.receipt = self.root / 'state/catalog/remote-scratch-setup.json'
        self.receipt.write_text(json.dumps({'phase': 'preflight', 'queue': []}))

    def tearDown(self):
        self.temp.cleanup()

    def migrate(self):
        original = Path.stat
        def stats(path, *args, **kwargs):
            actual = original(path, *args, **kwargs)
            if path == self.target:
                value = list(actual); value[2] += 1
                return type(actual)(value)
            return actual
        with mock.patch.object(Path, 'stat', stats), mock.patch.object(Path, 'is_mount', return_value=True), \
                mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(stdout='false\n')):
            return setup.preserve_metadata(self.root)

    def test_metadata_migration_preserves_bytes_originals_paths_and_configuration(self):
        before = setup.metadata_inventory(self.source)
        original_ini = (self.root / 'config/sabnzbd/sabnzbd.ini').read_bytes()
        result = self.migrate()
        self.assertEqual(result['media_moved'], 0)
        self.assertEqual(result['metadata_files'], 1)
        self.assertEqual(setup.metadata_inventory(self.target), before)
        rollback = self.root / 'downloads/incomplete-local-before-remote'
        self.assertEqual(setup.metadata_inventory(rollback), before)
        self.assertEqual(self.source.stat().st_mode & 0o777, 0)
        self.source.chmod(0o700)
        self.assertEqual(list(self.source.iterdir()), [])
        self.assertEqual((self.root / 'config/sabnzbd/sabnzbd.ini.before-remote-scratch').read_bytes(), original_ini)
        self.assertIn('complete_dir = /data/complete/remote/complete', (self.root / 'config/sabnzbd/sabnzbd.ini').read_text())

    def test_payload_or_symlink_refuses_migration_without_moving_originals(self):
        for link in (False, True):
            path = self.source / 'Example.Release/payload.rar'
            if link:
                path.symlink_to(self.source / 'Example.Release/__ADMIN__/queue')
            else:
                path.write_bytes(b'real download payload')
            with self.assertRaises(RuntimeError):
                self.migrate()
            self.assertTrue((self.source / 'Example.Release/__ADMIN__/queue').exists())
            self.assertFalse((self.root / 'downloads/incomplete-local-before-remote').exists())
            path.unlink()

    def test_running_sab_or_nonempty_remote_destination_is_refused(self):
        with mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(stdout='true\n')):
            with self.assertRaisesRegex(RuntimeError, 'sab_must_be_stopped'):
                setup.preserve_metadata(self.root)
        (self.target / 'Unrelated/__ADMIN__').mkdir(parents=True)
        (self.target / 'Unrelated/__ADMIN__/keep').write_bytes(b'preserve')
        with self.assertRaisesRegex(RuntimeError, 'destination_not_empty'):
            self.migrate()
        self.assertEqual((self.target / 'Unrelated/__ADMIN__/keep').read_bytes(), b'preserve')

    def test_storage_lifecycle_requires_mounts_and_disables_docker_autostart(self):
        config = SCRIPTS.parent / 'config'
        sab = (config / 'usenet-sab-remote.service').read_text()
        self.assertIn('BindsTo=srv-usenet-downloads-incomplete.mount', sab)
        self.assertIn('--force-recreate', sab)
        discovery = (config / 'discovery-remote-scratch.conf').read_text()
        self.assertIn('BindsTo=srv-usenet-downloads-incomplete.mount', discovery)
        self.assertIn('--force-recreate', discovery)
        self.assertIn('restart: "no"', (SCRIPTS.parent / 'compose/cloud/remote-scratch.override.yaml').read_text())


if __name__ == '__main__':
    unittest.main()
