import fcntl
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('cart_import_install', Path(__file__).parents[1] / 'scripts/cart-import-install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class CartInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'root'; self.stage = self.base / 'stage'
        self.stage.mkdir(); (self.root / 'libexec').mkdir(parents=True)
        self.lock = self.root / 'state/catalog/locks/cache.lock'
        self.lock.parent.mkdir(parents=True); self.lock.touch()
        for name in installer.FILES:
            (self.stage / name).write_text('VERSION = "new"\n')
            (self.root / 'libexec' / name).write_text('VERSION = "old"\n')
        self.quiet = mock.Mock()

    def install(self):
        return installer.install(self.stage, self.root, quiet=self.quiet)

    def assert_untouched(self):
        self.assertTrue(all((self.root / 'libexec' / n).read_text() == 'VERSION = "old"\n' for n in installer.FILES))

    def test_active_backup_lock_refuses_all_file_changes(self):
        with self.lock.open('r+') as active:
            fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(installer.InstallError, 'backup_or_import_active'):
                self.install()
        self.quiet.assert_not_called(); self.assert_untouched()

    def test_quiet_guard_runs_with_lock_held_before_file_replacements(self):
        def check(stage, root):
            self.assert_untouched()
            with self.lock.open('r+') as other:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.quiet.side_effect = check
        self.assertEqual(self.install()['changed'], len(installer.FILES))
        self.quiet.side_effect = None
        self.assertEqual(self.install()['changed'], 0)

    def test_active_sab_or_pending_processing_preserves_helpers(self):
        self.quiet.side_effect = RuntimeError('active SAB')
        with self.assertRaises(RuntimeError): self.install()
        self.assert_untouched()
        self.quiet.side_effect = None
        status = self.root / 'state/catalog/cart-import/status.json'
        status.parent.mkdir(); status.write_text(json.dumps({'status': 'processing'}))
        with self.assertRaisesRegex(installer.InstallError, 'requires_recovery'): self.install()
        self.assert_untouched()

    def test_bad_staged_last_file_cannot_partially_refresh_first_files(self):
        (self.stage / installer.FILES[-1]).write_text('not valid python!')
        with self.assertRaises(SyntaxError): self.install()
        self.assert_untouched(); self.quiet.assert_not_called()

    def test_target_and_lock_symlinks_are_refused(self):
        target = self.root / 'libexec' / installer.FILES[-1]
        target.unlink(); target.symlink_to(self.stage / installer.FILES[-1])
        with self.assertRaises(installer.InstallError): self.install()
        self.assertEqual((self.root / 'libexec' / installer.FILES[0]).read_text(), 'VERSION = "old"\n')
        self.lock.unlink(); self.lock.symlink_to(self.stage / installer.FILES[0])
        with self.assertRaises(installer.InstallError): self.install()


if __name__ == '__main__':
    unittest.main()
