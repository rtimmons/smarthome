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
            self.data[app, 'health'] = []
            self.data[app, 'config/indexer'] = {'rssSyncInterval': discovery.RSS_INTERVAL}
            self.data[app, 'config/downloadclient'] = dict(discovery.DOWNLOAD_POLICY)
            self.data[app, 'indexer'] = [dict(discovery.PROFILE_POLICY), dict(discovery.PROFILE_POLICY)]
            self.data[app, 'downloadclient'] = [{'name': discovery.CLIENT, 'enable': True,
                'removeCompletedDownloads': True, 'removeFailedDownloads': False}]

    def call(self, app, endpoint, method='GET', body=None):
        if method != 'GET':
            raise AssertionError('Inspection attempted a mutation')
        return copy.deepcopy(self.data[app, endpoint])


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        import json
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        marker = Path(temporary.name) / 'native.json'
        marker.write_text(json.dumps({'phase': 'active', 'integrity_policy': 'native_arr_import_and_cleanup'}))
        patcher = patch.object(discovery, 'NATIVE_MARKER', marker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_native_inspection_requires_explicit_requests_and_keeps_health_errors(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'native.json'
            marker.write_text(json.dumps({'phase': 'active', 'integrity_policy': 'native_arr_import_and_cleanup'}))
            with patch.object(discovery, 'NATIVE_MARKER', marker):
                api = ReadAPI()
                api.data['radarr', 'config/indexer']['rssSyncInterval'] = 15
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(api)
                for app in ('radarr', 'sonarr'):
                    api.data[app, 'config/indexer']['rssSyncInterval'] = 0
                result = discovery.inspect(api)
                self.assertFalse(result['automatic_acquisition'])
                self.assertTrue(result['explicit_native_requests'])
                self.assertFalse(result['apps']['sonarr']['rss_enabled'])
                api.data['sonarr', 'health'] = [{'type': 'error', 'source': 'DownloadClientCheck'}]
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(api)
                marker.write_text('{}')
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(ReadAPI())

    def test_inspection_is_read_only_and_checks_authorized_acquisition_policy(self):
        api = ReadAPI()
        result = discovery.inspect(api)
        self.assertEqual(result['status'], 'verified')
        self.assertFalse(result['automatic_acquisition'])
        self.assertTrue(result['automatic_import'])
        changes = [
            ('config/indexer', 'rssSyncInterval', 15),
            *[('config/downloadclient', key, not value) for key, value in discovery.DOWNLOAD_POLICY.items()],
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
                broken.data[app, 'downloadclient'][0][key] = not broken.data[app, 'downloadclient'][0][key]
                with self.assertRaises(discovery.DiscoveryError):
                    discovery.inspect(broken)


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

    def test_native_import_and_indexer_health_failures_are_not_hidden(self):
        api = ReadAPI()
        self.assertEqual(discovery.inspect(api)['apps']['radarr']['expected_policy_notices'], 0)
        for source in ('ImportMechanismCheck', 'DownloadClientCheck', 'IndexerRssCheck', 'IndexerSearchCheck'):
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

    def test_native_import_mounts_do_not_expose_credentials_or_incomplete_jobs(self):
        compose = (Path(__file__).parents[1] / 'compose/discovery/compose.yaml').read_text()
        for forbidden in ('/downloads/incomplete', '/secrets', 'storagebox', 'docker.sock', ':latest', '0.0.0.0:'):
            self.assertNotIn(forbidden, compose)
        self.assertIn('/srv/usenet/library:/storage', compose)
        self.assertIn('ARR_LIBRARY_KIND: TV', compose)
        self.assertIn('/srv/usenet/downloads/complete:/data/complete', compose)
        self.assertIn('restart: "no"', compose)
        self.assertIn('127.0.0.1:7878:7878', compose)
        self.assertIn('127.0.0.1:8989:8989', compose)
