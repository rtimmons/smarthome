import importlib.util
import json
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
