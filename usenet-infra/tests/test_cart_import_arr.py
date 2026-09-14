from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import cart_import_arr as adapter


QUALITY = {'quality': {'id': 19, 'name': 'Bluray-2160p'}, 'revision': {'version': 1}}
LANGUAGES = [{'id': 1, 'name': 'English'}]


class FakeAPI:
    def __init__(self, root, television=False):
        self.root, self.television = root, television
        self.calls = []
        self.existing = []
        self.queue = {'radarr': [], 'sonarr': []}
        self.history = {'radarr': [], 'sonarr': []}
        self.commands = {}
        self.files = []
        self.episodes = [{'id': 101, 'seriesId': 7, 'seasonNumber': 1, 'episodeNumber': 1, 'hasFile': False, 'episodeFileId': 0},
                         {'id': 102, 'seriesId': 7, 'seasonNumber': 1, 'episodeNumber': 2, 'hasFile': False, 'episodeFileId': 0}]
        self.extra_lookup = []
        self.remap_wrong = False
        self.reject = False
        self.fail_endpoint = None

    def parsed(self, app, title):
        if app == 'radarr':
            return {'parsedMovieInfo': {'movieTitle': 'Example Movie', 'movieTitles': ['Example Movie'], 'year': 2026}}
        number = 2 if 'E02' in title else 1
        return {'parsedEpisodeInfo': {'seriesTitle': 'Example Show', 'seriesTitleInfo': {'year': 2020},
                                     'seasonNumber': 1, 'episodeNumbers': [number]}}

    def call(self, app, endpoint, method='GET', body=None):
        self.calls.append((app, endpoint, method, copy.deepcopy(body)))
        if endpoint == self.fail_endpoint:
            raise RuntimeError('credential and private response must not escape')
        route = urlsplit(endpoint).path
        query = parse_qs(urlsplit(endpoint).query)
        if route in ('queue', 'history'):
            values = self.queue[app] if route == 'queue' else self.history[app]
            return {'records': copy.deepcopy(values), 'totalRecords': len(values)}
        if route == 'system/status':
            return {'version': adapter.VERSIONS[app]}
        if route == 'parse':
            return self.parsed(app, query['title'][0])
        if route in ('movie/lookup', 'series/lookup'):
            selected = {'title': 'Example Show', 'year': 2020, 'tvdbId': 800, 'seasons': [{'seasonNumber': 1, 'monitored': True}]} if app == 'sonarr' else {'title': 'Example Movie', 'year': 2026, 'tmdbId': 900}
            return [selected, *copy.deepcopy(self.extra_lookup)]
        if route in ('movie', 'series'):
            if method == 'GET':
                return copy.deepcopy(self.existing)
            title = 'Example Show' if app == 'sonarr' else 'Example Movie'
            self.existing = [{**copy.deepcopy(body), 'id': 7, 'title': title, 'path': '/library/' + title,
                              'hasFile': False, 'movieFileId': 0}]
            return copy.deepcopy(self.existing[0])
        if route in ('movie/7', 'series/7'):
            return copy.deepcopy(self.existing[0])
        if route == 'qualityprofile':
            return [{'id': 1, 'name': 'Any'}]
        if route == 'rootfolder':
            return [{'id': 1, 'path': '/library', 'accessible': True}]
        if route == 'episode':
            return copy.deepcopy(self.episodes)
        if route == 'episodefile':
            return copy.deepcopy(self.files)
        if route == 'manualimport':
            if method == 'GET':
                folder = adapter.SOURCE_ROOT / Path(query['folder'][0]).relative_to('/data/complete')
                return [{'path': adapter.api_source(path), 'folderName': path.parent.name, 'quality': copy.deepcopy(QUALITY),
                         'languages': copy.deepcopy(LANGUAGES), 'releaseGroup': 'test', 'indexerFlags': 0,
                         'rejections': [{'reason': 'sample', 'message': 'Sample'}] if path.stem == 'sample' else []}
                        for path in sorted(folder.iterdir()) if path.suffix == '.mkv']
            item = copy.deepcopy(body[0])
            item['rejections'] = [{'reason': 'unknown'}] if self.reject else []
            if app == 'radarr':
                item['movie'] = {'id': 99 if self.remap_wrong else 7}
            else:
                item['episodes'] = [{'id': i} for i in ([999] if self.remap_wrong else body[0]['episodeIds'])]
            return [item]
        if route == 'command':
            if method == 'GET':
                return copy.deepcopy(list(self.commands.values()))
            self.commands[42] = {'id': 42, 'name': 'ManualImport', 'body': copy.deepcopy(body), 'status': 'started',
                                 'result': 'unknown', 'queued': '2099-01-01T00:00:00Z', 'started': '2099-01-01T00:00:00Z'}
            return copy.deepcopy(self.commands[42])
        if route.startswith('command/'):
            return copy.deepcopy(self.commands[int(route.split('/')[1])])
        raise AssertionError((app, endpoint, method, body))


class NativeArrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.scratch = self.root / 'complete'
        self.library = self.root / 'library'
        self.directory = self.scratch / 'Example.Movie.2026'
        self.directory.mkdir(parents=True)
        (self.library / 'Movies').mkdir(parents=True)
        (self.library / 'TV').mkdir()
        self.source = self.directory / 'Example.Movie.2026.mkv'
        self.source.write_bytes(b'complete media fixture')
        self.patches = [mock.patch.object(adapter, 'SOURCE_ROOT', self.scratch), mock.patch.object(adapter, 'LIBRARY_ROOT', self.library)]
        for patch in self.patches:
            patch.start()
        self.api = FakeAPI(self.root)
        self.arr = adapter.NativeArr(self.api)
        self.job = {'nzo_id': 'new-cart-id', 'name': 'Example.Movie.2026'}

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.temp.cleanup()

    def prepare(self):
        return self.arr.prepare(self.job, self.directory, list(self.directory.iterdir()))

    def television(self):
        self.source.unlink()
        self.source = self.directory / 'Example.Show.S01E01.mkv'
        self.source.write_bytes(b'episode fixture')
        self.api.television = True

    def complete(self, plan):
        cid = self.arr.submit(plan)
        command = self.api.commands[cid]
        command.update(status='completed', result='successful', ended='2099-01-01T00:00:30Z')
        for index, mapping in enumerate(plan['files']):
            source = Path(mapping['source'])
            destination = adapter.host_destination(plan['app'], plan['target_path']) / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            record = {'id': 21 + index, 'movieId' if plan['app'] == 'radarr' else 'seriesId': 7,
                      'relativePath': source.name, 'path': plan['target_path'] + '/' + source.name,
                      'originalFilePath': source.parent.name + '/' + source.name,
                      'dateAdded': command['started'], 'size': source.stat().st_size}
            if plan['app'] == 'radarr':
                self.api.existing[0].update(hasFile=True, movieFileId=record['id'], movieFile=record)
            else:
                record.pop('originalFilePath')
                self.api.files.append(record)
                for episode in self.api.episodes:
                    if episode['id'] in mapping['episode_ids']:
                        episode.update(hasFile=True, episodeFileId=record['id'])
                        self.api.history['sonarr'].append({'eventType': 'downloadFolderImported', 'seriesId': 7,
                            'episodeId': episode['id'], 'date': command['ended'], 'downloadId': None,
                            'data': {'droppedPath': mapping['api_source'], 'importedPath': record['path'], 'fileId': str(record['id'])}})
        return cid

    def test_movie_copy_has_no_client_id_or_search_and_preserves_source(self):
        plan = self.prepare()
        add = next(call[3] for call in self.api.calls if call[1] == 'movie' and call[2] == 'POST')
        self.assertFalse(add['monitored'])
        self.assertFalse(add['addOptions']['searchForMovie'])
        self.complete(plan)
        self.assertEqual(plan['payload']['importMode'], 'copy')
        self.assertNotIn('downloadId', plan['payload']['files'][0])
        result = self.arr.imported_files(plan)
        self.assertEqual(result[0]['source'], str(self.source))
        self.assertEqual(Path(result[0]['destination']).read_bytes(), self.source.read_bytes())
        self.assertTrue(self.source.exists())
        self.assertIsInstance(plan['files'][0]['signature']['mtime_ns'], str)
        self.assertFalse(any(call[2] == 'DELETE' for call in self.api.calls))

    def test_ambiguous_identity_does_not_add(self):
        self.api.extra_lookup = [{'title': 'Example Movie', 'year': 2026, 'tmdbId': 901}]
        with self.assertRaisesRegex(adapter.CartImportHold, 'catalog_identity_ambiguous'):
            self.prepare()
        self.assertFalse(any(call[2] == 'POST' for call in self.api.calls))

    def test_durable_catalog_id_disambiguates_exact_title(self):
        self.api.extra_lookup = [{'title': 'Example Movie', 'year': 2026, 'tmdbId': 901}]
        self.job['tmdbId'] = 900
        self.assertEqual(self.prepare()['target_identity'], 900)

    def test_retained_history_ownership_blocks_even_when_queue_empty(self):
        self.api.history['sonarr'] = [{'downloadId': self.job['nzo_id']}]
        with self.assertRaisesRegex(adapter.CartImportHold, 'arr_owned_download'):
            self.prepare()

    def test_existing_canonical_file_is_never_upgraded(self):
        self.api.existing = [{'id': 7, 'title': 'Example Movie', 'tmdbId': 900, 'path': '/library/Example Movie',
                              'monitored': False, 'hasFile': True, 'movieFileId': 9}]
        with self.assertRaisesRegex(adapter.CartImportHold, 'native_target_has_file'):
            self.prepare()
        self.assertFalse(any(call[1] == 'command' and call[2] == 'POST' for call in self.api.calls))

    def test_destination_collision_created_after_prepare_blocks_submit(self):
        plan = self.prepare()
        destination = self.library / 'Movies/Example Movie'
        destination.mkdir()
        (destination / 'unrelated.mkv').write_bytes(b'owned by someone else')
        with self.assertRaisesRegex(adapter.CartImportHold, 'native_target_collision'):
            self.arr.submit(plan)

    def test_source_metadata_change_blocks_submit(self):
        plan = self.prepare()
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(adapter.CartImportHold, 'source_changed'):
            self.arr.submit(plan)

    def test_new_arr_ownership_blocks_submit(self):
        plan = self.prepare()
        self.api.queue['radarr'] = [{'downloadId': self.job['nzo_id'], 'movieId': 7}]
        with self.assertRaisesRegex(adapter.CartImportHold, 'arr_owned_download'):
            self.arr.submit(plan)

    def test_sample_and_sidecar_are_preserved_and_not_imported(self):
        sample = self.directory / 'sample.mkv'
        sample.write_bytes(b'sample')
        sidecar = self.directory / 'info.nfo'
        sidecar.write_text('retained sidecar')
        plan = self.prepare()
        self.assertEqual(plan['skipped_sources'], [str(sample)])
        self.assertEqual(len(plan['files']), 1)
        self.assertTrue(sample.exists() and sidecar.exists())

    def test_exact_file_selection_never_adopts_neighboring_video(self):
        neighbor = self.directory / 'Other.Movie.2025.mkv'
        neighbor.write_bytes(b'another completed job')
        plan = self.arr.prepare(self.job, self.directory, [self.source])
        self.assertEqual([f['source'] for f in plan['files']], [str(self.source)])
        self.assertEqual([f['path'] for f in plan['payload']['files']], [adapter.api_source(self.source)])
        self.assertTrue(neighbor.exists())

    def test_real_rejection_and_wrong_mapping_hold(self):
        self.api.reject = True
        with self.assertRaisesRegex(adapter.CartImportHold, 'candidate_rejected'):
            self.prepare()
        self.api.reject = False
        self.api.remap_wrong = True
        with self.assertRaisesRegex(adapter.CartImportHold, 'movie_remap_mismatch'):
            self.prepare()

    def test_failed_command_does_not_return_imported_files(self):
        plan = self.prepare()
        cid = self.arr.submit(plan)
        self.api.commands[cid].update(status='completed', result='failed')
        with self.assertRaisesRegex(adapter.CartImportHold, 'native_import_failed'):
            self.arr.imported_files(plan)

    def test_evicted_completed_command_with_unknown_result_requires_owned_file(self):
        plan = self.prepare()
        self.complete(plan)
        self.api.commands[42]['result'] = 'unknown'
        self.assertEqual(len(self.arr.imported_files(plan)), 1)
        self.api.existing[0]['movieFile']['originalFilePath'] = 'another-job/movie.mkv'
        with self.assertRaisesRegex(adapter.CartImportHold, 'imported_file_ownership_unproven'):
            self.arr.imported_files(plan)

    def test_orphaned_native_copy_holds_without_resubmit(self):
        plan = self.prepare()
        cid = self.arr.submit(plan)
        self.api.commands[cid]['status'] = 'orphaned'
        with self.assertRaisesRegex(adapter.CartImportHold, 'native_import_failed'):
            self.arr.command(plan, cid)
        self.assertEqual(sum(c[1] == 'command' and c[2] == 'POST' for c in self.api.calls), 1)

    def test_uncertain_submit_recovers_exact_command_without_second_post(self):
        plan = self.prepare()
        cid = self.arr.submit(plan)
        plan.pop('command_id')
        recovered = self.arr.command(plan, None)
        self.assertEqual(recovered['id'], cid)
        self.assertEqual(sum(c[1] == 'command' and c[2] == 'POST' for c in self.api.calls), 1)

    def test_ambiguous_command_recovery_holds(self):
        plan = self.prepare()
        self.arr.submit(plan)
        self.api.commands[43] = {**copy.deepcopy(self.api.commands[42]), 'id': 43}
        plan.pop('command_id')
        with self.assertRaisesRegex(adapter.CartImportHold, 'uncertain_import_submission'):
            self.arr.command(plan, None)

    def test_same_size_existing_path_is_not_import_ownership(self):
        plan = self.prepare()
        self.complete(plan)
        self.api.existing[0]['movieFile']['originalFilePath'] = 'some-other-job/same.mkv'
        with self.assertRaisesRegex(adapter.CartImportHold, 'imported_file_ownership_unproven'):
            self.arr.imported_files(plan)

    def test_episodic_tv_maps_each_native_episode_without_search(self):
        self.television()
        second = self.directory / 'Example.Show.S01E02.mkv'
        second.write_bytes(b'episode two')
        plan = self.prepare()
        self.assertEqual([f['episode_ids'] for f in plan['files']], [[101], [102]])
        add = next(c[3] for c in self.api.calls if c[1] == 'series' and c[2] == 'POST')
        self.assertFalse(add['addOptions']['searchForMissingEpisodes'])
        self.assertFalse(add['seasons'][0]['monitored'])
        self.complete(plan)
        self.assertEqual(len(self.arr.imported_files(plan)), 2)

    def test_episode_remapping_mismatch_holds(self):
        self.television()
        self.api.remap_wrong = True
        with self.assertRaisesRegex(adapter.CartImportHold, 'episode_remap_mismatch'):
            self.prepare()

    def test_post_import_wrong_episode_links_hold(self):
        self.television()
        plan = self.prepare()
        self.complete(plan)
        self.api.episodes[1]['episodeFileId'] = self.api.files[0]['id']
        with self.assertRaisesRegex(adapter.CartImportHold, 'imported_episode_mapping_mismatch'):
            self.arr.imported_files(plan)

    def test_missing_episode_record_holds(self):
        self.television()
        self.api.episodes = []
        with mock.patch.object(adapter.time, 'sleep') as sleep, self.assertRaisesRegex(adapter.CartImportHold, 'episode_metadata_not_ready'):
            self.prepare()
        self.assertEqual(sleep.call_count, 30)
        with self.assertRaisesRegex(adapter.CartImportHold, 'episode_metadata_not_ready'):
            self.prepare()
        self.assertEqual(sum(c[1] == 'series' and c[2] == 'POST' for c in self.api.calls), 1)

    def test_new_tv_metadata_waits_for_native_episode_refresh(self):
        self.television()
        expected = self.api.episodes
        self.api.episodes = []
        with mock.patch.object(adapter.time, 'sleep', side_effect=lambda _: setattr(self.api, 'episodes', expected)) as sleep:
            plan = self.prepare()
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(plan['files'][0]['episode_ids'], [101])

    def test_tv_sample_first_does_not_select_identity_from_sample(self):
        self.television()
        sample = self.directory / 'sample.mkv'
        sample.write_bytes(b'sample')
        plan = self.arr.prepare(self.job, self.directory, [sample, self.source])
        first_parse = next(c for c in self.api.calls if c[1].startswith('parse?'))
        self.assertIn('S01E01', first_parse[1])
        self.assertEqual(plan['skipped_sources'], [str(sample)])

    def test_missing_command_timestamp_cannot_establish_ownership(self):
        plan = self.prepare()
        self.complete(plan)
        self.api.commands[42]['started'] = None
        with self.assertRaisesRegex(adapter.CartImportHold, 'native_timestamp_invalid'):
            self.arr.imported_files(plan)

    def test_timestamp_offsets_are_compared_as_instants(self):
        plan = self.prepare()
        self.complete(plan)
        self.api.existing[0]['movieFile']['dateAdded'] = '2098-12-31T19:00:01-05:00'
        self.assertEqual(len(self.arr.imported_files(plan)), 1)

    def test_tv_import_requires_native_history_source_path(self):
        self.television()
        plan = self.prepare()
        self.complete(plan)
        self.api.history['sonarr'][0]['data']['droppedPath'] = '/data/complete/another-job.mkv'
        with self.assertRaisesRegex(adapter.CartImportHold, 'episode_import_history_unproven'):
            self.arr.imported_files(plan)

    def test_tv_year_qualified_parse_uses_native_title_without_year(self):
        self.television()
        old_parse = self.api.parsed
        def parsed(app, title):
            result = old_parse(app, title)
            if app == 'sonarr':
                result['parsedEpisodeInfo']['seriesTitle'] = 'Example Show 2020'
                result['parsedEpisodeInfo']['seriesTitleInfo']['titleWithoutYear'] = 'Example Show'
            return result
        self.api.parsed = parsed
        self.assertEqual(self.prepare()['target_identity'], 800)

    def test_symlink_source_is_refused(self):
        outside = self.root / 'elsewhere.mkv'
        outside.write_bytes(b'outside')
        self.source.unlink()
        self.source.symlink_to(outside)
        with self.assertRaisesRegex(adapter.CartImportHold, 'symlink_not_supported'):
            self.prepare()

    def test_api_error_is_sanitized(self):
        self.api.fail_endpoint = 'system/status'
        with self.assertRaisesRegex(adapter.CartImportHold, '^arr_request_failed$'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
