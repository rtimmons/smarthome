from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('cart_worker', SCRIPTS / 'cart-import.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class FakeSab:
    def __init__(self):
        self.state = {'queue': [], 'history': [], 'rss_hashes': [], 'paused': False, 'postprocessing': 0}

    def snapshot(self):
        return copy.deepcopy(self.state)

    def job(self, identity):
        return next((j for j in self.snapshot()['history'] if j['nzo_id'] == identity), None)


class FakeArr:
    def __init__(self, library):
        self.library, self.submissions = library, 0
        self.owned = set()
        self.uncertain = False
        self.recovered = False
        self.failed = False

    def owned_download_ids(self):
        return self.owned

    def prepare(self, job, directory, files):
        return {'files': [{'source': str(p), 'destination': str(self.library / 'Movies' / directory.name / p.name)}
                          for p in files if p.suffix == '.mkv']}

    def submit(self, plan):
        self.submissions += 1
        for item in plan['files']:
            target = Path(item['destination'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item['source'], target)
        if self.uncertain:
            raise RuntimeError('private response not logged')
        return 42

    def command(self, plan, identity):
        if identity is None:
            self.recovered = True
        return {'id': 42, 'status': 'failed' if self.failed else 'completed'}

    def imported_files(self, plan):
        return plan['files']


class FakeRemote:
    def __init__(self):
        self.calls = 0
        self.mismatch = False

    def verify(self, path, size, digest):
        self.calls += 1
        if self.mismatch or path.stat().st_size != size or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise worker.Hold('canonical_sha256_mismatch')
        return {'path': str(path), 'signature': worker.regular(path), 'sha256': digest}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.scratch, self.library, self.state = [self.root / n for n in ('complete', 'library', 'state')]
        for path in (self.scratch, self.library, self.state):
            path.mkdir()
        self.settings = worker.catalog.Settings('storage:catalog', self.library, self.state,
            self.root / 'staging', self.scratch, 'rclone', 1, 1, 0)
        self.sab, self.arr, self.remote = FakeSab(), FakeArr(self.library), FakeRemote()
        self.now = 1000.0
        self.coordinator = self.make_worker()

    def tearDown(self):
        self.temp.cleanup()

    def make_worker(self):
        return worker.Coordinator(self.settings, self.sab, self.arr, self.remote, library=self.library,
                                  clock=lambda: self.now, sleep=lambda _: None, mounted=lambda: True)

    def job(self, identity='new-cart', **changes):
        directory = self.scratch / identity
        directory.mkdir(exist_ok=True)
        (directory / 'Movie.2026.mkv').write_bytes(b'complete movie payload')
        job = {'nzo_id': identity, 'name': 'Movie.2026', 'storage': '/data/complete/' + identity,
               'status': 'Completed', 'category': 'Default', 'completed': 1010, 'time_added': 1001, 'archive': False,
               'provenance': {'feed': 'NZBGeek Cart', 'unique': True, 'downloaded_at': 1001,
                              'url_sha256': worker.ref(identity)}}
        job.update(changes)
        self.sab.state['history'].append(job)
        return directory, job

    def record(self, identity='new-cart'):
        return worker.read_json(self.coordinator.jobs / (worker.ref(identity) + '.json'))

    def test_arm_preserves_and_excludes_existing_jobs_and_rss(self):
        directory, job = self.job('historical')
        self.sab.state['queue'] = [{'nzo_id': 'paused', 'status': 'Paused'}]
        self.sab.state['rss_hashes'] = [worker.ref('old-feed')]
        before = self.sab.snapshot()
        self.coordinator.arm()
        self.now += 10
        self.assertEqual(self.coordinator.arm()['status'], 'already_armed')
        self.assertEqual(self.coordinator.run()['completed'], 0)
        activation = self.coordinator.activation()
        self.assertEqual(activation['excluded_ids'], ['historical', 'paused'])
        self.assertEqual(activation['armed_at'], 1000)
        self.assertEqual(activation['excluded_rss_hashes'], [worker.ref('old-feed')])
        self.assertEqual(before, self.sab.snapshot())
        self.assertTrue(directory.exists())

    def test_active_queue_or_postprocessing_refuses_activation(self):
        for queue, processing in [([{'nzo_id': 'active', 'status': 'Downloading'}], 0), ([], 1)]:
            self.sab.state.update(queue=queue, postprocessing=processing)
            with self.assertRaises(worker.Hold):
                self.coordinator.arm()
            self.assertFalse((self.coordinator.base / 'armed.json').exists())

    def test_missing_activation_never_implicitly_enrolls(self):
        directory, _ = self.job()
        with self.assertRaises(FileNotFoundError):
            self.coordinator.run()
        self.assertEqual(self.arr.submissions, 0)
        self.assertTrue(directory.exists())

    def test_only_future_unique_completed_default_cart_is_eligible(self):
        self.coordinator.arm()
        _, job = self.job()
        activation = self.coordinator.activation()
        self.assertTrue(self.coordinator.eligible(job, activation))
        variants = [{'category': 'prowlarr'}, {'status': 'Failed'}, {'archive': True}, {'provenance': None}, {'time_added': 999}]
        for key, value in [('unique', False), ('feed', 'Other'), ('downloaded_at', 999), ('url_sha256', 'invalid')]:
            variants.append({'provenance': {**job['provenance'], key: value}})
        for variant in variants:
            self.assertFalse(self.coordinator.eligible({**job, **variant}, activation), variant)

    def test_unproven_new_completion_is_visible_without_import_or_retry_bypass(self):
        self.coordinator.arm()
        directory, _ = self.job(provenance=None)
        self.assertEqual(self.coordinator.run()['held'], 1)
        self.assertEqual(self.record()['hold'], 'cart_provenance_unproven')
        with self.assertRaisesRegex(worker.Hold, 'cart_provenance_unproven'):
            self.coordinator.retry(worker.ref('new-cart'))
        self.assertTrue(directory.exists())
        self.assertEqual(self.arr.submissions, 0)

    def test_full_completion_removes_only_verified_new_media(self):
        old, _ = self.job('old')
        self.coordinator.arm()
        directory, job = self.job()
        before = self.sab.snapshot()
        result = self.coordinator.run()
        self.assertEqual(result, {'status': 'idle', 'completed': 1, 'held': 0, 'errors': 0})
        self.assertFalse(directory.exists())
        self.assertTrue((old / 'Movie.2026.mkv').exists())
        self.assertEqual(before, self.sab.snapshot())
        self.assertEqual(self.remote.calls, 1)
        self.assertEqual(self.record()['phase'], 'cleaned')
        self.assertEqual(self.make_worker().run()['completed'], 1)
        self.assertEqual(self.arr.submissions, 1)

    def test_unimported_sidecar_retained_and_reported(self):
        self.coordinator.arm()
        directory, _ = self.job()
        sidecar = directory / 'notes.nfo'
        sidecar.write_text('preserve sidecar')
        result = self.coordinator.run()
        self.assertEqual(result['held'], 1)
        self.assertEqual(sidecar.read_text(), 'preserve sidecar')
        self.assertFalse((directory / 'Movie.2026.mkv').exists())
        self.assertEqual(self.record()['retained_files'], 1)

    def test_file_receipt_never_imports_or_removes_sibling_media(self):
        self.coordinator.arm()
        directory, job = self.job()
        job['storage'] += '/Movie.2026.mkv'
        sibling = directory / 'Other.2026.mkv'
        sibling.write_bytes(b'unrelated sibling')
        self.assertEqual(self.coordinator.run()['completed'], 1)
        self.assertEqual(sibling.read_bytes(), b'unrelated sibling')
        self.assertFalse((directory / 'Movie.2026.mkv').exists())
        self.assertEqual(len(self.record()['sources']), 1)
        self.assertEqual(len(self.record()['verified']), 1)

    def test_empty_subdirectories_do_not_hold_successful_cleanup(self):
        self.coordinator.arm()
        directory, _ = self.job()
        (directory / 'Subs').mkdir()
        self.assertEqual(self.coordinator.run()['status'], 'idle')
        self.assertEqual(self.record()['phase'], 'cleaned')

    def test_remote_mismatch_and_owned_download_preserve_source(self):
        for owned in (False, True):
            with self.subTest(owned=owned):
                identity = 'owned' if owned else 'mismatch'
                self.coordinator.arm()
                directory, _ = self.job(identity)
                self.arr.owned = {identity} if owned else set()
                self.remote.mismatch = not owned
                result = self.make_worker().run()
                self.assertGreater(result['held'], 0)
                self.assertTrue((directory / 'Movie.2026.mkv').exists())
                self.assertEqual(self.record(identity)['hold'], 'arr_owned_download' if owned else 'canonical_sha256_mismatch')

    def test_uncertain_post_is_recovered_without_duplicate_submission(self):
        self.coordinator.arm()
        directory, _ = self.job()
        self.arr.uncertain = True
        self.assertEqual(self.coordinator.run()['errors'], 1)
        self.assertEqual(self.record()['phase'], 'submitting')
        self.assertTrue(directory.exists())
        result = self.make_worker().run()
        self.assertEqual(result['completed'], 1)
        self.assertTrue(self.arr.recovered)
        self.assertEqual(self.arr.submissions, 1)
        self.assertFalse(directory.exists())

    def test_transient_poll_failure_retries_existing_command(self):
        self.coordinator.arm()
        directory, _ = self.job()
        original = self.arr.command
        self.arr.command = mock.Mock(side_effect=worker.CartImportHold('arr_request_failed'))
        self.assertEqual(self.coordinator.run()['errors'], 1)
        self.assertNotIn('hold', self.record())
        self.assertEqual(self.record()['phase'], 'importing')
        self.arr.command = original
        self.assertEqual(self.make_worker().run()['completed'], 1)
        self.assertEqual(self.arr.submissions, 1)
        self.assertFalse(directory.exists())

    def test_retained_file_warning_can_be_rechecked_after_disposition(self):
        self.coordinator.arm()
        directory, _ = self.job()
        sidecar = directory / 'notes.nfo'
        sidecar.write_text('preserve')
        self.coordinator.run()
        self.coordinator.retry(worker.ref('new-cart'))
        self.assertTrue(sidecar.exists())
        self.assertEqual(self.record()['phase'], 'cleaned_with_retained_files')
        sidecar.unlink()
        self.coordinator.retry(worker.ref('new-cart'))
        self.assertEqual(self.record()['phase'], 'cleaned')
        self.assertEqual(self.arr.submissions, 1)

    def test_interrupted_quarantine_move_resumes_with_reverification(self):
        self.coordinator.arm()
        directory, _ = self.job()
        original = worker.exclusive_rename
        def interrupted(source, destination):
            original(source, destination)
            raise OSError('interrupted after rename')
        with mock.patch.object(worker, 'exclusive_rename', interrupted):
            self.assertEqual(self.coordinator.run()['errors'], 1)
        self.assertEqual(self.record()['phase'], 'verified')
        self.assertEqual(len(list(self.scratch.rglob('*.pending'))), 1)
        result = self.make_worker().run()
        self.assertEqual(result['completed'], 1)
        self.assertEqual(self.remote.calls, 2)
        self.assertEqual(list(self.scratch.rglob('*.pending')), [])
        self.assertFalse(directory.exists())

    def test_recovery_remote_mismatch_preserves_quarantined_bytes(self):
        self.coordinator.arm()
        self.job()
        original = worker.exclusive_rename
        def interrupted(source, destination):
            original(source, destination)
            raise OSError('interrupted')
        with mock.patch.object(worker, 'exclusive_rename', interrupted):
            self.coordinator.run()
        self.remote.mismatch = True
        result = self.make_worker().run()
        self.assertEqual(result['held'], 1)
        self.assertEqual(len(list(self.scratch.rglob('*.pending'))), 1)
        self.assertEqual(self.arr.submissions, 1)

    def test_failed_command_is_held_without_deleting_or_resubmitting(self):
        self.coordinator.arm()
        directory, _ = self.job()
        self.arr.failed = True
        self.assertEqual(self.coordinator.run()['held'], 1)
        self.assertEqual(self.record()['hold'], 'native_import_failed')
        self.make_worker().run()
        self.assertTrue(directory.exists())
        self.assertEqual(self.arr.submissions, 1)

    def test_source_mutation_before_delete_is_held(self):
        self.coordinator.arm()
        directory, _ = self.job()
        original = self.remote.verify
        def mutate(*args):
            proof = original(*args)
            (directory / 'Movie.2026.mkv').write_bytes(b'changed')
            return proof
        self.remote.verify = mutate
        self.assertEqual(self.coordinator.run()['held'], 1)
        self.assertEqual((directory / 'Movie.2026.mkv').read_bytes(), b'changed')

    def test_symlink_and_traversal_never_reach_native_import(self):
        self.coordinator.arm()
        directory, _ = self.job()
        (directory / 'link.mkv').symlink_to(self.root / 'private')
        self.assertEqual(self.coordinator.run()['held'], 1)
        self.assertEqual(self.arr.submissions, 0)
        for storage in ('/data/complete', '/data/complete/../outside', '/data/complete/.cart-import-cleanup/x', '/outside/x'):
            with self.assertRaises(worker.Hold):
                worker.source_directory({'storage': storage}, self.scratch)

    def test_one_held_job_does_not_prevent_other_completion(self):
        self.coordinator.arm()
        bad, _ = self.job('bad')
        good, _ = self.job('good')
        self.arr.owned = {'bad'}
        result = self.coordinator.run()
        self.assertEqual((result['completed'], result['held']), (1, 1))
        self.assertTrue(bad.exists())
        self.assertFalse(good.exists())


class RemoteVerifierTests(unittest.TestCase):
    def test_independent_remote_hash_and_metadata_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / 'Movies' / 'Example' / 'movie.mkv'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'media')
            settings = mock.Mock(remote='storage:catalog')
            remote = mock.Mock()
            digest = hashlib.sha256(b'media').hexdigest()
            metadata = '{"IsDir":false,"Size":5}'
            remote.run.side_effect = [metadata, digest + '  movie.mkv\n', metadata]
            proof = worker.RemoteVerifier(settings, remote, root).verify(path, 5, digest)
            self.assertEqual(proof['sha256'], digest)
            self.assertEqual(remote.run.call_args_list[1].args[:3], ('hashsum', 'sha256', 'storage:catalog/library/Movies/Example/movie.mkv'))
            remote.run.side_effect = [metadata, '0' * 64 + '  movie.mkv\n']
            with self.assertRaisesRegex(worker.Hold, 'canonical_sha256_mismatch'):
                worker.RemoteVerifier(settings, remote, root).verify(path, 5, digest)


if __name__ == '__main__':
    unittest.main()
