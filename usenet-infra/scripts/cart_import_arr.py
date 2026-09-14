"""Native, no-search imports for independently admitted cart completions.

This adapter never reads media payloads, removes files or changes download clients.
The coordinator owns admission, durable journaling, hashes and source reclamation.
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
from pathlib import Path, PurePosixPath
import re
import time
import unicodedata
from urllib.parse import urlencode

SOURCE_ROOT = Path('/srv/usenet/downloads/complete')
LIBRARY_ROOT = Path('/srv/usenet/library')
VERSIONS = {'radarr': '6.3.0.10514', 'sonarr': '4.0.19.2979'}
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.m4v', '.avi', '.ts'}
EPISODE_NUMBER = re.compile(r'(?<![a-z0-9])s\d{1,2}e\d{1,3}', re.I)


class CartImportHold(RuntimeError):
    """A fixed, nonsecret category suitable for a persistent operator hold."""


def require(condition, reason):
    if not condition:
        raise CartImportHold(reason)


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value)).casefold() if c.isalnum())


def series_title(parsed):
    info = parsed.get('seriesTitleInfo') or {}
    return info.get('titleWithoutYear') or parsed.get('seriesTitle')


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'native_timestamp_invalid')
        return parsed
    except (AttributeError, TypeError, ValueError):
        raise CartImportHold('native_timestamp_invalid') from None


def safe_path(value, root):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'path_not_confined')
    require(path != root and root in path.parents, 'path_not_confined')
    for part in [path, *path.parents]:
        require(not part.is_symlink(), 'symlink_not_supported')
        if part == root:
            break
    require(root.resolve() in path.resolve().parents, 'path_not_confined')
    return path


def signature(path):
    info = path.stat()
    return {'size': info.st_size, 'device': info.st_dev, 'inode': info.st_ino,
            'mtime_ns': str(info.st_mtime_ns)}


def api_source(path):
    return '/data/complete/' + path.relative_to(SOURCE_ROOT).as_posix()


def host_destination(app, path):
    relative = PurePosixPath(path)
    require(relative.is_absolute() and '..' not in relative.parts and
            PurePosixPath('/library') in relative.parents, 'native_path_invalid')
    root = LIBRARY_ROOT / ('Movies' if app == 'radarr' else 'TV')
    return safe_path(root / relative.relative_to('/library'), root)


class NativeArr:
    def __init__(self, api=None):
        if api is None:
            spec = importlib.util.spec_from_file_location('cart_discovery', Path(__file__).with_name('discovery-config.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            api = module.API()
        self.api = api

    def _call(self, app, endpoint, method='GET', body=None):
        try:
            return self.api.call(app, endpoint, method, body)
        except CartImportHold:
            raise
        except Exception:
            raise CartImportHold('arr_request_failed') from None

    def _records(self, app, endpoint):
        result = []
        for page in range(1, 102):
            response = self._call(app, endpoint + '?' + urlencode({'page': page, 'pageSize': 1000}))
            records = response.get('records', [])
            require(isinstance(records, list), 'arr_pagination_invalid')
            result.extend(records)
            if len(result) >= response.get('totalRecords', len(records)):
                return result
            require(bool(records), 'arr_pagination_incomplete')
        raise CartImportHold('arr_history_too_large')

    def owned_download_ids(self):
        return {record['downloadId'] for app in VERSIONS for endpoint in ('queue', 'history')
                for record in self._records(app, endpoint) if record.get('downloadId')}

    def _parse(self, app, title):
        resource = self._call(app, 'parse?' + urlencode({'title': title})) or {}
        parsed = resource.get('parsedMovieInfo' if app == 'radarr' else 'parsedEpisodeInfo')
        require(isinstance(parsed, dict), 'release_parse_ambiguous')
        return parsed

    def _identity(self, app, job, parsed):
        is_movie = app == 'radarr'
        title = (parsed.get('primaryMovieTitle') or parsed.get('movieTitle') or
                 next(iter(parsed.get('movieTitles') or []), None)) if is_movie else series_title(parsed)
        year = parsed.get('year') if is_movie else (parsed.get('seriesTitleInfo') or {}).get('year')
        require(bool(title), 'release_identity_missing')
        identity_key = 'tmdbId' if is_movie else 'tvdbId'
        durable = job.get(identity_key) or (job.get('metadata') or {}).get(identity_key)
        imdb = job.get('imdbId') or (job.get('metadata') or {}).get('imdbId')
        if durable:
            require(str(durable).isdigit() and int(durable) > 0, 'catalog_id_invalid')
            term = ('tmdb:' if is_movie else 'tvdb:') + str(durable)
        elif imdb and is_movie:
            require(bool(re.fullmatch(r'tt\d+', str(imdb))), 'catalog_id_invalid')
            term = 'imdb:' + imdb
        else:
            require(not is_movie or isinstance(year, int) and year >= 1900, 'movie_year_missing')
            term = title
        values = self._call(app, ('movie' if is_movie else 'series') + '/lookup?' + urlencode({'term': term}))
        require(isinstance(values, list), 'catalog_lookup_invalid')
        matches = [value for value in values if normalized(value.get('title')) == normalized(title)
                   and (not year or value.get('year') == year)
                   and (not durable or value.get(identity_key) == int(durable))
                   and (not imdb or value.get('imdbId') == imdb)]
        require(len(matches) == 1, 'catalog_identity_ambiguous')
        selected = matches[0]
        require(selected.get(identity_key, 0) > 0, 'catalog_identity_missing')
        return selected

    def _target(self, app, selected):
        movie = app == 'radarr'
        endpoint, key = ('movie', 'tmdbId') if movie else ('series', 'tvdbId')
        matches = [value for value in self._call(app, endpoint) if value.get(key) == selected[key]]
        require(len(matches) <= 1, 'native_target_ambiguous')
        if matches:
            target = matches[0]
            require(not target.get('monitored'), 'existing_target_monitored')
            created = False
        else:
            profiles = [p for p in self._call(app, 'qualityprofile') if p.get('name') == 'Any']
            require(len(profiles) == 1, 'native_profile_ambiguous')
            roots = [r for r in self._call(app, 'rootfolder') if r.get('path') == '/library' and r.get('accessible')]
            require(len(roots) == 1, 'native_root_unavailable')
            body = {k: copy.deepcopy(selected[k]) for k in ('title', 'year', key, 'titleSlug', 'seasons') if k in selected}
            body.update(rootFolderPath='/library', qualityProfileId=profiles[0]['id'], monitored=False)
            if movie:
                body.update(minimumAvailability='released', addOptions={'searchForMovie': False, 'monitor': 'none'})
            else:
                for season in body.get('seasons', []):
                    season['monitored'] = False
                body.update(seasonFolder=True, seriesType='standard', useSceneNumbering=False,
                            monitorNewItems='none', addOptions={'searchForMissingEpisodes': False,
                            'searchForCutoffUnmetEpisodes': False, 'monitor': 'none'})
            target = self._call(app, endpoint, 'POST', body)
            created = True
        require(target.get(key) == selected[key] and not target.get('monitored'), 'native_target_changed')
        require(normalized(target.get('title')) == normalized(selected['title']), 'native_target_changed')
        destination = host_destination(app, target['path'])
        require(not destination.exists() or destination.is_dir(), 'native_target_collision')
        # New metadata must never adopt an unrelated pre-existing directory.
        if created:
            require(not destination.exists() or not any(destination.iterdir()), 'native_target_collision')
        return target, created

    def _absence(self, plan):
        app = plan['app']
        require(plan['job_id'] not in self.owned_download_ids(), 'arr_owned_download')
        target = self._call(app, ('movie/' if app == 'radarr' else 'series/') + str(plan['target_id']))
        identity_key = 'tmdbId' if app == 'radarr' else 'tvdbId'
        require(target.get(identity_key) == plan['target_identity'] and target['path'] == plan['target_path']
                and not target.get('monitored'), 'native_target_changed')
        queue = self._records(app, 'queue')
        require(not any(q.get('movieId' if app == 'radarr' else 'seriesId') == target['id'] for q in queue), 'target_acquisition_active')
        destination = host_destination(app, target['path'])
        if app == 'radarr':
            require(not target.get('hasFile') and not target.get('movieFileId'), 'native_target_has_file')
            require(not destination.exists() or not any(destination.iterdir()), 'native_target_collision')
        else:
            require(target.get('seriesType', 'standard') == 'standard' and not target.get('useSceneNumbering'), 'tv_numbering_unsupported')
            episodes = {e['id']: e for e in self._call(app, 'episode?' + urlencode({'seriesId': target['id']}))}
            for file in plan['files']:
                for episode_id in file['episode_ids']:
                    episode = episodes.get(episode_id)
                    require(episode and episode.get('seriesId') == target['id'] and not episode.get('hasFile')
                            and not episode.get('episodeFileId'), 'native_episode_has_file')
            # Existing unrelated media could be overwritten even without an Arr file record.
            known = {str(host_destination(app, f['path'])) for f in self._call(app, 'episodefile?' + urlencode({'seriesId': target['id']}))}
            if destination.exists():
                for file in destination.rglob('*'):
                    require(not file.is_symlink(), 'native_target_collision')
                    if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS:
                        require(str(file) in known, 'native_unregistered_media')
        for file in plan['files']:
            source = safe_path(file['source'], SOURCE_ROOT)
            require(source.is_file() and signature(source) == file['signature'], 'source_changed')

    @staticmethod
    def _sample(candidate):
        rejections = candidate.get('rejections') or []
        return bool(rejections) and all(r.get('reason') in ('sample', 'sampleFile', 'Sample') or
               r.get('reason') is None and r.get('message') in ('Sample', 'Sample file') for r in rejections)

    def prepare(self, job, source_dir, source_files):
        require(isinstance(job.get('nzo_id'), str) and bool(job['nzo_id']), 'download_id_missing')
        require(job['nzo_id'] not in self.owned_download_ids(), 'arr_owned_download')
        directory = safe_path(source_dir, SOURCE_ROOT)
        require(directory.is_dir(), 'source_directory_missing')
        sources = [safe_path(p, SOURCE_ROOT) for p in source_files]
        require(all(directory in p.parents and p.is_file() for p in sources), 'source_not_in_job')
        require(len(set(sources)) == len(sources), 'duplicate_source')
        videos = [p for p in sources if p.suffix.lower() in VIDEO_EXTENSIONS]
        require(bool(videos), 'supported_video_missing')
        television = any(EPISODE_NUMBER.search(p.name) for p in videos)
        app = 'sonarr' if television else 'radarr'
        require(self._call(app, 'system/status').get('version') == VERSIONS[app], 'unsupported_arr_version')
        identity_source = next((p for p in videos if EPISODE_NUMBER.search(p.name)), videos[0])
        parsed = self._parse(app, identity_source.name if television else job.get('name', ''))
        selected = self._identity(app, job, parsed)
        target, created = self._target(app, selected)
        plan = {'schema_version': 1, 'app': app, 'job_id': job['nzo_id'],
                'prepared_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'target_id': target['id'], 'target_identity': selected['tvdbId' if television else 'tmdbId'],
                'target_path': target['path'], 'target_created': created, 'source_dir': str(directory),
                'files': [], 'skipped_sources': [], 'baseline_file_ids': []}
        if television:
            plan['baseline_file_ids'] = [f['id'] for f in self._call(app, 'episodefile?' + urlencode({'seriesId': target['id']}))]
        else:
            require(not target.get('hasFile') and not target.get('movieFileId'), 'native_target_has_file')
        candidates = self._call(app, 'manualimport?' + urlencode({'folder': api_source(directory), 'filterExistingFiles': 'true'}))
        require(isinstance(candidates, list), 'native_candidates_invalid')
        by_path = {api_source(p): p for p in videos}
        # File-valued SAB storage can share a parent with other completed jobs.
        # Only the coordinator's admitted source inventory may become payloads.
        candidates = [c for c in candidates if c.get('path') in by_path]
        require(len({c.get('path') for c in candidates}) == len(candidates), 'duplicate_candidate')
        require({c.get('path') for c in candidates} == set(by_path), 'candidate_inventory_mismatch')
        used_episodes = set()
        episode_records = self._call(app, 'episode?' + urlencode({'seriesId': target['id']})) if television else []
        # Sonarr queues its initial episode refresh after adding a new series.
        # Wait briefly for this native metadata operation, without any search.
        if television and created:
            for _ in range(30):
                if episode_records:
                    break
                time.sleep(2)
                episode_records = self._call(app, 'episode?' + urlencode({'seriesId': target['id']}))
        if television:
            require(bool(episode_records), 'episode_metadata_not_ready')
        for candidate in candidates:
            source = by_path[candidate['path']]
            if self._sample(candidate):
                plan['skipped_sources'].append(str(source))
                continue
            parsed_file = self._parse(app, source.name)
            item = {k: copy.deepcopy(candidate.get(k)) for k in ('path', 'folderName', 'quality', 'languages', 'releaseGroup', 'indexerFlags')}
            item['indexerFlags'] = item['indexerFlags'] or 0
            item['releaseGroup'] = item['releaseGroup'] or ''
            require((item['quality'] or {}).get('quality', {}).get('id', 0) > 0, 'quality_unknown')
            require(item['languages'] and all(language.get('id', 0) > 0 for language in item['languages']), 'language_unknown')
            mapping = {'source': str(source), 'api_source': candidate['path'], 'signature': signature(source)}
            if television:
                require(bool(EPISODE_NUMBER.search(source.name)), 'mixed_or_unnumbered_tv')
                require(normalized(series_title(parsed_file)) == normalized(selected['title']), 'episode_series_mismatch')
                season, numbers = parsed_file.get('seasonNumber'), parsed_file.get('episodeNumbers') or []
                require(isinstance(season, int) and season > 0 and numbers and all(isinstance(n, int) and n > 0 for n in numbers)
                        and not any(parsed_file.get(k) for k in ('isDaily', 'isAbsoluteNumbering', 'special', 'isMultiSeason', 'isSeasonExtra', 'isSplitEpisode')),
                        'tv_numbering_unsupported')
                episodes = [e for e in episode_records if e.get('seasonNumber') == season and e.get('episodeNumber') in numbers]
                require(len(episodes) == len(set(numbers)) and {e['episodeNumber'] for e in episodes} == set(numbers)
                        and all(e.get('seriesId') == target['id'] for e in episodes), 'episodes_not_unique')
                ids = sorted(e['id'] for e in episodes)
                require(not used_episodes.intersection(ids), 'episodes_overlap')
                used_episodes.update(ids)
                mapping['episode_ids'] = ids
                item.update(seriesId=target['id'], seasonNumber=season, episodeIds=ids,
                            releaseType='multiEpisode' if len(ids) > 1 else 'singleEpisode')
            else:
                title = parsed_file.get('movieTitle') or parsed_file.get('primaryMovieTitle') or next(iter(parsed_file.get('movieTitles') or []), '')
                require(normalized(title) == normalized(selected['title']) and parsed_file.get('year') == selected.get('year'), 'movie_source_identity_mismatch')
                item['movieId'] = target['id']
            checked = self._call(app, 'manualimport', 'POST', [item])
            require(isinstance(checked, list) and len(checked) == 1 and not checked[0].get('rejections'), 'candidate_rejected')
            remapped = checked[0]
            if television:
                require(sorted(e['id'] for e in remapped.get('episodes', [])) == mapping['episode_ids'], 'episode_remap_mismatch')
            else:
                require(remapped.get('movie', {}).get('id') == target['id'], 'movie_remap_mismatch')
            require(remapped.get('path') == item['path'], 'candidate_path_changed')
            mapping['payload'] = item
            plan['files'].append(mapping)
        require(bool(plan['files']) and (television or len(plan['files']) == 1), 'unsupported_media_count')
        plan['payload'] = {'name': 'ManualImport', 'importMode': 'copy', 'files': [f['payload'] for f in plan['files']]}
        self._absence(plan)
        return plan

    def submit(self, plan):
        require('command_id' not in plan, 'import_already_submitted')
        require(plan.get('schema_version') == 1 and plan.get('app') in VERSIONS
                and plan.get('payload') == {'name': 'ManualImport', 'importMode': 'copy',
                'files': [f['payload'] for f in plan['files']]}
                and all(not f['payload'].get('downloadId') and f['payload'].get('path') == f['api_source']
                        and f['api_source'] == api_source(Path(f['source'])) for f in plan['files']), 'import_plan_invalid')
        self._absence(plan)
        response = self._call(plan['app'], 'command', 'POST', plan['payload'])
        require(isinstance(response.get('id'), int), 'command_id_missing')
        plan['command_id'] = response['id']
        return response['id']

    @staticmethod
    def _matches_command(plan, command):
        body = command.get('body') or {}
        wanted = plan['payload']
        if command.get('name') != 'ManualImport' or str(body.get('importMode', '')).lower() != 'copy':
            return False
        actual = body.get('files') or []
        if len(actual) != len(wanted['files']):
            return False
        for candidate, expected in zip(actual, wanted['files']):
            if candidate.get('downloadId') or any(candidate.get(k) != v for k, v in expected.items() if k != 'seasonNumber'):
                return False
        return True

    def command(self, plan, command_id):
        if command_id is None:
            candidates = [c for c in self._call(plan['app'], 'command') if self._matches_command(plan, c)
                          and timestamp(c.get('queued') or c.get('started')) >= timestamp(plan['prepared_at']).replace(microsecond=0)]
            require(len(candidates) == 1, 'uncertain_import_submission')
            command_id = candidates[0]['id']
        command = self._call(plan['app'], 'command/' + str(command_id))
        require(self._matches_command(plan, command), 'import_command_mismatch')
        plan['command_id'] = command_id
        state = {k: command.get(k) for k in ('id', 'status', 'started', 'ended', 'result')}
        if command.get('status') in ('failed', 'aborted', 'cancelled', 'orphaned') or command.get('result') == 'failed':
            raise CartImportHold('native_import_failed')
        return state

    def imported_files(self, plan):
        require(isinstance(plan.get('command_id'), int), 'import_command_missing')
        command = self.command(plan, plan['command_id'])
        # Pinned CommandRepository.End persists status but not Result. After the
        # five-minute in-memory eviction, a successful command reads "unknown".
        # Completion alone is insufficient: the native file ownership checks
        # below and coordinator's independent byte verification remain required.
        require(command['status'] == 'completed' and command.get('result') in ('successful', 'unknown'), 'native_import_incomplete')
        started = timestamp(command.get('started'))
        app = plan['app']
        target = self._call(app, ('movie/' if app == 'radarr' else 'series/') + str(plan['target_id']))
        key = 'tmdbId' if app == 'radarr' else 'tvdbId'
        require(target.get(key) == plan['target_identity'] and target['path'] == plan['target_path'], 'native_target_changed')
        if app == 'radarr':
            records = [target.get('movieFile') or {}]
        else:
            records = self._call(app, 'episodefile?' + urlencode({'seriesId': plan['target_id']}))
        histories = self._records(app, 'history') if app == 'sonarr' else []
        outputs = []
        for mapping in plan['files']:
            source = safe_path(mapping['source'], SOURCE_ROOT)
            origin = PurePosixPath(source.parent.name) / source.name
            candidates = [r for r in records if r.get('id') not in plan['baseline_file_ids']
                          and r.get('id', 0) > 0 and r.get('movieId' if app == 'radarr' else 'seriesId') == plan['target_id']
                          and (app == 'sonarr' or r.get('originalFilePath') == str(origin))
                          and r.get('size') == mapping['signature']['size']]
            if app == 'sonarr':
                # Sonarr 4's EpisodeFileResource has no originalFilePath. Native
                # per-episode import history supplies exact dropped/imported paths.
                linked_ids = {e.get('episodeFileId') for e in self._call(app, 'episode?' + urlencode({'seriesId': plan['target_id']}))
                              if e['id'] in mapping['episode_ids']}
                candidates = [r for r in candidates if r['id'] in linked_ids]
            require(len(candidates) == 1, 'imported_file_ownership_unproven')
            record = candidates[0]
            require(timestamp(record.get('dateAdded')) >= started, 'imported_file_predates_command')
            path = str(PurePosixPath(plan['target_path']) / record.get('relativePath', ''))
            require(record.get('relativePath') and record.get('path', path) == path, 'imported_file_path_mismatch')
            destination = host_destination(app, path)
            require(destination.is_file() and destination.stat().st_size == mapping['signature']['size'], 'imported_file_missing_or_size_changed')
            if app == 'sonarr':
                episodes = self._call(app, 'episode?' + urlencode({'seriesId': plan['target_id']}))
                linked = sorted(e['id'] for e in episodes if e.get('episodeFileId') == record['id'])
                require(linked == mapping['episode_ids'], 'imported_episode_mapping_mismatch')
                evidenced = set()
                for event in histories:
                    data = {k.casefold(): v for k, v in (event.get('data') or {}).items()}
                    if (event.get('eventType') == 'downloadFolderImported' and event.get('seriesId') == plan['target_id']
                            and timestamp(event.get('date')) >= started and not event.get('downloadId')
                            and str(data.get('fileid')) == str(record['id'])
                            and data.get('droppedpath') == mapping['api_source'] and data.get('importedpath') == path):
                        evidenced.add(event.get('episodeId'))
                require(evidenced == set(mapping['episode_ids']), 'episode_import_history_unproven')
            outputs.append({'source': str(source), 'destination': str(destination), 'size': mapping['signature']['size']})
        require(len({o['destination'] for o in outputs}) == len(outputs), 'duplicate_import_destination')
        return outputs
