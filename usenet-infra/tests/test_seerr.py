import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('seerr_config', ROOT / 'scripts/seerr-config.py')
seerr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seerr)


class SeerrTests(unittest.TestCase):
    def settings(self):
        result = {'main': dict(seerr.MAIN), 'public': {'initialized': True},
                  'plex': {'ip': '192.168.1.66', 'port': 32400, 'useSsl': False,
                           'libraries': [{'id': str(i), 'enabled': i in (2, 3, 4, 5)} for i in range(1, 6)]}}
        for app, port in (('radarr', 7878), ('sonarr', 8989)):
            result[app] = [{'hostname': '127.0.0.1', 'port': port, 'baseUrl': '/' + app,
                'activeDirectory': '/library', 'activeProfileId': 4, 'is4k': False,
                'isDefault': True, 'syncEnabled': True, 'preventSearch': False, 'monitorNewItems': 'none'}]
        return result

    def test_only_selected_general_plex_libraries_are_enabled(self):
        value = self.settings()
        self.assertEqual(seerr.validate(value)['plex_library_ids'], ['2', '3', '4', '5'])
        value['plex']['libraries'][0]['enabled'] = True
        with self.assertRaisesRegex(RuntimeError, 'private_library_boundary'):
            seerr.validate(value)

    def test_uninitialized_or_open_registration_cannot_be_exposed(self):
        for section, field, value in (('public', 'initialized', False), ('main', 'newPlexLogin', True),
                                      ('main', 'localLogin', True)):
            settings = self.settings()
            settings[section][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                seerr.validate(settings)

    def test_requests_must_reach_native_apps_with_correct_root_and_search_enabled(self):
        for field, value in (('hostname', 'external.invalid'), ('activeDirectory', '/data/complete'),
                             ('preventSearch', True), ('isDefault', False), ('monitorNewItems', 'all')):
            settings = self.settings()
            settings['sonarr'][0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                seerr.validate(settings)
        settings = self.settings()
        settings['radarr'].append(copy.deepcopy(settings['radarr'][0]))
        with self.assertRaisesRegex(RuntimeError, 'unique_native_server'):
            seerr.validate(settings)

    def test_bootstrap_transport_refuses_redirects(self):
        with self.assertRaisesRegex(RuntimeError, 'redirect_refused'):
            seerr.NoRedirects().redirect_request(None, None, 302, None, None, 'https://example.invalid')

    def test_deployment_has_no_media_mounts_and_loopback_backend(self):
        compose = (ROOT / 'compose/seerr/compose.yaml').read_text()
        self.assertIn('HOST: 127.0.0.1', compose)
        self.assertIn('@sha256:', compose)
        self.assertNotIn('source: /srv/usenet/library', compose)
        self.assertNotIn('docker.sock', compose)
        proxy = (ROOT / 'compose/seerr/Caddyfile').read_text()
        self.assertIn('bind 10.77.0.1', proxy)
        self.assertIn('respond @api_key 403', proxy)
        self.assertIn('header_up -X-API-User', proxy)
