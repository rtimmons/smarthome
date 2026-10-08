import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('native_cutover', Path(__file__).parents[1] / 'scripts/native-cutover.py')
cutover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutover)


class NativeCutoverTests(unittest.TestCase):
    def test_sab_switch_readback_accepts_native_booleans_but_not_disabled_limits(self):
        misc = dict(cutover.LIMITS, top_only=True, pause_on_post_processing=True, preserve_paused_state=True)
        self.assertTrue(cutover.limits_match(misc))
        self.assertFalse(cutover.limits_match(dict(misc, top_only=False)))
        self.assertFalse(cutover.limits_match(dict(misc, size_limit='0')))

    def test_distinct_owners_keep_client_identity_and_credentials(self):
        for app, prefix in (('radarr', 'Movie'), ('sonarr', 'Tv')):
            category = prefix[0].lower() + prefix[1:] + 'Category'
            client = {'id': 7, 'implementation': 'Sabnzbd', 'name': 'fixture',
                      'fields': [{'name': 'apiKey', 'value': 'synthetic-credential'},
                                 {'name': category, 'value': 'prowlarr'},
                                 {'name': 'recent' + prefix + 'Priority', 'value': -100},
                                 {'name': 'older' + prefix + 'Priority', 'value': -100}],
                      'enable': True, 'removeCompletedDownloads': False, 'removeFailedDownloads': True}
            original = copy.deepcopy(client)
            changed = cutover.native_client(client, app)
            fields = {f['name']: f['value'] for f in changed['fields']}
            self.assertEqual(client, original)
            self.assertEqual(changed['id'], 7)
            self.assertEqual(fields[category], app)
            self.assertEqual(fields['apiKey'], 'synthetic-credential')
            self.assertTrue(changed['removeCompletedDownloads'])
            self.assertFalse(changed['removeFailedDownloads'])

    def test_ambiguous_client_fields_are_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'duplicate_client_fields'):
            cutover.native_client({'implementation': 'Sabnzbd', 'fields': [
                {'name': 'movieCategory'}, {'name': 'movieCategory'}]}, 'radarr')

    def test_historical_protection_allows_new_jobs_but_no_hold_release(self):
        before = {'queue': [{'nzo_id': 'held-fixture', 'status': 'Paused', 'cat': 'Default'}]}
        after = {'queue': [{'nzo_id': 'new-fixture', 'status': 'Downloading'}, *copy.deepcopy(before['queue'])]}
        self.assertTrue(cutover.preserved(before, after))
        after['queue'][1]['status'] = 'Downloading'
        self.assertFalse(cutover.preserved(before, after))
        self.assertFalse(cutover.preserved(before, {'queue': []}))

    def test_disposition_allows_only_exact_absent_original_requests(self):
        before = {'queue': [{'nzo_id': 'held-fixture', 'status': 'Paused'}]}
        self.assertTrue(cutover.preserved(before, {'queue': []}, ['held-fixture']))
        self.assertFalse(cutover.preserved(before, before, ['held-fixture']))
        self.assertFalse(cutover.preserved(before, {'queue': []}, ['unrelated-fixture']))
        self.assertFalse(cutover.preserved(before, {'queue': []}, ['held-fixture', 'held-fixture']))

    def test_current_inspector_preserves_journals_and_refuses_retired_workers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def save(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            save(cutover.MARKER, {'phase': 'active', 'integrity_policy': 'native_arr_import_and_cleanup'})
            save('config/catalog/remote-scratch.json', {'mode': 'hybrid'})
            save('state/catalog/cart-import/armed.json', {'baseline': 'fixture'})
            save('state/catalog/cart-import/jobs/fixture.json', {'status': 'completed'})
            save('state/catalog/capacity-admission/state.json', {'held': [], 'owned': [], 'admitted': None})
            save(cutover.RECEIPT, {'snapshot': {'queue': []}, 'fingerprints': cutover.state_fingerprints(root)})
            data = {('prowlarr', 'downloadclient'): []}
            for app, prefix in [('radarr', 'Movie'), ('sonarr', 'Tv')]:
                fields = [prefix[0].lower() + prefix[1:] + 'Category', 'recent' + prefix + 'Priority', 'older' + prefix + 'Priority']
                client = cutover.native_client({'implementation': 'Sabnzbd', 'fields': [{'name': f} for f in fields]}, app)
                data[app, 'downloadclient'] = [client]
                data[app, 'config/downloadclient'] = {'enableCompletedDownloadHandling': True,
                    'autoRedownloadFailed': False, 'autoRedownloadFailedFromInteractiveSearch': False}
                data[app, 'config/mediamanagement'] = {'skipFreeSpaceCheckWhenImporting': False,
                    'minimumFreeSpaceWhenImporting': 30 * 1024, 'copyUsingHardlinks': True}
                data[app, 'config/indexer'] = {'rssSyncInterval': 0}
            api = mock.Mock()
            api.call.side_effect = lambda app, endpoint: data[app, endpoint]
            config = {'misc': dict(cutover.LIMITS), 'rss': [], 'categories': [
                {'name': app, 'dir': app, 'priority': 0, 'pp': 3} for app in ('radarr', 'sonarr')]}
            sab = mock.Mock()
            sab.api.side_effect = lambda mode, section: {'config': {section: config[section]}}
            sab.snapshot.return_value = {'queue': []}
            with mock.patch.object(cutover, 'command', return_value='inactive') as command:
                self.assertEqual(cutover.inspect(root, api, sab)['status'], 'verified')
                self.assertTrue(any('usenet-publish.timer' in c.args for c in command.call_args_list))
                command.return_value = 'active'
                with self.assertRaisesRegex(RuntimeError, 'legacy_timer_still_active'):
                    cutover.inspect(root, api, sab)
                command.return_value = 'inactive'
                save('state/catalog/cart-import/jobs/fixture.json', {'status': 'changed'})
                with self.assertRaisesRegex(RuntimeError, 'historical_holds_or_journals_changed'):
                    cutover.inspect(root, api, sab)
            self.assertTrue(all(c.args[0] == 'get_config' for c in sab.api.call_args_list))
