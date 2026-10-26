#!/usr/bin/env python3
"""Report-only recovery for explicitly approved Seerr requests.

No search, grab, import, rename, deletion or acquisition-setting write exists.
The only remote write is an optional, confined Home Assistant notification.
Exact media evidence stays in private runtime reports, never stdout.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import fcntl
import hashlib
import http.client
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import urllib.parse
import urllib.request

ROOT = Path('/srv/usenet')
STATE = ROOT / 'config/catalog/seerr-recovery'
MODE = 'report-only'
GRACE_SECONDS = 900
MAX_ROWS = 5000
FILE_CHECK_SECONDS = 3600


class RecoveryError(Exception):
    """Only fixed, non-sensitive categories may be returned to operators."""


def require(ok, reason):
    if not ok:
        raise RecoveryError(reason)


def stamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def private_json(path, application_settings=False):
    info = path.lstat()
    # Seerr writes mode-0644 settings inside its protected application directory.
    mask = 0o022 if application_settings else 0o027
    if application_settings:
        require(not path.parent.stat().st_mode & 0o007, 'application_directory_not_private')
    require(stat.S_ISREG(info.st_mode) and not info.st_mode & mask and info.st_size <= 32 * 1024**2,
            'private_state_invalid')
    return json.loads(path.read_text())


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.report-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RecoveryError('redirect_refused')


class Reader:
    """Explicit read-route allowlist, including rejection of GET-triggered searches."""
    ROUTES = {
        'seerr': r'request\?take=100&skip=\d+&sort=added&sortDirection=asc',
        'sonarr': r'(?:series|episode\?seriesId=\d+|episodefile\?seriesId=\d+|queue\?page=\d+&pageSize=1000&includeUnknownSeriesItems=true|manualimport\?downloadId=[A-Za-z0-9_-]+&filterExistingFiles=true|health)',
        'radarr': r'(?:movie|queue\?page=\d+&pageSize=1000&includeUnknownMovieItems=true|health)',
    }

    def __init__(self, root=ROOT):
        spec = importlib.util.spec_from_file_location('recovery_discovery', root / 'libexec/discovery-config.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.arr = module.API(root / 'config')
        self.settings = private_json(root / 'config/seerr/settings.json', application_settings=True)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
        self.root = root

    def get(self, app, route):
        require(app in self.ROUTES and re.fullmatch(self.ROUTES[app], route), 'read_route_refused')
        try:
            if app != 'seerr':
                return self.arr.call(app, route, 'GET')
            request = urllib.request.Request('http://127.0.0.1:5055/api/v1/' + route,
                headers={'X-API-Key': self.settings['main']['apiKey']}, method='GET')
            with self.opener.open(request, timeout=45) as response:
                raw = response.read(8 * 1024**2 + 1)
                require(len(raw) <= 8 * 1024**2, 'response_too_large')
                return json.loads(raw)
        except RecoveryError:
            raise
        except Exception:
            raise RecoveryError('native_read_failed') from None

    def sab(self, mode):
        require(mode in ('queue', 'history'), 'sab_read_mode_refused')
        payload = {'mode': mode, 'apikey': self.arr.sab_key, 'output': 'json', 'limit': 1000}
        if mode == 'history':
            payload.update(start=0, archive=0)
        request = urllib.request.Request('http://127.0.0.1:8080/api',
            data=urllib.parse.urlencode(payload).encode(), method='POST')
        try:
            with self.opener.open(request, timeout=45) as response:
                raw = response.read(8 * 1024**2 + 1)
                require(len(raw) <= 8 * 1024**2, 'response_too_large')
                return json.loads(raw)[mode]
        except RecoveryError:
            raise
        except Exception:
            raise RecoveryError('sab_read_failed') from None


def requests(reader):
    rows, total = [], None
    for skip in range(0, MAX_ROWS, 100):
        page = reader.get('seerr', f'request?take=100&skip={skip}&sort=added&sortDirection=asc')
        count = page['pageInfo']['results']
        require(type(count) is int and 0 <= count <= MAX_ROWS, 'request_count_invalid')
        require(total is None or total == count, 'requests_changed_during_scan')
        require(not any(page.get('serviceErrors', {}).values()), 'seerr_service_unavailable')
        total = count
        rows.extend(page['results'])
        if len(rows) >= total:
            break
        require(len(page['results']) == 100, 'requests_truncated')
    require(len(rows) == total and len({r['id'] for r in rows}) == total, 'requests_truncated')
    # Never persist requestedBy, email, credentials, or discovery data.
    return [{k: r.get(k) for k in ('id', 'type', 'status', 'is4k', 'serverId', 'media', 'seasons')}
            for r in rows]


def bind_request(request, settings, items):
    """Seerr's approval and external IDs authorize scope, never title similarity."""
    if request.get('status') not in (2, 5) or request.get('is4k') is not False:
        return None, 'request_not_approved_single_copy'
    media = request.get('media') or {}
    if media.get('status') in (6, 7):
        return None, 'media_blocked_or_deleted'
    app = {'tv': 'sonarr', 'movie': 'radarr'}.get(request.get('type'))
    if not app:
        return None, 'unsupported_request_type'
    servers = settings.get(app, [])
    if len(servers) != 1 or media.get('serviceId') != servers[0]['id']:
        return None, 'request_server_mismatch'
    if request.get('serverId') not in (None, servers[0]['id']):
        return None, 'request_server_mismatch'
    identity = media.get('externalServiceId')
    item = items.get(f'{app}:{identity}')
    external = 'tvdbId' if app == 'sonarr' else 'tmdbId'
    if not item or not media.get(external) or item.get(external) != media[external]:
        return None, 'request_binding_missing'
    seasons = {s['seasonNumber'] for s in request.get('seasons') or [] if s.get('status') in (2, 5)}
    if app == 'sonarr' and not seasons:
        return None, 'no_approved_seasons'
    return (app, item, seasons), None


def confined(path, base):
    candidate = Path(path)
    require(candidate.is_absolute() and not candidate.is_symlink(), 'unsafe_media_path')
    resolved = candidate.resolve(strict=True)
    require(resolved.is_relative_to(base.resolve(strict=True)), 'unsafe_media_path')
    require(resolved.is_file(), 'media_file_missing')
    return resolved


def library_path(path, app, root=ROOT):
    value = Path(path)
    if str(value).startswith('/storage/'):
        candidate = root / 'library' / value.relative_to('/storage')
    elif str(value).startswith('/library/'):
        candidate = root / 'library' / ('TV' if app == 'sonarr' else 'Movies') / value.relative_to('/library')
    else:
        raise RecoveryError('unknown_library_path')
    base = root / 'library' / ('TV' if app == 'sonarr' else 'Movies')
    return confined(candidate, base)


def source_path(path, root=ROOT):
    prefix = '/storage/.acquisition-staging/complete/sonarr/'
    require(path.startswith(prefix), 'unknown_completed_path')
    base = root / 'library/.acquisition-staging/complete/sonarr'
    return confined(base / path[len(prefix):], base)


def mkv_title(path):
    """Read bounded Matroska header/global tags only; no media-wide scan or inference."""
    size = path.stat().st_size
    with path.open('rb') as stream:
        def vint(keep=False):
            first = stream.read(1)
            if not first or first == b'\0':
                raise RecoveryError('invalid_matroska')
            length = next(i for i in range(1, 9) if first[0] & (1 << (8-i)))
            raw = first + stream.read(length-1)
            require(len(raw) == length, 'invalid_matroska')
            value = int.from_bytes(raw, 'big')
            return value if keep else value & ((1 << (7*length))-1)

        def children(start, end):
            stream.seek(start)
            for _ in range(4096):
                if stream.tell() >= end:
                    return
                tag, length = vint(True), vint()
                pos = stream.tell()
                require(length >= 0 and pos <= size, 'invalid_matroska')
                yield tag, pos, length
                stream.seek(pos + length)
            raise RecoveryError('matroska_element_limit')

        segment = next(p for t, p, n in children(0, min(size, 262144)) if t == 0x18538067)
        offsets, title = [], ''
        for tag, pos, length in children(segment, min(size, segment+262144)):
            if tag == 0x1F43B675 or pos+length > min(size, segment+262144):
                break
            if tag == 0x1549A966:
                for t, p, n in children(pos, pos+length):
                    if t == 0x7BA9 and n <= 4096:
                        require(p+n <= pos+length, 'invalid_matroska')
                        stream.seek(p)
                        return stream.read(n).decode('utf-8', 'replace')
            if tag == 0x114D9B74:
                for _, p, n in children(pos, pos+length):
                    fields = {}
                    for t, q, m in children(p, p+n):
                        if m <= 8:
                            stream.seek(q); fields[t] = int.from_bytes(stream.read(m), 'big')
                    if fields.get(0x53AB) == 0x1254C367 and 0x53AC in fields:
                        offsets.append(segment + fields[0x53AC])
        if title:
            return title
        for offset in offsets[:4]:
            require(segment <= offset < size, 'invalid_matroska')
            stream.seek(offset)
            tag, length = vint(True), vint()
            start = stream.tell()
            require(tag == 0x1254C367 and length <= 1048576 and start+length <= size, 'invalid_matroska')
            for t, p, n in children(start, start+length):
                if t != 0x7373:
                    continue
                parts = list(children(p, p+n))
                # Track-targeted tags cannot establish an episode identity.
                targeted = False
                for tt, pp, nn in parts:
                    if tt == 0x63C0:
                        for x, q, m in children(pp, pp+nn):
                            if x in (0x63C5, 0x63C4, 0x63C6):
                                require(m <= 8, 'invalid_matroska')
                                stream.seek(q)
                                targeted |= int.from_bytes(stream.read(m), 'big') != 0
                if targeted:
                    continue
                for tt, pp, nn in parts:
                    if tt != 0x67C8:
                        continue
                    fields = {}
                    for x, q, m in children(pp, pp+nn):
                        if x in (0x45A3, 0x4487) and m <= 4096:
                            stream.seek(q); fields[x] = stream.read(m).decode('utf-8', 'replace')
                    if fields.get(0x45A3, '').upper() == 'TITLE':
                        return fields.get(0x4487, '')
    return ''


def metadata_match(candidate, item, episodes):
    title = candidate.get('embedded_title', '')
    codes = list(re.finditer(r'S(\d{2})E(\d{2})', title, re.I))
    if len(codes) != 1 or not candidate.get('source_verified'):
        return None
    code = codes[0]
    if normalized(title[:code.start()]) != normalized(item['title']):
        return None
    # Some global TITLE tags contain a conventional release suffix. Accept only
    # this narrow technical suffix, never arbitrary text after the episode title.
    episode_title = re.sub(
        r'[ ._-]+(?:2160|1080|720|480)p[ ._-]+(?:BluRay|WEB[ ._-]?DL|WEBRip|HDTV|DVDRip)'
        r'[ ._-]+(?:x26[45]|H[ ._-]?26[45]|HEVC|AVC)(?:-[A-Za-z0-9]+)?$',
        '', title[code.end():], flags=re.I)
    matches = [e for e in episodes if (e['seasonNumber'], e['episodeNumber']) == tuple(map(int, code.groups()))
               and normalized(e.get('title', '')) and normalized(e['title']) == normalized(episode_title)]
    return matches[0]['id'] if len(matches) == 1 else None


def unsuitable_release(title):
    # Match a release suffix after season/episode notation, not a show named "Extras".
    code = re.search(r'\bS\d{1,2}(?:E\d{1,3})?\b', title, re.I)
    return bool(code and re.search(r'\b(?:extras?|bonus|samples?)(?:[ ._-]*only)?\b', title[code.end():], re.I))


def plex_scan_fresh(settings, now):
    selected = [library for library in settings.get('plex', {}).get('libraries', []) if library.get('enabled')]
    return ({str(library['id']) for library in selected} == {'2', '3', '4', '5'}
            and all(type(library.get('lastScan')) in (int, float)
                    and 0 <= now - library['lastScan'] / 1000 <= 1200 for library in selected))


class FileChecks:
    """Observer-only positive cache. Executors never supply this to collect."""

    def __init__(self, saved=None, now=None):
        self.now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        self.saved = saved if isinstance(saved, dict) else {}
        self.entries = {}
        self.checked = self.reused = 0

    def verify(self, path, app, record, mount, resolve=None):
        # Native metadata/path changes and remounts invalidate earlier evidence.
        key = hashlib.sha256(json.dumps([app, str(path), record, mount], sort_keys=True).encode()).hexdigest()
        at = self.saved.get(key)
        if type(at) in (int, float) and 0 <= self.now - at < FILE_CHECK_SECONDS:
            self.entries[key] = at  # Reuse never extends the original deadline.
            self.reused += 1
            return True
        self.checked += 1
        path = resolve() if resolve is not None else path
        valid = path.stat().st_size == record['size'] and record['size'] > 0
        if valid:
            self.entries[key] = self.now
        return valid


def collect(reader, file_checks=None):
    raw_requests = requests(reader)
    items = {}
    for app, route in (('sonarr', 'series'), ('radarr', 'movie')):
        for item in reader.get(app, route):
            items[f'{app}:{item["id"]}'] = item
    settings = {app: [{'id': s['id']} for s in reader.settings[app]] for app in ('sonarr', 'radarr')}
    bindings = [bind_request(r, settings, items)[0] for r in raw_requests]
    wanted = {(b[0], b[1]['id']) for b in bindings if b}
    items = {key: item for key, item in items.items() if (key.split(':')[0], item['id']) in wanted}
    blocked = []
    if not plex_scan_fresh(reader.settings, dt.datetime.now(dt.timezone.utc).timestamp()):
        blocked.append('plex_availability_scan_stale')
    mounted = os.path.ismount(reader.root / 'library')
    if not mounted:
        blocked.append('library_mount_unavailable')
    else:
        fs = os.statvfs(reader.root / 'library')
        if fs.f_bavail * fs.f_frsize < 30 * 1024**3:
            blocked.append('library_reserve_low')
    mount = None
    if mounted and file_checks is not None:
        info = (reader.root / 'library').stat()
        mount = [info.st_dev, info.st_ino]
    for app, identity in sorted(wanted):
        item = items[f'{app}:{identity}']
        if app == 'sonarr':
            episodes = reader.get(app, f'episode?seriesId={identity}')
            files = {f['id']: f for f in reader.get(app, f'episodefile?seriesId={identity}')}
            item['episodes'] = episodes
        else:
            episodes = [item]
            files = {item.get('movieFileId'): item.get('movieFile', {})}
        for episode in episodes:
            episode['verified'] = None
            fid = episode.get('episodeFileId' if app == 'sonarr' else 'movieFileId')
            if mounted and (episode.get('hasFile') or fid):
                try:
                    f = files[fid]
                    raw_path = f.get('path') or str(Path(item['path']) / f['relativePath'])
                    if file_checks is not None:
                        episode['verified'] = file_checks.verify(raw_path, app, f, mount,
                            resolve=lambda: library_path(raw_path, app, reader.root))
                    else:
                        path = library_path(raw_path, app, reader.root)
                        episode['verified'] = path.stat().st_size == f['size'] and f['size'] > 0
                except (KeyError, OSError, RecoveryError):
                    episode['verified'] = False
    queue, candidates = {}, {}
    sabq, sabh = reader.sab('queue'), reader.sab('history')
    require(int(sabq['noofslots']) <= 1000, 'sab_queue_truncated')
    if sabq.get('paused'):
        blocked.append('manual_pause')
    if float(sabq['diskspace1']) < 30 or float(sabq['diskspace2']) < 30:
        blocked.append('sab_reserve_low')
    jobs = {j['nzo_id']: {'status': j['status'], 'name': j.get('name', j.get('filename', ''))}
            for j in sabh['slots'] + sabq['slots']}
    linked_jobs = set()
    for app in ('sonarr', 'radarr'):
        if any(h.get('type') in ('warning', 'error') for h in reader.get(app, 'health')):
            blocked.append(app + '_health_issue')
        unknown = 'Series' if app == 'sonarr' else 'Movie'
        page = reader.get(app, f'queue?page=1&pageSize=1000&includeUnknown{unknown}Items=true')
        require(page['totalRecords'] == len(page['records']), 'arr_queue_truncated')
        linked_jobs.update(q.get('downloadId') for q in page['records'])
        field = 'seriesId' if app == 'sonarr' else 'movieId'
        queue[app] = [row for row in page['records'] if (app, row.get(field)) in wanted]
        if app == 'sonarr' and mounted:
            completed = {row['downloadId'] for row in queue[app] if row.get('status') == 'completed'
                         and jobs.get(row.get('downloadId'), {}).get('status') == 'Completed'}
            require(len(completed) <= 25, 'completed_job_limit')
            for job in sorted(completed):
                files = reader.get(app, f'manualimport?downloadId={job}&filterExistingFiles=true')
                require(len(files) <= 100, 'candidate_limit')
                for file in files:
                    file['embedded_title'], file['source_verified'] = '', False
                    try:
                        path = source_path(file['path'], reader.root)
                        require(path.stat().st_size == file['size'] > 0, 'source_size_changed')
                        file['embedded_title'] = mkv_title(path) if path.suffix.lower() == '.mkv' else ''
                        file['source_verified'] = True
                    except (OSError, RecoveryError, StopIteration, ValueError):
                        pass
                candidates[job] = files
    require(int(sabh.get('noofslots', len(sabh['slots']))) <= 1000, 'sab_history_truncated')
    unlinked = sorted({j.get('category', j.get('cat')) for j in sabh['slots']
                       if j['status'] == 'Completed' and j['nzo_id'] not in linked_jobs
                       and j.get('category', j.get('cat')) in ('sonarr', 'radarr')})
    return {'requests': raw_requests, 'settings': settings, 'items': items, 'queue': queue,
            'candidates': candidates, 'jobs': jobs, 'blocked': blocked,
            'unlinked_completed_categories': unlinked,
            'processing': int(sabh['ppslots']), 'captured_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def plan(snapshot, previous=None, now=None, grace_seconds=GRACE_SECONDS):
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    previous = previous or {}
    observations, reports = {}, []
    for request in snapshot['requests']:
        binding, reason = bind_request(request, snapshot['settings'], snapshot['items'])
        if binding is None:
            attention = request.get('status') == 4 or (request.get('status') in (2, 5) and reason in
                ('request_binding_missing', 'request_server_mismatch', 'no_approved_seasons'))
            reports.append({'request_id': request['id'], 'state': 'excluded', 'reason': reason,
                            'findings': [reason] if attention else [], 'proposals': []})
            continue
        app, item, seasons = binding
        episodes = [e for e in item['episodes'] if e['seasonNumber'] in seasons] if app == 'sonarr' else [item]
        out = {'request_id': request['id'], 'app': app, 'native_id': item['id'], 'state': 'observing',
               'present_ids': [], 'missing_ids': [], 'held_ids': [], 'proposals': [], 'findings': []}
        reports.append(out)
        if not episodes:
            out['findings'].append('requested_metadata_missing')
        for e in episodes:
            fid = e.get('episodeFileId' if app == 'sonarr' else 'movieFileId')
            if e.get('hasFile') or fid:
                out['present_ids'].append(e['id'])
                if not e.get('hasFile') or not fid or e.get('verified') is not True:
                    out['findings'].append('library_record_or_file_needs_review')
                continue
            if e.get('verified') is True:
                out['held_ids'].append(e['id']); out['findings'].append('unindexed_file_needs_review'); continue
            date = e.get('airDateUtc') if app == 'sonarr' else (e.get('digitalRelease') or e.get('physicalRelease'))
            released = stamp(date)
            if e.get('monitored') is False or released is None or released > now:
                out['held_ids'].append(e['id']); continue
            out['missing_ids'].append(e['id'])
        missing = set(out['missing_ids'])
        field = 'seriesId' if app == 'sonarr' else 'movieId'
        rows = [q for q in snapshot['queue'].get(app, []) if q.get(field) == item['id']]
        held = set()
        for job in sorted({q.get('downloadId') for q in rows if q.get('downloadId')}):
            qrows = [q for q in rows if q.get('downloadId') == job]
            ids = {q.get('episodeId') if app == 'sonarr' else q.get('movieId') for q in qrows}
            # A queue row with unknown episode scope blocks the request conservatively.
            affected = missing if None in ids else missing & ids
            if not affected:
                continue
            status = snapshot.get('jobs', {}).get(job, {}).get('status')
            if status == 'Completed' or any(q.get('status') == 'completed' for q in qrows):
                held |= affected
                key = 'completed:' + job
                first = previous.get('observations', {}).get(key, {}).get('first_seen', now)
                observations[key] = {'first_seen': min(first, now)}
                if now - first < grace_seconds:
                    continue
                files = snapshot.get('candidates', {}).get(job, [])
                release = snapshot.get('jobs', {}).get(job, {}).get('name', qrows[0].get('title', ''))
                if unsuitable_release(release):
                    out['findings'].append('unsuitable_release_review'); continue
                matches = [(f, metadata_match(f, item, episodes)) for f in files] if app == 'sonarr' else []
                mapped = [eid for _, eid in matches if eid is not None]
                if (not matches or len(mapped) != len(files) or len(set(mapped)) != len(mapped)
                        or not set(mapped) <= affected):
                    out['findings'].append('completed_files_need_matching'); continue
                # Only filename-identity failures can be resolved by the exact
                # embedded identities above. Quality, permission and other failures stay held.
                allowed = {'Single episode file contains all episodes in seasons. Review file name or manually import',
                           'Invalid season or episode'}
                if any(r.get('reason') not in allowed for f, _ in matches for r in f.get('rejections', [])):
                    out['findings'].append('native_import_rejection_review'); continue
                out['proposals'].append({'kind': 'native_manual_import', 'download_id': job,
                    'episode_ids': sorted(mapped), 'files': [{'path': f['path'], 'episode_id': eid} for f, eid in matches]})
                out['findings'].append('exact_metadata_import_available')
            elif status == 'Failed' or any(q.get('status') == 'failed' for q in qrows):
                out['findings'].append('failed_release_needs_replacement')
            else:
                held |= affected
        searchable = sorted(missing - held)
        if searchable and app in snapshot.get('unlinked_completed_categories', []):
            out['findings'].append('unlinked_completed_download_review')
            searchable = []
        if request['status'] == 5 and missing:
            out['findings'].append('completed_request_missing_file')
            searchable = []
        if searchable:
            # Preserve each missing item's grace independently while neighbouring
            # imports finish. Newly missing items still receive their full grace.
            ready = []
            for identity in searchable:
                key = hashlib.sha256(json.dumps([request['id'], app, item['id'], identity]).encode()).hexdigest()
                first = previous.get('observations', {}).get(key, {}).get('first_seen', now)
                observations[key] = {'first_seen': min(first, now)}
                if now - first >= grace_seconds:
                    ready.append(identity)
            if ready:
                out['proposals'].append({'kind': 'missing_episode_search' if app == 'sonarr' else 'missing_movie_search',
                    'ids': ready, 'strategy': 'individual_missing_only', 'exclude_release_overlap': out['present_ids']})
                out['findings'].append('missing_without_active_download')
        if snapshot.get('blocked') or snapshot.get('processing'):
            out['proposals'] = []
            out['state'] = 'blocked' if snapshot.get('blocked') else 'waiting_for_processing'
        elif out['findings']:
            out['state'] = 'needs_review'
        elif not missing and not out['held_ids'] and episodes:
            # TV availability is scoped to the approved request seasons. A fulfilled
            # season can coexist with a partially available whole-series status.
            requested_seasons_available = (app == 'sonarr' and request['status'] == 5
                and all(s.get('status') == 5 for s in request['seasons']
                        if s['seasonNumber'] in seasons))
            available = request['media'].get('status') == 5 or requested_seasons_available
            out['state'] = 'available_in_seerr' if available else 'imported_waiting_for_availability'
            if out['state'] == 'imported_waiting_for_availability':
                key = 'availability:' + str(request['id'])
                first = previous.get('observations', {}).get(key, {}).get('first_seen', now)
                observations[key] = {'first_seen': min(first, now)}
                if now - first >= grace_seconds:
                    out['findings'].append('imported_waiting_for_seerr_availability')
        else:
            out['state'] = 'waiting'
        out['findings'] = sorted(set(out['findings']))
    claimed = set()
    for kind in ('native_manual_import', 'missing_episode_search', 'missing_movie_search'):
        for report in reports:
            for proposal in list(report['proposals']):
                if proposal['kind'] != kind:
                    continue
                field = 'episode_ids' if kind == 'native_manual_import' else 'ids'
                keys = {(report['app'], i) for i in proposal[field]}
                if keys & claimed:
                    report['proposals'].remove(proposal)
                else:
                    claimed |= keys
    summary = {'mode': MODE, 'requests': len(reports), 'states': dict(Counter(r['state'] for r in reports)),
               'proposals': dict(Counter(p['kind'] for r in reports for p in r['proposals'])),
               'blocked': snapshot.get('blocked', []), 'acquisition_writes': 0}
    return {'schema': 1, 'generated_at': dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
            'summary': summary, 'requests': reports, 'observations': observations}


def notification(report):
    summary = report['summary']
    issues = [{'request_id': r['request_id'], 'findings': r.get('findings', []),
               'missing': r.get('missing_ids', [])} for r in report['requests'] if r.get('findings')]
    value = {'blocked': summary['blocked'], 'issues': issues,
             'executor_attention': summary.get('executor_attention', 0)}
    digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    active = bool(issues or summary['blocked'] or summary.get('executor_attention'))
    message = (f'Report-only checks found {len(issues)} Seerr request(s) needing attention. '
               f'Proposed imports: {summary["proposals"].get("native_manual_import", 0)}; '
               f'proposed searches: {sum(n for k, n in summary["proposals"].items() if k.endswith("search"))}. '
               'This report does not execute recovery actions. '
               'Review Seerr and Sonarr/Radarr for details.')
    if summary.get('executor_enabled'):
        message += ' Bounded missing-TV backlog acquisition is enabled; its retry limits apply only to that worker. Native RSS and failed-release retries operate separately. Ambiguous imports still need review.'
    if summary.get('executor_attention'):
        message += f' {summary["executor_attention"]} custom-worker episode retry budget(s) or uncertain grab(s) need review.'
    if summary['blocked']:
        message += ' Recovery checks are held by a health, storage, or pause condition.'
    return digest, {'action': 'create' if active else 'dismiss', 'message': message}


def notify_ha(config, payload):
    address = ipaddress.ip_address(config['host'])
    require(address.version == 4 and address in ipaddress.ip_network('192.168.1.0/24'), 'notification_host_refused')
    require(re.fullmatch(r'[a-f0-9]{64}', config['webhook_id']), 'notification_token_invalid')
    connection = http.client.HTTPConnection(str(address), 8123, timeout=10, source_address=('10.77.0.1', 0))
    try:
        connection.request('POST', '/api/webhook/' + config['webhook_id'], json.dumps(payload),
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        require(200 <= response.status < 300, 'notification_delivery_failed')
        response.read(4096)
    finally:
        connection.close()


def executor_attention(state, snapshot):
    policy = state / 'executor-policy.json'
    if not policy.exists() or not private_json(policy).get('enabled'):
        return {'executor_enabled': False, 'executor_attention': 0}
    path = state / 'executor-journal.json'
    journal = private_json(path) if path.exists() else {'episodes': {}}
    missing = {(item['id'], e['id']) for key, item in snapshot.get('items', {}).items()
               if key.startswith('sonarr:') for e in item.get('episodes', [])
               if not e.get('hasFile') and not e.get('episodeFileId')}
    active = {(q.get('seriesId'), q.get('episodeId')) for q in snapshot.get('queue', {}).get('sonarr', [])
              if q.get('status') != 'failed'}
    attention = 0
    for key, entry in journal['episodes'].items():
        identity = tuple(map(int, key.split(':')))
        if identity in active or (identity[0], None) in active:
            continue
        attempts = entry.get('attempts', [])
        # Pending submission may be in flight; the same condition becomes
        # actionable after five minutes if the executor died before readback.
        pending_old = any(a['status'] == 'pending' and
            dt.datetime.now(dt.timezone.utc).timestamp() - a['at'] > 300 for a in attempts)
        if identity in missing and (entry.get('searches', 0) >= 7 or len(attempts) >= 3
                or pending_old or any(a['status'] == 'uncertain' for a in attempts)):
            attention += 1
    return {'executor_enabled': True, 'executor_attention': attention}


def run(reader, state=STATE):
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not state.is_symlink() and not state.stat().st_mode & 0o077, 'state_directory_not_private')
    with (state / 'run.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = private_json(state / 'report.json') if (state / 'report.json').exists() else {}
        try:
            cache_path = state / 'file-checks.json'
            checks = FileChecks(private_json(cache_path) if cache_path.exists() else {})
            snapshot = collect(reader, file_checks=checks)
            report = plan(snapshot, previous)
            report['summary']['file_checks'] = {'checked': checks.checked, 'reused': checks.reused,
                                               'maximum_age_seconds': FILE_CHECK_SECONDS}
            report['summary'].update(executor_attention(state, snapshot))
            atomic_json(state / 'snapshot.json', snapshot)
            atomic_json(cache_path, checks.entries)
        except Exception as error:
            reason = str(error) if isinstance(error, RecoveryError) else 'inspection_failed'
            report = plan({'requests': [], 'blocked': [reason], 'settings': {}, 'items': {}, 'queue': {}}, previous)
        atomic_json(state / 'report.json', report)
        digest, payload = notification(report)
        saved = private_json(state / 'notification-state.json') if (state / 'notification-state.json').exists() else {}
        if (state / 'notify.json').exists():
            try:
                changed = saved.get('digest') != digest
                # Quiet heartbeats let HA detect a stopped monitor independently.
                sent = payload if changed and (payload['action'] != 'dismiss' or saved) else {'action': 'heartbeat'}
                notify_ha(private_json(state / 'notify.json'), sent)
                atomic_json(state / 'notification-state.json', {'digest': digest, 'delivered_at': report['generated_at']})
                report['summary']['notification'] = 'delivered' if sent['action'] != 'heartbeat' else 'quiet_heartbeat'
            except Exception:
                report['summary']['notification'] = 'delivery_failed'
        else:
            report['summary']['notification'] = 'unchanged' if saved else 'not_configured'
        atomic_json(state / 'report.json', report)
        print(json.dumps(report['summary'], sort_keys=True))
        return 1 if report['summary']['blocked'] or report['summary'].get('notification') == 'delivery_failed' else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'status', 'replay'))
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'run':
            return run(Reader())
        if args.action == 'replay':
            require(args.snapshot is not None, 'snapshot_required')
            print(json.dumps(plan(private_json(args.snapshot))['summary'], sort_keys=True))
        else:
            report = private_json(STATE / 'report.json')
            age = dt.datetime.now(dt.timezone.utc).timestamp() - stamp(report['generated_at'])
            print(json.dumps(dict(report['summary'], age_seconds=round(age), fresh=age < 900), sort_keys=True))
            return 0 if age < 900 and not report['summary']['blocked'] else 1
        return 0
    except Exception as error:
        print(json.dumps({'mode': MODE, 'status': 'blocked', 'reason': str(error) if isinstance(error, RecoveryError) else 'inspection_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
