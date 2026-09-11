from __future__ import annotations

import importlib.util
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('config_backup', Path(__file__).parents[1] / 'scripts/config-backup.py')
assert SPEC and SPEC.loader
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)
REAL_AGE = Path(os.environ.get('CONFIG_BACKUP_TEST_AGE', str(
    Path(__file__).parents[2] / 'build/tools/age-1.3.2/darwin-arm64/age')))


class ConfigBackupTests(unittest.TestCase):
    def test_paused_queue_is_accepted_without_changing_jobs(self):
        for queued, paused, processing, allowed in [(3, True, 0, True), (0, False, 0, True),
                                                   (3, False, 0, False), (3, True, 1, False),
                                                   (3, 'true', 0, False)]:
            with self.subTest(queued=queued, paused=paused, processing=processing):
                opener = mock.Mock()
                opener.open.side_effect = [
                    io.BytesIO(json.dumps({'queue': {'noofslots_total': queued, 'paused': paused}}).encode()),
                    io.BytesIO(json.dumps({'history': {'ppslots': processing}}).encode())]
                with mock.patch.object(backup.urllib.request, 'build_opener', return_value=opener):
                    if allowed:
                        backup.require_idle('fixture')
                    else:
                        with self.assertRaises(backup.BackupError):
                            backup.require_idle('fixture')
                self.assertEqual(opener.open.call_count, 2)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / 'source'
        for name in backup.REQUIRED:
            self.write(name, b'PRIVATE-FIXTURE')
        self.write('config/catalog.env', b'SABNZBD_API_KEY=PRIVATE-FIXTURE\nCATALOG_REMOTE=storagebox:catalog\n')
        self.db = self.root / 'config/prowlarr/prowlarr.db'
        self.db.unlink()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute('CREATE TABLE settings (value TEXT)')
            connection.execute('INSERT INTO settings VALUES (?)', ('PRIVATE-FIXTURE',))
            connection.commit()
        self.stage = self.work / 'stage'
        self.stage.mkdir(mode=0o700)
        self.remote = {'metadata/manifests/test_item.v1.json': b'{"id":"test_item.v1"}'}

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o600)
        return path

    def snapshot(self, **overrides):
        return backup.stage_snapshot(self.root, self.stage,
                                     idle=overrides.get('idle', lambda key: None),
                                     manifests=overrides.get('manifests', lambda *args: self.remote))

    def tar(self, manifest=None, mutate=None):
        manifest = manifest or self.snapshot()
        path = self.work / 'snapshot.tar'
        with tarfile.open(path, 'w') as archive:
            value = json.dumps(manifest).encode()
            member = tarfile.TarInfo('MANIFEST.json')
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
            for entry in manifest['entries']:
                content = (self.stage / entry['path']).read_bytes()
                member = tarfile.TarInfo('payload/' + entry['path'])
                member.size = len(content)
                if mutate:
                    member, content = mutate(member, content)
                archive.addfile(member, io.BytesIO(content))
        return path

    def test_allowlisted_snapshot_omits_bulk_and_captures_writer_and_receipt(self):
        self.write('downloads/complete/movie.mkv', b'BULK')
        self.write('config/sabnzbd/Downloads/complete/movie.mkv', b'BULK')
        self.write('config/sabnzbd/nzbcache/upload.nzb', b'BULK')
        self.write('config/prowlarr/MediaCover/image.jpg', b'BULK')
        self.write('config/prowlarr/logs.db', b'LOGS')
        self.write('secrets/storagebox/id_ed25519', b'PRIVATE-WRITER-KEY')
        self.write('state/sab-smoke-test.json', b'{}')
        manifest = self.snapshot()
        paths = {entry['path'] for entry in manifest['entries']}
        self.assertIn('secrets/storagebox/id_ed25519', paths)
        self.assertIn('state/sab-smoke-test.json', paths)
        self.assertIn('metadata/manifests/test_item.v1.json', paths)
        self.assertFalse(any('movie.mkv' in path or 'MediaCover' in path or path.endswith('logs.db') or 'nzbcache' in path for path in paths))
        self.assertFalse(any('cloud-admin' in path for path in paths))
        self.assertNotIn('PRIVATE-', json.dumps(manifest))

    def test_discovery_backup_requires_both_apps_and_verifies_their_databases(self):
        self.write('compose/discovery/compose.yaml', b'services: {}')
        with self.assertRaises(backup.BackupError):
            backup.inventory(self.root)
        for app in ('radarr', 'sonarr'):
            self.write(f'config/{app}/config.xml', b'PRIVATE-FIXTURE')
            path = self.root / f'config/{app}/{app}.db'
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('CREATE TABLE settings (value TEXT)')
                connection.execute('INSERT INTO settings VALUES (?)', ('PRIVATE-FIXTURE',))
                connection.commit()
            self.write(f'config/{app}/MediaCover/test.jpg', b'BULK')
        manifest = self.snapshot()
        databases = {entry['path'] for entry in manifest['entries'] if entry['sqlite']}
        self.assertIn('config/radarr/radarr.db', databases)
        self.assertIn('config/sonarr/sonarr.db', databases)
        self.assertFalse(any('MediaCover' in entry['path'] for entry in manifest['entries']))

    def test_sqlite_backup_includes_committed_wal_without_copying_wal(self):
        connection = sqlite3.connect(self.db)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('INSERT INTO settings VALUES (?)', ('committed-in-wal',))
        connection.commit()
        self.assertTrue(Path(str(self.db) + '-wal').exists())
        manifest = self.snapshot()
        with closing(sqlite3.connect(self.stage / 'config/prowlarr/prowlarr.db')) as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM settings').fetchone()[0], 2)
        self.assertFalse(any(entry['path'].endswith(('-wal', '-shm')) for entry in manifest['entries']))
        self.assertTrue(next(entry for entry in manifest['entries'] if entry['path'].endswith('prowlarr.db'))['sqlite'])

    def test_concurrent_database_commit_refuses_capture(self):
        def manifests(*args):
            with closing(sqlite3.connect(self.db)) as writer:
                writer.execute('INSERT INTO settings VALUES (?)', ('arrived-during-backup',))
                writer.commit()
            return self.remote
        with self.assertRaisesRegex(backup.BackupError, 'database changed'):
            self.snapshot(manifests=manifests)

    def test_concurrent_settings_and_manifest_changes_refuse_capture(self):
        def manifests(*args):
            self.write('config/prowlarr/config.xml', b'changed')
            return self.remote
        with self.assertRaisesRegex(backup.BackupError, 'Configuration changed'):
            self.snapshot(manifests=manifests)
        calls = []
        def changing(*args):
            calls.append(True)
            return self.remote if len(calls) == 1 else {}
        with self.assertRaisesRegex(backup.BackupError, 'metadata changed'):
            self.snapshot(manifests=changing)

    def test_jobs_arriving_after_capture_refuse_snapshot(self):
        idle = mock.Mock(side_effect=[None, backup.BackupError('busy')])
        with self.assertRaisesRegex(backup.BackupError, 'busy'):
            self.snapshot(idle=idle)
        self.assertEqual(idle.call_count, 2)

    def test_source_symlinks_and_missing_config_refuse_capture(self):
        outside = self.work / 'outside'
        outside.write_text('PRIVATE-OUTSIDE')
        (self.root / 'config/prowlarr/unexpected').symlink_to(outside)
        with self.assertRaises(backup.BackupError):
            self.snapshot()
        (self.root / 'config/prowlarr/unexpected').unlink()
        (self.root / 'config/prowlarr/config.xml').unlink()
        with self.assertRaisesRegex(backup.BackupError, 'Required'):
            self.snapshot()

    def test_verified_restore_is_fresh_private_and_preserves_database(self):
        archive = self.tar()
        destination = self.work / 'restore'
        result = backup.extract_verified(archive, destination)
        self.assertEqual(len(result['entries']), len(self.snapshot()['entries']))
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        for path in destination.rglob('*'):
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        backup.sqlite_integrity(destination / 'config/prowlarr/prowlarr.db')
        with self.assertRaisesRegex(backup.BackupError, 'fresh'):
            backup.extract_verified(archive, destination)

    def test_checksum_failure_removes_partial_restore(self):
        manifest = self.snapshot()
        manifest['entries'][0]['sha256'] = '0' * 64
        archive = self.tar(manifest)
        destination = self.work / 'restore'
        with self.assertRaisesRegex(backup.BackupError, 'checksum'):
            backup.extract_verified(archive, destination)
        self.assertFalse(destination.exists())

    def test_incomplete_archive_cannot_be_reported_as_verified(self):
        manifest = self.snapshot()
        manifest['entries'] = [entry for entry in manifest['entries'] if entry['path'] != 'config/prowlarr/prowlarr.db']
        archive = self.tar(manifest)
        with self.assertRaisesRegex(backup.BackupError, 'inventory'):
            backup.extract_verified(archive, self.work / 'restore')
        self.assertFalse((self.work / 'restore').exists())

    def test_unsafe_tar_paths_links_devices_and_duplicates_are_rejected(self):
        cases = ['../escape', '/absolute', 'payload/../../escape', 'payload//double', 'link', 'device', 'duplicate']
        for case in cases:
            with self.subTest(case=case):
                used = []
                def mutate(member, content):
                    if case == 'duplicate':
                        member.name = 'MANIFEST.json'
                    elif not used:
                        used.append(True)
                        if case == 'link':
                            member.type, member.linkname, member.size = tarfile.SYMTYPE, '/etc/passwd', 0
                        elif case == 'device':
                            member.type, member.size = tarfile.CHRTYPE, 0
                        else:
                            member.name = case
                    return member, content
                archive = self.tar(mutate=mutate)
                destination = self.work / 'restore'
                with self.assertRaises(backup.BackupError):
                    backup.extract_verified(archive, destination)
                self.assertFalse(destination.exists())
        self.assertFalse((self.work / 'escape').exists())

    def test_decryption_failure_never_parses_authenticated_partial_plaintext(self):
        archive, identity = self.work / 'archive.age', self.work / 'key'
        for path in (archive, identity):
            path.write_bytes(b'PRIVATE-FIXTURE')
            path.chmod(0o600)
        def failed(command, **kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(b'PARTIAL-PLAINTEXT')
            raise subprocess.CalledProcessError(1, command, stderr=b'PRIVATE-ERROR')
        with mock.patch.object(backup.subprocess, 'run', side_effect=failed), \
                mock.patch.object(backup, 'extract_verified') as extract:
            with self.assertRaises(subprocess.CalledProcessError):
                backup.decrypt_verify(archive, identity, self.work / 'restore', 'reviewed-age')
            extract.assert_not_called()
        self.assertFalse((self.work / 'restore').exists())
        self.assertFalse(list(self.work.glob('usenet-config-restore-*')))

    def test_age_pin_and_private_archive_permissions_are_enforced(self):
        result = subprocess.CompletedProcess([], 0, stdout=b'v1.3.1\n')
        with mock.patch.object(backup.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(backup.BackupError, '1.3.2'):
                backup.check_age('age')
        path = self.work / 'archive.age'
        path.write_text('ciphertext')
        path.chmod(0o644)
        with self.assertRaisesRegex(backup.BackupError, '0600'):
            backup.private_file(path)

    @unittest.skipUnless(REAL_AGE.is_file(), 'Run the pinned age bootstrap for the real encryption integration test.')
    def test_real_age_roundtrip_and_tampered_ciphertext_refusal(self):
        # Synthetic configuration and a throwaway key only; this test never
        # reads operator credentials, calls a service, or installs software.
        key = self.work / 'temporary-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manifest = self.snapshot()
        archive = self.work / 'snapshot.age'
        backup.check_age(str(REAL_AGE))
        backup.encrypt(self.stage, key.with_suffix('.pub'), archive, str(REAL_AGE))
        self.assertNotIn(b'PRIVATE-FIXTURE', archive.read_bytes())
        verified = backup.decrypt_verify(archive, key, None, str(REAL_AGE))
        self.assertEqual(verified, manifest)
        destination = self.work / 'restored'
        self.assertEqual(backup.decrypt_verify(archive, key, destination, str(REAL_AGE)), manifest)
        self.assertEqual((destination / 'config/prowlarr/config.xml').read_bytes(), b'PRIVATE-FIXTURE')
        with self.assertRaises(backup.BackupError):
            backup.encrypt(self.stage, key.with_suffix('.pub'), archive, str(REAL_AGE))
        tampered = bytearray(archive.read_bytes())
        tampered[-1] ^= 1
        archive.write_bytes(tampered)
        with self.assertRaises(subprocess.CalledProcessError):
            backup.decrypt_verify(archive, key, self.work / 'rejected', str(REAL_AGE))
        self.assertFalse((self.work / 'rejected').exists())

    def test_unexpected_error_never_outputs_raw_secrets(self):
        previous = os.umask(0o077)
        try:
            with mock.patch.object(backup, 'check_age', side_effect=RuntimeError('PRIVATE-FIXTURE')), \
                    mock.patch('sys.stderr', new_callable=io.StringIO) as stderr:
                self.assertEqual(backup.main(['capture', '--recipient-file', 'key.pub', '--output', '/private/archive.age']), 1)
                self.assertNotIn('PRIVATE-FIXTURE', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
        finally:
            os.umask(previous)


if __name__ == '__main__':
    unittest.main()
