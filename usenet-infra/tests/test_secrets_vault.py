"""Synthetic-only tests for the SOPS vault boundary and restore safety."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('secrets_vault', Path(__file__).parents[1] / 'scripts/secrets-vault.py')
assert SPEC and SPEC.loader
vault = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vault)
INIT_SPEC = importlib.util.spec_from_file_location('recovery_master_init', Path(__file__).parents[1] / 'scripts/recovery-master-init.py')
initializer = importlib.util.module_from_spec(INIT_SPEC)
INIT_SPEC.loader.exec_module(initializer)


def synthetic_ciphertext():
    return json.dumps({'sops': {'age': [{'recipient': 'age1' + 'q' * 58,
                                       'enc': '-----BEGIN AGE ENCRYPTED FILE-----\nsynthetic\n-----END AGE ENCRYPTED FILE-----\n'}],
                               'lastmodified': '2026-09-11T00:00:00Z', 'mac': 'ENC[synthetic]',
                               'unencrypted_suffix': '_unencrypted', 'version': '3.13.3'}}).encode()


class SecretsVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.old = self.base / 'old-checkout'
        self.new = self.base / 'new-checkout'
        for root in (self.old, self.new):
            (root / 'usenet-infra/secrets').mkdir(parents=True, mode=0o700)
            (root / 'usenet-infra/vault').mkdir(mode=0o700)
        (self.old / '.sops.yaml').write_text(initializer.sops_config('age1' + 'q' * 58))
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

    def fake_sops(self, args, *, env, phase):
        if phase == 'encrypt':
            self.assertNotIn('SOPS_AGE_KEY', env)
        else:
            self.assertEqual(env['SOPS_AGE_KEY'], 'AGE-SECRET-KEY-1synthetic')
        self.assertNotIn('SOPS_CONFIG', env)
        for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
            self.assertTrue(Path(env[key]).is_dir())
            self.assertEqual(Path(env[key]).stat().st_mode & 0o777, 0o700)
            self.assertEqual(list(Path(env[key]).iterdir()), [])
        self.assertEqual(set(env) - {'SOPS_AGE_KEY'}, {'PATH', 'LANG', 'LC_ALL', 'HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'})
        output = Path(args[args.index('--output') + 1])
        if '--encrypt' in args:
            self.assertEqual(phase, 'encrypt')
            self.assertEqual(args[args.index('--filename-override') + 1], 'usenet-infra/vault/secrets.sops.json')
            self.bundle = Path(args[-1]).read_bytes()
            output.write_bytes(synthetic_ciphertext())
        else:
            self.assertIn(phase, ('verify', 'restore'))
            output.write_bytes(self.bundle)

    def encrypt(self, **kwargs):
        with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                mock.patch.object(vault, '_run_sops', side_effect=self.fake_sops):
            return vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path, sops=Path('/synthetic/sops'),
                                 environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic', 'SOPS_CONFIG': '/attacker/config'}, **kwargs)

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
        prior = list((self.new / 'build/recovery-prior').glob('*/usenet-infra/secrets/rebase.env'))
        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0].read_bytes(), b'keep this')
        self.assertEqual(prior[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(prior[0].parent.stat().st_mode & 0o777, 0o700)

    def test_repeat_restore_preserves_identical_inodes_and_repairs_permissions(self):
        self.encrypt()
        self.restore()
        destination = self.new / 'usenet-infra/secrets/rebase.env'
        inode = destination.stat().st_ino
        destination.chmod(0o644)
        self.assertEqual(self.restore(), 3)
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.new / 'build/recovery-prior').exists())

    def test_failed_verification_never_publishes_or_replaces_ciphertext(self):
        for previous in (None, b'previous valid ciphertext'):
            with self.subTest(previous=previous):
                if previous is not None:
                    self.vault_path.write_bytes(previous)
                candidate_paths = []

                def fail_verification(args, *, env, phase):
                    if phase == 'verify':
                        candidate_paths.append(Path(args[-1]))
                        self.assertNotEqual(Path(args[-1]), self.vault_path)
                        raise vault.VaultError('Synthetic verification failure')
                    self.fake_sops(args, env=env, phase=phase)

                with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                        mock.patch.object(vault, '_run_sops', side_effect=fail_verification), \
                        self.assertRaisesRegex(vault.VaultError, 'verification failure'):
                    vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path, replace=True,
                                  sops=Path('/synthetic/sops'), environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
                self.assertTrue(all(not path.exists() for path in candidate_paths))
                self.assertEqual(self.vault_path.read_bytes() if self.vault_path.exists() else None, previous)

    def test_verified_ciphertext_replacement_preserves_previous_ciphertext(self):
        self.vault_path.write_bytes(b'previous valid ciphertext')
        self.encrypt(replace=True)
        self.assertEqual(self.vault_path.read_bytes(), synthetic_ciphertext())
        prior = list((self.old / 'build/recovery-prior').glob('*/usenet-infra/vault/secrets.sops.json'))
        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0].read_bytes(), b'previous valid ciphertext')

    def test_verification_rejects_valid_but_changed_bundle(self):
        def changed_bundle(args, *, env, phase):
            self.fake_sops(args, env=env, phase=phase)
            if phase == 'verify':
                output = Path(args[args.index('--output') + 1])
                payload = json.loads(output.read_bytes())
                payload['source_checkout'] = '/different/checkout'
                output.write_text(json.dumps(payload))

        with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                mock.patch.object(vault, '_run_sops', side_effect=changed_bundle), \
                self.assertRaisesRegex(vault.VaultError, 'does not exactly match'):
            vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path,
                          sops=Path('/synthetic/sops'), environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        self.assertFalse(self.vault_path.exists())

    def test_termination_cleans_private_plaintext_and_restores_signal_handler(self):
        original = signal.getsignal(signal.SIGTERM)
        with self.assertRaisesRegex(vault.VaultError, 'interrupted'):
            with vault._private_directory() as directory:
                plaintext = Path(directory) / 'plain'
                plaintext.write_bytes(b'synthetic secret')
                os.kill(os.getpid(), signal.SIGTERM)
        self.assertFalse(plaintext.exists())
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)

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

    def test_restore_refuses_unsafe_existing_leaves_even_with_replace(self):
        self.encrypt()
        destination = self.new / 'usenet-infra/secrets/rebase.env'
        outside = self.base / 'unrelated'
        outside.write_bytes(b'unrelated bytes')
        for kind in ('symlink', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                if kind == 'symlink':
                    destination.symlink_to(outside)
                elif kind == 'hardlink':
                    os.link(outside, destination)
                else:
                    os.mkfifo(destination)
                try:
                    with self.assertRaisesRegex(vault.VaultError, 'unsafe existing'):
                        self.restore(replace=True)
                    self.assertEqual(outside.read_bytes(), b'unrelated bytes')
                    self.assertFalse((self.new / 'usenet-infra/secrets/exact.key').exists())
                finally:
                    destination.unlink()

    def test_publication_does_not_clobber_a_concurrently_created_destination(self):
        root_fd = vault._root_fd(self.new)
        destination = self.new / 'usenet-infra/secrets/new.key'
        real_link = os.link

        def raced_link(*args, **kwargs):
            destination.write_bytes(b'concurrent bytes')
            return real_link(*args, **kwargs)

        try:
            with mock.patch.object(vault.os, 'link', side_effect=raced_link), \
                    self.assertRaisesRegex(vault.VaultError, 'appeared concurrently'):
                vault._install(root_fd, 'usenet-infra/secrets/new.key', b'restored bytes', 0o600, replace=False)
        finally:
            os.close(root_fd)
        self.assertEqual(destination.read_bytes(), b'concurrent bytes')
        self.assertEqual(list(destination.parent.glob('.*.restore-*')), [])

    def test_failed_replacement_keeps_destination_and_private_prior_copy(self):
        root_fd = vault._root_fd(self.new)
        destination = self.new / 'usenet-infra/secrets/previous.key'
        destination.write_bytes(b'previous bytes')
        destination.chmod(0o600)
        try:
            with mock.patch.object(vault.os, 'replace', side_effect=OSError('synthetic failure')), \
                    self.assertRaises(OSError):
                vault._install(root_fd, 'usenet-infra/secrets/previous.key', b'replacement bytes', 0o600, replace=True)
        finally:
            os.close(root_fd)
        self.assertEqual(destination.read_bytes(), b'previous bytes')
        prior = list((self.new / 'build/recovery-prior').glob('*/usenet-infra/secrets/previous.key'))
        self.assertEqual([path.read_bytes() for path in prior], [b'previous bytes'])
        self.assertEqual(list(destination.parent.glob('.*.restore-*')), [])

    def test_only_valid_environment_value_is_supported(self):
        environment = vault._identity_env({'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        self.assertEqual(environment, {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C', 'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        for environment in ({}, {'SOPS_AGE_KEY': 'not-an-age-identity'}):
            with self.subTest(environment=environment):
                with self.assertRaises(vault.VaultError):
                    vault._identity_env(environment)

    def test_identity_environment_ignores_ambient_agents_cloud_secrets_and_settings(self):
        environment = vault._identity_env({'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic',
                                          'HOME': '/ambient/home', 'XDG_CONFIG_HOME': '/ambient/config',
                                          'AWS_SECRET_ACCESS_KEY': 'synthetic-cloud-secret',
                                          'SSH_AUTH_SOCK': '/ambient/agent', 'SOPS_AGE_KEY_FILE': '/ambient/key',
                                          'SOPS_AGE_KEY_CMD': 'unsafe-command', 'PATH': '/ambient/plugins',
                                          'HTTPS_PROXY': 'https://ambient-proxy.invalid'})
        self.assertEqual(set(environment), {'SOPS_AGE_KEY', 'PATH', 'LANG', 'LC_ALL'})
        self.assertEqual(environment['PATH'], os.defpath)

    def test_cloud_and_plugin_identity_metadata_is_rejected_before_sops_runs(self):
        self.encrypt()
        original = json.loads(self.vault_path.read_bytes())
        for field in ('kms', 'gcp_kms', 'azure_kv', 'hc_vault', 'pgp', 'key_groups'):
            changed = json.loads(json.dumps(original))
            changed['sops'][field] = [{'synthetic': 'unapproved identity provider'}]
            self.vault_path.write_text(json.dumps(changed))
            with self.subTest(field=field), \
                    mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                    mock.patch.object(vault, '_run_sops') as run, self.assertRaisesRegex(vault.VaultError, 'no other identity providers'):
                vault.restore(self.old, self.old / 'manifest.json', self.vault_path,
                              sops=Path('/synthetic/sops'), environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
            run.assert_not_called()
        for recipient in ('age1plugin1synthetic', 'ssh-ed25519 synthetic', 'https://identity.invalid'):
            changed = json.loads(json.dumps(original))
            changed['sops']['age'][0]['recipient'] = recipient
            with self.assertRaises(vault.VaultError):
                vault._validate_ciphertext(json.dumps(changed).encode())

    def test_nonstandard_encryption_configuration_is_rejected_before_sops_runs(self):
        (self.old / '.sops.yaml').write_text(initializer.sops_config('age1' + 'q' * 58) + '    kms: synthetic-cloud-key\n')
        with mock.patch.object(vault, '_load_checker', return_value=self.checker()), \
                mock.patch.object(vault, '_run_sops') as run, self.assertRaisesRegex(vault.VaultError, 'native-age-only'):
            vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path,
                          sops=Path('/synthetic/sops'), environ={'SOPS_AGE_KEY': 'AGE-SECRET-KEY-1synthetic'})
        run.assert_not_called()

    def test_native_sops_wrong_injected_key_cannot_fall_back_to_ambient_matching_key(self):
        recovery_spec = importlib.util.spec_from_file_location('native_recovery_tools', Path(__file__).parents[1] / 'scripts/recovery-bundle.py')
        recovery = importlib.util.module_from_spec(recovery_spec)
        recovery_spec.loader.exec_module(recovery)
        try:
            sops = vault._default_sops(vault.REPO_ROOT)
            age = recovery.pinned_age(vault.REPO_ROOT)
        except (vault.VaultError, recovery.RecoveryError, recovery.vault.VaultError, OSError):
            self.skipTest('Reviewed native recovery tools are not cached.')
        identities = []
        environment = {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'}
        for _ in range(2):
            generated = subprocess.run([str(age.with_name('age-keygen'))], capture_output=True, env=environment,
                                       check=True, timeout=10).stdout.decode()
            identity = next(line for line in generated.splitlines() if line.startswith('AGE-SECRET-KEY-1'))
            recipient = subprocess.run([str(age.with_name('age-keygen')), '-y'], input=(identity + '\n').encode(),
                                       capture_output=True, env=environment, check=True, timeout=10).stdout.decode().strip()
            identities.append((identity, recipient))
        correct, recipient = identities[0]
        wrong = identities[1][0]
        (self.old / '.sops.yaml').write_text(initializer.sops_config(recipient))
        with mock.patch.object(vault, '_load_checker', return_value=self.checker()):
            self.assertEqual(vault.encrypt(self.old, self.old / 'manifest.json', self.vault_path, sops=sops,
                                           environ=dict(environment, SOPS_AGE_KEY=correct)), 3)
            ambient = self.base / 'ambient-home'
            config = ambient / '.config'
            keys = config / 'sops/age/keys.txt'
            keys.parent.mkdir(parents=True, mode=0o700)
            keys.write_text(correct + '\n')
            keys.chmod(0o600)
            poisoned_environment = dict(environment, HOME=str(ambient), XDG_CONFIG_HOME=str(config), SOPS_AGE_KEY=wrong)
            # Establish the regression: ordinary SOPS can use the ambient
            # matching key even when the explicitly injected identity is wrong.
            result = subprocess.run([str(sops), '--decrypt', '--output', str(self.base / 'baseline.json'), str(self.vault_path)],
                                    env=poisoned_environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=10)
            self.assertEqual(result.returncode, 0, 'Native SOPS ambient-key fallback fixture must work.')
            target = self.new / 'usenet-infra/vault/secrets.sops.json'
            target.write_bytes(self.vault_path.read_bytes())
            with self.assertRaisesRegex(vault.VaultError, 'does not match'):
                vault.restore(self.new, self.new / 'manifest.json', target, sops=sops, environ=poisoned_environment)
            self.assertEqual(list((self.new / 'usenet-infra/secrets').iterdir()), [])
            self.assertEqual(vault.restore(self.new, self.new / 'manifest.json', target, sops=sops,
                                           environ=dict(poisoned_environment, SOPS_AGE_KEY=correct)), 3)

    def test_sops_rule_failure_has_a_safe_specific_diagnostic(self):
        failure = subprocess.CalledProcessError(
            1, ['sops'], stderr=b'error loading config: no matching creation rules found')
        with mock.patch.object(vault.subprocess, 'run', side_effect=failure), \
                self.assertRaisesRegex(vault.VaultError, 'does not cover'):
            vault._run_sops(['sops'], env={}, phase='encrypt')

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
