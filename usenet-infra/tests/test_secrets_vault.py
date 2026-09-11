"""Synthetic-only tests for the SOPS vault boundary and restore safety."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('secrets_vault', Path(__file__).parents[1] / 'scripts/secrets-vault.py')
assert SPEC and SPEC.loader
vault = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vault)


class SecretsVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.old = self.base / 'old-checkout'
        self.new = self.base / 'new-checkout'
        for root in (self.old, self.new):
            (root / 'usenet-infra/secrets').mkdir(parents=True, mode=0o700)
            (root / 'usenet-infra/vault').mkdir(mode=0o700)
        (self.old / '.sops.yaml').write_text('creation_rules: []\n')
        (self.old / '.sops.yaml').chmod(0o644)
        self.manifest = {'schema_version': 1, 'scope': 'smarthome', 'files': [
            {'id': 'rebase', 'path': 'usenet-infra/secrets/rebase.env', 'restore_path': 'usenet-infra/secrets/rebase.env',
             'category': 'vault', 'required': True, 'mode': '0600', 'path_policy': 'rebase-checkout-paths'},
            {'id': 'exact', 'path': 'usenet-infra/secrets/exact.key', 'restore_path': 'usenet-infra/secrets/exact.key',
             'category': 'vault', 'required': True, 'mode': '0600', 'path_policy': 'exact-bytes'},
            {'id': 'public', 'path': 'usenet-infra/secrets/key.pub', 'restore_path': 'usenet-infra/secrets/key.pub',
             'category': 'vault', 'required': False, 'mode': '0644', 'path_policy': 'exact-bytes'},
        ]}
        source = self.old / 'usenet-infra/secrets'
        (source / 'rebase.env').write_bytes(b'LOCAL=' + os.fsencode(self.old) + b'/private\nUNCHANGED=' + os.fsencode(self.old) + b'-extra\n')
        (source / 'exact.key').write_bytes(b'synthetic exact bytes\x00\xff')
        (source / 'key.pub').write_bytes(b'synthetic public key\n')
        for path, mode in ((source / 'rebase.env', 0o600), (source / 'exact.key', 0o600), (source / 'key.pub', 0o644)):
            path.chmod(mode)
        self.vault_path = self.old / 'usenet-infra/vault/secrets.sops.json'
        self.bundle = None

    def tearDown(self):
        self.temp.cleanup()

    def checker(self):
        return mock.Mock(load_manifest=mock.Mock(return_value=self.manifest))

    def fake_sops(self, args, *, env):
        self.assertEqual(env['SOPS_AGE_KEY'], 'AGE-SECRET-KEY-1synthetic')
        self.assertNotIn('SOPS_CONFIG', env)
        output = Path(args[args.index('--output') + 1])
        if '--encrypt' in args:
            self.assertEqual(args[args.index('--filename-override') + 1], 'usenet-infra/vault/secrets.sops.json')
            self.bundle = Path(args[-1]).read_bytes()
            output.write_bytes(b'encrypted synthetic ciphertext')
        else:
            output.write_bytes(self.bundle)

    def encrypt(self):
        with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                mock.patch.object(vault, '_run_sops', side_effect=self.fake_sops):
            return vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path, sops=Path('/synthetic/sops'),
                                 environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic', 'SOPS_CONFIG': '/attacker/config'})

    def restore(self, **kwargs):
        vault_path = self.new / 'usenet-infra/vault/secrets.sops.json'
        vault_path.write_bytes(self.vault_path.read_bytes())
        vault_path.chmod(0o644)
        with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                mock.patch.object(vault, '_run_sops', side_effect=self.fake_sops):
            return vault.restore(self.new, self.new / 'manifest.json', vault_path, sops=Path('/synthetic/sops'),
                                 environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'}, **kwargs)

    def test_encrypted_bundle_is_inventory_bound_and_rebases_only_path_boundaries(self):
        self.assertEqual(self.encrypt(), 3)
        payload = json.loads(self.bundle)
        self.assertEqual(payload['schema_version'], 1)
        self.assertEqual(payload['inventory_sha256'], vault._manifest_digest(self.manifest))
        self.assertEqual(self.restore(), 3)
        restored = self.new / 'usenet-infra/secrets/rebase.env'
        self.assertEqual(restored.read_bytes(), b'LOCAL=' + os.fsencode(self.new) + b'/private\nUNCHANGED=' + os.fsencode(self.old) + b'-extra\n')
        self.assertEqual((self.new / 'usenet-infra/secrets/exact.key').read_bytes(), b'synthetic exact bytes\x00\xff')
        self.assertEqual((self.new / 'usenet-infra/secrets/key.pub').stat().st_mode & 0o777, 0o644)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)

    def test_restore_never_overwrites_without_explicit_replace(self):
        self.encrypt()
        destination = self.new / 'usenet-infra/secrets/rebase.env'
        destination.write_bytes(b'keep this')
        destination.chmod(0o600)
        with self.assertRaisesRegex(vault.VaultError, 'already exists'):
            self.restore()
        self.assertEqual(destination.read_bytes(), b'keep this')
        self.restore(replace=True)
        self.assertIn(os.fsencode(self.new), destination.read_bytes())

    def test_decrypted_entries_must_exactly_match_required_inventory(self):
        self.encrypt()
        payload = json.loads(self.bundle)
        payload['entries'] = [entry for entry in payload['entries'] if entry['id'] != 'exact']
        self.bundle = json.dumps(payload).encode()
        with self.assertRaisesRegex(vault.VaultError, 'missing a required'):
            self.restore()

    def test_restore_refuses_a_symlinked_parent(self):
        self.encrypt()
        secret_dir = self.new / 'usenet-infra/secrets'
        outside = self.base / 'outside'
        outside.mkdir(mode=0o700)
        secret_dir.rmdir()
        secret_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(vault.VaultError, 'unsafe parent'):
            self.restore()

    def test_only_valid_environment_value_is_supported(self):
        environment = vault._identity_env({'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        self.assertEqual(environment, {'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        for environment in ({}, {'SOPS_AGE_KEY': 'not-an-age-identity'}):
            with self.subTest(environment=environment):
                with self.assertRaises(vault.VaultError):
                    vault._identity_env(environment)

    def test_rebase_does_not_rewrite_a_longer_path_prefix(self):
        content = b'/a/old/path /a/old/path/x /a/old/path-extra'
        self.assertEqual(vault._rebase(content, '/a/old/path', Path('/b/new'), 'rebase-checkout-paths'),
                         b'/b/new /b/new/x /a/old/path-extra')

    def test_all_destinations_are_preflighted_before_any_file_is_replaced(self):
        self.encrypt()
        first = self.new / 'usenet-infra/secrets/rebase.env'
        second = self.new / 'usenet-infra/secrets/exact.key'
        first.write_bytes(b'first must survive')
        second.write_bytes(b'second conflict')
        first.chmod(0o600)
        second.chmod(0o600)
        with self.assertRaisesRegex(vault.VaultError, 'already exists'):
            self.restore()
        self.assertEqual(first.read_bytes(), b'first must survive')


if __name__ == '__main__':
    unittest.main()
