import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('checkout_backup', Path(__file__).parents[1] / 'scripts/checkout-backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class CheckoutBackupTests(unittest.TestCase):
    def archive(self, name='local/settings', content=b'local state', digest=None):
        manifest = {'schema_version': 1, 'scope': 'checkout-local-files', 'source_revision': 'fixture',
                    'entries': [{'path': name, 'size': len(content), 'mode': 0o600,
                                 'sha256': digest or hashlib.sha256(content).hexdigest()}]}
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w:gz') as tar:
            for name, data in [('MANIFEST.json', json.dumps(manifest).encode()), ('payload/' + name, content)]:
                item = tarfile.TarInfo(name); item.size = len(data)
                tar.addfile(item, io.BytesIO(data))
        return output.getvalue()

    def verify(self, data, destination=None):
        process = Mock(stdout=io.BytesIO(data))
        process.wait.return_value = 0
        context = Mock()
        context.__enter__ = Mock(return_value=process)
        context.__exit__ = Mock(return_value=False)
        with patch.object(backup.subprocess, 'Popen', return_value=context):
            return backup.verify(Path('ciphertext'), Path('identity'), Path('age'), destination)

    def test_restore_is_isolated_and_preserves_private_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'restore'
            self.verify(self.archive(), destination)
            path = destination / 'local/settings'
            self.assertEqual(path.read_bytes(), b'local state')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(RuntimeError, 'new absolute destination'):
                self.verify(self.archive(), destination)

    def test_bad_checksum_or_traversal_never_publishes_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            for data in (self.archive(digest='incorrect'), self.archive(name='../escape')):
                destination = Path(temporary) / 'restore'
                with self.assertRaises(RuntimeError):
                    self.verify(data, destination)
                self.assertFalse(destination.exists())
            self.assertFalse((Path(temporary) / 'escape').exists())

    def test_exclusions_keep_unique_local_work(self):
        for name in ('mongodb/data/WiredTiger', 'new-hass-configs/secrets.yaml', 'build/notes.json',
                     '.agents/skills/example/SKILL.md', 'usenet-infra/ansible/inventory.yml'):
            self.assertFalse(backup.excluded(name), name)
        for name in ('build/tools/age', 'printer/.venv/lib', 'snapshot-service/node_modules/foo',
                     'build/checkout-backups/receipt', 'usenet-infra/terraform/cloud/cloud.tfplan'):
            self.assertTrue(backup.excluded(name), name)

    def test_install_rebases_only_reviewed_paths_and_refuses_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'restored', root / 'clone'
            (source / 'usenet-infra').mkdir(parents=True)
            (target / '.git').mkdir(parents=True)
            value = b'KEY=/old/checkout/usenet-infra/key\nREMOTE=/srv/usenet/key\nOTHER=/old/checkout-extra/key\n'
            (source / 'usenet-infra/.env').write_bytes(value)
            backup.install(source, target, '/old/checkout')
            changed = (target / 'usenet-infra/.env').read_text()
            self.assertIn(str(target) + '/usenet-infra/key', changed)
            self.assertIn('/srv/usenet/key', changed)
            self.assertIn('/old/checkout-extra/key', changed)
            (source / 'usenet-infra/.env').write_bytes(b'new')
            with self.assertRaisesRegex(RuntimeError, 'overwrite'):
                backup.install(source, target, '/old/checkout')
            self.assertEqual((target / 'usenet-infra/.env').read_text(), changed)
