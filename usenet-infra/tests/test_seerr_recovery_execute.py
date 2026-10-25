import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
x = load('seerr-recovery-execute')
r = load('seerr-recovery')
NOW = 1800000000


def release():
    return {'approved': True, 'downloadAllowed': True, 'rejected': False, 'temporarilyRejected': False,
            'rejections': [], 'protocol': 'usenet', 'fullSeason': False, 'mappedSeriesId': 10,
            'mappedEpisodeInfo': [{'id': 20}], 'size': 3 * 1024**3, 'guid': 'fixture-guid',
            'indexerId': 1, 'title': 'Synthetic.Series.S01E02.1080p.WEB.H264-Fixture', 'releaseWeight': 0}


def scoped_snapshot():
    return {'requests': [{'id': 1, 'status': 2}], 'items': {'sonarr:10': {
        'monitored': True, 'seasons': [{'seasonNumber': 1, 'monitored': True}],
        'episodes': [{'id': 20, 'seasonNumber': 1, 'monitored': True, 'hasFile': False}]}}}


class ExecutorTests(unittest.TestCase):
    def test_release_cannot_override_rejections_or_overlap_existing_scope(self):
        self.assertTrue(x.eligible_release(release(), 10, 20, 100, set()))
        for change in [dict(approved=False), dict(rejected=True), dict(rejections=['Wrong quality']),
                dict(fullSeason=True), dict(mappedSeriesId=11), dict(mappedEpisodeInfo=[{'id': 20}, {'id': 21}]),
                dict(mappedEpisodeInfo=[]), dict(protocol='torrent'), dict(size=101*1024**3),
                dict(title='Synthetic AV1'), dict(title='Synthetic Extras'), dict(downloadAllowed=False)]:
            self.assertFalse(x.eligible_release(dict(release(), **change), 10, 20, 1000, set()))
        self.assertFalse(x.eligible_release(release(), 10, 20, 35, set()))
        self.assertFalse(x.eligible_release(release(), 10, 20, 100, {x.fingerprint(release())}))

    def test_budget_cooldown_and_uncertain_writes_survive_restarts(self):
        self.assertTrue(x.due({}, NOW))
        for entry in [{'attempts': [{'status': 'uncertain'}]}, {'attempts': [{'status': 'pending'}]},
                      {'attempts': [{'status': 'submitted'}]*3}, {'searches': 7},
                      {'last_search': NOW-3600}, {'last_search': NOW-23000, 'last_result': 'no_eligible_release'}]:
            self.assertFalse(x.due(json.loads(json.dumps(entry)), NOW))

    def test_completed_requests_and_processing_cannot_authorize_search(self):
        snapshot = scoped_snapshot()
        report = {'requests': [{'request_id': 1, 'app': 'sonarr', 'native_id': 10,
                               'proposals': [{'kind': 'missing_episode_search', 'ids': [20]}]}]}
        self.assertEqual(x.targets(snapshot, report), [(1, 10, 20)])
        for changed in [dict(snapshot, processing=1), dict(snapshot, blocked=['manual_pause']),
                        {'requests': [{'id': 1, 'status': 5}]}]:
            self.assertEqual(x.targets(changed, report), [])

    def test_series_season_episode_unmonitoring_and_existing_file_hold_dispatch(self):
        report = {'requests':[{'request_id':1,'app':'sonarr','native_id':10,
                    'proposals':[{'kind':'missing_episode_search','ids':[20]}]}]}
        for level in ('series', 'season', 'episode', 'file'):
            value = scoped_snapshot(); item = value['items']['sonarr:10']
            if level == 'series': item['monitored'] = False
            elif level == 'season': item['seasons'][0]['monitored'] = False
            elif level == 'episode': item['episodes'][0]['monitored'] = False
            else: item['episodes'][0]['episodeFileId'] = 42
            self.assertEqual(x.targets(value,report),[])

    def setup_run(self, folder):
        state = Path(folder); state.chmod(0o700)
        r.atomic_json(state/'executor-policy.json', {'schema':1, 'enabled':True, 'scope':'approved_missing_tv'})
        r.atomic_json(state/'report.json', {'generated_at':'2027-01-15T08:00:00+00:00'})
        reader = mock.Mock()
        reader.sab.return_value = {'noofslots': 0, 'paused':False, 'diskspace1':'100', 'diskspace2':'1000', 'slots':[]}
        snapshot = scoped_snapshot()
        report = {'requests':[{'request_id':1,'app':'sonarr','native_id':10,
                    'proposals':[{'kind':'missing_episode_search','ids':[20]}]}]}
        return state, reader, snapshot, report

    def test_changed_scope_after_lookup_prevents_grab(self):
        with tempfile.TemporaryDirectory() as folder:
            state, reader, snapshot, report = self.setup_run(folder)
            reader.arr.call.side_effect = lambda app, route, *args, **kw: (
                [] if route == 'command' else {'totalRecords':0,'records':[]} if route.startswith('queue?') else [release()])
            with mock.patch.object(r, 'collect', return_value=snapshot), mock.patch.object(r, 'stamp', return_value=NOW), \
                    mock.patch.object(r, 'plan', side_effect=[report, {'requests':[]}]):
                self.assertEqual(x.execute(reader,r,state,NOW)['status'], 'deferred')
                entry = r.private_json(state/'executor-journal.json')['episodes']['10:20']
                self.assertFalse(x.due(entry,NOW+59))
                self.assertTrue(x.due(entry,NOW+61))
                self.assertEqual(entry['attempts'], [])
            self.assertFalse(any('POST' in c.args for c in reader.arr.call.call_args_list))

    def test_write_ahead_and_timeout_never_blindly_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            state, reader, snapshot, report = self.setup_run(folder)
            posts = []
            def call(app, route, *args, **kw):
                if route.startswith('queue?'): return {'totalRecords':0,'records':[]}
                if route == 'command': return []
                if route.startswith('release?'): return [release()]
                self.assertEqual((app,route,args), ('sonarr','release',('POST', {'guid':'fixture-guid','indexerId':1})))
                saved = r.private_json(state/'executor-journal.json')
                self.assertEqual(saved['episodes']['10:20']['attempts'][0]['status'],'pending')
                posts.append(route)
                raise TimeoutError()
            reader.arr.call.side_effect = call
            with mock.patch.object(r,'collect',return_value=snapshot), mock.patch.object(r,'stamp',return_value=NOW), \
                    mock.patch.object(r,'plan',return_value=report):
                with self.assertRaisesRegex(r.RecoveryError,'grab_outcome_uncertain'):
                    x.execute(reader,r,state,NOW)
                self.assertEqual(x.execute(reader,r,state,NOW)['grabs'],0)
            self.assertEqual(posts,['release'])

    def test_successful_grab_is_journaled_and_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder:
            state, reader, snapshot, report = self.setup_run(folder)
            writes = []
            def call(app, route, *args, **kwargs):
                if route.startswith('queue?'): return {'totalRecords':0,'records':[]}
                if route == 'command': return []
                if route.startswith('release?'): return [release()]
                writes.append((app, route, args)); return release()
            reader.arr.call.side_effect = call
            with mock.patch.object(r, 'collect', return_value=snapshot), mock.patch.object(r,'stamp',return_value=NOW),                     mock.patch.object(r,'plan',return_value=report):
                self.assertEqual(x.execute(reader,r,state,NOW)['grabs'],1)
                self.assertEqual(x.execute(reader,r,state,NOW)['grabs'],0)
            self.assertEqual(len(writes),1)
            self.assertEqual(r.private_json(state/'executor-journal.json')['episodes']['10:20']['attempts'][0]['status'],'submitted')

    def test_queue_cap_and_manual_pause_stop_before_search(self):
        with tempfile.TemporaryDirectory() as folder:
            state, reader, snapshot, report = self.setup_run(folder)
            reader.arr.call.side_effect = lambda app, route: {'totalRecords':0,'records':[]} if route.startswith('queue?') else []
            with mock.patch.object(r,'collect',return_value=snapshot), mock.patch.object(r,'stamp',return_value=NOW),                     mock.patch.object(r,'plan',return_value=report):
                for update in ({'paused':True}, {'noofslots':3}):
                    reader.sab.return_value.update(paused=False,noofslots=0)
                    reader.sab.return_value.update(update)
                    with self.assertRaisesRegex(r.RecoveryError,'queue_or_pause_gate'):
                        x.execute(reader,r,state,NOW)
            self.assertFalse(any(c.args[1].startswith('release') for c in reader.arr.call.call_args_list))

    def test_unlinked_active_sab_job_holds_even_with_empty_native_queues(self):
        reader = mock.Mock()
        reader.arr.call.side_effect = lambda app,route: {'totalRecords':0,'records':[]} if route.startswith('queue?') else []
        reader.sab.return_value = {'noofslots':1,'paused':False,'diskspace1':'100','diskspace2':'100',
                                  'slots':[{'nzo_id':'unknown','status':'Downloading'}]}
        with self.assertRaisesRegex(r.RecoveryError,'unlinked_active_download'):
            x.native_gate(reader,r)

    def test_disabled_policy_and_stale_report_refuse_all_api_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            state, reader, snapshot, report = self.setup_run(folder)
            with mock.patch.object(r,'stamp',return_value=NOW-901):
                with self.assertRaisesRegex(r.RecoveryError,'report_stale'):x.execute(reader,r,state,NOW)
            self.assertEqual(reader.mock_calls,[])
            r.atomic_json(state/'executor-policy.json',{'schema':1,'enabled':False,'scope':'approved_missing_tv'})
            with self.assertRaisesRegex(r.RecoveryError,'executor_not_enabled'):x.execute(reader,r,state,NOW)
            self.assertEqual(reader.mock_calls,[])
