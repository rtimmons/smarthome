from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.parse


SPEC = importlib.util.spec_from_file_location('sab_smoke', Path(__file__).parents[1] / 'scripts/sab-smoke-test.py')
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
JOB = 'SABnzbd_nzo_fixture123'


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.misc = dict(smoke.MISC_SETTINGS)
        self.server = dict(smoke.SERVER_SETTINGS, host='news.eweka.nl', username='PRIVATE_USER', password='PRIVATE_PASSWORD')
        self.queue = {'noofslots_total': 0, 'paused': False, 'slots': []}
        self.history = {'ppslots': 0, 'slots': []}
        self.response = {'status': True, 'nzo_ids': [JOB]}
        self.receipt_path = None

    def call(self, mode, **fields):
        self.calls.append((mode, fields))
        if mode == 'version':
            return {'version': '5.1.3'}
        if mode == 'get_config':
            section = fields['section']
            if section == 'servers':
                return {'config': {'servers': [self.server]}}
            if section == 'misc':
                key = fields['keyword']
                return {'config': {'misc': {key: self.misc[key]}}}
            if section == 'categories':
                return {'config': {'categories': [dict(name='*', pp='3', script='None', dir='')]}}
            if section == 'rss':
                return {'config': {}}
        if mode == 'queue':
            return {'queue': self.queue}
        if mode == 'history':
            return {'history': self.history}
        if mode == 'addurl':
            assert self.receipt_path is not None
            receipt = smoke.read_receipt(self.receipt_path)
            assert receipt['state'] == 'intent' and receipt['job_id'] is None
            if isinstance(self.response, Exception):
                raise self.response
            return self.response
        raise AssertionError('unexpected API mode')


class SabSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.receipt = Path(self.temp.name) / 'private-state/sab-smoke-test.json'
        self.api = FakeAPI()
        self.api.receipt_path = self.receipt

    def tearDown(self):
        self.temp.cleanup()

    def test_submission_writes_private_intent_then_one_exact_fixture_request(self):
        self.assertEqual(smoke.start(self.api, self.receipt)['status'], 'submitted')
        additions = [fields for mode, fields in self.api.calls if mode == 'addurl']
        self.assertEqual(additions, [dict(name=smoke.FIXTURE_URL, priority=0, pp=3, cat='*', script='None', nzbname=smoke.FIXTURE_NAME)])
        receipt = smoke.read_receipt(self.receipt)
        self.assertEqual(receipt['job_id'], JOB)
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('PRIVATE', self.receipt.read_text())

    def test_repeat_start_never_reenqueues(self):
        smoke.start(self.api, self.receipt)
        self.api.calls.clear()
        self.assertEqual(smoke.start(self.api, self.receipt), {'status': 'already_submitted', 'reenqueued': False})
        self.assertEqual(self.api.calls, [])

    def test_network_ambiguity_is_persistent_and_never_auto_retried(self):
        self.api.response = OSError('PRIVATE_API_KEY network error')
        with self.assertRaises(OSError):
            smoke.start(self.api, self.receipt)
        self.assertEqual(smoke.read_receipt(self.receipt)['state'], 'ambiguous')
        self.api.calls.clear()
        with self.assertRaisesRegex(smoke.SmokeError, 'prior_submission_uncertain'):
            smoke.start(self.api, self.receipt)
        self.assertEqual(self.api.calls, [])

    def test_malformed_submission_response_stays_ambiguous(self):
        self.api.response = {'status': True, 'nzo_ids': [JOB, 'SECOND_JOB'], 'error': 'PRIVATE_RESPONSE'}
        with self.assertRaisesRegex(smoke.SmokeError, 'submission_response_ambiguous'):
            smoke.start(self.api, self.receipt)
        self.assertEqual(smoke.read_receipt(self.receipt)['state'], 'ambiguous')

    def test_rejected_submission_is_not_retried_automatically(self):
        self.api.response = {'status': False, 'error': 'PRIVATE_RESPONSE'}
        with self.assertRaises(smoke.SmokeError):
            smoke.start(self.api, self.receipt)
        self.assertEqual(smoke.read_receipt(self.receipt)['state'], 'rejected')
        with self.assertRaises(smoke.SmokeError):
            smoke.start(self.api, self.receipt)
        self.assertEqual(sum(mode == 'addurl' for mode, _ in self.api.calls), 1)

    def test_busy_queue_or_weak_tls_or_changed_path_prevents_intent_and_submission(self):
        for change in ('queue', 'tls', 'path'):
            api = FakeAPI()
            if change == 'queue':
                api.queue['noofslots_total'] = 1
            elif change == 'tls':
                api.server['ssl_verify'] = 1
            else:
                api.misc['complete_dir'] = '/PRIVATE/UNAPPROVED'
            with self.assertRaises(smoke.SmokeError):
                smoke.start(api, self.receipt)
            self.assertFalse(self.receipt.exists())
            self.assertFalse(any(mode == 'addurl' for mode, _ in api.calls))

    def test_status_polls_exact_job_only_and_discards_unrelated_data(self):
        smoke.start(self.api, self.receipt)
        self.api.calls.clear()
        self.api.queue['slots'] = [dict(nzo_id='UNRELATED', status='PRIVATE_TITLE'),
                                   dict(nzo_id=JOB, status='Downloading', mb='100', mbleft='50', percentage='50', password='PRIVATE_PASSWORD')]
        report = smoke.status(self.api, self.receipt)
        self.assertEqual(report, {'status': 'downloading', 'size_mb': 100, 'remaining_mb': 50, 'percent': 50})
        self.assertEqual([mode for mode, _ in self.api.calls], ['queue', 'history'])
        self.assertTrue(all(fields['nzo_ids'] == JOB for _, fields in self.api.calls))
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_completed_result_reports_allowlisted_indicators_and_known_directory(self):
        smoke.start(self.api, self.receipt)
        self.api.history['slots'] = [dict(nzo_id=JOB, status='Completed', pp='D', bytes=100, downloaded=101,
            download_time=2, postproc_time=3, storage='/data/complete/' + smoke.FIXTURE_NAME,
            password='PRIVATE_PASSWORD', fail_message='',
            stage_log=[dict(name='Repair', actions=['PRIVATE_SET Quick Check OK']),
                       dict(name='Unpack', actions=['Unpacked 1 files/folders in 1 second'])])]
        report = smoke.status(self.api, self.receipt)
        self.assertTrue(report['processing_checks_passed'])
        self.assertTrue(report['verification_success_reported'])
        self.assertEqual(report['test_directory'], '/srv/usenet/downloads/complete/' + smoke.FIXTURE_NAME)
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.api.history['slots'][0]['storage'] = '/data/complete/PRIVATE_UNRELATED'
        self.api.history['slots'][0]['stage_log'][0]['actions'] = ['repair did not finish']
        report = smoke.status(self.api, self.receipt)
        self.assertNotIn('test_directory', report)
        self.assertFalse(report['processing_checks_passed'])
        self.assertTrue(report['verification_stage_observed'])

    def test_missing_job_never_searches_by_title_or_requeues(self):
        smoke.start(self.api, self.receipt)
        self.api.calls.clear()
        self.assertEqual(smoke.status(self.api, self.receipt), {'status': 'job_not_found', 'reenqueued': False})
        self.assertEqual([mode for mode, _ in self.api.calls], ['queue', 'history'])

    def test_invalid_receipt_and_concurrent_start_fail_closed(self):
        with smoke.receipt_lock(self.receipt):
            with self.assertRaisesRegex(smoke.SmokeError, 'already_running'):
                smoke.start(self.api, self.receipt)
        self.receipt.write_text('{"job_id":"PRIVATE_WRONG_RECEIPT"}')
        self.receipt.chmod(0o600)
        with self.assertRaises(smoke.SmokeError):
            smoke.start(self.api, self.receipt)
        self.assertEqual(self.api.calls, [])

    def test_http_uses_body_and_sanitizes_exceptions(self):
        api = smoke.SabAPI('PRIVATE_KEY')
        with mock.patch.object(api.opener, 'open', side_effect=OSError('PRIVATE_KEY http://secret.invalid')) as request:
            with self.assertRaisesRegex(smoke.SmokeError, '^api_request_failed$'):
                api.call('queue', nzo_ids=JOB)
        req = request.call_args.args[0]
        self.assertEqual(req.full_url, smoke.API_URL)
        self.assertEqual(req.method, 'POST')
        self.assertEqual(urllib.parse.parse_qs(req.data.decode())['apikey'], ['PRIVATE_KEY'])

    def test_cli_never_echoes_unexpected_exception(self):
        with mock.patch.object(smoke, 'read_api_key', side_effect=ValueError('PRIVATE_KEY PRIVATE_USER https://secret.invalid')):
            with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(smoke.main(['status']), 1)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertNotIn('https:', output.getvalue())


if __name__ == '__main__':
    unittest.main()
