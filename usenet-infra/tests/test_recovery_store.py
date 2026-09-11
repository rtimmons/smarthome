from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('recovery_store', Path(__file__).parents[1] / 'scripts/recovery-store.py')
store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(store)
SNAPSHOT = '20260911T123456Z-a1b2c3d4'
CIPHERTEXT = b'age-encryption.org/v1\nSYNTHETIC-CIPHERTEXT\n'


class RecoveryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / 'remote-store'
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.receipt = {'schema_version': 1, 'snapshot_id': SNAPSHOT,
                        'ciphertext_sha256': hashlib.sha256(CIPHERTEXT).hexdigest(),
                        'ciphertext_bytes': len(CIPHERTEXT), 'deletion_safe': False}
        (self.bundle / store.FILES[0]).write_bytes(CIPHERTEXT)
        self.write_receipt()
        self.calls = []

    def write_receipt(self):
        (self.bundle / store.FILES[1]).write_text(json.dumps(self.receipt))

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.assertEqual(kwargs['env'], store.SAFE_ENV)
        # Execute the actual remote POSIX shell protocol on an isolated local store.
        script = shlex.split(command[-1])[-1]
        script = script.replace('root=' + shlex.quote(store.STORE), 'root=' + shlex.quote(str(self.remote)))
        return subprocess.run(['/bin/sh', '-c', script], **kwargs)

    def popen(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.assertEqual(kwargs['env'], store.SAFE_ENV)
        script = shlex.split(command[-1])[-1]
        script = script.replace('root=' + shlex.quote(store.STORE), 'root=' + shlex.quote(str(self.remote)))
        return subprocess.Popen(['/bin/sh', '-c', script], **kwargs)

    def test_round_trip_verifies_ciphertext_and_private_modes(self):
        self.assertEqual(store.push(self.bundle, ['fake-ssh'], self.runner), SNAPSHOT)
        saved = self.remote / SNAPSHOT
        self.assertEqual(saved.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.remote.stat().st_mode & 0o777, 0o700)
        destination = self.root / 'fetched'
        self.assertEqual(store.fetch(SNAPSHOT, destination, ['fake-ssh'], popen=self.popen), SNAPSHOT)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        for name in store.FILES:
            self.assertEqual((destination / name).read_bytes(), (self.bundle / name).read_bytes())
            self.assertEqual((destination / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual((saved / name).stat().st_mode & 0o777, 0o600)

    def test_exact_republish_is_idempotent_and_different_receipt_refused(self):
        store.push(self.bundle, ['fake-ssh'], self.runner)
        saved = self.remote / SNAPSHOT / store.FILES[0]
        before = saved.stat().st_mtime_ns
        store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertEqual(saved.stat().st_mtime_ns, before)
        self.receipt['created_at'] = 'different-public-receipt'
        self.write_receipt()
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertNotIn('created_at', json.loads((saved.parent / store.FILES[1]).read_text()))
        self.assertEqual(list(self.remote.iterdir()), [saved.parent])

    def test_new_snapshot_keeps_all_older_versions(self):
        store.push(self.bundle, ['fake-ssh'], self.runner)
        self.receipt['snapshot_id'] = '20260911T123457Z-deadbeef'
        self.write_receipt()
        store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertEqual({p.name for p in self.remote.iterdir()}, {SNAPSHOT, self.receipt['snapshot_id']})

    def test_corrupt_local_bundle_is_refused_before_network(self):
        (self.bundle / store.FILES[0]).write_bytes(CIPHERTEXT + b'corruption')
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertFalse(self.calls)

    def test_corrupt_remote_bundle_is_refused_and_destination_removed(self):
        store.push(self.bundle, ['fake-ssh'], self.runner)
        (self.remote / SNAPSHOT / store.FILES[0]).write_bytes(CIPHERTEXT + b'corruption')
        destination = self.root / 'failed-download'
        with self.assertRaises(store.StoreError):
            store.fetch(SNAPSHOT, destination, ['fake-ssh'], popen=self.popen)
        self.assertFalse(destination.exists())
        self.assertTrue((self.remote / SNAPSHOT).exists())

    def test_existing_fetch_destination_is_never_changed(self):
        destination = self.root / 'exists'
        destination.mkdir()
        marker = destination / 'existing'
        marker.write_text('preserve')
        with self.assertRaises(FileExistsError):
            store.fetch(SNAPSHOT, destination, ['fake-ssh'], popen=self.popen)
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertFalse(self.calls)

    def test_symlinked_remote_snapshot_cannot_be_replaced_or_fetched(self):
        self.remote.mkdir(mode=0o700)
        (self.remote / SNAPSHOT).symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        with self.assertRaises(store.StoreError):
            store.fetch(SNAPSHOT, self.root / 'fetch', ['fake-ssh'], popen=self.popen)
        self.assertTrue((self.remote / SNAPSHOT).is_symlink())

    def test_interrupted_upload_does_not_publish_partial_version(self):
        def truncate(command, **kwargs):
            with tempfile.TemporaryFile() as invalid:
                invalid.write(b'invalid transport')
                invalid.seek(0)
                kwargs['stdin'] = invalid
                return self.runner(command, **kwargs)
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], truncate)
        self.assertEqual(list(self.remote.iterdir()), [])

    def test_remote_checksum_failure_never_publishes(self):
        def corrupt(command, **kwargs):
            with tempfile.TemporaryFile() as transport:
                with tarfile.open(fileobj=transport, mode='w') as archive:
                    for name, data in ((store.FILES[0], CIPHERTEXT + b'corrupted'),
                                       (store.FILES[1], (self.bundle / store.FILES[1]).read_bytes())):
                        member = tarfile.TarInfo(name)
                        member.size = len(data)
                        archive.addfile(member, io.BytesIO(data))
                transport.seek(0)
                kwargs['stdin'] = transport
                return self.runner(command, **kwargs)
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], corrupt)
        self.assertEqual(list(self.remote.iterdir()), [])

    def test_busy_publication_lock_is_never_removed_by_another_push(self):
        self.remote.mkdir(mode=0o700)
        lock = self.remote / ('.' + SNAPSHOT + '.lock')
        lock.mkdir()
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertEqual(list(self.remote.iterdir()), [lock])

    def test_existing_root_permissions_are_checked_without_chmod(self):
        self.remote.mkdir(mode=0o755)
        self.remote.chmod(0o755)
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        self.assertEqual(self.remote.stat().st_mode & 0o777, 0o755)
        self.assertFalse(list(self.remote.iterdir()))

    def test_remote_loose_modes_and_hardlinks_are_rejected(self):
        store.push(self.bundle, ['fake-ssh'], self.runner)
        saved = self.remote / SNAPSHOT / store.FILES[0]
        saved.chmod(0o644)
        with self.assertRaises(store.StoreError):
            store.push(self.bundle, ['fake-ssh'], self.runner)
        with self.assertRaises(store.StoreError):
            store.fetch(SNAPSHOT, self.root / 'fetch-mode', ['fake-ssh'], popen=self.popen)
        saved.chmod(0o600)
        os.link(saved, self.root / 'external-link')
        with self.assertRaises(store.StoreError):
            store.fetch(SNAPSHOT, self.root / 'fetch-link', ['fake-ssh'], popen=self.popen)

    def test_streaming_download_is_bounded_and_stalled_process_is_killed(self):
        processes = []
        for program in ('import os; os.write(1, b"x" * 65536)', 'import time; time.sleep(10)'):
            def popen(command, **kwargs):
                self.assertEqual(kwargs['env'], store.SAFE_ENV)
                process = subprocess.Popen([sys.executable, '-c', program], **kwargs)
                processes.append(process)
                return process
            with tempfile.TemporaryFile() as transport, self.assertRaises(store.StoreError):
                store.receive(['fake-ssh'], '', transport, popen=popen, timeout=0.1, limit=16)
            self.assertIsNotNone(processes[-1].poll())

    def test_dotenv_rejects_symlink_hardlink_and_unsafe_parent(self):
        private = self.root / 'private'
        private.mkdir(mode=0o700)
        environment = private / '.env'
        environment.write_text('QNAP_SSH_TARGET=a@b\nQNAP_SSH_KEY=a\nQNAP_SSH_KNOWN_HOSTS=b\n')
        environment.chmod(0o644)
        with self.assertRaises(store.StoreError):
            store.read_environment(environment, self.root)
        environment.chmod(0o600)
        alias = self.root / 'alias.env'
        alias.symlink_to(environment)
        with self.assertRaises(store.StoreError):
            store.read_environment(alias, self.root)
        alias.unlink()
        os.link(environment, alias)
        with self.assertRaises(store.StoreError):
            store.read_environment(environment, self.root)
        alias.unlink()
        private.chmod(0o777)
        with self.assertRaises(store.StoreError):
            store.read_environment(environment, self.root)
        private.chmod(0o700)
        linked_parent = self.root / 'linked-parent'
        linked_parent.symlink_to(private, target_is_directory=True)
        with self.assertRaises(store.StoreError):
            store.read_environment(linked_parent / '.env', self.root)

    def test_retrieval_rejects_traversal_links_and_duplicate_entries(self):
        for names in (('../escape', 'receipt.json'), ('recovery.tar.age', 'recovery.tar.age')):
            transport = io.BytesIO()
            with tarfile.open(fileobj=transport, mode='w') as archive:
                for name in names:
                    member = tarfile.TarInfo(name)
                    member.size = 1
                    archive.addfile(member, io.BytesIO(b'x'))
            transport.seek(0)
            with self.assertRaises(store.StoreError):
                store.unpack(transport, SNAPSHOT)
        transport = io.BytesIO()
        with tarfile.open(fileobj=transport, mode='w') as archive:
            for name in store.FILES:
                member = tarfile.TarInfo(name)
                member.type, member.linkname = tarfile.SYMTYPE, '../escape'
                archive.addfile(member)
        transport.seek(0)
        with self.assertRaises(store.StoreError):
            store.unpack(transport, SNAPSHOT)

    def test_snapshot_injection_and_false_integrity_metadata_are_refused(self):
        for snapshot in ('../escape', '2026;touch /tmp/bad', '-bad', '$(id)', ''):
            with self.assertRaises(store.StoreError):
                store.fetch_script(snapshot)
        for field, value in (('deletion_safe', True), ('ciphertext_bytes', True),
                             ('schema_version', True), ('ciphertext_sha256', 'bad')):
            receipt = {**self.receipt, field: value}
            with self.assertRaises(store.StoreError):
                store.validate_bundle(CIPHERTEXT, json.dumps(receipt).encode())

    def test_env_is_literal_and_relative_ssh_paths_resolve_from_infra(self):
        infra = self.root / 'usenet-infra'
        key = infra / 'secrets/ssh/qnap-admin'
        key.parent.mkdir(parents=True)
        pin = infra / 'ansible/files/secrets/qnap-known-hosts'
        pin.parent.mkdir(parents=True)
        key.write_text('SYNTHETIC-KEY')
        key.chmod(0o600)
        pin.write_text('SYNTHETIC-PIN')
        pin.chmod(0o600)
        environment = infra / '.env'
        environment.write_text("# comment\nQNAP_SSH_TARGET='service@nas.local'\n"
                               'QNAP_SSH_KEY=secrets/ssh/qnap-admin\nQNAP_SSH_KNOWN_HOSTS=ansible/files/secrets/qnap-known-hosts\n'
                               'UNRELATED_SECRET=opaque-value\n')
        environment.chmod(0o600)
        values = store.read_environment(environment, self.root)
        self.assertNotIn('UNRELATED_SECRET', values)
        command = store.connection_command(values, infra)
        self.assertIn(str(key), command)
        self.assertIn('UserKnownHostsFile=' + str(pin), command)
        for option in ('IdentityAgent=none', 'IdentitiesOnly=yes', 'StrictHostKeyChecking=yes',
                       'PasswordAuthentication=no', 'GlobalKnownHostsFile=/dev/null'):
            self.assertIn(option, command)
        self.assertEqual(command[1:3], ['-F', '/dev/null'])
        self.assertNotIn('SOPS_AGE_KEY', store.SAFE_ENV)
        key.chmod(0o644)
        with self.assertRaises(store.StoreError):
            store.connection_command(values, infra)
        for line in ('QNAP_SSH_KEY=$(touch /tmp/bad)', 'QNAP_SSH_KEY="${HOME}/key"',
                     'QNAP_SSH_KEY=first\nQNAP_SSH_KEY=second', 'source other.env'):
            environment.write_text(line)
            with self.assertRaises(store.StoreError):
                store.read_environment(environment, self.root)


if __name__ == '__main__':
    unittest.main()
