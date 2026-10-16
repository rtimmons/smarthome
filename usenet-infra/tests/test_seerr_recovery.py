import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('seerr_recovery', ROOT / 'scripts/seerr-recovery.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def snapshot():
    return {'settings': {'sonarr': [{'id': 0}], 'radarr': [{'id': 0}]},
        'requests': [{'id': 1, 'type': 'tv', 'status': 2, 'is4k': False, 'serverId': 0,
            'media': {'status': 3, 'serviceId': 0, 'externalServiceId': 10, 'tvdbId': 123},
            'seasons': [{'seasonNumber': 1, 'status': 2}]}],
        'items': {'sonarr:10': {'id': 10, 'tvdbId': 123, 'title': 'Imaginary Observatory',
            'episodes': [{'id': i, 'seasonNumber': 1, 'episodeNumber': i, 'title': f'Chapter {i}',
                'hasFile': i == 1, 'episodeFileId': 100 if i == 1 else 0,
                'verified': True if i == 1 else None, 'monitored': True,
                'airDateUtc': '2000-01-01T00:00:00Z'} for i in (1, 2, 3)]}},
        'queue': {'sonarr': [], 'radarr': []}, 'jobs': {}, 'candidates': {}, 'blocked': [], 'processing': 0}


def aged(value):
    first = r.plan(value, now=1700000000)
    return r.plan(value, first, now=1700001000)


def completed(value):
    value['queue']['sonarr'] = [{'seriesId': 10, 'episodeId': i, 'downloadId': 'job-one', 'status': 'completed'} for i in (2, 3)]
    value['jobs']['job-one'] = {'status': 'Completed', 'name': 'Imaginary.Observatory.S01.COMPLETE'}
    value['candidates']['job-one'] = [{'path': f'/storage/.acquisition-staging/complete/sonarr/job/{i}.mkv',
        'embedded_title': f'Imaginary Observatory S01E0{i} - Chapter {i}', 'source_verified': True,
        'rejections': [{'reason': 'Single episode file contains all episodes in seasons. Review file name or manually import'}]}
        for i in (2, 3)]
    return value


class RecoveryTests(unittest.TestCase):
    def test_plex_scan_freshness_requires_every_selected_general_library(self):
        value = {'plex': {'libraries': [{'id': str(i), 'enabled': True, 'lastScan': 1699999990000} for i in (2,3,4,5)]}}
        self.assertTrue(r.plex_scan_fresh(value, 1700000000))
        for stamp in (None, 1699990000000, 1700000010000):
            altered = copy.deepcopy(value); altered['plex']['libraries'][0]['lastScan'] = stamp
            self.assertFalse(r.plex_scan_fresh(altered, 1700000000))
        value['plex']['libraries'].append({'id': '1', 'enabled': True, 'lastScan': 1699999990000})
        self.assertFalse(r.plex_scan_fresh(value, 1700000000))

    def test_missing_only_never_includes_present_episode(self):
        report = aged(snapshot())
        proposal = report['requests'][0]['proposals'][0]
        self.assertEqual(proposal['ids'], [2, 3])
        self.assertEqual(proposal['exclude_release_overlap'], [1])
        self.assertEqual(proposal['strategy'], 'individual_missing_only')
        self.assertEqual(report['summary']['acquisition_writes'], 0)

    def test_reports_no_actions_after_repaired_library(self):
        value = snapshot()
        for e in value['items']['sonarr:10']['episodes']:
            e.update(hasFile=True, episodeFileId=e['id']+100, verified=True)
        self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_scope_is_approved_request_and_exact_external_identity(self):
        for field, change in (('status', 1), ('status', 3), ('is4k', True), ('serverId', 8)):
            value = snapshot(); value['requests'][0][field] = change
            self.assertEqual(aged(value)['summary']['proposals'], {})
        value = snapshot(); value['requests'][0]['media']['tvdbId'] = 999
        self.assertEqual(aged(value)['requests'][0]['reason'], 'request_binding_missing')
        value = snapshot(); value['requests'][0]['seasons'][0]['seasonNumber'] = 2
        self.assertEqual(aged(value)['summary']['proposals'], {})
        value = snapshot(); value['requests'][0]['media']['status'] = 7
        self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_exact_metadata_import_precedes_replacement_search(self):
        report = aged(completed(snapshot()))
        self.assertEqual(report['summary']['proposals'], {'native_manual_import': 1})
        self.assertEqual(report['requests'][0]['proposals'][0]['episode_ids'], [2, 3])

    def test_metadata_accepts_only_reviewed_technical_release_suffix(self):
        value = completed(snapshot())
        for f in value['candidates']['job-one']:
            f['embedded_title'] += '.1080p.BluRay.x264-FIXTURE'
        value['candidates']['job-one'][0]['rejections'] = [{'reason': 'Invalid season or episode'}]
        self.assertEqual(aged(value)['summary']['proposals'], {'native_manual_import': 1})
        value['candidates']['job-one'][0]['embedded_title'] += '.Bonus'
        self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_ambiguous_season_pack_is_held_not_replaced(self):
        value = completed(snapshot())
        for f in value['candidates']['job-one']:
            f['embedded_title'] = ''
        report = aged(value)
        self.assertEqual(report['summary']['proposals'], {})
        self.assertIn('completed_files_need_matching', report['requests'][0]['findings'])

    def test_duplicate_or_wrong_episode_mapping_cannot_import(self):
        for title in ('Imaginary Observatory S01E02 - Chapter 2',
                      'Another Show S01E03 - Chapter 3',
                      'Imaginary Observatory S01E03 - Wrong Title',
                      'Imaginary Observatory S02E03 - Chapter 3',
                      'Imaginary Observatory S01E02 S01E03 - Chapter 3'):
            value = completed(snapshot()); value['candidates']['job-one'][1]['embedded_title'] = title
            self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_present_candidate_and_native_rejection_are_not_overridden(self):
        for change in ('existing', 'rejection', 'source'):
            value = completed(snapshot())
            if change == 'existing':
                value['items']['sonarr:10']['episodes'][1].update(hasFile=True, episodeFileId=102, verified=True)
            elif change == 'rejection':
                value['candidates']['job-one'][0]['rejections'] = [{'reason': 'Permission denied'}]
            else:
                value['candidates']['job-one'][0]['source_verified'] = False
            self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_extras_release_is_reviewed_without_discarding_files(self):
        value = completed(snapshot()); value['jobs']['job-one']['name'] += '.Extras.Only'
        report = aged(value)
        self.assertEqual(report['summary']['proposals'], {})
        self.assertIn('unsuitable_release_review', report['requests'][0]['findings'])
        self.assertFalse(r.unsuitable_release('Extras.S01.1080p.COMPLETE'))
        self.assertFalse(r.unsuitable_release('Imaginary.Observatory.S01.COMPLETE'))

    def test_active_and_unknown_scope_jobs_prevent_duplicates(self):
        for episode in (None, 2):
            value = snapshot()
            value['queue']['sonarr'] = [{'seriesId': 10, 'episodeId': episode, 'downloadId': 'busy', 'status': 'downloading'}]
            ids = [i for p in aged(value)['requests'][0]['proposals'] for i in p.get('ids', [])]
            self.assertEqual(ids, [] if episode is None else [3])

    def test_unlinked_completed_jobs_hold_search_until_review(self):
        value = snapshot(); value['unlinked_completed_categories'] = ['sonarr']
        self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_pause_mount_health_and_processing_hold_every_proposal(self):
        for value in (snapshot(), completed(snapshot())):
            for reason in ('manual_pause', 'library_mount_unavailable', 'sonarr_health_issue'):
                changed = copy.deepcopy(value); changed['blocked'] = [reason]
                self.assertEqual(aged(changed)['summary']['proposals'], {})
            value['processing'] = 1
            self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_inconsistent_existing_file_record_never_triggers_search(self):
        value = snapshot()
        for e in value['items']['sonarr:10']['episodes']:
            e.update(hasFile=True, episodeFileId=e['id']+100, verified=False)
        report = aged(value)
        self.assertEqual(report['summary']['proposals'], {})
        self.assertIn('library_record_or_file_needs_review', report['requests'][0]['findings'])

    def test_future_unknown_unmonitored_and_completed_requests_are_not_researched(self):
        for field, value in (('airDateUtc', '2099-01-01T00:00:00Z'), ('airDateUtc', None), ('monitored', False)):
            snap = snapshot()
            for e in snap['items']['sonarr:10']['episodes']: e[field] = value
            self.assertEqual(aged(snap)['summary']['proposals'], {})
        snap = snapshot(); snap['requests'][0]['status'] = 5
        self.assertEqual(aged(snap)['summary']['proposals'], {})

    def test_grace_period_and_overlapping_requests_do_not_repeat_actions(self):
        self.assertEqual(r.plan(snapshot())['summary']['proposals'], {})
        self.assertEqual(r.plan(completed(snapshot()))['summary']['proposals'], {})
        value = snapshot(); second = copy.deepcopy(value['requests'][0]); second['id'] = 2
        value['requests'].append(second)
        self.assertEqual(aged(value)['summary']['proposals'], {'missing_episode_search': 1})

    def test_notifications_are_stable_and_do_not_contain_media_identifiers(self):
        a = aged(snapshot()); b = copy.deepcopy(a); b['generated_at'] = '2099-01-01'
        self.assertEqual(r.notification(a), r.notification(b))
        self.assertNotIn('Imaginary', json.dumps(r.notification(a)))

    def test_availability_lag_alert_waits_and_clears_after_seerr_update(self):
        value = snapshot()
        for e in value['items']['sonarr:10']['episodes']:
            e.update(hasFile=True, episodeFileId=e['id']+100, verified=True)
        self.assertEqual(r.plan(value)['requests'][0]['findings'], [])
        self.assertIn('imported_waiting_for_seerr_availability', aged(value)['requests'][0]['findings'])
        value['requests'][0]['media']['status'] = 5
        self.assertEqual(r.notification(aged(value))[1]['action'], 'dismiss')

    def test_notification_delivery_retries_and_unchanged_reports_send_only_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            r.atomic_json(state / 'notify.json', {'host': '192.168.1.163', 'webhook_id': 'a'*64})
            value = snapshot(); value['blocked'] = ['manual_pause']
            with mock.patch.object(r, 'collect', return_value=value), mock.patch.object(r, 'notify_ha') as send, mock.patch('builtins.print'):
                send.side_effect = OSError('delivery failed')
                self.assertEqual(r.run(mock.Mock(), state), 1)
                self.assertFalse((state / 'notification-state.json').exists())
                send.side_effect = None
                r.run(mock.Mock(), state)
                self.assertEqual(send.call_args.args[1]['action'], 'create')
                r.run(mock.Mock(), state)
                self.assertEqual(send.call_args.args[1]['action'], 'heartbeat')
                value['blocked'] = []
                for e in value['items']['sonarr:10']['episodes']:
                    e.update(hasFile=True, episodeFileId=e['id']+100, verified=True)
                value['requests'][0]['media']['status'] = 5
                r.run(mock.Mock(), state)
                self.assertEqual(send.call_args.args[1]['action'], 'dismiss')

    def test_partial_api_failure_becomes_blocked_report_without_proposals(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(r, 'collect', side_effect=r.RecoveryError('native_read_failed')), mock.patch('builtins.print'):
                self.assertEqual(r.run(mock.Mock(), Path(temp)), 1)
            report = r.private_json(Path(temp) / 'report.json')
            self.assertEqual(report['summary']['proposals'], {})
            self.assertEqual(report['summary']['blocked'], ['native_read_failed'])

    def test_request_pagination_rejects_incomplete_duplicate_and_changing_data(self):
        reader = mock.Mock()
        for page in ({'pageInfo': {'results': 2}, 'results': [{'id': 1}]},
                     {'pageInfo': {'results': 2}, 'results': [{'id': 1}, {'id': 1}]},
                     {'pageInfo': {'results': 0}, 'results': [], 'serviceErrors': {'sonarr': True}}):
            reader.get.return_value = page
            with self.assertRaises(r.RecoveryError): r.requests(reader)

    def test_movie_existing_file_and_explicit_scope(self):
        value = snapshot()
        value['items'] = {'radarr:20': {'id': 20, 'tmdbId': 456, 'hasFile': False,
            'movieFileId': 0, 'digitalRelease': '2000-01-01T00:00:00Z', 'monitored': True}}
        value['requests'][0].update(type='movie', media={'status': 3, 'serviceId': 0, 'externalServiceId': 20, 'tmdbId': 456})
        self.assertEqual(aged(value)['summary']['proposals'], {'missing_movie_search': 1})
        value['items']['radarr:20'].update(hasFile=True, movieFileId=200, verified=False)
        self.assertEqual(aged(value)['summary']['proposals'], {})

    def test_notification_target_is_confined_before_connection(self):
        with mock.patch.object(r.http.client, 'HTTPConnection') as connection:
            for host, token in (('8.8.8.8', 'a'*64), ('192.168.1.163', '../wrong')):
                with self.assertRaises(r.RecoveryError): r.notify_ha({'host': host, 'webhook_id': token}, {})
            connection.assert_not_called()

    def test_transport_refuses_mutating_and_search_routes(self):
        reader = r.Reader.__new__(r.Reader); reader.arr = mock.Mock()
        for route in ('release?episodeId=2', 'command', 'queue/3?removeFromClient=true', '../command', 'history'):
            with self.assertRaises(r.RecoveryError): reader.get('sonarr', route)
        for mode in ('addurl', 'delete', 'set_config', 'resume'):
            with self.assertRaises(r.RecoveryError): reader.sab(mode)
        reader.arr.call.assert_not_called()
        with self.assertRaises(r.RecoveryError): r.NoRedirects().redirect_request(None)

    def test_path_traversal_and_symlink_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); base = root / 'library/.acquisition-staging/complete/sonarr'; base.mkdir(parents=True)
            outside = root / 'outside.mkv'; outside.write_bytes(b'file')
            (base / 'link.mkv').symlink_to(outside)
            for path in ('/storage/.acquisition-staging/complete/sonarr/link.mkv',
                         '/storage/.acquisition-staging/complete/sonarr/../../../../outside.mkv'):
                with self.assertRaises(r.RecoveryError): r.source_path(path, root)

    def test_bounded_header_title_is_read_without_scanning_media(self):
        def element(tag, data):
            return bytes.fromhex(tag) + bytes([0x80 | len(data)]) + data
        title = b'Imaginary Observatory S01E02 - Chapter 2'
        info = element('1549a966', element('7ba9', title))
        segment = bytes.fromhex('18538067') + b'\xff' + info
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'file.mkv'; path.write_bytes(segment + b'\0' * 1000000)
            self.assertEqual(r.mkv_title(path), title.decode())


if __name__ == '__main__':
    unittest.main()
