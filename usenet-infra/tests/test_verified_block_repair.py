import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('block_repair', Path(__file__).resolve().parents[1] / 'scripts/verified-block-repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class BlockRepairTests(unittest.TestCase):
    def fixture(self, root):
        original, verified, receipt = root / 'failed.bin', root / 'verified.bin', root / 'receipt'
        before = b'a' * (repair.BLOCK + 30)
        after = before[:10] + b'X' + before[11:]
        original.write_bytes(before)
        verified.write_bytes(after)
        return original, verified, receipt, before, after

    def test_repair_is_verified_and_original_is_independently_reconstructible(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, verified, receipt, before, after = self.fixture(Path(tmp))
            record = repair.prepare(original, verified, receipt, hashlib.sha256(after).hexdigest())
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(repair.apply(receipt)['status'], 'verified')
            self.assertEqual(original.read_bytes(), after)
            reconstructed = bytearray(original.read_bytes())
            for block in record['blocks']:
                reconstructed[block['offset']:block['offset'] + block['size']] = (receipt / f"{block['offset']}.before").read_bytes()
            self.assertEqual(bytes(reconstructed), before)
            self.assertEqual(repair.restore(receipt)['status'], 'original_bytes_restored')
            self.assertEqual(original.read_bytes(), before)

    def test_rollback_refuses_unrelated_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, verified, receipt, before, after = self.fixture(Path(tmp))
            repair.prepare(original, verified, receipt, hashlib.sha256(after).hexdigest())
            repair.apply(receipt)
            with original.open('r+b') as stream:
                stream.seek(repair.BLOCK + 5)
                stream.write(b'X')
            current = original.read_bytes()
            with self.assertRaises(repair.Refused):
                repair.restore(receipt)
            self.assertEqual(original.read_bytes(), current)

    def test_hash_mismatch_and_changed_block_budget_leave_source_unchanged(self):
        for wrong_hash, budget in ((True, repair.MAX_CHANGED), (False, 1)):
            with tempfile.TemporaryDirectory() as tmp:
                original, verified, receipt, before, after = self.fixture(Path(tmp))
                with self.assertRaises(repair.Refused):
                    repair.prepare(original, verified, receipt, '0' * 64 if wrong_hash else hashlib.sha256(after).hexdigest(), max_changed=budget)
                self.assertEqual(original.read_bytes(), before)

    def test_shared_files_and_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, verified, receipt, before, after = self.fixture(Path(tmp))
            alias = Path(tmp) / 'alias'
            alias.hardlink_to(original)
            with self.assertRaises(repair.Refused):
                repair.prepare(original, verified, receipt, hashlib.sha256(after).hexdigest())
            alias.unlink()
            alias.symlink_to(original)
            with self.assertRaises(repair.Refused):
                repair.prepare(alias, verified, receipt, hashlib.sha256(after).hexdigest())

    def test_source_or_saved_block_drift_refuses_apply(self):
        for drift in ('source', 'receipt'):
            with tempfile.TemporaryDirectory() as tmp:
                original, verified, receipt, before, after = self.fixture(Path(tmp))
                repair.prepare(original, verified, receipt, hashlib.sha256(after).hexdigest())
                if drift == 'source':
                    original.write_bytes(before + b'changed')
                else:
                    (receipt / '0.after').write_bytes(b'changed')
                current = original.read_bytes()
                with self.assertRaises(repair.Refused):
                    repair.apply(receipt)
                self.assertEqual(original.read_bytes(), current)
