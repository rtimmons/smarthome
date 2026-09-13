"""Transfer log integration; optional real rclone test uses generated local bytes only."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import catalogctl


class TransferStreamTests(unittest.TestCase):
    def test_real_child_mixed_output_delivers_only_structured_stats(self):
        samples = []
        program = '''import json,sys
print('ordinary diagnostic', flush=True)
print('{incomplete', flush=True)
print('[]', flush=True)
print(json.dumps({'stats': 'not an object'}), flush=True)
print(json.dumps({'stats': {'bytes': 12, 'totalBytes': 24, 'speed': 6}}), file=sys.stderr, flush=True)
'''
        with contextlib.redirect_stderr(io.StringIO()):
            catalogctl.Rclone(SimpleNamespace(rclone=sys.executable)).run('-c', program, progress=samples.append)
        self.assertEqual(samples, [dict(bytes=12, totalBytes=24, speed=6)])

    def test_child_failure_does_not_become_success_after_progress(self):
        samples = []
        program = "import json; print(json.dumps({'stats': {'bytes': 12, 'totalBytes': 24, 'speed': 6}}),flush=True); raise SystemExit(17)"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(catalogctl.CatalogError, 'exit 17'):
            catalogctl.Rclone(SimpleNamespace(rclone=sys.executable)).run('-c', program, progress=samples.append)
        self.assertEqual(len(samples), 1)

    def test_streamed_stats_persist_across_verification_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(state_root=Path(directory), rclone=sys.executable)
            with (Path(directory) / 'lock').open('w+') as lock, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(catalogctl.CatalogError):
                    with catalogctl.cache_operation(settings, 'pull', 'sample-id', lock) as update:
                        catalogctl.Rclone(settings).run('-c', "print('{\"stats\":{\"bytes\":12,\"totalBytes\":24,\"speed\":6}}')",
                                                       progress=lambda stats: update(None, stats))
                        update('verifying SHA-256')
                        raise catalogctl.CatalogError('fixture checksum mismatch')
            payload = json.loads((Path(directory) / 'operations/sample-id.json').read_text())
            self.assertEqual(payload['status'], 'failed')
            self.assertEqual(payload['phase'], 'verifying SHA-256')
            self.assertEqual(payload['progress']['bytes'], 12)
            self.assertEqual(len(payload['speed_history']), 1)

    @unittest.skipUnless(os.environ.get('CATALOG_TEST_RCLONE'), 'Set CATALOG_TEST_RCLONE to the pinned rclone binary for the local-byte fixture')
    def test_real_rclone_local_copy_records_history_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'fixture.bin').write_bytes(b'x' * 1024**2)
            settings = SimpleNamespace(state_root=root / 'state', rclone=os.environ['CATALOG_TEST_RCLONE'])
            with (root / 'lock').open('w+') as lock, contextlib.redirect_stderr(io.StringIO()):
                with catalogctl.cache_operation(settings, 'pull', 'fixture-item', lock) as update:
                    update('downloading')
                    catalogctl.Rclone(settings).run('copy', str(source), str(root / 'destination'), '--config', os.devnull,
                                                   '--bwlimit', '256k', '--stats', '1s', '--stats-log-level', 'NOTICE', '--use-json-log',
                                                   progress=lambda stats: update(None, stats))
                    update('verifying SHA-256')
                    self.assertEqual(catalogctl.sha256_file(source / 'fixture.bin'), catalogctl.sha256_file(root / 'destination/fixture.bin'))
            record = json.loads((settings.state_root / 'operations/fixture-item.json').read_text())
            self.assertEqual(record['status'], 'succeeded')
            self.assertEqual(record['progress']['bytes'], 1024**2)
            self.assertGreaterEqual(len(record['speed_history']), 2)
            self.assertEqual((source / 'fixture.bin').stat().st_size, 1024**2)
