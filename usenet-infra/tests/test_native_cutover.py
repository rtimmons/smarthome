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
    def test_finish_cannot_claim_acceptance_from_partial_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = root / 'state/catalog/native-acceptance.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'phase': 'verified', 'verification': {'movie_import_cleanup': True}}))
            api, helper = mock.Mock(), mock.Mock()
            with mock.patch.object(cutover, 'inspect', return_value={'phase': 'acceptance'}):
                with self.assertRaisesRegex(RuntimeError, 'complete_native_acceptance_evidence_required'):
                    cutover.finish(root, api, mock.Mock(), helper)
            api.call.assert_not_called()
            helper.save_receipt.assert_not_called()

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
