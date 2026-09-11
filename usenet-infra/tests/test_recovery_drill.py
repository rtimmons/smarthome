from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('recovery_drill', Path(__file__).parents[1] / 'scripts/recovery-drill.py')
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)
SNAPSHOT = '20260911T123456Z-0123456789abcdef'
REVISION = 'a' * 40
IDENTITY = 'AGE-SECRET-KEY-1SYNTHETIC-NEVER-REAL'


class RecoveryDrillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'source'
        self.root.mkdir(mode=0o700)
        self.destination = self.base / 'fresh'
        self.calls, self.events = [], []
        self.env = {'SOPS_AGE_KEY': IDENTITY, 'HOME': str(self.base),
                    'SSH_AUTH_SOCK': '/synthetic/git-agent', 'PRIVATE_SERVICE_TOKEN': 'NEVER-FORWARD',
                    'GIT_SSH_COMMAND': 'NEVER-RUN', 'SOPS_AGE_KEY_FILE': '/NEVER-READ'}
        self.dirty, self.remote_revision, self.inject_cold_file = False, REVISION, False
        self.manifest = {'files': [{'path': 'usenet-infra/.env'}, {'path': 'usenet-infra/state.tfstate'}]}
        self.checker = mock.Mock()
        self.checker.load_manifest.return_value = self.manifest
        self.checker.check.return_value = {'inventory_ok': True, 'ignored_secret': 'NEVER-REPORT'}
        self.vault = mock.Mock()
        self.vault.restore.side_effect = self.restore_vault
        self.store = mock.Mock()
        self.store.read_environment.side_effect = self.read_environment
        self.store.connection_command.return_value = ['synthetic-pinned-nas']
        self.store.fetch.side_effect = self.fetch
        self.bundle = mock.Mock()
        self.results = [self.result(3), self.result(0)]
        self.bundle.verify.side_effect = self.verify
        self.modules = {'secrets-check': self.checker, 'secrets-vault': self.vault,
                        'recovery-store': self.store, 'recovery-bundle': self.bundle}

    def result(self, installed):
        return {'snapshot_id': SNAPSHOT, 'entries': 3, 'keypairs_verified': 6,
                'new_files_restored': installed, 'master_decryption_verified': True,
                'private_unexpected_field': 'NEVER-REPORT'}

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.assertNotIn('SOPS_AGE_KEY', os.environ)
        self.assertNotIn(IDENTITY, str(command))
        for forbidden in ('SOPS_AGE_KEY', 'SOPS_AGE_KEY_FILE', 'GIT_SSH_COMMAND', 'PRIVATE_SERVICE_TOKEN'):
            self.assertNotIn(forbidden, kwargs['env'])
        self.assertLessEqual(kwargs['timeout'], 300)
        if 'clone' in command:
            self.events.append('clone')
            self.assertEqual(list(self.destination.iterdir()), [])
            infra = self.destination / 'usenet-infra'
            (infra / 'scripts').mkdir(parents=True)
            if self.inject_cold_file:
                (infra / '.env').write_text('SHOULD-NOT-EXIST')
        if command[0] == drill.sys.executable:
            self.events.append(Path(command[-1]).name)
            self.assertEqual(kwargs['cwd'], self.destination)
            self.assertEqual(command[1], '-I')
            self.assertNotIn('HOME', kwargs['env'])
            self.assertNotIn('SSH_AUTH_SOCK', kwargs['env'])
            (self.destination / 'build').mkdir(mode=0o700, exist_ok=True)
        stdout = b''
        if 'rev-parse' in command:
            stdout = ((self.remote_revision if kwargs['cwd'] == self.destination else REVISION) + '\n').encode()
        if 'status' in command and self.dirty:
            stdout = b'?? usenet-infra/scripts/uncommitted.py\x00'
        return subprocess.CompletedProcess(command, 0, stdout, b'')

    def loader(self, root, name):
        self.assertEqual(root, self.destination)
        self.assertNotIn('SOPS_AGE_KEY', os.environ)
        return self.modules[name]

    def restore_vault(self, root, manifest, vault, *, environ):
        self.events.append('vault')
        self.assertEqual(root, self.destination)
        self.assertEqual(environ, {'SOPS_AGE_KEY': IDENTITY})
        self.assertEqual(vault, self.destination / 'usenet-infra/vault/secrets.sops.json')
        (root / 'usenet-infra/.env').write_text('RESTORED-NAS-CONNECTIONS')
        return 8

    def read_environment(self, path):
        self.assertEqual(path, self.destination / 'usenet-infra/.env')
        self.assertEqual(path.read_text(), 'RESTORED-NAS-CONNECTIONS')
        return {'QNAP_SSH_TARGET': 'synthetic@nas'}

    def fetch(self, snapshot, destination, connection):
        self.events.append('fetch')
        self.assertEqual(snapshot, SNAPSHOT)
        self.assertEqual(destination, self.destination / 'build/recovery-download')
        self.assertEqual(connection, ['synthetic-pinned-nas'])
        destination.mkdir()

    def verify(self, root, bundle, *, identity, restore):
        self.events.append('verify')
        self.assertEqual(root, self.destination)
        self.assertEqual(bundle, self.destination / 'build/recovery-download')
        self.assertEqual(identity, IDENTITY)
        self.assertTrue(restore)
        return self.results.pop(0)

    def execute(self, **kwargs):
        with mock.patch.dict(os.environ, {'SOPS_AGE_KEY': IDENTITY}):
            return drill.drill(SNAPSHOT, self.destination, root=self.root, environ=self.env,
                               runner=self.runner, module_loader=self.loader, **kwargs)

    def test_clean_clone_bootstraps_restores_twice_and_reports_only_verified_counts(self):
        report_path, report = self.execute()
        self.assertEqual(self.events, ['clone', 'bootstrap-age.py', 'bootstrap-sops.py',
                                      'vault', 'fetch', 'verify', 'verify'])
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(report['vault_entries_restored'], 8)
        self.assertEqual(report['bundle_entries_verified'], 3)
        self.assertEqual(report['first_pass_new_files'], 3)
        self.assertEqual(report['second_pass_new_files'], 0)
        self.assertFalse(report['deletion_safe'])
        self.assertFalse(report['application_startup_repeated'])
        self.assertFalse(report['unifi_native_restore_supported'])
        self.assertTrue(report['inventory_ok'])
        self.assertNotIn('NEVER-', report_path.read_text())
        self.assertEqual(report_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o700)
        self.assertNotIn('SOPS_AGE_KEY', self.env)
        clone = next(command for command, kwargs in self.calls if 'clone' in command)
        self.assertIn('--no-local', clone)
        self.assertIn('--no-hardlinks', clone)
        self.assertEqual(clone[clone.index('--branch') + 1], 'usenet')
        statuses = [command for command, kwargs in self.calls if 'status' in command]
        self.assertIn('--untracked-files=all', statuses[0])
        self.assertIn('usenet-infra', statuses[0])

    def test_uncommitted_source_prevents_clone_and_master_never_reaches_git(self):
        self.dirty = True
        with self.assertRaisesRegex(drill.DrillError, 'source-commit-gate'):
            self.execute()
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.events)

    def test_stale_remote_revision_preserves_clone_but_never_restores(self):
        self.remote_revision = 'b' * 40
        with self.assertRaisesRegex(drill.DrillError, 'clone-revision-gate'):
            self.execute()
        self.assertEqual(self.events, ['clone'])
        report = json.loads((self.destination / 'build/recovery-drill.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['deletion_safe'])
        self.vault.restore.assert_not_called()

    def test_expected_revision_must_match_current_head(self):
        with self.assertRaisesRegex(drill.DrillError, 'source-commit-gate'):
            self.execute(expected_revision='b' * 40)
        self.assertFalse(self.destination.exists())

    def test_preexisting_ignored_recovery_material_fails_cold_checkout_gate(self):
        self.inject_cold_file = True
        with self.assertRaisesRegex(drill.DrillError, 'cold-checkout-gate'):
            self.execute()
        self.assertEqual(self.events, ['clone'])

    def test_non_idempotent_repeat_and_bad_metadata_cannot_report_success(self):
        self.results[1]['new_files_restored'] = 1
        with self.assertRaisesRegex(drill.DrillError, 'idempotent-restore-and-verify'):
            self.execute()
        report = json.loads((self.destination / 'build/recovery-drill.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('NEVER-', json.dumps(report))
        self.checker.check.assert_not_called()

    def test_bad_metadata_blocks_success_after_both_restores(self):
        self.checker.check.return_value = {'inventory_ok': False, 'secret': 'NEVER-REPORT'}
        with self.assertRaisesRegex(drill.DrillError, 'restored-metadata-check'):
            self.execute()
        self.assertEqual(self.events.count('verify'), 2)

    def test_raw_module_exception_is_never_reported(self):
        self.vault.restore.side_effect = RuntimeError('NEVER-REPORT ' + IDENTITY)
        with self.assertRaises(drill.DrillError) as error:
            self.execute()
        self.assertEqual(str(error.exception), 'vault-restore')
        text = (self.destination / 'build/recovery-drill.json').read_text()
        self.assertNotIn('NEVER-', text)
        self.assertNotIn(IDENTITY, text)

    def test_local_source_existing_destination_and_inside_source_are_refused(self):
        for source in ('/old/checkout', 'file:///old/checkout', 'https://token@github.com/org/repo.git'):
            with self.assertRaisesRegex(drill.DrillError, 'remote-git-source'):
                drill.validate_request(SNAPSHOT, source, self.destination, self.root)
        with self.assertRaisesRegex(drill.DrillError, 'destination-inside-source'):
            drill.validate_request(SNAPSHOT, drill.SOURCE, self.root / 'nested', self.root)
        with self.assertRaisesRegex(drill.DrillError, 'new-absolute-destination'):
            drill.validate_request(SNAPSHOT, drill.SOURCE, Path('relative'), self.root)
        self.destination.mkdir()
        marker = self.destination / 'existing'
        marker.write_text('preserve')
        with self.assertRaisesRegex(drill.DrillError, 'new-absolute-destination'):
            self.execute()
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertFalse(self.calls)

    def test_missing_master_stops_before_children(self):
        self.env.pop('SOPS_AGE_KEY')
        with self.assertRaisesRegex(drill.DrillError, 'master-input'):
            self.execute()
        self.assertFalse(self.calls)

    def test_cli_interruption_returns_without_a_plaintext_traceback(self):
        import io
        with mock.patch.object(drill, 'drill', side_effect=KeyboardInterrupt), \
                mock.patch('sys.stderr', new_callable=io.StringIO) as output:
            result = drill.main(['--snapshot', SNAPSHOT, '--destination', str(self.destination)])
        self.assertEqual(result, 130)
        self.assertNotIn('Traceback', output.getvalue())

    def test_bootstrap_failure_is_sanitized_and_stops_before_vault_restore(self):
        original = self.runner
        def failed_bootstrap(command, **kwargs):
            if command[0] == drill.sys.executable:
                return subprocess.CompletedProcess(command, 1, b'NEVER-REPORT', b'NEVER-REPORT')
            return original(command, **kwargs)
        self.runner = failed_bootstrap
        with self.assertRaisesRegex(drill.DrillError, 'pinned-public-bootstrap'):
            self.execute()
        self.vault.restore.assert_not_called()
        self.assertNotIn('NEVER-', (self.destination / 'build/recovery-drill.json').read_text())

    def test_module_loader_uses_actual_fresh_clone_source_and_refuses_links(self):
        scripts = self.destination / 'usenet-infra/scripts'
        scripts.mkdir(parents=True)
        source = scripts / 'synthetic.py'
        source.write_text('from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n')
        self.assertEqual(drill.load_module(self.destination, 'synthetic').ROOT, self.destination.resolve())
        source.unlink()
        outside = self.base / 'outside.py'
        outside.write_text('raise Exception("NEVER-IMPORT")\n')
        source.symlink_to(outside)
        with self.assertRaisesRegex(drill.DrillError, 'fresh-source-module'):
            drill.load_module(self.destination, 'synthetic')


if __name__ == '__main__':
    unittest.main()
