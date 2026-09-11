from __future__ import annotations

import importlib.util
from pathlib import Path
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
        if command[1] == '-y':
            identity = Path(command[2])
            self.assertTrue(identity.exists())
            self.assertEqual(identity.stat().st_mode & 0o777, 0o600)
            return subprocess.CompletedProcess(command, 0, stdout=(RECIPIENT + '\n').encode())
        raise AssertionError(command)

    def initialize(self, environment=None):
        if environment is None:
            environment = {'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1syntheticfixtureonly'}
        return master.initialize_from_environment(
            confirmed_second_copy=True, keygen=self.keygen, runner=self.runner,
            environ=environment,
            recipient_path=self.recipient_path, sops_path=self.sops_path)

    def test_environment_identity_writes_only_public_configuration(self):
        self.assertEqual(self.initialize(), RECIPIENT)
        self.assertEqual(self.recipient_path.read_text(), RECIPIENT + '\n')
        config = self.sops_path.read_text()
        self.assertIn(RECIPIENT, config)
        self.assertIn('(^|.*/)usenet-infra/vault/', config)
        self.assertNotIn('AGE-SECRET', config)

    def test_environment_identity_rejects_missing_or_bad_input(self):
        for environment in (
                {},
                {'SOPS_AGE_KEY': 'not-age'}):
            with self.subTest(environment=environment):
                with self.assertRaises(master.RecoveryError):
                    self.initialize(environment)

    def test_requires_second_copy_confirmation(self):
        with self.assertRaisesRegex(master.RecoveryError, 'second independent'):
            master.initialize_from_environment(
                confirmed_second_copy=False, keygen=self.keygen, runner=self.runner,
                environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'},
                recipient_path=self.recipient_path, sops_path=self.sops_path)

    def test_refuses_divergent_public_configuration_without_replacing_it(self):
        self.recipient_path.write_text('age1differentrecipient000000000000000000000000000000\n')
        with self.assertRaisesRegex(master.RecoveryError, 'divergent'):
            self.initialize()
        self.assertEqual(self.recipient_path.read_text(), 'age1differentrecipient000000000000000000000000000000\n')


if __name__ == '__main__':
    unittest.main()
