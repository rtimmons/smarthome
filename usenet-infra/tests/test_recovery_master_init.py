from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location('recovery_master_init',
                                               Path(__file__).parents[1] / 'scripts/recovery-master-init.py')
assert SPEC and SPEC.loader
master = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(master)


RECIPIENT = 'age1q3nz5zhqaue5p2c9w2jg8e6x79m0q3nz5zhqaue5p2c9w2jg8e6x79m0'


class RecoveryMasterInitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.external = self.base / 'operator-held'
        self.external.mkdir(mode=0o700)
        self.identity = self.external / 'recovery.agekey'
        self.recipient_path = self.base / 'public' / 'age-recipient.txt'
        self.recipient_path.parent.mkdir(mode=0o700)
        self.sops_path = self.base / 'public' / '.sops.yaml'
        self.keygen = self.base / 'age-keygen'
        self.keygen.write_bytes(b'fixture')
        self.keygen.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, command, **kwargs):
        if command[1] == '--version':
            return subprocess.CompletedProcess(command, 0, stdout=b'v1.3.2\n')
        if command[1] == '-o':
            path = Path(command[2])
            path.write_bytes(b'fixture private identity never printed')
            path.chmod(0o600)
            return subprocess.CompletedProcess(command, 0, stdout=b'')
        if command[1] == '-y':
            return subprocess.CompletedProcess(command, 0, stdout=(RECIPIENT + '\n').encode())
        raise AssertionError(command)

    def initialize(self, **kwargs):
        return master.initialize(self.identity, confirmed_second_copy=True, keygen=self.keygen,
                                 runner=self.runner, recipient_path=self.recipient_path,
                                 sops_path=self.sops_path, **kwargs)

    def test_creates_private_identity_and_public_narrow_rule(self):
        self.assertEqual(self.initialize(), RECIPIENT)
        self.assertEqual(self.identity.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.recipient_path.read_text(), RECIPIENT + '\n')
        config = self.sops_path.read_text()
        self.assertIn(RECIPIENT, config)
        self.assertIn('^usenet-infra/vault/', config)
        self.assertNotIn('fixture private', config)

    def test_requires_operator_second_copy_confirmation_before_keygen(self):
        with self.assertRaisesRegex(master.RecoveryError, 'second independent'):
            master.initialize(self.identity, confirmed_second_copy=False, keygen=self.keygen,
                              runner=self.runner, recipient_path=self.recipient_path, sops_path=self.sops_path)
        self.assertFalse(self.identity.exists())

    def test_refuses_existing_identity_without_calling_keygen(self):
        self.identity.write_bytes(b'existing')
        self.identity.chmod(0o600)
        with self.assertRaisesRegex(master.RecoveryError, 'existing'):
            self.initialize()

    def test_refuses_identity_in_checkout_or_nonprivate_parent(self):
        with self.assertRaisesRegex(master.RecoveryError, 'outside this checkout'):
            master.private_parent(master.REPO_ROOT / 'ignored-recovery.agekey')
        self.external.chmod(0o755)
        with self.assertRaisesRegex(master.RecoveryError, 'mode-0700'):
            self.initialize()

    def test_refuses_symlink_parent_or_identity(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.external, target_is_directory=True)
        with self.assertRaisesRegex(master.RecoveryError, 'symlinks'):
            master.private_parent(alias / 'recovery.agekey')
        self.identity.symlink_to(self.keygen)
        with self.assertRaisesRegex(master.RecoveryError, 'existing'):
            self.initialize()

    def test_refuses_nonprivate_created_file_and_invalid_public_recipient(self):
        def loose_runner(command, **kwargs):
            if command[1] == '--version':
                return subprocess.CompletedProcess(command, 0, stdout=b'v1.3.2\n')
            if command[1] == '-o':
                Path(command[2]).write_bytes(b'fixture')
                Path(command[2]).chmod(0o644)
                return subprocess.CompletedProcess(command, 0, stdout=b'')
            raise AssertionError(command)
        with self.assertRaisesRegex(master.RecoveryError, 'mode-0600'):
            master.initialize(self.identity, confirmed_second_copy=True, keygen=self.keygen,
                              runner=loose_runner, recipient_path=self.recipient_path, sops_path=self.sops_path)
        self.identity.unlink()
        def invalid_recipient(command, **kwargs):
            result = self.runner(command, **kwargs)
            if command[1] == '-y':
                return subprocess.CompletedProcess(command, 0, stdout=b'not-a-recipient\n')
            return result
        with self.assertRaisesRegex(master.RecoveryError, 'invalid public'):
            master.initialize(self.identity, confirmed_second_copy=True, keygen=self.keygen,
                              runner=invalid_recipient, recipient_path=self.recipient_path, sops_path=self.sops_path)

    def test_refuses_divergent_public_configuration_without_replacing_it(self):
        self.recipient_path.write_text('age1differentrecipient000000000000000000000000000000\n')
        with self.assertRaisesRegex(master.RecoveryError, 'divergent'):
            self.initialize()
        self.assertEqual(self.recipient_path.read_text(), 'age1differentrecipient000000000000000000000000000000\n')


if __name__ == '__main__':
    unittest.main()
