#!/usr/bin/env python3
"""One-shot settings migration and verification; never search or alter media.

Recyclarr owns naming/upgrade/codec settings. This helper only supplies its secrets,
records preservation evidence, and reconciles Seerr tags/monitoring through the
native APIs. It is not scheduled and contains no recovery executor.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path('/srv/usenet')
TAG = 'seerr-approved'
BASE = ROOT / 'config/catalog/settings-rollout'
ROUTES = ('config/naming', 'config/mediamanagement', 'config/indexer',
          'config/downloadclient', 'qualityprofile', 'customformat', 'downloadclient', 'tag')


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def reader():
    spec = importlib.util.spec_from_file_location('safety_recovery', ROOT / 'libexec/seerr-recovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.Reader()


def approved(module, requests, settings, items):
    result = {}
    for request in requests:
        binding, reason = module.bind_request(request, settings, items)
        if request.get('status') in (2, 5) and reason not in (
                'media_blocked_or_deleted', 'request_not_approved_single_copy'):
            require(binding is not None, 'approved_request_binding_requires_review')
        if binding:
            app, item, seasons = binding
            result.setdefault((app, item['id']), set()).update(seasons)
    return result


def desired_item(app, item, scope, tag_id):
    value = dict(item)
    is_approved = (app, item['id']) in scope
    tags = set(item.get('tags', []))
    tags.add(tag_id) if is_approved else tags.discard(tag_id)
    value['tags'] = sorted(tags)
    if not is_approved:
        value['monitored'] = False
    if app == 'sonarr':
        value['monitorNewItems'] = 'none'
        value['seasons'] = [dict(s, monitored=bool(s.get('monitored')) and
                                s['seasonNumber'] in scope.get((app, item['id']), set()))
                            for s in item.get('seasons', [])]
    return value


def capture(module, r):
    out = {'requests': module.requests(r), 'settings': r.settings, 'apps': {}}
    queue, history = r.sab('queue'), r.sab('history')
    require(not queue['slots'] and int(history['ppslots']) == 0, 'downloads_must_be_idle')
    out['sab_pause'] = queue.get('paused')
    out['sab_job_ids'] = sorted(j['nzo_id'] for j in history['slots'])
    for app in ('radarr', 'sonarr'):
        a = {route: r.arr.call(app, route) for route in ROUTES}
        commands = r.arr.call(app, 'command')
        require(not any(c.get('status') in ('queued', 'started') for c in commands), 'native_commands_must_be_idle')
        a['commands'] = [c for c in commands if c.get('name') in
                         ('ManualImport', 'RenameFiles', 'RenameMovie', 'EpisodeSearch',
                          'SeasonSearch', 'SeriesSearch', 'MoviesSearch')]
        a['items'] = r.arr.call(app, 'movie' if app == 'radarr' else 'series')
        a['files'] = []
        for i in a['items']:
            if app == 'sonarr':
                a['files'].extend(r.arr.call(app, f'episodefile?seriesId={i["id"]}'))
            elif i.get('movieFileId'):
                a['files'].append(i['movieFile'])
        a['files'].sort(key=lambda f: f['id'])
        a['stats'] = {}
        for f in a['files']:
            path = module.library_path(f['path'], app)
            st = path.stat()
            a['stats'][str(f['id'])] = [str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
        out['apps'][app] = a
    return out


def item_map(snapshot):
    return {f'{app}:{i["id"]}': i for app, a in snapshot['apps'].items() for i in a['items']}


def same_media_files(before, after):
    # Arr recalculates these presentation fields when a custom format changes.
    # File IDs, paths, MediaInfo and every other field remain preservation checks;
    # capture's independent inode/size/mtime inventory is also compared below.
    computed = {'customFormats', 'customFormatScore'}
    def stable(files):
        return [{k: v for k, v in f.items() if k not in computed} for f in files]
    return stable(before) == stable(after)


def verify_codec_policy(before, after):
    """Allow only the reviewed AV1 rejection; preserve every other profile field."""
    old_formats, new_formats = before['customformat'], after['customformat']
    av1 = [f for f in new_formats if f['name'] == 'AV1']
    require(len(av1) == 1, 'av1_format_missing_or_duplicate')
    rule = av1[0]
    specs = rule.get('specifications', [])
    require(not rule.get('includeCustomFormatWhenRenaming') and len(specs) == 1,
            'av1_format_definition_changed')
    spec = specs[0]
    fields = {f['name']: f.get('value') for f in spec.get('fields', [])}
    require(spec.get('implementation') == 'ReleaseTitleSpecification'
            and spec.get('negate') is False and spec.get('required') is True
            and fields.get('value') == r'\bAV1\b', 'av1_format_definition_changed')
    require([f for f in old_formats if f['name'] != 'AV1'] ==
            [f for f in new_formats if f['name'] != 'AV1'], 'unrelated_custom_format_changed')
    old = {p['id']: p for p in before['qualityprofile']}
    require(set(old) == {p['id'] for p in after['qualityprofile']}, 'quality_profiles_changed')
    old_av1_ids = {f['id'] for f in old_formats if f['name'] == 'AV1'}
    for profile in after['qualityprofile']:
        scores = [f for f in profile['formatItems'] if f['format'] == rule['id']]
        require(len(scores) == 1 and scores[0]['score'] == -10000
                and profile['minFormatScore'] == 0, 'av1_rejection_score_missing')
        previous = dict(old[profile['id']])
        current = dict(profile)
        previous['formatItems'] = [f for f in previous['formatItems'] if f['format'] not in old_av1_ids]
        current['formatItems'] = [f for f in current['formatItems'] if f['format'] != rule['id']]
        previous['minFormatScore'] = 0
        require(current == previous, 'unrelated_quality_policy_changed')


def seerr_update(r, app, server):
    req = urllib.request.Request(f'http://127.0.0.1:5055/api/v1/settings/{app}/{server["id"]}',
        method='PUT', data=json.dumps({k: v for k, v in server.items() if k != 'id'}).encode(), headers={'Content-Type': 'application/json',
        'X-API-Key': r.settings['main']['apiKey']})
    with r.opener.open(req, timeout=45) as response:
        return json.load(response)


def main(action):
    os.umask(0o077)
    module, r = reader()
    if action == 'prepare':
        snap = capture(module, r)
        approved(module, snap['requests'], snap['settings'], item_map(snap))
        BASE.mkdir(mode=0o700, exist_ok=True)
        path = BASE / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        path.mkdir(mode=0o700)
        (path / 'before.json').write_text(json.dumps(snap))
        (BASE / 'latest-path').write_text(str(path))
        config = ROOT / 'config/catalog/recyclarr-preview'
        config.mkdir(mode=0o700, exist_ok=True)
        (config / 'secrets.yml').write_text(''.join(f'{app}_api_key: {json.dumps(r.arr.keys[app])}\n' for app in ('radarr', 'sonarr')))
        (ROOT / 'compose/recyclarr-preview/.env').write_text(f'USENET_UID={os.getuid()}\nUSENET_GID={os.getgid()}\nRECYCLARR_CONFIG_DIR={config}\n')
        return {'status': 'prepared', 'file_counts': {a: len(v['files']) for a,v in snap['apps'].items()}}
    path = Path((BASE / 'latest-path').read_text())
    require(path.parent == BASE and not path.is_symlink(), 'invalid_evidence_path')
    before = json.loads((path / 'before.json').read_text())
    current = capture(module, r)
    scope = approved(module, current['requests'], current['settings'], item_map(current))
    require(scope == approved(module, before['requests'], before['settings'], item_map(before)), 'request_scope_changed')
    if action == 'scope':
        changes = {'tagged': 0, 'unmonitored': 0}
        for app in ('radarr','sonarr'):
            matches = [t for t in current['apps'][app]['tag'] if t['label'] == TAG]
            require(len(matches) <= 1, 'duplicate_scope_tag')
            tag = matches[0] if matches else r.arr.call(app, 'tag', 'POST', {'label': TAG})
            for item in current['apps'][app]['items']:
                desired = desired_item(app, item, scope, tag['id'])
                if desired != item:
                    # Native item PUT with no moveFiles/search options; only monitoring/tags differ.
                    r.arr.call(app, ('movie/' if app == 'radarr' else 'series/') + str(item['id']), 'PUT', desired)
                    changes['tagged'] += desired['tags'] != item.get('tags', [])
                    changes['unmonitored'] += bool(item.get('monitored')) and not desired['monitored']
            server = dict(r.settings[app][0])
            server['tags'] = sorted(set(server.get('tags', [])) | {tag['id']})
            if app == 'sonarr':
                server['monitorNewItems'] = 'none'
            if server != r.settings[app][0]:
                seerr_update(r, app, server)
        (path / 'scope.json').write_text(json.dumps(changes))
        return {'status': 'scope_reconciled', **changes}
    require(action == 'verify', 'unsupported_action')
    for app in ('radarr','sonarr'):
        a, b = current['apps'][app], before['apps'][app]
        require(same_media_files(b['files'], a['files']) and a['stats'] == b['stats'], 'existing_media_changed')
        require(a['commands'] == b['commands'], 'unexpected_media_command')
        for route in ('config/indexer','config/downloadclient','downloadclient'):
            require(a[route] == b[route], 'acquisition_or_quality_policy_changed')
        verify_codec_policy(b, a)
        expected_naming = dict(b['config/naming'], **{'renameEpisodes' if app == 'sonarr' else 'renameMovies': True})
        require(a['config/naming'] == expected_naming, 'naming_readback_failed')
        require(a['config/mediamanagement'] == dict(b['config/mediamanagement'], downloadPropersAndRepacks='doNotPrefer'), 'media_management_readback_failed')
        tags = [t['id'] for t in a['tag'] if t['label'] == TAG]
        require(len(tags) == 1 and tags[0] in r.settings[app][0]['tags'], 'seerr_tag_missing')
        for i in a['items']:
            require(desired_item(app, i, scope, tags[0]) == i, 'monitoring_scope_drift')
        # Native APIs may refresh statistics, but settings outside our explicit
        # monitoring/tag allowlist must remain exactly as they were.
        old_items = {i['id']: i for i in b['items']}
        require(set(old_items) == {i['id'] for i in a['items']}, 'native_inventory_changed')
        for i in a['items']:
            for field in ('path', 'qualityProfileId', 'rootFolderPath', 'seriesType'):
                require(i.get(field) == old_items[i['id']].get(field), 'native_item_policy_changed')
    require(current['sab_pause'] == before['sab_pause'] and current['sab_job_ids'] == before['sab_job_ids'], 'download_state_changed')
    (path / 'after.json').write_text(json.dumps(current))
    receipt = {'status': 'verified', 'existing_files_preserved': {a: len(v['files']) for a,v in current['apps'].items()},
               'scope': 'approved_seerr_requests', 'recovery_mode': 'report-only', 'settings_owner': 'recyclarr',
               'rss_enabled': all(a['config/indexer']['rssSyncInterval'] > 0 for a in current['apps'].values()), 'acquisition_writes': 0}
    (path / 'receipt.json').write_text(json.dumps(receipt))
    (ROOT / 'config/catalog/recyclarr/ownership.json').write_text(json.dumps(receipt))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'scope', 'verify'))
    args = parser.parse_args()
    try:
        print(json.dumps(main(args.action), sort_keys=True))
    except Exception as exc:
        # External exceptions may contain media names or secrets.
        print(json.dumps({'status': 'failed', 'reason': str(exc) if type(exc) is RuntimeError else 'private_operation_failed'}))
        raise SystemExit(1)
