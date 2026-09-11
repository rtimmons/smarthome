from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('prowlarr_indexer', Path(__file__).parents[1] / 'scripts/prowlarr-indexer.py')
assert SPEC and SPEC.loader
indexer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(indexer)


def preset(provider='nzbgeek'):
    name, base_url = indexer.INDEXERS[provider]
    values = {'baseUrl': base_url, 'apiPath': '/api', 'apiKey': '',
              'additionalParameters': None, 'vipExpiration': '',
              'baseSettings.queryLimit': None, 'baseSettings.grabLimit': None, 'baseSettings.limitsUnit': 0}
    return dict(name=name, implementation='Newznab', configContract='NewznabSettings',
                protocol='usenet', enable=True, redirect=True, priority=25, appProfileId=0,
                fields=[dict(name=key, value=value) for key, value in values.items()])


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.saved = []
        self.schema = [preset()]
        self.certificates = 'enabled'
        self.profiles = [dict(name='Standard', id=1)]
        self.test_result = {}

    def call(self, path, *, method='GET', payload=None):
        self.calls.append((path, method, copy.deepcopy(payload)))
        if path == 'system/status':
            return {'version': indexer.VERSION}
        if path == 'config/host':
            return {'certificateValidation': self.certificates, 'apiKey': 'PRIVATE_PROWLARR_KEY'}
        if path == 'indexer/schema':
            return copy.deepcopy(self.schema)
        if path == 'appprofile':
            return copy.deepcopy(self.profiles)
        if path == 'indexer' and method == 'GET':
            return copy.deepcopy(self.saved)
        if path == 'indexer' and method == 'POST':
            self.saved.append(dict(copy.deepcopy(payload), id=max([11, *[entry['id'] for entry in self.saved]]) + 1))
            return copy.deepcopy(self.saved[-1])
        if path == 'indexer/test' and method == 'POST':
            return self.test_result
        if path.startswith('indexer/') and path.rsplit('/', 1)[-1].isdigit() and method == 'PUT':
            self.saved = [copy.deepcopy(payload) if entry['id'] == payload['id'] else entry for entry in self.saved]
            return copy.deepcopy(payload)
        raise AssertionError('unexpected API request')


class ProwlarrIndexerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lock = Path(self.temp.name) / 'indexer.lock'
        self.api = FakeAPI()

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return indexer.prepare_disabled(self.api, self.lock)

    def test_prepare_uses_disabled_official_preset_without_guessed_limits(self):
        report = self.prepare()
        writes = [(path, payload) for path, method, payload in self.api.calls if method == 'POST']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], 'indexer')
        payload = writes[0][1]
        self.assertFalse(payload['enable'])
        self.assertEqual(payload['appProfileId'], 1)
        self.assertEqual(payload['priority'], 25)
        self.assertEqual(indexer.fields(payload)['apiKey'], '')
        self.assertIsNone(indexer.fields(payload)['baseSettings.queryLimit'])
        self.assertIsNone(indexer.fields(payload)['baseSettings.grabLimit'])
        self.assertTrue(report['changed'])
        self.assertFalse(report['api_key_saved'])

    def test_prepare_is_idempotent_and_preserves_existing_enabled_key_and_limits(self):
        self.prepare()
        saved = self.api.saved[0]
        saved['enable'] = True
        for field in saved['fields']:
            if field['name'] == 'apiKey':
                field['value'] = 'PRIVATE_NZBGEEK_KEY'
            if field['name'] == 'baseSettings.queryLimit':
                field['value'] = 50
        before = copy.deepcopy(saved)
        self.api.calls.clear()
        report = self.prepare()
        self.assertFalse(report['changed'])
        self.assertEqual(self.api.saved[0], before)
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_duplicate_names_or_renamed_same_endpoint_refuse_creation(self):
        self.api.saved = [dict(preset(), id=1), dict(preset(), name='Custom saved name', id=2)]
        with self.assertRaisesRegex(indexer.IndexerError, 'duplicate_nzbgeek'):
            self.prepare()
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_weak_certificate_validation_refuses_prepare_and_test(self):
        self.api.certificates = 'disabled'
        for action in (self.prepare, lambda: indexer.test_saved(self.api)):
            with self.assertRaisesRegex(indexer.IndexerError, 'strict_certificate_validation'):
                action()
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_nonofficial_endpoint_refuses_credentialed_test(self):
        saved = dict(preset(), id=2)
        for field in saved['fields']:
            if field['name'] == 'baseUrl':
                field['value'] = 'https://unreviewed.invalid'
            if field['name'] == 'apiKey':
                field['value'] = 'PRIVATE_KEY'
        self.api.saved = [saved]
        with self.assertRaisesRegex(indexer.IndexerError, 'requires_review'):
            indexer.test_saved(self.api)
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_test_posts_exact_existing_id_and_saved_mask_without_configuration_update(self):
        self.prepare()
        for field in self.api.saved[0]['fields']:
            if field['name'] == 'apiKey':
                field['value'] = '********'
        self.api.calls.clear()
        result = indexer.test_saved(self.api)
        writes = [(path, payload) for path, method, payload in self.api.calls if method != 'GET']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], 'indexer/test')
        self.assertEqual(writes[0][1]['id'], 12)
        self.assertTrue(writes[0][1]['enable'])
        self.assertEqual(indexer.fields(writes[0][1])['apiKey'], '********')
        self.assertTrue(result['connection_test_passed'])
        self.assertFalse(result['enabled'])

    def test_enable_tests_credentials_then_updates_existing_id_and_is_idempotent(self):
        self.prepare()
        for field in self.api.saved[0]['fields']:
            if field['name'] == 'apiKey':
                field['value'] = '********'
        self.api.calls.clear()
        report = indexer.enable_saved(self.api, self.lock)
        self.assertTrue(report['enabled'])
        self.assertTrue(report['changed'])
        writes = [(path, method) for path, method, _ in self.api.calls if method != 'GET']
        self.assertEqual(writes, [('indexer/test', 'POST'), ('indexer/12', 'PUT'), ('indexer/test', 'POST')])
        self.api.calls.clear()
        self.assertFalse(indexer.enable_saved(self.api, self.lock)['changed'])
        self.assertFalse(any(method == 'PUT' for _, method, _ in self.api.calls))

    def test_failed_validation_never_enables(self):
        self.prepare()
        for field in self.api.saved[0]['fields']:
            if field['name'] == 'apiKey':
                field['value'] = '********'
        self.api.test_result = {'message': 'PRIVATE error'}
        self.api.calls.clear()
        with self.assertRaises(indexer.IndexerError):
            indexer.enable_saved(self.api, self.lock)
        self.assertFalse(self.api.saved[0]['enable'])
        self.assertFalse(any(method == 'PUT' for _, method, _ in self.api.calls))

    def test_empty_key_never_calls_test(self):
        self.prepare()
        self.api.calls.clear()
        with self.assertRaisesRegex(indexer.IndexerError, 'saved_nzbgeek_api_key_required'):
            indexer.test_saved(self.api)
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_missing_profile_and_changed_default_limits_never_create(self):
        self.api.profiles = []
        with self.assertRaises(indexer.IndexerError):
            self.prepare()
        self.api.profiles = [dict(name='Standard', id=1)]
        for field in self.api.schema[0]['fields']:
            if field['name'] == 'baseSettings.queryLimit':
                field['value'] = 123
        with self.assertRaises(indexer.IndexerError):
            self.prepare()
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_api_key_header_and_raw_errors_never_reach_output(self):
        api = indexer.ProwlarrAPI('PRIVATE_PROWLARR_KEY')
        with mock.patch.object(api.opener, 'open', side_effect=OSError('PRIVATE_KEY https://private.invalid/?apikey=PRIVATE_KEY')) as request:
            with mock.patch.object(indexer, 'api_key', return_value='PRIVATE_PROWLARR_KEY'), mock.patch.object(indexer, 'ProwlarrAPI', return_value=api):
                with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                    self.assertEqual(indexer.main(['inspect']), 1)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertNotIn('https:', output.getvalue())
        self.assertEqual(request.call_args.args[0].full_url, indexer.API_ROOT + 'system/status')
        self.assertEqual(request.call_args.args[0].get_header('X-api-key'), 'PRIVATE_PROWLARR_KEY')

    def test_unexpected_test_response_never_becomes_success_or_leaks_message(self):
        self.prepare()
        for field in self.api.saved[0]['fields']:
            if field['name'] == 'apiKey':
                field['value'] = '********'
        self.api.test_result = {'message': 'PRIVATE_KEY unexpected failure'}
        with self.assertRaisesRegex(indexer.IndexerError, '^unexpected_indexer_test_response$'):
            indexer.test_saved(self.api)

    def test_finder_preparation_preserves_geek_and_uses_its_own_disabled_preset(self):
        self.prepare()
        geek_before = copy.deepcopy(self.api.saved[0])
        self.api.schema.append(preset('nzbfinder'))
        report = indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        self.assertEqual(self.api.saved[0], geek_before)
        finder = self.api.saved[1]
        self.assertEqual(finder['name'], 'NZBFinder')
        self.assertEqual(finder['priority'], 25)
        self.assertFalse(finder['enable'])
        values = indexer.fields(finder)
        self.assertEqual(values['baseUrl'], 'https://nzbfinder.ws')
        self.assertEqual(values['apiPath'], '/api')
        self.assertEqual(values['apiKey'], '')
        self.assertIsNone(values['baseSettings.queryLimit'])
        self.assertIsNone(values['baseSettings.grabLimit'])
        self.assertEqual(report['indexer'], 'NZBFinder')
        self.assertTrue(report['changed'])

    def test_finder_prepare_preserves_existing_key_enable_priority_and_limits(self):
        saved = dict(preset('nzbfinder'), id=4, enable=True, priority=10)
        for field in saved['fields']:
            if field['name'] == 'apiKey':
                field['value'] = 'PRIVATE_FINDER_KEY'
            if field['name'] == 'baseSettings.grabLimit':
                field['value'] = 1000
        self.api.saved = [saved]
        before = copy.deepcopy(saved)
        report = indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        self.assertFalse(report['changed'])
        self.assertEqual(self.api.saved, [before])
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_renamed_duplicate_finder_and_conflicting_endpoint_refuse_writes(self):
        self.api.saved = [dict(preset('nzbfinder'), id=3), dict(preset('nzbfinder'), id=4, name='Custom')]
        with self.assertRaisesRegex(indexer.IndexerError, 'duplicate_nzbfinder'):
            indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        wrong_endpoint = dict(preset(), id=5, name='NZBFinder')
        for field in wrong_endpoint['fields']:
            if field['name'] == 'apiKey':
                field['value'] = 'PRIVATE_GEEK_KEY'
        self.api.saved = [wrong_endpoint]
        with self.assertRaisesRegex(indexer.IndexerError, 'nzbfinder_endpoint_or_definition_requires_review'):
            indexer.test_saved(self.api, 'nzbfinder')
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))

    def test_finder_enable_and_test_select_only_its_id_without_changing_geek(self):
        self.prepare()
        geek_before = copy.deepcopy(self.api.saved[0])
        self.api.schema.append(preset('nzbfinder'))
        indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        for field in self.api.saved[1]['fields']:
            if field['name'] == 'apiKey':
                field['value'] = '********'
        self.api.calls.clear()
        report = indexer.enable_saved(self.api, self.lock, 'nzbfinder')
        self.assertTrue(report['enabled'])
        self.assertTrue(report['connection_test_passed'])
        self.assertEqual(report['id'], 13)
        self.assertEqual(self.api.saved[0], geek_before)
        writes = [(path, payload) for path, method, payload in self.api.calls if method != 'GET']
        self.assertEqual([path for path, _ in writes], ['indexer/test', 'indexer/13', 'indexer/test'])
        self.assertTrue(all(payload['id'] == 13 for _, payload in writes))
        self.assertTrue(all(indexer.fields(payload)['baseUrl'] == 'https://nzbfinder.ws' for _, payload in writes))
        self.assertNotIn('********', json.dumps(report))

    def test_cli_default_geek_and_explicit_finder_select_distinct_entries(self):
        self.api.saved = [dict(preset(), id=3), dict(preset('nzbfinder'), id=4)]
        for arguments, expected in [(['inspect'], 3), (['inspect', 'nzbfinder'], 4)]:
            with mock.patch.object(indexer, 'api_key', return_value='PRIVATE'), mock.patch.object(indexer, 'ProwlarrAPI', return_value=self.api):
                with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                    self.assertEqual(indexer.main(arguments), 0)
            self.assertEqual(json.loads(output.getvalue())['id'], expected)
            self.assertNotIn('PRIVATE', output.getvalue())

    def test_missing_or_changed_finder_preset_does_not_fall_back_to_geek(self):
        with self.assertRaisesRegex(indexer.IndexerError, 'nzbfinder_preset_missing'):
            indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        changed = preset('nzbfinder')
        for field in changed['fields']:
            if field['name'] == 'baseSettings.queryLimit':
                field['value'] = 10
        self.api.schema.append(changed)
        with self.assertRaisesRegex(indexer.IndexerError, 'nzbfinder_preset_changed'):
            indexer.prepare_disabled(self.api, self.lock, 'nzbfinder')
        self.assertFalse(any(method != 'GET' for _, method, _ in self.api.calls))


if __name__ == '__main__':
    unittest.main()
