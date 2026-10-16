#!/usr/bin/env python3
"""Disposable offline compatibility test, never a production recovery worker.

export reads private saved snapshots; serve/run operate only on an internal
Docker network. No live credentials or media mounts are admitted to the lab.
"""
import copy
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DATA = Path('/replay')
IMAGE = 'ghcr.io/cleanuparr/cleanuparr:2.10.11@sha256:c51af6957780ad2719e97a2131fe668f61da28e43363719c7b557577fc39ebaf'
SAFE = 'Found matching series via grab history, but release was matched to series by ID.'


def export(destination):
    base = Path('/srv/usenet/config/catalog')
    spec = importlib.util.spec_from_file_location('recovery', '/srv/usenet/libexec/seerr-recovery.py')
    recovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(recovery)
    sources = {}
    def read(relative):
        raw = (base / relative).read_bytes()
        sources[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    tv = read('seerr-recovery-replay-20261016/before.json')
    movies = read('movie-recovery-20261016/before.json')
    final = read('movie-recovery-20261016/final-audit.json')
    target_requests = {t['request_id'] for t in movies['targets']}
    movies = movies['snapshot']
    movies['requests'] = [r for r in movies['requests'] if r['id'] in target_requests]
    cases, counts = {}, {}
    for name, snap in [('repaired_tv_before', tv), ('repaired_movies_before', movies)]:
        allowed, episode_ids = {}, set()
        for request in snap['requests']:
            binding, _ = recovery.bind_request(request, snap['settings'], snap['items'])
            assert binding is not None, 'saved_request_binding_invalid'
            app, item, seasons = binding
            allowed[(app, item['id'])] = seasons
            episode_ids.update(e['id'] for e in item.get('episodes', []) if e['seasonNumber'] in seasons)
        rows = {}
        for app in ('sonarr', 'radarr'):
            key = 'seriesId' if app == 'sonarr' else 'movieId'
            rows[app] = [dict(q, title=f'Private replay {app}', outputPath='/fixtures/unmounted')
                         for q in snap['queue'][app] if (app, q.get(key)) in allowed
                         and (app == 'radarr' or q.get('episodeId') in episode_ids)]
        jobs = {q['downloadId'] for qs in rows.values() for q in qs}
        candidates = {}
        for job, files in snap['candidates'].items():
            if job not in jobs:
                continue
            candidates[job] = []
            for n, f in enumerate(files):
                if ('sonarr', (f.get('series') or {}).get('id')) not in allowed:
                    continue
                if not {e['id'] for e in f.get('episodes', [])} <= episode_ids:
                    continue
                value = {k: f[k] for k in ('id', 'downloadId', 'quality', 'languages', 'rejections', 'size', 'episodes', 'series') if k in f}
                value.update(path=f'/fixtures/unmounted/{n}.mkv', folderName='Private replay')
                candidates[job].append(value)
        cases[name] = {'queue': rows, 'candidates': candidates, 'commands': []}
        counts[name] = {'requests': len(snap['requests']), 'queue_rows': sum(map(len, rows.values())),
                       'excluded_queue_rows': sum(map(len, snap['queue'].values())) - sum(map(len, rows.values())),
                       'candidate_files': sum(map(len, candidates.values()))}
    # The final saved audit proves both repaired movie requests were available.
    assert len(final['results']) == 2
    after = read('seerr-recovery/snapshot.json')
    repaired_ids = target_requests | {r['id'] for r in tv['requests']}
    repaired = [r for r in after['requests'] if r['id'] in repaired_ids]
    assert len(repaired) == 5 and all(r['media']['status'] == 5 for r in repaired)
    after_ids = {('sonarr' if r['type'] == 'tv' else 'radarr', r['media']['externalServiceId']) for r in repaired}
    after_queue = {app: [dict(q, title=f'Private repaired {app}', outputPath='/fixtures/unmounted')
                        for q in after['queue'][app]
                        if (app, q.get('seriesId' if app == 'sonarr' else 'movieId')) in after_ids]
                   for app in ('sonarr', 'radarr')}
    assert not after['candidates'], 'after_candidate_review_required'
    cases['repaired_after'] = {'queue': after_queue, 'candidates': {}, 'commands': []}
    counts['repaired_after'] = {'requests': 5, 'available_in_seerr': 5,
                               'queue_rows': sum(map(len, after_queue.values()))}
    quality = {'quality': {'id': 3, 'name': 'WEBDL-1080p'}, 'revision': {'version': 1, 'real': 0, 'isRepack': False}}
    row = {'id': 900001, 'seriesId': 900001, 'episodeId': 900001, 'seasonNumber': 1,
           'title': 'Invented Observatory S01E01', 'downloadId': 'synthetic-positive',
           'downloadClient': 'Offline fixture', 'protocol': 'usenet', 'size': 1000, 'sizeleft': 0,
           'status': 'completed', 'trackedDownloadStatus': 'warning', 'trackedDownloadState': 'importBlocked',
           'quality': quality, 'statusMessages': [{'title': 'Import blocked', 'messages': [SAFE]}]}
    candidate = {'path': '/fixtures/unmounted/synthetic.mkv', 'folderName': 'Invented Observatory',
                 'quality': quality, 'languages': [{'id': 1, 'name': 'English'}],
                 'series': {'id': 900001}, 'episodes': [{'id': 900001}], 'rejections': [{'reason': SAFE}]}
    positive = {'queue': {'sonarr': [row], 'radarr': []}, 'commands': [],
                'candidates': {'synthetic-positive': [candidate]}}
    cases['synthetic_supported_import'] = positive
    for name in ('synthetic_existing_file', 'synthetic_active_import', 'synthetic_history_unavailable'):
        case = copy.deepcopy(positive)
        new_job = name
        case['queue']['sonarr'][0]['downloadId'] = new_job
        case['candidates'] = {new_job: [copy.deepcopy(candidate)]}
        if name.endswith('existing_file'):
            case['candidates'][new_job][0]['rejections'] = [{'reason': 'Not an upgrade for existing episode file(s).'}]
        elif name.endswith('active_import'):
            case['commands'] = [{'id': 1, 'name': 'ManualImport', 'status': 'started'}]
        else:
            case['history_unavailable'] = True
        cases[name] = case
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    (destination / 'fixtures.json').write_text(json.dumps(cases))
    (destination / 'sources.json').write_text(json.dumps({'hashes': sources, 'scope_counts': counts}))
    return counts


class Fixture(http.server.BaseHTTPRequestHandler):
    cases = {}
    case = 'repaired_after'
    audit = []

    def log_message(self, *_):
        pass

    def respond(self, value, code=200):
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/audit':
            return self.respond(self.audit)
        parts = parsed.path.strip('/').split('/')
        self.audit.append({'case': self.case, 'method': 'GET', 'path': parsed.path})
        (DATA / 'audit.json').write_text(json.dumps(self.audit))
        if len(parts) < 4 or parts[0] not in ('sonarr', 'radarr') or parts[1:3] != ['api', 'v3']:
            return self.respond({'error': 'unknown_route'}, 404)
        app, route = parts[0], '/'.join(parts[3:])
        case = self.cases[self.case]
        if route == 'system/status':
            return self.respond({'version': '4.0.20.3014' if app == 'sonarr' else '6.4.4.10685'})
        if route == 'queue':
            rows = case['queue'][app]
            return self.respond({'page': 1, 'pageSize': 1000, 'totalRecords': len(rows), 'records': rows})
        if route == 'command':
            return self.respond(case['commands'])
        if route == 'history':
            if case.get('history_unavailable'):
                return self.respond({'error': 'fixture_unavailable'}, 503)
            return self.respond({'page': 1, 'pageSize': 1, 'totalRecords': 0, 'records': []})
        if route == 'manualimport':
            job = urllib.parse.parse_qs(parsed.query)['downloadId'][0]
            return self.respond(case['candidates'].get(job, []))
        return self.respond({'error': 'unknown_route'}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if self.path == '/control' and body.get('case') in self.cases:
            type(self).case = body['case']
            return self.respond({'case': self.case})
        self.audit.append({'case': self.case, 'method': self.command, 'path': self.path})
        (DATA / 'audit.json').write_text(json.dumps(self.audit))
        return self.respond({'error': 'all_arr_writes_forbidden'}, 405)

    do_PUT = do_POST
    do_DELETE = do_POST


def call(base, path, body=None, method=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                    method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        # Lab-only errors contain synthetic settings, never production secrets.
        (DATA / 'api-error.json').write_text(exc.read().decode())
        raise RuntimeError(f'lab_http_{exc.code}_{path}') from None


def run():
    url = 'http://cleanuparr:11011'
    for _ in range(50):
        try:
            call(url, '/api/auth/status'); break
        except (OSError, RuntimeError):
            time.sleep(1)
    credentials_path = DATA / 'credentials.json'
    if not credentials_path.exists():
        creds = {'username': 'offline-replay', 'password': 'Aa1!' + secrets.token_hex(20)}
        call(url, '/api/auth/setup/account', creds)
        call(url, '/api/auth/setup/complete', {})
        credentials_path.write_text(json.dumps(creds))
    creds = json.loads(credentials_path.read_text())
    token = call(url, '/api/auth/login', creds)['tokens']['accessToken']
    def api(path, body=None, method=None):
        return call(url, path, body, method, token)
    general = api('/api/configuration/general')
    general.update(dryRun=True, statusCheckEnabled=False, connectivityCheckEnabled=False, httpMaxRetries=0, httpTimeout=5)
    general['log']['level'] = 'Debug'
    api('/api/configuration/general', general, 'PUT')
    assert api('/api/configuration/general')['dryRun'] is True
    seeker = api('/api/configuration/seeker')
    seeker.update(searchEnabled=False, proactiveSearchEnabled=False)
    api('/api/configuration/seeker', seeker, 'PUT')
    for app, version in [('sonarr', 4), ('radarr', 6)]:
        config = api('/api/configuration/' + app)
        assert not config['instances'], 'use_fresh_lab_for_replay'
        api('/api/configuration/' + app, {'failedImportMaxStrikes': 0}, 'PUT')
        api('/api/configuration/' + app + '/instances', {'name': 'Offline ' + app, 'url': 'http://fixtures:8080/' + app,
            'enabled': True, 'version': version, 'apiKey': 'offline-synthetic-key'})
    queue = api('/api/configuration/queue_cleaner')
    queue.update(enabled=True, cronExpression=f'0 0 {(time.gmtime().tm_hour + 1) % 3}/3 * * ?', useAdvancedScheduling=True,
                 downloadingMetadataMaxStrikes=0, processNoContentId=False)
    queue['failedImport'].update(maxStrikes=0, forceImport=True, forceImportMaxTries=3,
                                deletePrivate=False, changeCategory=False, skipIfNotFoundInClient=True)
    queue['errored']['maxStrikes'] = 0
    api('/api/configuration/queue_cleaner', queue, 'PUT')
    receipt = {'image': IMAGE, 'dry_run': True, 'search_enabled': False, 'production_connections': 0,
               'media_mounts': 0, 'cases': []}
    cases = json.loads((DATA / 'fixtures.json').read_text())
    for name in cases:
        call('http://fixtures:8080', '/control', {'case': name})
        # Await an observed new run and job completion, not just an arbitrary delay.
        for _ in range(2):
            before = len(call('http://fixtures:8080', '/audit'))
            api('/api/jobs/QueueCleaner/trigger', {})
            for attempt in range(50):
                time.sleep(0.3)
                state = api('/api/jobs/QueueCleaner')
                observed = call('http://fixtures:8080', '/audit')[before:]
                polled = {row['path'].split('/')[1] for row in observed if row['path'].endswith('/queue')}
                if polled == {'sonarr', 'radarr'} and state['status'] != 'Running':
                    break
            else:
                raise RuntimeError('queue_job_did_not_finish')
        receipt['cases'].append(name)
    audit = call('http://fixtures:8080', '/audit')
    assert all(row['method'] == 'GET' for row in audit), 'attempted_arr_write'
    for name in cases:
        assert any(row['case'] == name and row['path'].endswith('/queue') for row in audit), 'case_not_exercised'
    receipt['arr_write_attempts'] = 0
    receipt['config'] = {key: api('/api/configuration/' + key) for key in ('general', 'seeker', 'queue_cleaner')}
    (DATA / 'run.json').write_text(json.dumps(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k != 'config'}))


def topology():
    root = Path('/srv/usenet/config/catalog/cleanuparr-replay')
    cwd = '/srv/usenet/compose/cleanuparr-replay'
    ids = subprocess.check_output(['docker', 'compose', 'ps', '-q'], cwd=cwd, text=True).split()
    assert len(ids) == 2
    containers = json.loads(subprocess.check_output(['docker', 'inspect', *ids]))
    networks = set()
    allowed_mounts = {str(root / 'config'), str(root / 'data'), '/srv/usenet/libexec/cleanuparr_replay.py'}
    for c in containers:
        assert c['Config']['Image'] == IMAGE
        assert c['Config']['User'] and not c['Config']['User'].startswith('0:')
        assert c['HostConfig']['ReadonlyRootfs'] and not c['HostConfig']['Privileged']
        assert not c['HostConfig'].get('PortBindings')
        assert all(m['Source'] in allowed_mounts for m in c['Mounts'] if m['Type'] != 'tmpfs')
        networks.update(c['NetworkSettings']['Networks'])
    assert len(networks) == 1
    assert all(n['Internal'] for n in json.loads(subprocess.check_output(['docker', 'network', 'inspect', *networks])))
    (root / 'data/topology.json').write_text(json.dumps({'internal_network': True, 'published_ports': 0,
        'production_connections': 0, 'media_mounts': 0, 'rootless': True, 'pinned_image': IMAGE}))


def verify():
    root = Path('/srv/usenet/config/catalog/cleanuparr-replay')
    result = json.loads((root / 'data/run.json').read_text())
    audit = json.loads((root / 'data/audit.json').read_text())
    log = (root / 'log.txt').read_text()
    assert log.count('[DRY RUN] would ask the arr to import 1 file(s) | Invented Observatory S01E01') == 2
    assert log.count('[DRY RUN] would ask the arr to import') == 2
    assert all(row['method'] == 'GET' for row in audit)
    expected = {
        'repaired_tv_before': {'queue'}, 'repaired_movies_before': {'queue'}, 'repaired_after': {'queue'},
        'synthetic_supported_import': {'queue', 'command', 'history', 'manualimport'},
        'synthetic_existing_file': {'queue', 'command', 'history', 'manualimport'},
        'synthetic_active_import': {'queue', 'command'},
        'synthetic_history_unavailable': {'queue', 'command', 'history'},
    }
    for case, routes in expected.items():
        actual = {row['path'].split('/')[-1] for row in audit if row['case'] == case}
        assert actual == routes, f'unexpected_routes_{case}'
    assert result['config']['general']['dryRun'] is True
    assert result['config']['seeker']['searchEnabled'] is False
    receipt = {'status': 'passed', 'scenarios': 7, 'passes_per_scenario': 2, 'arr_write_attempts': 0,
               'supported_synthetic_would_import': 2, 'historical_would_import': 0,
               'production_promotion': 'not_qualified', 'recovery_mode': 'report-only',
               'isolation': json.loads((root / 'data/topology.json').read_text())}
    (root / 'receipt.json').write_text(json.dumps(receipt))
    print(json.dumps(receipt))


if __name__ == '__main__':
    os.umask(0o077)
    if sys.argv[1] == 'export':
        print(json.dumps(export(Path(sys.argv[2]))))
    elif sys.argv[1] == 'serve':
        Fixture.cases = json.loads((DATA / 'fixtures.json').read_text())
        http.server.HTTPServer(('0.0.0.0', 8080), Fixture).serve_forever()
    elif sys.argv[1] == 'run':
        run()
    elif sys.argv[1] == 'topology':
        topology()
    elif sys.argv[1] == 'verify':
        verify()
