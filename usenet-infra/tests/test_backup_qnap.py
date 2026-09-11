from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('backup_qnap', Path(__file__).parents[1] / 'scripts/backup-qnap.py')
assert SPEC and SPEC.loader
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)
REAL_AGE = backup.age_binary()


class BackupQnapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / 'source'
        self.host_root = '/share/Container/usenet'
        for name in backup.REQUIRED:
            self.write(name, b'PRIVATE-TEST-FIXTURE')
        suffixes = {
            'QNAP_CATALOG_STATE_DIR': '/state', 'QNAP_CATALOG_SCRIPTS_DIR': '/scripts',
            'QNAP_DASHBOARD_CONFIG_DIR': '/compose/qnap/olivetin',
            'QNAP_DASHBOARD_STATE_DIR': '/state/dashboard',
            'QNAP_DASHBOARD_AUTH_FILE': '/secrets/dashboard-auth.json',
            'QNAP_STORAGEBOX_KEY_FILE': '/secrets/storagebox/id_ed25519',
            'QNAP_STORAGEBOX_KNOWN_HOSTS_FILE': '/secrets/storagebox/known_hosts',
        }
        self.values = {key: self.host_root + suffix for key, suffix in suffixes.items()}
        self.values['QNAP_CATALOG_CACHE_DIR'] = '/share/Media/usenet-cache'
        self.write_env()

    def write_env(self):
        self.write('compose/qnap/.env', '\n'.join(key + '=' + json.dumps(value)
                   for key, value in self.values.items()).encode())

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(value)
        path.chmod(0o600)
        return path

    def snapshot(self, **kwargs):
        return backup.snapshot(self.root, self.host_root, **kwargs)

    def tar(self, *, mutate=None, manifest=None, contents=None):
        if manifest is None:
            manifest, contents = self.snapshot()
        output = io.BytesIO()
        if mutate is None:
            backup.write_tar(manifest, contents, output)
        else:
            with tarfile.open(fileobj=output, mode='w') as archive:
                values = [('MANIFEST.json', json.dumps(manifest).encode()),
                          *(('payload/' + entry['path'], contents[entry['path']]) for entry in manifest['entries'])]
                for name, value in values:
                    member = tarfile.TarInfo(name)
                    member.size = len(value)
                    member, value = mutate(member, value)
                    archive.addfile(member, io.BytesIO(value))
        return output.getvalue()

    def identity(self):
        path = self.work / 'identity'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return path

    def encrypted(self, identity, value=None):
        archive = self.work / 'fixture.tar.age'
        subprocess.run([str(REAL_AGE), '--encrypt', '--recipients-file', str(identity) + '.pub',
                        '--output', str(archive)], input=value if value is not None else self.tar(),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        archive.chmod(0o600)
        return archive

    def test_complete_configuration_and_execution_history_without_media_or_client_cache(self):
        included = ['config/catalog/catalog.schema.json', 'state/items/item.json',
                    'state/failures/failed.json', 'state/operations/item.json',
                    'state/dashboard/logs/results/action.json', 'state/dashboard/logs/output/action.txt']
        excluded = ['media/item.mkv', 'state/docker-client/config.json', 'state/docker-client/buildx/current',
                    'scripts/__pycache__/module.pyc', 'state/dashboard/.temporary',
                    'state/dashboard/refresh.lock', 'state/locks/cache.lock']
        for name in included + excluded:
            self.write(name, b'PRIVATE-CONTENT')
        manifest, contents = self.snapshot()
        paths = {entry['path'] for entry in manifest['entries']}
        self.assertTrue(set(backup.REQUIRED + tuple(included)) <= paths)
        self.assertTrue(paths.isdisjoint(excluded))
        self.assertEqual(set(contents), paths)
        self.assertNotIn('PRIVATE-', json.dumps(manifest))
        self.assertFalse(manifest['cache_content_included'])

    def test_locks_use_existing_readonly_descriptors_and_leave_no_new_files(self):
        lock = self.write('state/locks/cache.lock', b'')
        lock.chmod(0o400)
        before = backup.fingerprint(lock.stat())
        self.snapshot()
        self.assertEqual(backup.fingerprint(lock.stat()), before)
        self.assertFalse((self.root / 'state/dashboard/refresh.lock').exists())
        with lock.open('rb') as writer:
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(backup.BackupError, 'active'):
                self.snapshot()

    def test_active_refresh_and_newly_created_catalog_lock_refuse_capture(self):
        lock = self.write('state/dashboard/refresh.lock', b'')
        with lock.open('rb') as writer:
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(backup.BackupError, 'active'):
                self.snapshot()
        with self.assertRaisesRegex(backup.BackupError, 'activity began'):
            self.snapshot(after_copy=lambda: self.write('state/locks/cache.lock', b''))

    def test_independent_history_write_addition_and_removal_refuse_capture(self):
        path = self.write('state/dashboard/logs/output/execution.txt', b'BEFORE')
        for change in (lambda: path.write_bytes(b'AFTER!'),
                       lambda: self.write('state/dashboard/logs/results/new.json', b'{}'),
                       lambda: path.unlink()):
            with self.subTest(change=change), self.assertRaisesRegex(backup.BackupError, 'changed'):
                self.snapshot(after_copy=change)
            if not path.exists():
                path.write_bytes(b'BEFORE')

    def test_second_hash_catches_content_change_even_with_mocked_stable_metadata(self):
        path = self.write('state/dashboard/logs/output/execution.txt', b'BEFORE')
        with mock.patch.object(backup, 'fingerprint', return_value=('stable',)):
            with self.assertRaisesRegex(backup.BackupError, 'history changed'):
                self.snapshot(after_copy=lambda: path.write_bytes(b'AFTER!'))

    def test_source_link_and_fifo_refused_without_following_or_blocking(self):
        path = self.write('scripts/unsafe', b'')
        path.unlink()
        path.symlink_to(self.root / 'secrets/dashboard-auth.json')
        with self.assertRaises(OSError):
            self.snapshot()
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(backup.BackupError, 'special'):
            self.snapshot()
        path.unlink()
        path.symlink_to(self.root / 'secrets', target_is_directory=True)
        with self.assertRaisesRegex(backup.BackupError, 'directory links'):
            self.snapshot()

    def test_missing_configuration_custom_secret_path_and_sqlite_refused(self):
        self.values['QNAP_DASHBOARD_AUTH_FILE'] = '/share/elsewhere/auth.json'
        self.write_env()
        with self.assertRaisesRegex(backup.BackupError, 'Custom QNAP paths'):
            self.snapshot()
        self.values['QNAP_DASHBOARD_AUTH_FILE'] = self.host_root + '/secrets/dashboard-auth.json'
        self.write_env()
        path = self.write('state/dashboard/history.db', b'SQLite format 3\x00')
        with self.assertRaisesRegex(backup.BackupError, 'database'):
            self.snapshot()
        path.unlink()
        (self.root / 'state/dashboard/runtime/config.yaml').unlink()
        with self.assertRaisesRegex(backup.BackupError, 'missing'):
            self.snapshot()

    def test_cache_inside_application_root_and_oversized_snapshot_refused(self):
        self.values['QNAP_CATALOG_CACHE_DIR'] = self.host_root + '/cache'
        self.write_env()
        with self.assertRaisesRegex(backup.BackupError, 'cache must be outside'):
            self.snapshot()
        with mock.patch.object(backup, 'MAX_BYTES', 1):
            with self.assertRaisesRegex(backup.BackupError, 'exceeds'):
                self.snapshot()

    def test_archive_verification_does_not_create_plaintext_files(self):
        value = self.tar()
        before = set(self.work.rglob('*'))
        with mock.patch.object(backup.tempfile, 'TemporaryDirectory', side_effect=AssertionError('no staging')):
            manifest = backup.verify_tar(value)
        self.assertEqual(manifest['scope'], 'qnap-config')
        self.assertEqual(set(self.work.rglob('*')), before)

    def test_explicit_isolated_restore_matches_all_hashes_and_private_modes(self):
        destination = self.work / 'restore'
        manifest = backup.verify_tar(self.tar(), destination)
        for entry in manifest['entries']:
            target = destination / entry['path']
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), entry['sha256'])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
        with self.assertRaisesRegex(backup.BackupError, 'new absolute destination'):
            backup.verify_tar(self.tar(), destination)

    def test_malicious_archive_names_links_and_duplicate_members_refused(self):
        for replacement in ('../escaped', '/absolute', 'payload/../escaped', 'MANIFEST.json'):
            def mutate(member, value):
                if member.name == 'payload/scripts/catalogctl.py':
                    member.name = replacement
                return member, value
            with self.subTest(replacement=replacement), self.assertRaises(backup.BackupError):
                backup.verify_tar(self.tar(mutate=mutate), self.work / 'restore')
        def symlink(member, value):
            if member.name == 'payload/scripts/catalogctl.py':
                member.type, member.linkname, member.size = tarfile.SYMTYPE, '/private/file', 0
                value = b''
            return member, value
        with self.assertRaises(backup.BackupError):
            backup.verify_tar(self.tar(mutate=symlink), self.work / 'restore')
        self.assertFalse((self.work / 'restore').exists())

    def test_wrong_hash_missing_required_and_extra_cache_refused_before_restore(self):
        manifest, contents = self.snapshot()
        contents['scripts/catalogctl.py'] = b'X' * len(contents['scripts/catalogctl.py'])
        with self.assertRaisesRegex(backup.BackupError, 'checksum'):
            backup.verify_tar(self.tar(manifest=manifest, contents=contents), self.work / 'restore')
        manifest['entries'] = [entry for entry in manifest['entries'] if entry['path'] != 'scripts/catalogctl.py']
        with self.assertRaisesRegex(backup.BackupError, 'allowlisted'):
            backup.verify_tar(self.tar(manifest=manifest, contents=contents))
        manifest, contents = self.snapshot()
        manifest['entries'].append({'path': 'state/docker-client/config.json', 'size': 0, 'sha256': hashlib.sha256(b'').hexdigest()})
        contents['state/docker-client/config.json'] = b''
        with self.assertRaisesRegex(backup.BackupError, 'allowlisted'):
            backup.verify_tar(self.tar(manifest=manifest, contents=contents))
        self.assertFalse((self.work / 'restore').exists())

    def test_archive_limits_checked_before_extracting(self):
        value = self.tar()
        with mock.patch.object(backup, 'MAX_TAR_BYTES', 1):
            with self.assertRaisesRegex(backup.BackupError, 'limit'):
                backup.verify_tar(value)
        with mock.patch.object(backup, 'MAX_FILES', 1):
            with self.assertRaisesRegex(backup.BackupError, 'file-count'):
                backup.verify_tar(value)

    def test_pinned_connection_readonly_mount_network_disabled_and_shell_quoted(self):
        identity = self.work / 'key'
        identity.touch(mode=0o600)
        known = self.work / 'known hosts'
        known.touch()
        environment = {'QNAP_SSH_TARGET': 'usenet-deploy@nas.local', 'QNAP_SSH_KEY': str(identity),
                       'QNAP_SSH_KNOWN_HOSTS': str(known),
                       'QNAP_PROJECT_DIR': "/share/Container/a b'$(touch NEVER)/compose/qnap"}
        command, returned = backup.connection(environment)
        self.assertEqual(returned, identity)
        for flag in ('StrictHostKeyChecking=yes', 'IdentitiesOnly=yes', 'IdentityAgent=none',
                     'PreferredAuthentications=publickey', 'PasswordAuthentication=no', 'BatchMode=yes'):
            self.assertIn(flag, command)
        invocation = shlex.split(command[-1].split('exec "$qnap_docker" ', 1)[1])
        self.assertIn('--network=none', invocation)
        self.assertIn('--read-only', invocation)
        self.assertIn('--pull=never', invocation)
        self.assertIn("type=bind,src=/share/Container/a b'$(touch NEVER),dst=/source,readonly", invocation)
        self.assertIn(backup.IMAGE, invocation)
        self.assertNotIn('/var/run/docker.sock', command[-1])
        environment['QNAP_PROJECT_DIR'] = '/share/Container/x,readonly=false/compose/qnap'
        with self.assertRaises(backup.BackupError):
            backup.connection(environment)

    @unittest.skipUnless(REAL_AGE.is_file(), 'reviewed age binary not bootstrapped')
    def test_real_age_authentication_verify_and_isolated_restore(self):
        identity = self.identity()
        archive = self.encrypted(identity)
        before = set(self.work.rglob('*'))
        manifest = backup.decrypt_verify(archive, identity, REAL_AGE)
        self.assertEqual(manifest['scope'], 'qnap-config')
        self.assertEqual(set(self.work.rglob('*')), before)
        backup.decrypt_verify(archive, identity, REAL_AGE, self.work / 'restore')
        self.assertEqual((self.work / 'restore/secrets/dashboard-auth.json').read_bytes(), b'PRIVATE-TEST-FIXTURE')
        value = bytearray(archive.read_bytes())
        value[-1] ^= 1
        archive.write_bytes(value)
        with mock.patch.object(backup, 'verify_tar', side_effect=AssertionError('must authenticate first')):
            with self.assertRaisesRegex(backup.BackupError, 'authentication'):
                backup.decrypt_verify(archive, identity, REAL_AGE, self.work / 'invalid')
        self.assertFalse((self.work / 'invalid').exists())

    @unittest.skipUnless(REAL_AGE.is_file(), 'reviewed age binary not bootstrapped')
    def test_streamed_capture_only_publishes_verified_ciphertext_and_rejects_partial_failure(self):
        identity = self.identity()
        # The fake SSH process consumes this helper's program, then emits a
        # synthetic tar. It never connects to a host or accesses real secrets.
        emitter = self.work / 'fake-ssh.py'
        fixture = self.work / 'fixture.tar'
        fixture.write_bytes(self.tar())
        emitter.write_text('import pathlib, sys\nsys.stdin.buffer.read()\nsys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())\nraise SystemExit(int(sys.argv[2]))\n')
        import sys
        output_dir = self.work / 'backups'
        command = [sys.executable, str(emitter), str(fixture), '0']
        with mock.patch.object(backup, 'connection', return_value=(command, identity)):
            archive, manifest = backup.capture({}, REAL_AGE, output_dir)
        self.assertEqual(manifest['scope'], 'qnap-config')
        self.assertEqual(list(output_dir.iterdir()), [archive])
        self.assertTrue(archive.read_bytes().startswith(b'age-encryption.org/v1\n'))
        self.assertNotIn(b'PRIVATE-TEST-FIXTURE', archive.read_bytes())
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        command[-1] = '1'
        with mock.patch.object(backup, 'connection', return_value=(command, identity)):
            with self.assertRaisesRegex(backup.BackupError, 'no archive was published'):
                backup.capture({}, REAL_AGE, output_dir)
        self.assertEqual(list(output_dir.iterdir()), [archive])

    def test_cli_never_prints_arbitrary_exceptions(self):
        with mock.patch.object(backup, 'check_age', side_effect=RuntimeError('SECRET URL PASSWORD')):
            with mock.patch('sys.stderr', new_callable=io.StringIO) as output:
                self.assertEqual(backup.main(['capture']), 1)
        self.assertNotIn('SECRET', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error'], 'QNAP backup failed; no raw error or secret was displayed.')


if __name__ == '__main__':
    unittest.main()
