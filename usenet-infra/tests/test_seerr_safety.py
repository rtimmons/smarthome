import copy
import importlib.util
from pathlib import Path
import unittest
from test_seerr_recovery import r, snapshot

spec = importlib.util.spec_from_file_location('seerr_safety', Path(__file__).parents[1] / 'scripts/seerr-safety.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class SafetyTests(unittest.TestCase):
    def test_scope_excludes_deleted_denied_and_separate_4k(self):
        value = snapshot()
        for patch in ({'status': 3}, {'is4k': True}, {'media': {'status': 7}}, {'media': {'status': 6}}):
            request = copy.deepcopy(value['requests'][0]); request.update(patch)
            self.assertEqual(s.approved(r, [request], value['settings'], value['items']), {})
        self.assertEqual(s.approved(r, value['requests'], value['settings'], value['items']), {('sonarr', 10): {1}})

    def test_approved_but_unbound_fails_closed(self):
        value = snapshot(); value['items'] = {}
        with self.assertRaisesRegex(RuntimeError, 'binding_requires_review'):
            s.approved(r, value['requests'], value['settings'], value['items'])

    def test_monitoring_only_narrows_and_preserves_unrelated_tags(self):
        item = {'id': 10, 'path': '/fictional', 'qualityProfileId': 5, 'tags': [8],
                'monitored': True, 'monitorNewItems': 'all',
                'seasons': [{'seasonNumber': 1, 'monitored': True},
                            {'seasonNumber': 2, 'monitored': True},
                            {'seasonNumber': 3, 'monitored': False}]}
        before = copy.deepcopy(item)
        result = s.desired_item('sonarr', item, {('sonarr', 10): {1, 3}}, 7)
        self.assertEqual([x['monitored'] for x in result['seasons']], [True, False, False])
        self.assertEqual(result['tags'], [7, 8]); self.assertEqual(result['monitorNewItems'], 'none')
        self.assertEqual(item, before)
        self.assertEqual(result['path'], item['path']); self.assertEqual(result['qualityProfileId'], 5)
        self.assertEqual(s.desired_item('sonarr', result, {('sonarr', 10): {1, 3}}, 7), result)
        excluded = s.desired_item('sonarr', result, {}, 7)
        self.assertFalse(excluded['monitored']); self.assertEqual(excluded['tags'], [8])

    def test_movie_does_not_reenable_or_change_existing_file(self):
        item = {'id': 20, 'monitored': False, 'tags': [], 'movieFileId': 123, 'qualityProfileId': 3}
        result = s.desired_item('radarr', item, {('radarr', 20): set()}, 7)
        self.assertEqual(result, dict(item, tags=[7]))

class TransportTests(unittest.TestCase):
    def test_seerr_update_excludes_readonly_id_and_keeps_tags(self):
        import io
        import json
        from unittest import mock
        client = mock.Mock()
        client.settings = {'main': {'apiKey': 'synthetic'}}
        client.opener.open.return_value = io.BytesIO(b'{}')
        s.seerr_update(client, 'sonarr', {'id': 0, 'tags': [7], 'monitorNewItems': 'none'})
        request = client.opener.open.call_args.args[0]
        self.assertTrue(request.full_url.endswith('/sonarr/0'))
        self.assertEqual(request.method, 'PUT')
        self.assertEqual(json.loads(request.data), {'tags': [7], 'monitorNewItems': 'none'})

class CodecPolicyTests(unittest.TestCase):
    def test_recalculated_scores_do_not_hide_file_changes(self):
        before = [{'id': 1, 'path': '/synthetic.mkv', 'size': 100,
                   'customFormats': [], 'customFormatScore': 0}]
        after = [dict(before[0], customFormats=[{'id': 9}], customFormatScore=-10000)]
        self.assertTrue(s.same_media_files(before, after))
        for field, value in [('id', 2), ('path', '/other.mkv'), ('size', 101)]:
            changed = [dict(after[0], **{field: value})]
            self.assertFalse(s.same_media_files(before, changed))

    def fixture(self):
        before = {'customformat': [], 'qualityprofile': [
            {'id': 4, 'name': 'HD-1080p', 'minFormatScore': 0,
             'upgradeAllowed': False, 'items': [{'allowed': True}], 'formatItems': []}]}
        after = copy.deepcopy(before)
        after['customformat'] = [{'id': 9, 'name': 'AV1', 'includeCustomFormatWhenRenaming': False,
            'specifications': [{'implementation': 'ReleaseTitleSpecification', 'negate': False,
                'required': True, 'fields': [{'name': 'value', 'value': r'\bAV1\b'}]}]}]
        after['qualityprofile'][0]['formatItems'] = [{'format': 9, 'name': 'AV1', 'score': -10000}]
        return before, after

    def test_codec_rejection_and_idempotent_readback(self):
        before, after = self.fixture()
        s.verify_codec_policy(before, after)
        s.verify_codec_policy(after, after)

    def test_other_profile_changes_are_refused(self):
        for field, value in [('upgradeAllowed', True), ('items', []), ('minFormatScore', -10000)]:
            before, after = self.fixture()
            after['qualityprofile'][0][field] = value
            with self.assertRaises(RuntimeError):
                s.verify_codec_policy(before, after)

    def test_disabled_or_broadened_codec_filter_is_refused(self):
        for patch in ['score', 'regex', 'negate']:
            before, after = self.fixture()
            if patch == 'score':
                after['qualityprofile'][0]['formatItems'][0]['score'] = 0
            elif patch == 'regex':
                after['customformat'][0]['specifications'][0]['fields'][0]['value'] = '.*'
            else:
                after['customformat'][0]['specifications'][0]['negate'] = True
            with self.assertRaises(RuntimeError):
                s.verify_codec_policy(before, after)


if __name__ == '__main__':
    unittest.main()
