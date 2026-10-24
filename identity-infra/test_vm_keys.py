"""Key-loss and repeat-run guards for disposable controller checkouts."""
from pathlib import Path
import tempfile
import unittest

from vm_prepare import keypair, write_seed


class VMKeyPreservation(unittest.TestCase):
    def test_existing_seed_is_not_silently_replaced_beneath_stale_iso(self):
        with tempfile.TemporaryDirectory() as temporary:
            seed = Path(temporary)
            iso = seed/'cidata.iso'
            original = {'user-data': 'synthetic existing seed\n'}
            write_seed(seed, original, iso)
            iso.write_bytes(b'synthetic iso bytes')
            write_seed(seed, original, iso)
            with self.assertRaisesRegex(RuntimeError, 'Existing bootstrap ISO differs'):
                write_seed(seed, {'user-data': 'different seed\n'}, iso)
            self.assertEqual((seed/'user-data').read_text(), original['user-data'])
            self.assertEqual(iso.read_bytes(), b'synthetic iso bytes')

    def test_repeated_preparation_preserves_exact_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'guest_key'
            public = keypair(path, 'synthetic-test-identity')
            private = path.read_bytes()
            self.assertEqual(keypair(path, 'different-comment'), public)
            self.assertEqual(path.read_bytes(), private)
            path.unlink()
            with self.assertRaisesRegex(RuntimeError, 'restore'):
                keypair(path, 'must-not-replace-lost-key')
            self.assertFalse(path.exists())

    def test_mismatched_public_key_is_rejected_without_rotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary)/'first'
            second = Path(temporary)/'second'
            keypair(first, 'synthetic-first')
            second_public = keypair(second, 'synthetic-second')
            original = first.read_bytes()
            first.with_suffix('.pub').write_text(second_public+'\n')
            with self.assertRaisesRegex(RuntimeError, 'differ'):
                keypair(first, 'must-not-replace-mismatched-key')
            self.assertEqual(first.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
