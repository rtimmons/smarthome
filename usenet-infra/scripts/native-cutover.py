#!/usr/bin/env python3
"""Verify native Arr ownership, acquisition limits and preserved recovery evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path('/srv/usenet')
LIMITS = {'size_limit': '100G', 'top_only': 1, 'pause_on_post_processing': 1,
          'direct_unpack': 0, 'safe_postproc': 1, 'download_free': '30G',
          'complete_free': '30G', 'preserve_paused_state': 1}
MARKER = 'config/catalog/native-ownership.json'
RECEIPT = 'state/catalog/native-cutover.json'


def module(name, root=ROOT):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root / 'libexec' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def native_client(client, app):
    require(client.get('implementation') == 'Sabnzbd', 'sab_client_required')
    result = copy.deepcopy(client)
    prefix = 'Movie' if app == 'radarr' else 'Tv'
    category = prefix[0].lower() + prefix[1:] + 'Category'
    fields = {field['name']: field for field in result['fields']}
    require(len(fields) == len(result['fields']), 'duplicate_client_fields')
    require(all(k in fields for k in (category, 'recent' + prefix + 'Priority', 'older' + prefix + 'Priority')),
            'client_category_priority_fields_missing')
    fields[category]['value'] = app
    for key in ('recent' + prefix + 'Priority', 'older' + prefix + 'Priority'):
        fields[key]['value'] = 0
    result.update(enable=True, removeCompletedDownloads=True, removeFailedDownloads=False)
    return result


def preserved(before, after, discarded=()):
    # Historical requests are compared by identity even after new jobs exist.
    current = {j['nzo_id']: j for j in after['queue']}
    original = {j['nzo_id'] for j in before['queue']}
    if len(discarded) != len(set(discarded)) or not set(discarded) <= original or set(discarded) & current.keys():
        return False
    return all(j['nzo_id'] in discarded or current.get(j['nzo_id']) == j for j in before['queue'])


def limits_match(misc):
    # SAB's API returns booleans for some switches and integers for others.
    return all(misc.get(k) == v for k, v in LIMITS.items())


TIMERS = ('usenet-capacity-admission.timer', 'usenet-cart-import.timer',
          'usenet-incomplete-maintenance.timer', 'usenet-publish.timer')


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def state_fingerprints(root):
    paths = [root / 'state/catalog/cart-import/armed.json',
             root / 'config/catalog/remote-scratch.json',
             *sorted((root / 'state/catalog/cart-import/jobs').glob('*.json'))]
    capacity = json.loads((root / 'state/catalog/capacity-admission/state.json').read_text())
    require(not capacity.get('admitted'), 'admission_active')
    return {'files': {str(p.relative_to(root)): digest(p) for p in paths},
            'held': capacity['held'], 'owned': capacity['owned']}


def inspect(root, api, sab):
    marker = json.loads((root / MARKER).read_text())
    require(marker.get('integrity_policy') == 'native_arr_import_and_cleanup'
            and marker.get('phase') == 'active', 'native_marker_invalid')
    misc = sab.api('get_config', section='misc')['config']['misc']
    require(limits_match(misc), 'native_sab_limits_changed')
    categories = {v['name']: v for v in sab.api('get_config', section='categories')['config']['categories']}
    for app in ('radarr', 'sonarr'):
        require(app in categories and categories[app]['dir'] == app
                and int(categories[app]['priority']) == 0 and str(categories[app]['pp']) == '3',
                'native_sab_category_changed')
        clients = api.call(app, 'downloadclient')
        require(len(clients) == 1 and clients[0] == native_client(clients[0], app), 'native_client_changed')
        config = api.call(app, 'config/downloadclient')
        require(config.get('enableCompletedDownloadHandling') is True
                and config.get('autoRedownloadFailed') is False
                and config.get('autoRedownloadFailedFromInteractiveSearch') is False, 'native_cleanup_changed')
        media = api.call(app, 'config/mediamanagement')
        require(media.get('skipFreeSpaceCheckWhenImporting') is False
                and media.get('minimumFreeSpaceWhenImporting', 0) >= 30 * 1024
                and media.get('copyUsingHardlinks') is True, 'native_import_reserve_changed')
        require(api.call(app, 'config/indexer')['rssSyncInterval'] == 0,
                'native_intake_phase_changed')
    require(not any(int(f['enable']) for f in sab.api('get_config', section='rss')['config']['rss']),
            'direct_feed_still_enabled')
    require(not any(c.get('enable') for c in api.call('prowlarr', 'downloadclient')),
            'prowlarr_direct_download_still_enabled')
    for timer in TIMERS:
        require(command('systemctl', 'show', timer, '--property=ActiveState', '--value') == 'inactive',
                'legacy_timer_still_active')
    old = json.loads((root / RECEIPT).read_text())
    disposition_path = root / 'state/catalog/native-disposition.json'
    discarded = []
    if disposition_path.exists():
        require(not disposition_path.is_symlink(), 'disposition_receipt_invalid')
        disposition = json.loads(disposition_path.read_text())
        require(disposition.get('schema_version') == 1 and disposition.get('status') == 'completed'
                and disposition.get('baseline_sha256') == hashlib.sha256((root / RECEIPT).read_bytes()).hexdigest(),
                'disposition_receipt_invalid')
        discarded = disposition['discarded_queue_ids']
    require(preserved(old['snapshot'], sab.snapshot(), discarded) and state_fingerprints(root) == old['fingerprints'],
            'historical_holds_or_journals_changed')
    return {'status': 'verified', 'phase': marker['phase'], 'distinct_categories': True,
            'legacy_timers_inactive': True, 'historical_state_preserved': True,
            'discarded_historical_requests': len(discarded),
            'integrity_policy': marker['integrity_policy'], 'download_limit': '100G'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect',))
    args = parser.parse_args()
    try:
        import cart_import_sab
        api = module('discovery-config').API()
        sab = cart_import_sab.SabSource(ROOT)
        result = inspect(ROOT, api, sab)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error) if type(error) is RuntimeError
                          else 'native_ownership_requires_review', 'error_type': type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
