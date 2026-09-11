from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.parse

SPEC = importlib.util.spec_from_file_location('sab_settings', Path(__file__).parents[1] / 'scripts/sab-settings.py')
assert SPEC and SPEC.loader
settings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(settings)


class FakeAPI:
    def __init__(self):
        self.misc = dict(settings.DESIRED_MISC)
        self.categories = [dict(name='*', pp='3', script='None', dir=''),
                           dict(name='books', pp='', script='Default', dir='')]
        self.feeds = []
        self.queued = 0
        self.processing = 0
        self.calls = []
        self.retain = True

    def call(self, mode, **params):
        self.calls.append((mode, params))
        if mode == 'version':
            return {'version': '5.1.3'}
        if mode == 'queue':
            return {'queue': {'noofslots_total': self.queued, 'slots': [{'filename': 'DO-NOT-PRINT', 'password': 'DO-NOT-PRINT'}]}}
        if mode == 'history':
            return {'history': {'ppslots': self.processing, 'slots': [{'name': 'DO-NOT-PRINT'}]}}
        if mode == 'get_config':
            if params['section'] == 'misc':
                return {'config': {'misc': {params['keyword']: self.misc[params['keyword']]}}}
            return {'config': {params['section']: self.categories if params['section'] == 'categories' else self.feeds}}
        if mode == 'set_config':
            if self.retain:
                if params['section'] == 'misc':
                    self.misc[params['keyword']] = params['value']
                else:
                    if not self.categories:
                        self.categories.append({'name': '*', 'dir': ''})
                    self.categories[0].update({key: value for key, value in params.items() if key in ('pp', 'script', 'priority', 'dir', 'order')})
            return {'config': {'ignored': 'DO-NOT-PRINT'}}
        raise AssertionError(mode)


class SabSettingsTests(unittest.TestCase):
    def test_already_correct_is_read_only_and_does_not_emit_jobs(self):
        api = FakeAPI()
        before = settings.inspect(api)
        self.assertTrue(before['safe_to_apply'])
        self.assertEqual(settings.apply(api, before), [])
        self.assertNotIn('set_config', [call[0] for call in api.calls])
        self.assertNotIn('DO-NOT-PRINT', json.dumps(before))

    def test_only_changed_allowlisted_values_are_sent(self):
        api = FakeAPI()
        api.misc['download_dir'] = '/config/Downloads/incomplete'
        api.misc['download_free'] = '1G'
        api.categories[0]['pp'] = '0'
        changed = settings.apply(api, settings.inspect(api))
        self.assertEqual(changed, ['download_dir', 'download_free', 'default_category.pp'])
        writes = [params for mode, params in api.calls if mode == 'set_config']
        self.assertEqual(writes, [
            {'section': 'misc', 'keyword': 'download_dir', 'value': '/data/incomplete'},
            {'section': 'misc', 'keyword': 'download_free', 'value': '30G'},
            {'section': 'categories', 'keyword': '*', 'pp': '3'},
        ])
        self.assertFalse(any('server' in str(params) for params in writes))

    def test_active_queue_or_postprocessing_refuses_every_change(self):
        for counter in ('queued', 'processing'):
            with self.subTest(counter=counter):
                api = FakeAPI()
                api.misc['complete_dir'] = '/wrong'
                setattr(api, counter, 1)
                with self.assertRaises(settings.SettingsError):
                    settings.apply(api, settings.inspect(api))
                self.assertFalse(any(mode == 'set_config' for mode, _ in api.calls))

    def test_jobs_arriving_after_inspection_prevent_path_change(self):
        api = FakeAPI()
        api.misc['complete_dir'] = '/wrong'
        before = settings.inspect(api)
        api.processing = 1
        with self.assertRaises(settings.SettingsError):
            settings.apply(api, before)
        self.assertFalse(any(mode == 'set_config' for mode, _ in api.calls))

    def test_unreviewed_feeds_and_category_overrides_refuse_apply(self):
        api = FakeAPI()
        api.feeds = [{'enable': 1, 'uri': 'https://private?token=DO-NOT-PRINT'}]
        api.categories[1]['script'] = 'DO-NOT-PRINT'
        before = settings.inspect(api)
        self.assertEqual(before['enabled_rss_feeds'], 1)
        self.assertEqual(before['unreviewed_category_overrides'], 1)
        self.assertNotIn('DO-NOT-PRINT', json.dumps(before))
        with self.assertRaises(settings.SettingsError):
            settings.apply(api, before)

    def test_ignored_api_setting_is_detected_by_readback(self):
        api = FakeAPI()
        api.misc['download_free'] = '1G'
        api.retain = False
        with self.assertRaisesRegex(settings.SettingsError, 'did not retain'):
            settings.apply(api, settings.inspect(api))

    def test_api_key_is_only_in_post_body_and_errors_are_redacted(self):
        api = settings.SabAPI('private-api-key')
        api.opener = mock.Mock()
        api.opener.open.side_effect = urllib.error.URLError('http://evil/?apikey=private-api-key')
        with self.assertRaises(settings.SettingsError) as raised:
            api.call('get_config', section='misc', keyword='download_dir')
        self.assertNotIn('private-api-key', str(raised.exception))
        request = api.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:8080/api')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())['apikey'], ['private-api-key'])

    def test_redirects_and_raw_server_errors_are_not_exposed(self):
        with self.assertRaises(settings.SettingsError):
            settings.NoRedirects().redirect_request(None, None, 302, '', {}, 'https://evil')
        api = settings.SabAPI('private-api-key')
        response = io.StringIO(json.dumps({'status': False, 'error': 'private-api-key DO-NOT-PRINT'}))
        api.opener = mock.Mock()
        api.opener.open.return_value = response
        with self.assertRaises(settings.SettingsError) as raised:
            api.call('set_config', section='misc', keyword='download_free', value='30G')
        self.assertNotIn('private-api-key', str(raised.exception))
        self.assertNotIn('DO-NOT-PRINT', str(raised.exception))

    def test_fresh_wizard_missing_sections_inspects_without_mutation(self):
        api = FakeAPI()
        original = api.call
        api.categories = []
        def call(mode, **params):
            if mode == 'get_config' and params.get('section') in ('categories', 'rss'):
                if params['section'] == 'rss' or not api.categories:
                    return {'config': {}}
            return original(mode, **params)
        api.call = call
        before = settings.inspect(api)
        self.assertTrue(before['safe_to_apply'])
        self.assertFalse(before['default_category_exists'])
        self.assertFalse(any(mode == 'set_config' for mode, _ in api.calls))
        settings.apply(api, before)
        writes = [params for mode, params in api.calls if mode == 'set_config']
        self.assertEqual(writes, [{'section': 'categories', 'keyword': '*', 'pp': '3',
                                 'script': 'None', 'priority': 0, 'dir': '', 'order': 0}])

    def test_missing_rss_section_and_legacy_category_pp_are_safe(self):
        api = FakeAPI()
        original = api.call
        api.categories[1]['pp'] = '-1'
        def call(mode, **params):
            if mode == 'get_config' and params.get('section') == 'rss':
                return {'config': {}}
            return original(mode, **params)
        api.call = call
        self.assertTrue(settings.inspect(api)['safe_to_apply'])

    def test_unexpected_exception_cannot_emit_traceback_or_credentials(self):
        with mock.patch.object(settings, 'read_api_key', side_effect=RuntimeError('DO-NOT-PRINT secret')), \
                mock.patch('sys.stderr', new_callable=io.StringIO) as stderr:
            self.assertEqual(settings.main(['inspect']), 1)
            self.assertNotIn('DO-NOT-PRINT', stderr.getvalue())
            self.assertNotIn('Traceback', stderr.getvalue())

    def test_protected_environment_permissions_and_duplicate_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.env'
            path.write_text('SABNZBD_API_KEY=private\n')
            path.chmod(0o640)
            self.assertEqual(settings.read_api_key(path), 'private')
            path.chmod(0o644)
            with self.assertRaises(settings.SettingsError):
                settings.read_api_key(path)
            path.chmod(0o600)
            path.write_text('SABNZBD_API_KEY=private\nSABNZBD_API_KEY=duplicate\n')
            with self.assertRaises(settings.SettingsError):
                settings.read_api_key(path)


if __name__ == '__main__':
    unittest.main()
