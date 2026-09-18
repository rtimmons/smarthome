from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('hybrid_setup', SCRIPTS / 'hybrid-scratch-setup.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


class HybridScratchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'downloads/incomplete'
        (self.source / 'Example/__ADMIN__').mkdir(parents=True)
        (self.source / 'Example/__ADMIN__/state').write_bytes(b'request metadata')
        self.target = self.root / 'downloads/incomplete-local-spool'
        (self.root / 'state/catalog').mkdir(parents=True)
        self.receipt = self.root / 'state/catalog/hybrid-scratch-setup.json'
        self.receipt.write_text(json.dumps({'schema_version': 1, 'phase': 'preflight', 'queue': []}))

    def tearDown(self):
        self.temp.cleanup()

    def test_mountpoint_detection_accepts_same_filesystem_bind_mounts(self):
        path = self.root / 'downloads/incomplete'
        with mock.patch.object(setup.shutil, 'which', return_value='/usr/bin/findmnt'), \
                mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(
                    stdout=f'{path}\n')):
            self.assertTrue(setup.is_mountpoint(path))

    def test_mountpoint_detection_rejects_parent_mounts(self):
        path = self.root / 'downloads/incomplete'
        with mock.patch.object(setup.shutil, 'which', return_value='/usr/bin/findmnt'), \
                mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(
                    stdout=f'{self.root}\n')):
            self.assertFalse(setup.is_mountpoint(path))

    def migrate(self):
        original = Path.stat
        def stats(path, *args, **kwargs):
            actual = original(path, *args, **kwargs)
            if path == self.source:
                values = list(actual); values[2] += 1
                return type(actual)(values)
            return actual
        with mock.patch.object(Path, 'stat', stats), \
                mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(stdout='false\n')), \
                mock.patch.object(setup.pwd, 'getpwnam', return_value=mock.Mock(pw_uid=os.getuid(), pw_gid=os.getgid())):
            return setup.copy_metadata(self.root)

    def test_metadata_copies_are_verified_and_remote_originals_preserved(self):
        before = setup.module('remote-scratch-setup').metadata_inventory(self.source)
        result = self.migrate()
        self.assertEqual(result['media_moved'], 0)
        self.assertEqual(result['files'], 1)
        self.assertEqual(setup.module('remote-scratch-setup').metadata_inventory(self.source), before)
        self.assertEqual(setup.module('remote-scratch-setup').metadata_inventory(self.target), before)
        self.assertEqual(json.loads(self.receipt.read_text())['phase'], 'metadata_copied')

    def test_payload_or_existing_destination_cannot_be_overwritten(self):
        (self.source / 'Example/download.rar').write_bytes(b'active payload')
        with self.assertRaisesRegex(RuntimeError, 'payload_present'):
            self.migrate()
        self.assertFalse(self.target.exists())
        (self.source / 'Example/download.rar').unlink()
        self.target.mkdir()
        (self.target / 'preserve').write_bytes(b'original')
        with self.assertRaisesRegex(RuntimeError, 'spool_destination_exists'):
            self.migrate()
        self.assertEqual((self.target / 'preserve').read_bytes(), b'original')

    def test_running_sab_and_partial_migration_refuse_replay(self):
        with mock.patch.object(setup.subprocess, 'run', return_value=mock.Mock(stdout='true\n')):
            with self.assertRaisesRegex(RuntimeError, 'sab_must_be_stopped'):
                setup.copy_metadata(self.root)
        self.migrate()
        with self.assertRaisesRegex(RuntimeError, 'setup_phase_requires_review'):
            self.migrate()


if __name__ == '__main__':
    unittest.main()
