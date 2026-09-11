from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('reader_access', Path(__file__).parents[1] / 'scripts/verify-reader-access.py')
assert SPEC and SPEC.loader
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


class ReaderAccessTests(unittest.TestCase):
    def run_fixture(self, *, read_error=False, overwrite_denied=True, cleanup=True):
        calls = []
        def call(side, source, args):
            calls.append((side, args))
            if side == 'reader':
                if read_error:
                    raise RuntimeError('PRIVATE-RAW-CONNECTION-ERROR')
                return dict(read_matched=True, overwrite_denied=overwrite_denied, delete_denied=True,
                            preserved_after_overwrite=True, preserved_after_delete=True)
            if args[0] == 'create':
                return {'created': True}
            return {'original_preserved': True, 'cleaned': cleanup}
        return reader.verify(call, 'a' * 32), calls

    def test_both_denials_preservation_and_cleanup_are_required(self):
        report, calls = self.run_fixture()
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(calls[-1], ('writer', ['finish', 'a' * 32, 'created']))
        for changes in ({'overwrite_denied': False}, {'cleanup': False}):
            report, _ = self.run_fixture(**changes)
            self.assertEqual(report['status'], 'failed')

    def test_cleanup_still_runs_after_reader_exception_without_echoing_error(self):
        report, calls = self.run_fixture(read_error=True)
        self.assertEqual(calls[-1][1][0], 'finish')
        self.assertTrue(report['sentinel_cleaned'])
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('PRIVATE-', str(report))


if __name__ == '__main__':
    unittest.main()
