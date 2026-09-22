import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('native_cutover_preflight',
    Path(__file__).parents[1] / 'scripts/native-cutover-preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
G = preflight.GIB


def fixture():
    private = 'PRIVATE-MEDIA-TITLE-OR-SECRET'
    data = {
        'checked_at': '2026-09-20T00:00:00+00:00',
        'filesystems': {key: {'available_bytes': 250 * G, 'mounted': True}
                        for key in ('local', 'remote', 'library')},
        'history_sizes': [80 * G],
        'journals': {private: {'phase': 'cleaned', 'sources': {private: {'signature': [75 * G, 1, 2, 3]}}}},
        'snapshot': {'queue': [{'status': 'Paused', 'filename': private}], 'paused': False, 'postprocessing': 0},
        'capacity': {'held': [private], 'admitted': None},
        'importer_status': {'errors': 0, 'held': 1},
        'sab_misc': {'download_free': '30G', 'complete_free': '30G', 'api_key': private},
        'sab_feeds': [{'enable': 1, 'uri': private}], 'apps': {},
    }
    for app, field in (('radarr', 'movieCategory'), ('sonarr', 'tvCategory')):
        data['apps'][app] = {
            'downloadclient': [{'implementation': 'Sabnzbd', 'name': private, 'fields': [
                {'name': field, 'value': 'prowlarr'}, {'name': 'apiKey', 'value': private}]}],
            'config/downloadclient': {'enableCompletedDownloadHandling': True},
            'config/mediamanagement': {'copyUsingHardlinks': True, 'skipFreeSpaceCheckWhenImporting': False},
            'rootfolder': [{'accessible': True, 'path': private}], 'health': [{'message': private}],
        }
    return data


class NativeCutoverPreflightTests(unittest.TestCase):
    def test_same_filesystem_bind_uses_mount_table(self):
        path = Path('/srv/usenet/downloads/incomplete')
        with mock.patch.object(preflight.shutil, 'which', return_value='/usr/bin/findmnt'), \
                mock.patch.object(preflight.subprocess, 'run') as run:
            run.return_value.stdout = str(path) + '\n'
            self.assertTrue(preflight.mounted(path))
            run.return_value.stdout = '/\n'
            self.assertFalse(preflight.mounted(path))

    def test_full_repair_and_copy_fallback_are_reserved(self):
        result = preflight.budget(120 * G, 63 * G, 80 * G, 75 * G)
        self.assertEqual(result['local_required_bytes'], 195 * G)
        self.assertEqual(result['remote_required_bytes'], 185 * G)
        self.assertEqual(result['local_shortfall_bytes'], 75 * G)
        self.assertEqual(result['remote_shortfall_bytes'], 122 * G)

    def test_expansion_is_independent_of_download_size(self):
        result = preflight.budget(250 * G, 250 * G, 10 * G, 100 * G)
        self.assertEqual(result['remote_required_bytes'], 235 * G)

    def test_invalid_or_missing_sizes_fail_closed(self):
        for value in (None, -1, True, '8000', float('nan'), 0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight.budget(250 * G, 250 * G, value, 75 * G)

    def test_public_report_does_not_leak_private_nested_values(self):
        data = fixture()
        original = copy.deepcopy(data)
        report = preflight.summarize(data)
        self.assertNotIn('PRIVATE-', json.dumps(report))
        self.assertEqual(data, original)
        self.assertIn('arr_categories_not_distinct', report['blockers'])
        self.assertFalse(report['cutover_performed'])

    def test_low_library_space_not_masked_by_staging_space(self):
        data = fixture()
        data['filesystems']['library']['available_bytes'] = 40 * G
        self.assertIn('remote_capacity_insufficient_for_observed_workload', preflight.summarize(data)['blockers'])

    def test_mount_and_inflight_blockers(self):
        data = fixture()
        data['filesystems']['remote']['mounted'] = False
        data['snapshot']['postprocessing'] = 1
        data['capacity']['admitted'] = {'private': True}
        report = preflight.summarize(data)
        for reason in ('required_mount_missing', 'sab_not_idle', 'existing_admission_requires_reconciliation'):
            self.assertIn(reason, report['blockers'])

    def test_no_ready_claim_when_capacity_and_categories_pass(self):
        data = fixture()
        for app in ('radarr', 'sonarr'):
            data['apps'][app]['downloadclient'][0]['fields'][0]['value'] = app
        report = preflight.summarize(data)
        self.assertEqual(report['blockers'], [])
        self.assertEqual(report['status'], 'preflight_only')
        self.assertIn('explicit_integrity_policy', report['pending_requirements'])

    def test_prior_acceptance_is_distinct_from_a_read_only_capture(self):
        data = fixture()
        data['native_ownership'] = {'phase': 'active', 'private': 'PRIVATE-SOURCE'}
        data['native_acceptance'] = {'phase': 'verified', 'verification': {
            key: True for key in ('movie_import_cleanup', 'episode_import_cleanup', 'plex_movie',
                                 'plex_episode', 'large_repair', 'service_restart', 'historical_state_preserved')}}
        result = preflight.summarize(data)
        self.assertTrue(result['prior_acceptance_evidence_recorded'])
        self.assertTrue(result['read_only_capture'])
        self.assertFalse(result['cutover_performed'])
        self.assertEqual(result['pending_requirements'], [])
        self.assertNotIn('PRIVATE-', json.dumps(result))
        data['native_acceptance']['verification']['plex_episode'] = False
        self.assertFalse(preflight.summarize(data)['prior_acceptance_evidence_recorded'])


if __name__ == '__main__':
    unittest.main()
