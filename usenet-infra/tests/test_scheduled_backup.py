import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('scheduled_backup', Path(__file__).parents[1] / 'scripts/scheduled-backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class ScheduledBackupTests(unittest.TestCase):
    def test_native_settings_snapshot_captures_committed_wal_and_latest_qts_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qts, hbs = root / 'qts', root / 'hbs'
            qts.mkdir()
            hbs.mkdir()
            old = qts / '1_20261007_0304.bak'
            old.write_bytes(b'previous synthetic settings')
            os.utime(old, (time.time() - 7 * 86400,) * 2)
            (qts / '0_20261014_0304.bak').write_bytes(b'current synthetic settings')
            (qts / 'unrelated.bin').write_bytes(b'exclude')
            (hbs / 'media.mkv').write_bytes(b'exclude')
            connections = []
            try:
                for name in ('cc3_config.db', 'hbs.db'):
                    db = sqlite3.connect(hbs / name)
                    connections.append(db)
                    db.execute('PRAGMA journal_mode=WAL')
                    db.execute('CREATE TABLE settings(value TEXT)')
                    db.execute("INSERT INTO settings VALUES ('committed synthetic setting')")
                    db.commit()
                    db.execute("INSERT INTO settings VALUES ('uncommitted')")
                manifest, contents = backup.nas_system_snapshot(qts, hbs)
                self.assertEqual(set(contents), {'qts/settings.bak', 'hbs/cc3_config.db', 'hbs/hbs.db'})
                self.assertEqual(contents['qts/settings.bak'], b'current synthetic settings')
                self.assertEqual(manifest['scope'], 'nas-system-config')
                for entry in manifest['entries']:
                    restored = root / Path(entry['path']).name
                    restored.write_bytes(contents[entry['path']])
                    self.assertEqual(backup.digest(restored), entry['sha256'])
                    if restored.suffix == '.db':
                        with closing(sqlite3.connect(restored)) as db:
                            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
                            self.assertEqual(db.execute('SELECT * FROM settings').fetchall(),
                                             [('committed synthetic setting',)])
            finally:
                for db in connections:
                    db.close()

    def test_native_settings_refuse_missing_stale_and_symlink_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qts, hbs = root / 'qts', root / 'hbs'
            qts.mkdir()
            hbs.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                backup.nas_system_snapshot(qts, hbs)
            path = qts / '0_20261014_0304.bak'
            path.write_bytes(b'synthetic')
            os.utime(path, (time.time() - 15 * 86400,) * 2)
            with self.assertRaisesRegex(RuntimeError, 'stale'):
                backup.nas_system_snapshot(qts, hbs)
            path.unlink()
            outside = root / 'outside'
            outside.write_bytes(b'do not capture')
            path.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'unsafe'):
                backup.nas_system_snapshot(qts, hbs)
            path.unlink()
            path.write_bytes(b'synthetic settings')
            (hbs / 'cc3_config.db').symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'unsafe HBS'):
                backup.nas_system_snapshot(qts, hbs)

    def test_offhost_requires_config_when_enabled(self):
        with patch.object(backup, 'NAS_OFFHOST_CONFIG', Path('/nonexistent/backup-config')), patch.dict(backup.os.environ, {'NAS_OFFHOST_REQUIRED': 'true'}):
            with self.assertRaisesRegex(RuntimeError, 'configuration missing'):
                backup.replicate_nas_settings([])

    def test_offhost_verifies_readback_before_marking_success(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / 'rclone.conf'
                config.write_text('synthetic')
                config.chmod(0o600)
                source = root / 'qnap-20261008T000000Z.tar.age'
                source.write_bytes(b'encrypted fixture')
                receipt = {'file': source.name, 'sha256': backup.digest(source)}
                calls = []
                def run(args):
                    calls.append(args)
                    index = args.index('copyto')
                    if args[index + 1].startswith('nasbackup:'):
                        Path(args[index + 2]).write_bytes(b'corrupt' if corrupt else source.read_bytes())
                with patch.object(backup, 'OUTPUT', root), patch.object(backup, 'NAS_OFFHOST_CONFIG', config), patch.object(backup, 'run', side_effect=run):
                    if corrupt:
                        with self.assertRaisesRegex(RuntimeError, 'readback mismatch'):
                            backup.replicate_nas_settings([receipt])
                        self.assertNotIn('remote_ciphertext_verified', receipt)
                        self.assertEqual(len(calls), 2)
                    else:
                        backup.replicate_nas_settings([receipt])
                        self.assertTrue(receipt['remote_ciphertext_verified'])
                        self.assertEqual(len(calls), 3)
                self.assertEqual(source.read_bytes(), b'encrypted fixture')

    def test_offhost_rejects_paths_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'rclone.conf'
            config.touch(mode=0o600)
            with patch.object(backup, 'NAS_OFFHOST_CONFIG', config), patch.object(backup, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'filename'):
                    backup.replicate_nas_settings([{'file': '../outside.tar.age'}])
                run.assert_not_called()

    def test_online_plex_snapshot_includes_committed_wal_and_excludes_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Preferences.xml').write_text('<Preferences/>')
            connections = []
            try:
                for name in backup.PLEX_FILES[1:]:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    db = sqlite3.connect(path)
                    connections.append(db)
                    db.execute('PRAGMA journal_mode=WAL')
                    db.execute('CREATE TABLE sample(value TEXT)')
                    db.execute("INSERT INTO sample VALUES ('committed')")
                    db.commit()
                    db.execute("INSERT INTO sample VALUES ('uncommitted')")
                (root / 'media.mkv').write_bytes(b'not backed up')
                manifest, contents = backup.plex_snapshot(root)
                self.assertEqual(set(contents), set(backup.PLEX_FILES))
                self.assertEqual(len(manifest['entries']), 3)
                for name in backup.PLEX_FILES[1:]:
                    restored = root / ('restored-' + Path(name).name)
                    restored.write_bytes(contents[name])
                    with sqlite3.connect(restored) as db:
                        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
                        self.assertEqual(db.execute('SELECT * FROM sample').fetchall(), [('committed',)])
            finally:
                for db in connections:
                    db.close()

    def test_retention_preserves_seven_generations_and_unrelated_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(10):
                name = f'plex-202501{index + 1:02}T000000Z.tar.age'
                archive = root / name
                archive.write_bytes(str(index).encode())
                archive.with_suffix('.json').write_text(json.dumps({'file': name, 'created_at': index, 'sha256': backup.digest(archive)}))
            original = root / 'original-master.tar.age'
            original.write_bytes(b'keep')
            backup.prune_local('plex', root)
            self.assertEqual(len(list(root.glob('plex-*.tar.age'))), 7)
            self.assertEqual(original.read_bytes(), b'keep')

    def test_retention_does_not_delete_mismatched_ciphertext(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(8):
                archive = root / f'plex-202501{index + 1:02}T000000Z.tar.age'
                archive.write_bytes(b'changed')
                archive.with_suffix('.json').write_text(json.dumps({'file': archive.name, 'created_at': index, 'sha256': 'mismatch'}))
            with self.assertRaisesRegex(RuntimeError, 'retention receipt mismatch'):
                backup.prune_local('plex', root)
            self.assertEqual(len(list(root.glob('*.tar.age'))), 8)


if __name__ == '__main__':
    unittest.main()
