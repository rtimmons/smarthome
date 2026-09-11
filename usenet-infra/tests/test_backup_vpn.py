from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('backup_vpn', Path(__file__).parents[1] / 'scripts/backup-vpn.py')
assert SPEC and SPEC.loader
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)
REAL_AGE = backup.age_binary()


class BackupVpnTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.infra = self.work / 'infra'
        self.infra.mkdir()
        self.patch = mock.patch.object(backup, 'INFRA', self.infra)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.contents = {path: ('PRIVATE-FIXTURE-' + str(i)).encode() for i, path in enumerate(backup.SOURCES)}

    def identity(self, name='identity'):
        path = self.work / name
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(path)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return path

    def environment(self, identity):
        return dict(os.environ, CLOUD_SSH_KEY=str(identity), CLOUD_SSH_TARGET='test@example.invalid',
                    CLOUD_SSH_KNOWN_HOSTS=str(self.work / 'test-pin'))

    def encrypt(self, identity, content):
        archive = self.work / 'fixture.age'
        subprocess.run([str(REAL_AGE), '--encrypt', '--recipients-file', str(identity) + '.pub',
                        '--output', str(archive)], input=content, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        archive.chmod(0o600)
        return archive

    def fake_cloud_command(self, values=None, exit_code=0):
        values = values if values is not None else self.contents
        wrapper = self.infra / 'scripts/cloud-command'
        wrapper.parent.mkdir()
        wrapper.write_text('#!' + sys.executable + '\n'
                           'import sys\n'
                           'assert sys.argv[1:5] == ["sudo", "-n", "cat", "--"]\n'
                           'values=' + repr(values) + '\n'
                           'sys.stdout.buffer.write(values[sys.argv[5]])\n'
                           'sys.stderr.write("PRIVATE-RAW-ERROR")\n'
                           'raise SystemExit(' + str(exit_code) + ')\n')
        wrapper.chmod(0o700)
        return wrapper

    def changed_tar(self, mutation):
        value = backup.package(self.contents)
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(value), mode='r:') as original:
            with tarfile.open(fileobj=output, mode='w') as archive:
                for member in original:
                    content = original.extractfile(member).read()
                    member, content = mutation(member, content)
                    if member:
                        archive.addfile(member, io.BytesIO(content))
        return output.getvalue()

    def test_capture_reads_only_four_fixed_sources_with_bounded_sudo_cat(self):
        environment = {'test': 'only'}
        with mock.patch.object(backup, 'read_bounded', side_effect=lambda command, limit, **kw: self.contents[command[-1]]) as read:
            self.assertEqual(backup.read_sources(environment), self.contents)
        self.assertEqual(read.call_count, 4)
        for call, source in zip(read.call_args_list, backup.SOURCES):
            self.assertEqual(call.args[0], [str(self.infra / 'scripts/cloud-command'), 'sudo', '-n', 'cat', '--', source])
            self.assertLessEqual(call.args[1], backup.MAX_BYTES)
            self.assertEqual(call.kwargs['environment'], environment)
        self.assertEqual(read.call_args_list[0].args[1], 64 * 1024)

    def test_empty_and_oversized_remote_sources_are_refused(self):
        self.fake_cloud_command({**self.contents, backup.SOURCES[0]: b''})
        with self.assertRaisesRegex(backup.BackupError, 'empty'):
            backup.read_sources(dict(os.environ))
        with self.assertRaisesRegex(backup.BackupError, 'size limit'):
            backup.read_bounded([sys.executable, '-c', 'print("X"*100)'], 10)

    def test_failed_read_never_returns_partial_configuration_or_raw_stderr(self):
        self.fake_cloud_command(exit_code=1)
        with self.assertRaisesRegex(backup.BackupError, 'raw output withheld') as error:
            backup.read_sources(dict(os.environ))
        self.assertNotIn('PRIVATE-', str(error.exception))

    @unittest.skipUnless(hasattr(os, 'fork'), 'process-group test requires Unix')
    def test_timeout_kills_descendants_even_after_successful_parent_exit(self):
        script = 'import os,time\nif os.fork():\n os._exit(0)\nelse:\n print("PRIVATE-PARTIAL",flush=True)\n time.sleep(10)\n'
        with mock.patch.object(backup, 'kill_group', wraps=backup.kill_group) as kill:
            with self.assertRaisesRegex(backup.BackupError, 'failed'):
                backup.read_bounded([sys.executable, '-c', script], 1024, timeout=0.2)
            kill.assert_called_once()

    def test_exact_tar_allowlist_manifest_and_checksums_without_plaintext_disk(self):
        value = backup.package(self.contents)
        before = set(self.work.rglob('*'))
        with mock.patch.object(backup.tempfile, 'TemporaryDirectory', side_effect=AssertionError('no plaintext staging')):
            manifest = backup.verify_tar(value)
        self.assertEqual(set(self.work.rglob('*')), before)
        self.assertEqual({entry['path'] for entry in manifest['files']}, set(backup.SOURCES))
        self.assertNotIn('PRIVATE-', json.dumps(manifest))

    def test_missing_extra_traversal_and_duplicate_tar_members_are_refused(self):
        for name in ('../escape', '/etc/passwd', 'payload/etc/shadow', 'MANIFEST.json', None):
            def change(member, content):
                if member.name == 'payload' + backup.SOURCES[0]:
                    if name is None:
                        return None, b''
                    member.name = name
                return member, content
            with self.subTest(name=name), self.assertRaises(backup.BackupError):
                backup.verify_tar(self.changed_tar(change))

    def test_tar_symlink_and_wrong_checksum_refused(self):
        def link(member, content):
            if member.name == 'payload' + backup.SOURCES[0]:
                member.type, member.size, member.linkname = tarfile.SYMTYPE, 0, '/etc/shadow'
                content = b''
            return member, content
        with self.assertRaisesRegex(backup.BackupError, 'unsafe'):
            backup.verify_tar(self.changed_tar(link))
        def corrupt(member, content):
            if member.name == 'payload' + backup.SOURCES[0]:
                content = b'X' * len(content)
            return member, content
        with self.assertRaisesRegex(backup.BackupError, 'checksum'):
            backup.verify_tar(self.changed_tar(corrupt))

    def test_tar_size_limits_and_manifest_source_allowlist(self):
        value = backup.package(self.contents)
        with mock.patch.object(backup, 'MAX_TAR_BYTES', 1):
            with self.assertRaisesRegex(backup.BackupError, 'size limit'):
                backup.verify_tar(value)
        with mock.patch.object(backup, 'MAX_BYTES', 20):
            with self.assertRaises(backup.BackupError):
                backup.verify_tar(value)
        def manifest_change(member, content):
            if member.name == 'MANIFEST.json':
                manifest = json.loads(content)
                manifest['files'][0]['path'] = '/etc/shadow'
                content = json.dumps(manifest).encode()
                member.size = len(content)
            return member, content
        with self.assertRaisesRegex(backup.BackupError, 'allowlist'):
            backup.verify_tar(self.changed_tar(manifest_change))

    @unittest.skipUnless(REAL_AGE.is_file(), 'reviewed age binary not bootstrapped')
    def test_real_capture_publishes_only_verified_private_ciphertext(self):
        identity = self.identity()
        self.fake_cloud_command()
        destination = self.infra / 'backups'
        archive, manifest = backup.capture(self.environment(identity), REAL_AGE, destination)
        self.assertEqual(list(destination.iterdir()), [archive])
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)
        self.assertNotIn(b'PRIVATE-', archive.read_bytes())
        self.assertEqual(backup.verify_tar(backup.decrypt(archive, identity, REAL_AGE)), manifest)
        with mock.patch.dict(os.environ, self.environment(identity)), mock.patch.object(backup, 'age_binary', return_value=REAL_AGE):
            with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(backup.main(['verify', '--archive', str(archive)]), 0)
        response = json.loads(output.getvalue())
        self.assertEqual(response['files'], 4)
        self.assertNotIn('PRIVATE-', output.getvalue())
        self.assertNotIn('/etc/', output.getvalue())

    @unittest.skipUnless(REAL_AGE.is_file(), 'reviewed age binary not bootstrapped')
    def test_changed_source_or_roundtrip_mismatch_never_publishes(self):
        identity = self.identity()
        changed = {**self.contents, backup.SOURCES[0]: b'CHANGED'}
        destination = self.infra / 'backups'
        with mock.patch.object(backup, 'read_sources', side_effect=[self.contents, changed]):
            with self.assertRaisesRegex(backup.BackupError, 'changed during capture'):
                backup.capture(self.environment(identity), REAL_AGE, destination)
        self.assertFalse(destination.exists())
        with mock.patch.object(backup, 'read_sources', return_value=self.contents), mock.patch.object(backup, 'decrypt', return_value=b'wrong'):
            with self.assertRaisesRegex(backup.BackupError, 'checksum'):
                backup.capture(self.environment(identity), REAL_AGE, destination)
        self.assertEqual(list(destination.iterdir()), [])

    @unittest.skipUnless(REAL_AGE.is_file(), 'reviewed age binary not bootstrapped')
    def test_age_authentication_must_succeed_before_any_tar_parsing(self):
        identity = self.identity()
        archive = self.encrypt(identity, backup.package(self.contents))
        content = bytearray(archive.read_bytes())
        content[-1] ^= 1
        archive.write_bytes(content)
        with mock.patch.dict(os.environ, self.environment(identity)), mock.patch.object(backup, 'age_binary', return_value=REAL_AGE):
            with mock.patch.object(backup, 'verify_tar', side_effect=AssertionError('must authenticate first')) as parse:
                with mock.patch('sys.stderr', new_callable=io.StringIO) as output:
                    self.assertEqual(backup.main(['verify', '--archive', str(archive)]), 1)
                parse.assert_not_called()
                self.assertNotIn('PRIVATE-', output.getvalue())

    def test_insecure_identity_or_archive_refused_before_subprocess(self):
        identity = self.work / 'identity'
        identity.touch(mode=0o600)
        archive = self.work / 'archive'
        archive.touch(mode=0o644)
        archive.chmod(0o644)
        with mock.patch.object(backup, 'read_bounded') as read:
            with self.assertRaisesRegex(backup.BackupError, 'private'):
                backup.decrypt(archive, identity, REAL_AGE)
            read.assert_not_called()
        identity.unlink()
        identity.symlink_to(archive)
        with self.assertRaises(backup.BackupError):
            backup.identity_path({'CLOUD_SSH_KEY': str(identity)})

    def test_missing_recipient_stops_before_remote_read(self):
        identity = self.work / 'identity'
        identity.touch(mode=0o600)
        with mock.patch.object(backup, 'read_sources') as read:
            with self.assertRaisesRegex(backup.BackupError, 'public recipient'):
                backup.capture(self.environment(identity), REAL_AGE, self.infra / 'backups')
            read.assert_not_called()

    def test_unexpected_cli_exception_never_prints_secret_or_url(self):
        with mock.patch.object(backup, 'check_age', side_effect=RuntimeError('PSK SECRET https://secret.invalid/')):
            with mock.patch('sys.stderr', new_callable=io.StringIO) as output:
                self.assertEqual(backup.main([]), 1)
        self.assertNotIn('SECRET', output.getvalue())
        self.assertNotIn('https://', output.getvalue())


if __name__ == '__main__':
    unittest.main()
