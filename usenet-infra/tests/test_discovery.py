import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


discovery = load('discovery-config')
bootstrap = load('discovery-init')


class ReadAPI:
    def __init__(self):
        self.data = {}
        for app, (_, version) in discovery.APPS.items():
            self.data[app, 'system/status'] = {'version': version}
        self.data['prowlarr', 'appprofile'] = [dict(discovery.PROFILE_POLICY, id=8, name=discovery.PROFILE)]
        self.data['prowlarr', 'indexer'] = [{'appProfileId': 8}, {'appProfileId': 8}]
        for app in ('radarr', 'sonarr'):
            self.data[app, 'importlist'] = []
            self.data[app, 'health'] = [{'type': 'error', 'source': 'ImportMechanismCheck'}]
            self.data[app, 'config/indexer'] = {'rssSyncInterval': discovery.RSS_INTERVAL}
            self.data[app, 'config/downloadclient'] = dict(discovery.DOWNLOAD_POLICY)
            self.data[app, 'indexer'] = [dict(discovery.PROFILE_POLICY), dict(discovery.PROFILE_POLICY)]
            self.data[app, 'downloadclient'] = [{'name': discovery.CLIENT, 'enable': True,
                'removeCompletedDownloads': False, 'removeFailedDownloads': False}]

    def call(self, app, endpoint, method='GET', body=None):
        if method != 'GET':
            raise AssertionError('Inspection attempted a mutation')
        return copy.deepcopy(self.data[app, endpoint])


class DiscoveryTests(unittest.TestCase):
    def test_inspection_is_read_only_and_checks_authorized_acquisition_policy(self):
        api = ReadAPI()
        result = discovery.inspect(api)
        self.assertEqual(result['status'], 'verified')
        self.assertTrue(result['automatic_acquisition'])
        self.assertFalse(result['automatic_import'])
        changes = [
            ('config/indexer', 'rssSyncInterval', 0),
            *[('config/downloadclient', key, True) for key in discovery.DOWNLOAD_POLICY],
        ]
        for app in ('radarr', 'sonarr'):
            for endpoint, key, value in changes:
                with self.subTest(app=app, key=key):
                    broken = ReadAPI()
                    broken.data[app, endpoint][key] = value
                    with self.assertRaises(discovery.DiscoveryError):
                        discovery.inspect(broken)
            for key in ('enableRss', 'enableAutomaticSearch'):
                broken = ReadAPI()
                broken.data[app, 'indexer'][0][key] = False
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(broken)
            for key in ('removeCompletedDownloads', 'removeFailedDownloads'):
                broken = ReadAPI()
                broken.data[app, 'downloadclient'][0][key] = True
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(broken)

    def test_configuration_commands_wait_for_completion_and_refuse_searches(self):
        from unittest.mock import Mock
        api = Mock()
        api.call.side_effect = [{'id': 9}, {'status': 'started'}, {'status': 'completed'}]
        with patch.object(discovery.time, 'sleep'):
            discovery.run_configuration_command(api, 'prowlarr', 'ApplicationIndexerSync')
        self.assertEqual(api.call.call_count, 3)
        api = Mock()
        with self.assertRaises(discovery.DiscoveryError):
            discovery.run_configuration_command(api, 'radarr', 'MoviesSearch')
        api.call.assert_not_called()
        api.call.side_effect = [{'id': 10}, {'status': 'failed'}]
        with self.assertRaises(discovery.DiscoveryError):
            discovery.run_configuration_command(api, 'radarr', 'CheckHealth')

    def test_missing_controls_and_upgraded_versions_fail_closed(self):
        api = ReadAPI()
        del api.data['sonarr', 'config/downloadclient']['autoRedownloadFailedFromInteractiveSearch']
        with self.assertRaises(discovery.DiscoveryError):
            discovery.inspect(api)
        api = ReadAPI()
        api.data['radarr', 'system/status']['version'] = 'future-unreviewed'
        with self.assertRaises(discovery.DiscoveryError):
            discovery.inspect(api)
        self.assertFalse(discovery.require_policy({'enabled': 0}, {'enabled': False}))

    def test_list_subscription_cannot_silently_enable_acquisition(self):
        api = ReadAPI()
        api.data['radarr', 'importlist'] = [{'enableAuto': True, 'searchOnAdd': False}]
        with self.assertRaises(discovery.DiscoveryError):
            discovery.inspect(api)
        api = ReadAPI()
        api.data['sonarr', 'importlist'] = [{'enableAutomaticAdd': False, 'searchForMissingEpisodes': True}]
        with self.assertRaises(discovery.DiscoveryError):
            discovery.inspect(api)

    def test_redirects_cannot_forward_api_keys(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.NoRedirects().redirect_request(None, None, 302, '', {}, 'https://outside.invalid')

    def test_manual_mode_notices_do_not_hide_unrelated_health_failures(self):
        api = ReadAPI()
        self.assertEqual(discovery.inspect(api)['apps']['radarr']['expected_policy_notices'], 1)
        for source in ('DownloadClientCheck', 'IndexerRssCheck', 'IndexerSearchCheck'):
            with self.subTest(source=source):
                api = ReadAPI()
                api.data['radarr', 'health'].append({'type': 'error', 'source': source})
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(api)

    def test_identity_bootstrap_is_private_and_preserves_existing_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for app in ('radarr', 'sonarr'):
                (root / app).mkdir()
            bootstrap.initialize(root)
            before = {app: (root / app / 'config.xml').read_bytes() for app in ('radarr', 'sonarr')}
            bootstrap.initialize(root)
            for app, content in before.items():
                path = root / app / 'config.xml'
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(content, path.read_bytes())
                xml = ET.fromstring(content)
                self.assertEqual(xml.findtext('AuthenticationMethod'), 'External')
                self.assertEqual(xml.findtext('UrlBase'), '/' + app)
                self.assertEqual(len(xml.findtext('ApiKey')), 32)

    def test_discovery_has_no_download_storage_or_remote_writer_mounts(self):
        compose = (Path(__file__).parents[1] / 'compose/discovery/compose.yaml').read_text()
        for forbidden in ('/downloads', '/secrets', 'storagebox', 'docker.sock', ':latest', '0.0.0.0:'):
            self.assertNotIn(forbidden, compose)
        self.assertIn('127.0.0.1:7878:7878', compose)
        self.assertIn('127.0.0.1:8989:8989', compose)

    def test_masked_unchanged_connection_is_tested_without_rewriting_credentials(self):
        resource = {'id': 1, 'name': 'fixture', 'implementation': 'Sabnzbd', 'enable': True,
                    'fields': [{'name': 'apiKey', 'value': '********'}]}
        from unittest.mock import Mock
        api = Mock()
        api.call.side_effect = [[resource], None]
        result, changed = discovery.upsert(api, 'radarr', 'downloadclient', 'fixture',
            {'enable': True}, {'apiKey': 'fixture-current-key'}, 'Sabnzbd')
        self.assertFalse(changed)
        self.assertEqual(api.call.call_count, 2)
        self.assertEqual(api.call.call_args.args, ('radarr', 'downloadclient/test', 'POST', resource))

    def test_failed_masked_connection_is_repaired_with_current_key_and_retested(self):
        resource = {'id': 1, 'name': 'fixture', 'implementation': 'Sabnzbd', 'enable': True,
                    'fields': [{'name': 'apiKey', 'value': '********'}]}
        from unittest.mock import Mock
        api = Mock()
        api.call.side_effect = [[resource], discovery.DiscoveryError('invalid_stored_key'), None, resource]
        _, changed = discovery.upsert(api, 'radarr', 'downloadclient', 'fixture',
            {'enable': True}, {'apiKey': 'fixture-current-key'}, 'Sabnzbd')
        self.assertTrue(changed)
        self.assertEqual(api.call.call_args_list[2].args[3]['fields'][0]['value'], 'fixture-current-key')
        self.assertEqual(api.call.call_args.args[2], 'PUT')
