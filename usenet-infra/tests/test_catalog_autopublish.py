import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('autopublish', SCRIPTS / 'catalog-autopublish.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class LocalRclone:
    def __init__(self, root):
        self.root = root
        self.fail = None
        self.calls = []

    def path(self, value):
        return self.root / value.split(':', 1)[1] if ':' in value else Path(value)

    def succeeds(self, *args):
        try:
            self.run(*args)
            return True
        except (OSError, worker.catalog.CatalogError):
            return False

    def read_json(self, path):
        if self.fail == 'read':
            raise worker.catalog.CatalogError('read failed')
        return json.loads(self.path(path).read_text())

    def run(self, *args, **kwargs):
        self.calls.append(args[0])
        if self.fail == args[0]:
            raise worker.catalog.CatalogError('injected transfer failure')
        if args[0] == 'lsf':
            return ''.join(p.name + '\n' for p in self.path(args[1]).glob('*.json'))
        source, target = self.path(args[1]), self.path(args[2])
        if args[0] == 'check':
            if worker.catalog.inventory_files(source) != worker.catalog.inventory_files(target):
                raise worker.catalog.CatalogError('different bytes')
        elif args[0] == 'copy':
            shutil.copytree(source, target, dirs_exist_ok=True)
        elif args[0] == 'moveto':
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        elif args[0] == 'copyto':
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and source.read_bytes() != target.read_bytes():
                raise worker.catalog.CatalogError('immutable manifest changed')
            shutil.copyfile(source, target)
        else:
            raise AssertionError(args)
        return ''


class AutoPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = worker.catalog.Settings(remote='remote:catalog', local_root=root/'local',
            state_root=root/'state', staging_root=root/'stage', promotion_root=root/'complete',
            rclone='unused', transfers=1, checkers=1, min_free_bytes=0)
        self.source = self.settings.promotion_root / 'movie'
        self.source.mkdir(parents=True)
        (self.source / 'movie.mkv').write_bytes(b'generated test video')
        self.receipts = root / 'receipts'
        self.receipts.mkdir()
        self.remote = LocalRclone(root / 'remote')
        self.known = {}
        self.job = {'nzo_id': 'job-123', 'name': 'Generated test movie',
                    'storage': '/data/complete/movie', 'completed': 1700000000,
                    'status': 'Completed'}
        self.environment = patch.dict(os.environ, CATALOG_ROLE='cloud')
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def publish(self):
        return worker.publish_job(self.job, self.settings, self.remote, self.known, self.receipts)

    def test_verified_publication_reclaims_source_and_retry_does_not_upload_again(self):
        self.assertEqual(self.publish(), 'published')
        self.assertFalse(self.source.exists())
        manifest = self.known[worker.job_id(self.job)]
        self.assertEqual(self.remote.path('remote:catalog/' + manifest['remote_path']).joinpath('movie.mkv').read_bytes(), b'generated test video')
        calls = list(self.remote.calls)
        self.assertEqual(self.publish(), 'already_published')
        self.assertEqual(calls, self.remote.calls)

    def test_upload_failure_preserves_source(self):
        for operation in ('copy', 'check', 'copyto', 'read'):
            with self.subTest(operation=operation):
                self.remote.fail = operation
                with self.assertRaises(worker.catalog.CatalogError):
                    self.publish()
                self.assertEqual((self.source/'movie.mkv').read_bytes(), b'generated test video')
                self.assertFalse(any(self.receipts.iterdir()))
                self.remote.fail = None

    def test_crash_after_remote_publication_resumes_same_object(self):
        self.remote.fail = 'read'
        with self.assertRaises(worker.catalog.CatalogError):
            self.publish()
        self.remote.fail = None
        self.known = {x['id']: x for x in worker.catalog.manifests(self.remote, self.settings)}
        copies = self.remote.calls.count('copy')
        self.assertEqual(self.publish(), 'published')
        self.assertEqual(self.remote.calls.count('copy'), copies)

    def interrupt_cleanup(self, path, *args, **kwargs):
        if '.catalog-published' in str(path):
            raise OSError('interrupted')
        return self.original_rmtree(path, *args, **kwargs)

    def test_interrupted_cleanup_uses_receipt_without_touching_replacement_source(self):
        self.original_rmtree = shutil.rmtree
        with patch.object(worker.shutil, 'rmtree', side_effect=self.interrupt_cleanup):
            with self.assertRaises(OSError):
                self.publish()
        self.source.mkdir()
        (self.source/'new.mkv').write_bytes(b'new download')
        self.assertEqual(self.publish(), 'published')
        self.assertEqual((self.source/'new.mkv').read_bytes(), b'new download')

    def test_changed_remote_manifest_blocks_cleanup_resume(self):
        self.original_rmtree = shutil.rmtree
        with patch.object(worker.shutil, 'rmtree', side_effect=self.interrupt_cleanup):
            with self.assertRaises(OSError):
                self.publish()
        self.known[worker.job_id(self.job)]['title'] = 'changed'
        with self.assertRaises(worker.catalog.CatalogError):
            self.publish()
        self.assertTrue((self.settings.promotion_root/'.catalog-published'/worker.job_id(self.job)).exists())

    def test_unsafe_sources_are_rejected(self):
        for value in ('/data/complete', '/data/incomplete/movie', '/data/complete/../movie', '/data/complete/.catalog-published/test'):
            with self.subTest(value=value), self.assertRaises(worker.catalog.CatalogError):
                worker.source_path(dict(self.job, storage=value), self.settings.promotion_root)
        (self.settings.promotion_root/'linked').symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(worker.catalog.CatalogError):
            worker.source_path(dict(self.job, storage='/data/complete/linked'), self.settings.promotion_root)

    def test_history_ignores_active_and_failed_jobs(self):
        api = Mock()
        api.call.return_value = {'history': {'slots': [self.job, dict(self.job, nzo_id='active', status='Extracting'), dict(self.job, nzo_id='failed', status='Failed')]}}
        self.assertEqual(worker.history(api), [self.job])

    def test_changed_local_bytes_are_never_deleted(self):
        self.remote.fail = 'read'
        with self.assertRaises(worker.catalog.CatalogError):
            self.publish()
        self.remote.fail = None
        self.known = {x['id']: x for x in worker.catalog.manifests(self.remote, self.settings)}
        (self.source/'movie.mkv').write_bytes(b'changed')
        with self.assertRaises(worker.catalog.CatalogError):
            self.publish()
        self.assertTrue(self.source.exists())
