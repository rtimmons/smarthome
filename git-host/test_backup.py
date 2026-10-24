import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3
import io
import json
import os
import tarfile
import tempfile
import unittest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data/custom/conf').mkdir(parents=True)
        (self.root / 'config').mkdir()
        (self.root / 'data/custom/conf/app.ini').write_text('APP_NAME = Fixture Forgejo\n[database]\nPATH = /var/lib/gitea/forgejo.db\n')
        with closing(sqlite3.connect(self.root / 'data/forgejo.db')) as db:
            db.execute('CREATE TABLE fixture (value TEXT)')
            db.execute("INSERT INTO fixture VALUES ('Synthetic repository')")
            db.commit()
        for name in ('compose.yaml', 'backup.sh', 'backup.py', 'install-cron.py'):
            (self.root / name).write_text('fixture\n')
        self.backup = module('backup')

    def test_snapshot_includes_raw_database_and_secret_configuration(self):
        entries = {e['path']: e for e in self.backup.inventory(self.root)}
        self.assertIn('sha256', entries['data/forgejo.db'])
        self.assertIn('sha256', entries['data/custom/conf/app.ini'])

    def test_refuse_link_outside_service(self):
        (self.root / 'data/outside').symlink_to('/etc/passwd')
        with self.assertRaises(RuntimeError):
            self.backup.inventory(self.root)

    def test_database_wal_is_preserved_as_persistent_state(self):
        writer = sqlite3.connect(self.root / 'data/forgejo.db')
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("INSERT INTO fixture VALUES ('Committed WAL value')")
        writer.commit()
        entries = {e['path'] for e in self.backup.inventory(self.root)}
        self.assertIn('data/forgejo.db-wal', entries)

    def test_refuse_corrupt_database(self):
        (self.root / 'data/forgejo.db').write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):
            self.backup.inventory(self.root)

    def test_cron_preserves_other_jobs_and_removes_only_own_probe(self):
        cron = module('install-cron')
        unrelated = '# existing comment\n5 2 * * * /existing/job\n'
        probed = cron.reconcile(unrelated, True)
        self.assertTrue(probed.startswith(unrelated))
        result = cron.reconcile(probed)
        self.assertEqual(result, cron.reconcile(result))
        self.assertTrue(result.startswith(unrelated))
        self.assertNotIn('home-git-cron-probe', result)
        self.assertEqual(result.count(cron.MARKER), 1)

    def test_independent_restore_checks_manifest_and_database(self):
        writer = sqlite3.connect(self.root / 'data/forgejo.db')
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("INSERT INTO fixture VALUES ('Committed WAL value')")
        writer.commit()
        os.link(self.root / 'backup.sh', self.root / 'data/fixture-hardlink')
        entries = self.backup.inventory(self.root)
        archive_path = self.root / 'test.tar'
        with tarfile.open(archive_path, 'w', dereference=True) as archive:
            raw = json.dumps({'schema': 1, 'scope': 'forgejo', 'entries': entries}).encode()
            info = tarfile.TarInfo('manifest.json'); info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            for entry in entries:
                archive.add(self.root / entry['path'], arcname=entry['path'], recursive=False)
        verifier = module('verify-backup')
        result = verifier.verify(archive_path, self.root / 'restored')
        self.assertTrue(result['verified'])
        self.assertEqual(result['sqlite_integrity'], 'ok')
        with closing(sqlite3.connect(self.root / 'restored/data/forgejo.db')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fixture').fetchone()[0], 2)

    def test_restore_rejects_parent_path(self):
        archive_path = self.root / 'unsafe.tar'
        with tarfile.open(archive_path, 'w') as archive:
            info = tarfile.TarInfo('../escape'); info.size = 1
            archive.addfile(info, io.BytesIO(b'x'))
        with self.assertRaises(RuntimeError):
            module('verify-backup').verify(archive_path, self.root / 'restored')


if __name__ == '__main__':
    unittest.main()
