"""Synthetic fixtures for recovery authentication, publication, and concurrency."""
from contextlib import contextmanager
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('recovery_bundle', Path(__file__).parents[1] / 'scripts/recovery-bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class RecoveryBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'checkout'
        self.root.mkdir(mode=0o700)
        self.package = self.base / 'package.tar'
        self.saved = self.base / 'saved'
        self.saved.mkdir(mode=0o700)
        self.manifest = {'schema_version': 1, 'scope': 'smarthome', 'files': [
            self.entry('first', 'state'), self.entry('second', 'archive'),
        ]}
        self.contents = {'first': b'synthetic state', 'second': b'synthetic archive'}
        self.header = {'schema_version': 1, 'snapshot_id': '20260911T123456Z-0123456789abcdef',
                       'created_at': '2026-09-11T12:34:56+00:00',
                       'inventory_sha256': bundle.vault._manifest_digest(self.manifest),
                       'vault_sha256': 'a' * 64, 'recipient': 'age1' + 'q' * 58,
                       'source_revision': 'b' * 40, 'entries': self.records(self.contents)}
        self.receipt = {key: value for key, value in self.header.items() if key != 'entries'}
        self.receipt.update(ciphertext_sha256='', ciphertext_bytes=0, entry_ids=sorted(self.contents), deletion_safe=False)
        self.validator = mock.Mock()
        self.validator.verify_keypairs.return_value = 0
        self.validator.validate_entry.return_value = {'validation': 'synthetic'}

    @staticmethod
    def entry(identifier, category):
        return {'id': identifier, 'category': category, 'path': 'local/' + identifier,
                'restore_path': 'local/' + identifier, 'mode': '0600', 'required': True,
                'path_policy': 'exact-bytes'}

    @staticmethod
    def records(contents):
        return [{'id': key, 'bytes': len(value), 'sha256': bundle.digest(value)} for key, value in contents.items()]

    def private(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(content)
        path.chmod(0o600)

    def make_package(self, *, header=None, contents=None):
        self.package.unlink(missing_ok=True)
        bundle.write_package(self.package, header or self.header, self.contents if contents is None else contents)
        return self.package

    def save_ciphertext(self, ciphertext=b'age-encryption.org/v1\nsynthetic encrypted bytes'):
        self.private(self.saved / 'recovery.tar.age', ciphertext)
        self.receipt.update(ciphertext_sha256=bundle.digest(ciphertext), ciphertext_bytes=len(ciphertext))
        self.private(self.saved / 'receipt.json', bundle.encode(self.receipt))
        trusted = self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])
        self.private(trusted, bundle.encode(self.receipt))
        trusted.chmod(0o644)

    def test_private_clone_modes_work_for_public_metadata_only(self):
        recipient = self.root / 'usenet-infra/recovery/age-recipient.txt'
        encrypted_vault = self.root / 'usenet-infra/vault/secrets.sops.json'
        self.private(recipient, self.header['recipient'].encode() + b'\n')
        self.private(encrypted_vault, b'synthetic ciphertext')
        checker = mock.Mock(load_manifest=mock.Mock(return_value=self.manifest))
        with mock.patch.object(bundle, 'module', return_value=checker):
            self.assertEqual(bundle.policy(self.root)[1], self.header['recipient'])
        self.save_ciphertext()
        trusted = self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])
        trusted.chmod(0o600)
        bundle.verify_snapshot_receipt(self.root, self.receipt)
        trusted.chmod(0o666)
        with self.assertRaises(bundle.RecoveryError):
            bundle.verify_snapshot_receipt(self.root, self.receipt)
        self.private(self.root / 'secret', b'synthetic private input')
        (self.root / 'secret').chmod(0o644)
        fd = bundle.vault._root_fd(self.root)
        try:
            with self.assertRaises(bundle.RecoveryError):
                bundle.checked_read(fd, 'secret', '0600')
        finally:
            os.close(fd)

    @contextmanager
    def verification(self, *, crypto=None):
        original_module = bundle.module

        def decrypt(age, args, *, identity=None):
            Path(args[args.index('--output') + 1]).write_bytes(self.package.read_bytes())

        with mock.patch.object(bundle, 'policy', return_value=(self.manifest, self.header['recipient'], self.header['vault_sha256'])), \
                mock.patch.object(bundle, 'pinned_age', return_value=Path('/synthetic/age')), \
                mock.patch.object(bundle, 'crypto', side_effect=crypto or decrypt) as crypto_mock, \
                mock.patch.object(bundle, 'module', side_effect=lambda name: self.validator if name == 'recovery-contents' else original_module(name)):
            yield crypto_mock

    def test_package_round_trip_and_inventory_receipt_binding(self):
        self.make_package()
        self.assertEqual(bundle.read_package(self.package, self.manifest, self.receipt), self.contents)
        for field in ('inventory_sha256', 'vault_sha256', 'recipient', 'source_revision', 'snapshot_id'):
            receipt = dict(self.receipt, **{field: 'different'})
            with self.subTest(field=field), self.assertRaises(bundle.RecoveryError):
                bundle.read_package(self.package, self.manifest, receipt)

    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaises(bundle.RecoveryError):
            bundle.parse(b'{"schema_version":1,"schema_version":1}')

    def test_authenticated_schema_requires_integer_version(self):
        self.make_package(header=dict(self.header, schema_version=True))
        with self.assertRaises(bundle.RecoveryError):
            bundle.read_package(self.package, self.manifest, self.receipt)

    def test_missing_extra_and_wrong_checksum_members_fail(self):
        cases = [({'first': self.contents['first']}, self.header),
                 (dict(self.contents, third=b'unknown'), self.header),
                 (dict(self.contents, second=b'tampered archive'), self.header),
                 (dict(self.contents, second=b'X' * len(self.contents['second'])), self.header)]
        for contents, header in cases:
            with self.subTest(names=sorted(contents)):
                self.make_package(header=header, contents=contents)
                with self.assertRaises(bundle.RecoveryError):
                    bundle.read_package(self.package, self.manifest, self.receipt)

    def test_unsafe_tar_member_and_duplicate_members_fail(self):
        for kind in ('symlink', 'hardlink', 'traversal', 'duplicate'):
            self.make_package()
            with tarfile.open(self.package, 'a') as archive:
                entry = tarfile.TarInfo('../escape' if kind == 'traversal' else 'payload/first')
                if kind in ('symlink', 'hardlink'):
                    entry.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                    entry.linkname = '/outside'
                    archive.addfile(entry)
                else:
                    entry.size = 1
                    archive.addfile(entry, io.BytesIO(b'x'))
            with self.subTest(kind=kind), self.assertRaises(bundle.RecoveryError):
                bundle.read_package(self.package, self.manifest, self.receipt)

    def test_missing_truncated_and_tampered_ciphertext_fail(self):
        for kind in ('missing', 'truncated', 'tampered'):
            self.save_ciphertext()
            path = self.saved / 'recovery.tar.age'
            if kind == 'missing':
                path.unlink()
            elif kind == 'truncated':
                path.write_bytes(path.read_bytes()[:12])
            else:
                path.write_bytes(path.read_bytes()[:-1] + b'X')
            with self.subTest(kind=kind), self.assertRaises((bundle.RecoveryError, OSError)):
                bundle.receipt_and_ciphertext(self.saved)

    def test_receipt_refuses_noninteger_size_and_duplicate_entry_list(self):
        self.make_package()
        self.save_ciphertext()
        self.receipt['ciphertext_bytes'] = True
        self.private(self.saved / 'receipt.json', bundle.encode(self.receipt))
        with self.assertRaises(bundle.RecoveryError):
            bundle.receipt_and_ciphertext(self.saved)
        self.receipt['entry_ids'] = ['first', 'first', 'second']
        with self.assertRaises(bundle.RecoveryError):
            bundle.read_package(self.package, self.manifest, self.receipt)

    def test_all_authenticated_content_checks_finish_before_installation(self):
        self.make_package()
        self.save_ciphertext()
        self.validator.validate_entry.side_effect = [{'validation': 'ok'}, ValueError('synthetic archive invalid')]
        with self.verification(), mock.patch.object(bundle, 'restore_contents') as install, self.assertRaises(ValueError):
            bundle.verify(self.root, self.saved, identity='AGE-SECRET-KEY-1synthetic', restore=True)
        install.assert_not_called()
        self.assertFalse((self.root / 'local').exists())

    def test_missing_or_malformed_identity_never_invokes_decryption_or_restore(self):
        self.save_ciphertext()
        for identity in (None, '', 'wrong-format', 'AGE-SECRET-KEY-1bad\x00'):
            with self.subTest(valid=bool(identity)), self.verification() as crypto, self.assertRaises(bundle.RecoveryError):
                bundle.verify(self.root, self.saved, identity=identity, restore=True)
            crypto.assert_not_called()
        self.assertFalse((self.root / 'local').exists())

    def test_vault_pairing_failure_precedes_decryption(self):
        self.save_ciphertext()
        self.receipt['vault_sha256'] = 'c' * 64
        self.private(self.saved / 'receipt.json', bundle.encode(self.receipt))
        with self.verification() as crypto, self.assertRaises(bundle.RecoveryError):
            bundle.verify(self.root, self.saved, identity='AGE-SECRET-KEY-1synthetic', restore=True)
        crypto.assert_not_called()

    def test_missing_trusted_snapshot_receipt_prevents_decryption(self):
        self.save_ciphertext()
        (self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])).unlink()
        with self.verification() as crypto, self.assertRaisesRegex(bundle.RecoveryError, 'trusted Git snapshot receipt'):
            bundle.verify(self.root, self.saved, identity='AGE-SECRET-KEY-1synthetic', restore=True)
        crypto.assert_not_called()
        self.assertFalse((self.root / 'local').exists())

    def test_recomputed_untrusted_ciphertext_receipt_fails_before_decryption(self):
        self.save_ciphertext()
        ciphertext = b'age-encryption.org/v1\nattacker-generated replacement'
        self.private(self.saved / 'recovery.tar.age', ciphertext)
        changed = dict(self.receipt, ciphertext_sha256=bundle.digest(ciphertext), ciphertext_bytes=len(ciphertext))
        self.private(self.saved / 'receipt.json', bundle.encode(changed))
        with self.verification() as crypto, self.assertRaisesRegex(bundle.RecoveryError, 'does not exactly match'):
            bundle.verify(self.root, self.saved, identity='AGE-SECRET-KEY-1synthetic', restore=True)
        crypto.assert_not_called()

    def test_trusted_snapshot_requires_exact_fields_and_types(self):
        self.save_ciphertext()
        trusted = self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])
        for changed in (dict(self.receipt, schema_version=True), dict(self.receipt, extra='unexpected'),
                        {key: value for key, value in self.receipt.items() if key != 'deletion_safe'}):
            trusted.write_bytes(bundle.encode(changed))
            with self.assertRaises(bundle.RecoveryError):
                bundle.verify_snapshot_receipt(self.root, self.receipt)
        trusted.write_text(json.dumps(self.receipt, indent=2))
        bundle.verify_snapshot_receipt(self.root, self.receipt)

    def test_snapshot_identifiers_cannot_select_untrusted_paths(self):
        for identifier in ('../receipt', '/tmp/receipt', '20260911T123456Z-0123456789abcdef/../receipt',
                           '20260911T123456Z-0123456789abcdef\n', None, 1):
            with self.subTest(identifier=identifier), self.assertRaises(bundle.RecoveryError):
                bundle.snapshot_receipt_path(identifier)

    def test_trusted_receipt_symlink_hardlink_and_symlinked_parent_are_rejected(self):
        self.save_ciphertext()
        trusted = self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])
        outside = self.base / 'untrusted-receipt.json'
        self.private(outside, trusted.read_bytes())
        outside.chmod(0o644)
        for kind in ('symlink', 'hardlink'):
            trusted.unlink()
            if kind == 'symlink':
                trusted.symlink_to(outside)
            else:
                os.link(outside, trusted)
            with self.subTest(kind=kind), self.assertRaises(bundle.RecoveryError):
                bundle.verify_snapshot_receipt(self.root, self.receipt)
        trusted.unlink()
        trusted.parent.rmdir()
        trusted.parent.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(bundle.RecoveryError):
            bundle.verify_snapshot_receipt(self.root, self.receipt)

    def test_public_receipt_publication_sets_mode_and_never_replaces(self):
        bundle.publish_snapshot_receipt(self.root, self.receipt)
        path = self.root / bundle.snapshot_receipt_path(self.receipt['snapshot_id'])
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        original = path.read_bytes()
        with self.assertRaises(bundle.vault.VaultError):
            bundle.publish_snapshot_receipt(self.root, dict(self.receipt, ciphertext_sha256='c' * 64))
        self.assertEqual(path.read_bytes(), original)

    def test_interrupted_decryption_cleans_partial_plaintext(self):
        self.save_ciphertext()
        outputs = []

        def interrupted(age, args, *, identity=None):
            path = Path(args[args.index('--output') + 1])
            outputs.append(path)
            path.write_bytes(b'synthetic partially decrypted bytes')
            raise KeyboardInterrupt

        with self.verification(crypto=interrupted), self.assertRaises(KeyboardInterrupt):
            bundle.verify(self.root, self.saved, identity='AGE-SECRET-KEY-1synthetic', restore=True)
        self.assertTrue(outputs)
        self.assertTrue(all(not path.parent.exists() for path in outputs))
        self.assertFalse((self.root / 'local').exists())

    def test_restore_is_idempotent_and_resumes_an_interruption(self):
        real_install = bundle.vault._install
        attempts = 0

        def interrupted(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise KeyboardInterrupt
            return real_install(*args, **kwargs)

        with mock.patch.object(bundle.vault, '_install', side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            bundle.restore_contents(self.root, self.manifest, self.contents)
        first = self.root / 'local/first'
        self.assertEqual(first.read_bytes(), self.contents['first'])
        inode = first.stat().st_ino
        self.assertFalse((self.root / 'local/second').exists())
        self.assertEqual(bundle.restore_contents(self.root, self.manifest, self.contents), 1)
        self.assertEqual(bundle.restore_contents(self.root, self.manifest, self.contents), 0)
        self.assertEqual(first.stat().st_ino, inode)

    def test_later_conflict_prevents_all_file_installations(self):
        conflict = self.root / 'local/second'
        self.private(conflict, b'preserve this divergent archive')
        with self.assertRaises(bundle.RecoveryError):
            bundle.restore_contents(self.root, self.manifest, self.contents)
        self.assertFalse((self.root / 'local/first').exists())
        self.assertEqual(conflict.read_bytes(), b'preserve this divergent archive')

    def test_existing_symlink_hardlink_and_fifo_are_rejected(self):
        outside = self.base / 'outside'
        self.private(outside, self.contents['second'])
        (self.root / 'local').mkdir(mode=0o700)
        destination = self.root / 'local/second'
        for kind in ('symlink', 'hardlink', 'fifo'):
            if kind == 'symlink':
                destination.symlink_to(outside)
            elif kind == 'hardlink':
                os.link(outside, destination)
            else:
                os.mkfifo(destination)
            try:
                with self.subTest(kind=kind), self.assertRaises((bundle.RecoveryError, OSError)):
                    bundle.restore_contents(self.root, self.manifest, self.contents)
                self.assertFalse((self.root / 'local/first').exists())
            finally:
                destination.unlink()

    def test_symlinked_restore_parent_is_rejected(self):
        outside = self.base / 'outside'
        outside.mkdir(mode=0o700)
        (self.root / 'local').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(bundle.vault.VaultError):
            bundle.restore_contents(self.root, self.manifest, self.contents)
        self.assertEqual(list(outside.iterdir()), [])

    def terraform_fixture(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['files'] = [self.entry('cloud-tfstate', 'state'), self.entry('storage-tfstate', 'state')]
        for entry in manifest['files']:
            entry['path'] = entry['id'] + '/terraform.tfstate'
            self.private(self.root / entry['path'], b'synthetic terraform state')
        return manifest

    def test_terraform_lock_record_refuses_capture(self):
        manifest = self.terraform_fixture()
        self.private(self.root / 'cloud-tfstate/.terraform.tfstate.lock.info', b'synthetic lock')
        with self.assertRaisesRegex(bundle.RecoveryError, 'lock record'):
            bundle.collect(self.root, manifest, Path('/synthetic/age'))

    def test_other_process_terraform_write_lock_refuses_capture(self):
        manifest = self.terraform_fixture()
        code = 'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.lockf(f,fcntl.LOCK_EX); print("ready",flush=True); sys.stdin.read(1)'
        with subprocess.Popen([sys.executable, '-c', code, str(self.root / 'cloud-tfstate/terraform.tfstate')],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              env=bundle.child_env(), text=True) as process:
            try:
                self.assertEqual(process.stdout.readline(), 'ready\n')
                with self.assertRaisesRegex(bundle.RecoveryError, 'state is locked'):
                    bundle.collect(self.root, manifest, Path('/synthetic/age'))
            finally:
                process.communicate('x', timeout=5)

    def test_state_replacement_during_capture_is_detected(self):
        manifest = self.terraform_fixture()
        original_module = bundle.module

        def replace_during_validation(entry, content, root, age):
            if entry['id'] == 'storage-tfstate':
                replacement = self.root / 'replacement'
                self.private(replacement, b'concurrently replaced terraform state')
                os.replace(replacement, self.root / 'cloud-tfstate/terraform.tfstate')
            return {'validation': 'synthetic'}

        self.validator.validate_entry.side_effect = replace_during_validation
        with mock.patch.object(bundle, 'module', side_effect=lambda name: self.validator if name == 'recovery-contents' else original_module(name)), \
                self.assertRaisesRegex(bundle.RecoveryError, 'changed or was replaced'):
            bundle.collect(self.root, manifest, Path('/synthetic/age'))

    def test_both_terraform_locks_remain_held_through_content_validation(self):
        manifest = self.terraform_fixture()
        original_module = bundle.module
        code = ('import fcntl,sys\n'
                'f=open(sys.argv[1],"r+")\n'
                'try: fcntl.lockf(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
                'except BlockingIOError: sys.exit(0)\n'
                'sys.exit(1)\n')

        def check_locks(entry, content, root, age):
            for state in manifest['files']:
                process = subprocess.run([sys.executable, '-c', code, str(self.root / state['path'])],
                                         capture_output=True, env=bundle.child_env(), timeout=5)
                self.assertEqual(process.returncode, 0, 'Both Terraform states must remain read-locked.')
            return {'validation': 'synthetic'}

        self.validator.validate_entry.side_effect = check_locks
        with mock.patch.object(bundle, 'module', side_effect=lambda name: self.validator if name == 'recovery-contents' else original_module(name)):
            contents, evidence = bundle.collect(self.root, manifest, Path('/synthetic/age'))
        self.assertEqual(set(contents), {'cloud-tfstate', 'storage-tfstate'})
        self.assertEqual(len(evidence), 2)

    def test_crypto_subprocess_does_not_inherit_master_or_service_credentials(self):
        with mock.patch.dict(os.environ, {'SOPS_AGE_KEY': 'synthetic-master', 'HCLOUD_TOKEN': 'synthetic-token'}), \
                mock.patch.object(bundle.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            bundle.crypto(Path('/synthetic/age'), ['--encrypt'])
        self.assertEqual(run.call_args.kwargs['env'], {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'})
        self.assertIsNone(run.call_args.kwargs['input'])


class NativeAgeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.age = bundle.pinned_age(bundle.ROOT)
        except (bundle.RecoveryError, bundle.vault.VaultError, OSError):
            raise unittest.SkipTest('Reviewed native age tools are not cached.')
        cls.identities = []
        for _ in range(2):
            generated = subprocess.run([str(cls.age.with_name('age-keygen'))], capture_output=True,
                                       env=bundle.child_env(), check=True, timeout=10)
            identity = next(line for line in generated.stdout.decode().splitlines() if line.startswith('AGE-SECRET-KEY-1'))
            recipient = subprocess.run([str(cls.age.with_name('age-keygen')), '-y'], input=(identity + '\n').encode(),
                                       capture_output=True, env=bundle.child_env(), check=True, timeout=10).stdout.decode().strip()
            cls.identities.append((identity, recipient))

    def test_native_age_capture_restore_wrong_identity_and_authentication_failure(self):
        identity, recipient = self.identities[0]
        wrong_identity = self.identities[1][0]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, destination = base / 'source', base / 'destination'
            for root in (source, destination):
                root.mkdir(mode=0o700)
            entry = RecoveryBundleTests.entry('zwave-historical-nvm', 'state')
            manifest = {'schema_version': 1, 'scope': 'smarthome', 'files': [entry]}
            (source / 'local').mkdir(mode=0o700)
            original = b'synthetic historical NVM fixture; no device data'
            bundle.private_write(source / entry['path'], original)
            saved = base / 'package'
            validator = bundle.module('recovery-contents')
            original_module = bundle.module
            with mock.patch.object(bundle, 'policy', return_value=(manifest, recipient, 'a' * 64)), \
                    mock.patch.object(bundle, 'pinned_age', return_value=self.age), \
                    mock.patch.object(bundle, 'source_revision', return_value='b' * 40), \
                    mock.patch.object(bundle, 'module', side_effect=lambda name: validator if name == 'recovery-contents' else original_module(name)), \
                    mock.patch.object(validator, 'verify_keypairs', return_value=0):
                captured = bundle.capture(source, saved)
                self.assertFalse(captured['master_decryption_verified'])
                self.assertFalse(captured['deletion_safe'])
                relative_receipt = bundle.snapshot_receipt_path(captured['snapshot_id'])
                trusted = source / relative_receipt
                self.assertEqual(trusted.stat().st_mode & 0o777, 0o644)
                self.assertEqual(json.loads(trusted.read_bytes()), json.loads((saved / 'receipt.json').read_bytes()))
                # A clean clone receives this independently trusted file from Git.
                destination_receipt = destination / relative_receipt
                destination_receipt.parent.mkdir(parents=True, mode=0o700)
                destination_receipt.write_bytes(trusted.read_bytes())
                destination_receipt.chmod(0o644)
                original_ciphertext = (saved / 'recovery.tar.age').read_bytes()
                with self.assertRaises(FileExistsError):
                    bundle.capture(source, saved)
                self.assertEqual((saved / 'recovery.tar.age').read_bytes(), original_ciphertext)
                self.assertEqual(list(base.glob('.recovery-publish-*')), [])
                with self.assertRaises(bundle.RecoveryError):
                    bundle.verify(destination, saved, identity=wrong_identity, restore=True)
                self.assertFalse((destination / 'local').exists())
                result = bundle.verify(destination, saved, identity=identity, restore=True)
                self.assertEqual(result['new_files_restored'], 1)
                self.assertTrue(result['master_decryption_verified'])
                self.assertFalse(result['deletion_safe'])
                self.assertEqual((destination / entry['restore_path']).read_bytes(), original)
                self.assertEqual(bundle.verify(destination, saved, identity=identity, restore=True)['new_files_restored'], 0)
                encrypted = saved / 'recovery.tar.age'
                receipt_path = saved / 'receipt.json'
                trusted_receipt = json.loads(receipt_path.read_bytes())
                # A hostile backup server knows the public recipient and all
                # public header fields, so it can construct a decryptable forgery.
                forged_contents = {entry['id']: b'attacker-selected NVM fixture'}
                forged_header = {key: value for key, value in trusted_receipt.items()
                                 if key not in {'ciphertext_sha256', 'ciphertext_bytes', 'entry_ids', 'deletion_safe'}}
                forged_header['entries'] = RecoveryBundleTests.records(forged_contents)
                forged_plain = base / 'forged.tar'
                forged_encrypted = base / 'forged.age'
                bundle.write_package(forged_plain, forged_header, forged_contents)
                bundle.crypto(self.age, ['--encrypt', '--recipient', recipient, '--output', str(forged_encrypted), str(forged_plain)])
                # It authenticates cryptographically despite having no trusted
                # sender: demonstrate successful age decryption independently.
                decrypted_forgery = base / 'forged-decrypted.tar'
                bundle.crypto(self.age, ['--decrypt', '--identity', '-', '--output', str(decrypted_forgery), str(forged_encrypted)],
                              identity=(identity + '\n').encode())
                self.assertEqual(decrypted_forgery.read_bytes(), forged_plain.read_bytes())
                forged_bytes = forged_encrypted.read_bytes()
                encrypted.write_bytes(forged_bytes)
                forged_receipt = dict(trusted_receipt, ciphertext_sha256=bundle.digest(forged_bytes), ciphertext_bytes=len(forged_bytes))
                receipt_path.write_bytes(bundle.encode(forged_receipt))
                with mock.patch.object(bundle, 'crypto', wraps=bundle.crypto) as decrypt, \
                        self.assertRaisesRegex(bundle.RecoveryError, 'does not exactly match'):
                    bundle.verify(destination, saved, identity=identity, restore=True)
                decrypt.assert_not_called()
                self.assertEqual((destination / entry['restore_path']).read_bytes(), original)
                encrypted.write_bytes(original_ciphertext)
                receipt_path.write_bytes(bundle.encode(trusted_receipt))
                tampered = encrypted.read_bytes()[:-8]
                encrypted.write_bytes(tampered)
                receipt = json.loads(receipt_path.read_bytes())
                receipt.update(ciphertext_sha256=bundle.digest(tampered), ciphertext_bytes=len(tampered))
                receipt_path.write_bytes(bundle.encode(receipt))
                with self.assertRaises(bundle.RecoveryError):
                    bundle.verify(destination, saved, identity=identity, restore=True)
                with self.assertRaises(bundle.RecoveryError):
                    bundle.crypto(self.age, ['--decrypt', '--identity', '-', '--output', str(base / 'truncated.tar'), str(encrypted)],
                                  identity=(identity + '\n').encode())
                self.assertEqual((destination / entry['restore_path']).read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
