#!/usr/bin/env python3
"""Switch an idle hybrid to native ownership; never search, grab or delete media.

The private receipt is the rollback baseline. An interrupted apply is not replayed.
RSS stays disabled to preserve the existing backlog; new explicit Arr searches
own acquisition. Finish requires complete acceptance evidence.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

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


def inspect(root, api, sab, helper):
    marker = json.loads((root / MARKER).read_text())
    require(marker.get('integrity_policy') == 'native_arr_import_and_cleanup'
            and marker.get('phase') in ('acceptance', 'active'), 'native_marker_invalid')
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
    for timer in helper.TIMERS:
        require(helper.command('systemctl', 'show', timer, '--property=ActiveState', '--value') == 'inactive',
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
    require(preserved(old['snapshot'], sab.snapshot(), discarded) and helper.state_fingerprints(root) == old['fingerprints'],
            'historical_holds_or_journals_changed')
    return {'status': 'verified', 'phase': marker['phase'], 'distinct_categories': True,
            'legacy_timers_inactive': True, 'historical_state_preserved': True,
            'discarded_historical_requests': len(discarded),
            'integrity_policy': marker['integrity_policy'], 'download_limit': '100G'}


def apply(root, api, sab, helper):
    receipt = root / RECEIPT
    require(not receipt.exists() and not (root / MARKER).exists(), 'existing_cutover_requires_phase_review')
    snapshot = helper.quiet(sab)
    controller = helper.capacity_module(root).Controller(root)
    controller.require_resources(); controller.require_dependencies()
    require(controller.available() >= 235 * 1024**3 and controller.budget_available() >= 235 * 1024**3,
            'initial_100g_envelope_not_available')
    value = {'schema_version': 1, 'phase': 'quiesce_intent', 'created_at': time.time(),
             'snapshot': snapshot, 'fingerprints': helper.state_fingerprints(root),
             'timers': {t: helper.command('systemctl', 'show', t, '--property=ActiveState,UnitFileState')
                        for t in helper.TIMERS},
             'feeds': sab.api('get_config', section='rss')['config']['rss'],
             'misc': sab.api('get_config', section='misc')['config']['misc'],
             'categories': sab.api('get_config', section='categories')['config']['categories'],
             'prowlarr_downloadclients': api.call('prowlarr', 'downloadclient'),
             'apps': {a: {e: api.call(a, e) for e in ('downloadclient', 'config/downloadclient', 'config/indexer', 'config/mediamanagement')}
                      for a in ('radarr', 'sonarr')}}
    require(not any(c['name'] in ('radarr', 'sonarr') for c in value['categories']), 'native_category_already_exists')
    require(all(len(v['downloadclient']) == 1 for v in value['apps'].values()), 'unique_clients_required')
    require(all(c.get('implementation') == 'Sabnzbd' for c in value['prowlarr_downloadclients']),
            'unreviewed_prowlarr_download_client')
    helper.save_receipt(receipt, value)
    helper.command('systemctl', 'stop', *helper.TIMERS)
    deadline = time.monotonic() + 150
    while any(helper.command('systemctl', 'show', t.replace('.timer', '.service'), '--property=ActiveState', '--value')
              not in ('inactive', 'failed') for t in helper.TIMERS):
        require(time.monotonic() < deadline, 'legacy_worker_still_active')
        time.sleep(1)
    with (root / 'state/catalog/capacity-admission/lock').open('r+') as admission, \
            (root / 'state/catalog/locks/cache.lock').open('r+') as cache:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(cache, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(helper.quiet(sab)['queue'] == snapshot['queue'], 'queue_changed_before_cutover')
        for feed in value['feeds']:
            helper.set_feed(sab, feed['name'], 0)
        require(sab.api('pause').get('status') is True, 'global_pause_failed')
        marker = {'schema_version': 1, 'phase': 'acceptance', 'integrity_policy': 'native_arr_import_and_cleanup',
                  'max_download_bytes': 100 * 1024**3, 'planning_unpacked_bytes': 100 * 1024**3}
        helper.save_receipt(root / MARKER, marker)
        for timer in helper.TIMERS:
            service = timer.replace('.timer', '.service')
            dropin = Path('/etc/systemd/system') / (service + '.d/native-ownership.conf')
            require(not dropin.exists(), 'legacy_guard_already_exists')
            dropin.parent.mkdir(exist_ok=True)
            dropin.write_text('[Unit]\nConditionPathExists=!' + str(root / MARKER) + '\n')
            dropin.chmod(0o644)
            helper.command('systemctl', 'disable', timer)
        helper.command('systemctl', 'daemon-reload')
        value['phase'] = 'configuration_intent'; helper.save_receipt(receipt, value)
        for client in value['prowlarr_downloadclients']:
            disabled = dict(client, enable=False)
            api.call('prowlarr', 'downloadclient/' + str(client['id']), 'PUT', disabled)
        for key, setting in LIMITS.items():
            sab.api('set_config', section='misc', keyword=key, value=setting)
        for app in ('radarr', 'sonarr'):
            sab.api('set_config', section='categories', name=app, dir=app, priority=0, pp=3, script='None', newzbin='')
            client = native_client(value['apps'][app]['downloadclient'][0], app)
            api.call(app, 'downloadclient/' + str(client['id']), 'PUT', client)
            config = copy.deepcopy(value['apps'][app]['config/downloadclient'])
            config.update(enableCompletedDownloadHandling=True, autoRedownloadFailed=False,
                          autoRedownloadFailedFromInteractiveSearch=False)
            api.call(app, 'config/downloadclient', 'PUT', config)
            config = copy.deepcopy(value['apps'][app]['config/indexer'])
            config.update(rssSyncInterval=0, maximumSize=102400)
            api.call(app, 'config/indexer', 'PUT', config)
            media = copy.deepcopy(value['apps'][app]['config/mediamanagement'])
            media.update(skipFreeSpaceCheckWhenImporting=False, copyUsingHardlinks=True,
                         minimumFreeSpaceWhenImporting=max(30 * 1024, media['minimumFreeSpaceWhenImporting']))
            api.call(app, 'config/mediamanagement', 'PUT', media)
        require(helper.quiet(sab)['history'] == snapshot['history'], 'historical_sab_history_changed')
        result = inspect(root, api, sab, helper)
        value['phase'] = 'configured'; helper.save_receipt(receipt, value)
        # The operator admits only the selected acceptance jobs while RSS is off.
        if not snapshot['paused']:
            require(sab.api('resume').get('status') is True, 'global_resume_failed')
        return result


def finish(root, api, sab, helper):
    result = inspect(root, api, sab, helper)
    helper.quiet(sab)
    evidence = json.loads((root / 'state/catalog/native-acceptance.json').read_text())
    required = {'movie_import_cleanup', 'episode_import_cleanup', 'plex_movie', 'plex_episode',
                'large_repair', 'service_restart', 'historical_state_preserved'}
    require(evidence.get('phase') == 'verified'
            and all(evidence.get('verification', {}).get(k) is True for k in required),
            'complete_native_acceptance_evidence_required')
    require(api.call('radarr', 'movie/' + str(evidence['added']['radarr']['id'])).get('hasFile') is True
            and api.call('sonarr', 'episode/' + str(evidence['episode']['id'])).get('hasFile') is True,
            'native_media_files_required')
    marker = json.loads((root / MARKER).read_text())
    marker.update(phase='active', rss_policy='explicit_requests_only_preserve_existing_backlog',
                  accepted_at=time.time())
    helper.save_receipt(root / MARKER, marker)
    # Existing monitored missing movies must not become an implicit backfill.
    # Keep RSS off; explicit native searches/add-and-search own new requests.
    result['phase'] = 'active'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('apply', 'inspect', 'finish'))
    parser.add_argument('--accept-native-cleanup', action='store_true')
    args = parser.parse_args()
    try:
        import cart_import_sab
        helper = module('repair-spool-setup')
        api = module('discovery-config').API()
        sab = cart_import_sab.SabSource(ROOT)
        require(args.action != 'apply' or (args.accept_native_cleanup and os.geteuid() == 0),
                'explicit_native_cleanup_decision_required')
        require(args.action != 'finish' or os.geteuid() == 0, 'root_required')
        result = (apply(ROOT, api, sab, helper) if args.action == 'apply' else
                  finish(ROOT, api, sab, helper) if args.action == 'finish' else
                  inspect(ROOT, api, sab, helper))
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error) if type(error) is RuntimeError
                          else 'private_cutover_phase_requires_review', 'error_type': type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
