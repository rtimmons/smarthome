#!/usr/bin/env python3
"""Read-only native-cutover baseline; never authorizes or performs a cutover.

Run through Justfile so cloud-command uses the dedicated identity and host pin.
Private snapshots stay in build/native-cutover; stdout contains only an allowlist.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

GIB = 1024 ** 3
RESERVE = 30 * GIB
MARGIN = 5 * GIB
UNITS = (
    "usenet-capacity-admission.timer", "usenet-cart-import.timer",
    "usenet-incomplete-maintenance.timer", "usenet-library.service",
    "usenet-discovery.service", "usenet-sab-remote.service",
)


def mounted(path):
    # Same-filesystem bind mounts are invisible to Path.is_mount().
    if shutil.which('findmnt'):
        result = subprocess.run(['findmnt', '--noheadings', '--output', 'TARGET',
                                 '--target', str(path)], capture_output=True, text=True, check=True)
        return str(path) in (line.strip() for line in result.stdout.splitlines())
    return path.is_mount()


def collect():
    """Cloud-side reads only. Raw data must go to the private capture file."""
    root = Path('/srv/usenet')
    sys.path.insert(0, str(root / 'libexec'))
    import cart_import_sab
    spec = importlib.util.spec_from_file_location('discovery', root / 'libexec/discovery-config.py')
    discovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery)
    api = discovery.API()
    sab = cart_import_sab.SabSource(root)
    snapshot = sab.snapshot()
    def read(relative):
        return json.loads((root / relative).read_text())
    def signature(relative):
        return hashlib.sha256((root / relative).read_bytes()).hexdigest()
    filesystems = {}
    for name, relative in (('local', 'downloads/incomplete'),
                           ('remote', 'downloads/complete/remote'), ('library', 'library')):
        path = root / relative
        stats = os.statvfs(path)
        filesystems[name] = {'available_bytes': stats.f_bavail * stats.f_frsize,
                             'available_inodes': stats.f_favail, 'mounted': mounted(path)}
    # Read the native database's byte counters, not rounded display-size strings.
    with sqlite3.connect(sab.database.absolute().as_uri() + '?mode=ro', uri=True) as db:
        history_sizes = [row[0] for row in db.execute('SELECT downloaded FROM history WHERE downloaded > 0')]
    journals = {p.name: json.loads(p.read_text()) for p in sorted(
        (root / 'state/catalog/cart-import/jobs').glob('*.json'))}
    native = read('config/catalog/native-ownership.json') if (root / 'config/catalog/native-ownership.json').exists() else {}
    acceptance = read('state/catalog/native-acceptance.json') if (root / 'state/catalog/native-acceptance.json').exists() else {}
    return {
        'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'snapshot': snapshot, 'history_sizes': history_sizes, 'journals': journals,
        'journal_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(
            (root / 'state/catalog/cart-import/jobs').glob('*.json'))},
        'activation_sha256': signature('state/catalog/cart-import/armed.json'),
        'capacity': read('state/catalog/capacity-admission/state.json'),
        'importer_status': read('state/catalog/cart-import/status.json'),
        'scratch_mode': read('config/catalog/remote-scratch.json'),
        'native_ownership': native,
        'native_acceptance': {'phase': acceptance.get('phase'), 'verification': acceptance.get('verification', {})},
        'filesystems': filesystems,
        'sab_misc': sab.api('get_config', section='misc')['config']['misc'],
        'sab_categories': sab.api('get_config', section='categories')['config']['categories'],
        'sab_feeds': sab.api('get_config', section='rss')['config'].get('rss', []),
        'apps': {app: {endpoint: api.call(app, endpoint) for endpoint in (
            'downloadclient', 'config/downloadclient', 'config/mediamanagement',
            'rootfolder', 'remotepathmapping', 'health')} for app in ('radarr', 'sonarr')},
        'units': {unit: subprocess.check_output(['systemctl', 'show', unit,
            '--property=LoadState,ActiveState,SubState,UnitFileState'], text=True) for unit in UNITS},
    }


def byte_count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('invalid byte counter')
    return value


def budget(local_free, remote_free, download, unpacked):
    """One new job: complete repair replacement and remote import-copy fallback.

    Historical maxima are a lower bound for planning, not a future size limit.
    Unpacked size is independent of NZB size; compressible input can expand.
    """
    local_free, remote_free, download, unpacked = map(
        byte_count, (local_free, remote_free, download, unpacked))
    if not download or not unpacked:
        raise ValueError('missing measured size')
    local_required = 2 * download + RESERVE + MARGIN
    remote_required = 2 * unpacked + RESERVE + MARGIN
    return {
        'download_bytes': download, 'unpacked_bytes': unpacked,
        'reserve_bytes': RESERVE, 'planning_margin_bytes': MARGIN,
        'local_required_bytes': local_required, 'remote_required_bytes': remote_required,
        'local_shortfall_bytes': max(0, local_required - local_free),
        'remote_shortfall_bytes': max(0, remote_required - remote_free),
    }


def summarize(data):
    """Build a fresh allowlist; never copy remote dictionaries into public output."""
    fs = data['filesystems']
    journals = list(data['journals'].values())
    largest_download = max(map(byte_count, data['history_sizes']), default=0)
    largest_unpacked = max((sum(byte_count(v['signature'][0]) for v in j.get('sources', {}).values())
                            for j in journals), default=0)
    measured = budget(fs['local']['available_bytes'], min(fs['remote']['available_bytes'],
                      fs['library']['available_bytes']), largest_download, largest_unpacked)
    blockers = []
    for name in ('local', 'remote'):
        if measured[name + '_shortfall_bytes']:
            blockers.append(name + '_capacity_insufficient_for_observed_workload')
    if not all(fs[name]['mounted'] for name in ('local', 'remote', 'library')):
        blockers.append('required_mount_missing')
    queue = data['snapshot']['queue']
    if data['snapshot']['postprocessing'] or any(q.get('status') != 'Paused' for q in queue):
        blockers.append('sab_not_idle')
    if data['capacity'].get('admitted'):
        blockers.append('existing_admission_requires_reconciliation')
    apps = {}
    categories = []
    for app, field in (('radarr', 'movieCategory'), ('sonarr', 'tvCategory')):
        values = data['apps'][app]
        clients = values['downloadclient']
        category = None
        if len(clients) == 1 and clients[0].get('implementation') == 'Sabnzbd':
            category = next((f.get('value') for f in clients[0].get('fields', []) if f['name'] == field), None)
        categories.append(category)
        apps[app] = {
            'client_count': len(clients),
            'completed_handling': values['config/downloadclient'].get('enableCompletedDownloadHandling') is True,
            'hardlinks_enabled': values['config/mediamanagement'].get('copyUsingHardlinks') is True,
            'skip_free_space_check': values['config/mediamanagement'].get('skipFreeSpaceCheckWhenImporting') is True,
            'minimum_import_free_mib': values['config/mediamanagement'].get('minimumFreeSpaceWhenImporting')
                if type(values['config/mediamanagement'].get('minimumFreeSpaceWhenImporting')) is int else None,
            'all_roots_accessible': bool(values['rootfolder']) and all(r.get('accessible') is True for r in values['rootfolder']),
            'health_issue_count': len(values['health']),
        }
    distinct = all(isinstance(c, str) and c for c in categories) and len(set(categories)) == 2
    if not distinct:
        blockers.append('arr_categories_not_distinct')
    misc = data['sab_misc']
    floors = all(misc.get(key) == '30G' for key in ('download_free', 'complete_free'))
    if not floors:
        blockers.append('sab_reserve_settings_changed')
    native = data.get('native_ownership', {})
    phase = native.get('phase') if native.get('phase') in ('acceptance', 'active') else None
    evidence = data.get('native_acceptance', {})
    recorded = (phase == 'active' and evidence.get('phase') == 'verified' and
                all(evidence.get('verification', {}).get(k) is True for k in (
                    'movie_import_cleanup', 'episode_import_cleanup', 'plex_movie', 'plex_episode',
                    'large_repair', 'service_restart', 'historical_state_preserved')))
    return {
        'schema_version': 1, 'status': 'preflight_only', 'checked_at': data['checked_at'],
        'cutover_performed': False, 'read_only_capture': True, 'blockers': blockers,
        'native_ownership_phase': phase, 'prior_acceptance_evidence_recorded': recorded,
        'queue': {'count': len(queue), 'paused_count': sum(q.get('status') == 'Paused' for q in queue),
                  'globally_paused': data['snapshot']['paused'] is True,
                  'postprocessing': byte_count(data['snapshot']['postprocessing'])},
        'journal_count': len(journals),
        'completed_journals': sum(j.get('phase', '').startswith('cleaned') for j in journals),
        'capacity_hold_count': len(data['capacity']['held']),
        'importer_errors': byte_count(data['importer_status']['errors']),
        'importer_holds': byte_count(data['importer_status']['held']),
        'available_bytes': {name: byte_count(fs[name]['available_bytes']) for name in ('local', 'remote', 'library')},
        'observed_workload_budget': measured, 'sab_30G_floors_preserved': floors,
        'enabled_direct_feeds': sum(f.get('enable') in (True, 1, '1') for f in data['sab_feeds']),
        'arr_categories_distinct': bool(distinct), 'apps': apps,
        'pending_requirements': [] if recorded else [
            'explicit_integrity_policy', 'approved_future_size_and_expansion_bounds',
            'native_queue_limit_validation', 'fresh_application_user_filesystem_probes',
            'fresh_movie_and_episode_selections', 'movie_tv_cleanup_and_plex_acceptance',
            'large_repair_and_service_restart_acceptance', 'post_cutover_hold_and_journal_comparison',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.collect:
            print(json.dumps(collect()))
            return 0
        base = Path('build/native-cutover')
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder = Path(tempfile.mkdtemp(prefix='preflight-', dir=base))
        with (folder / 'snapshot.json').open('xb') as output, (folder / 'stderr.txt').open('xb') as errors:
            with Path(__file__).open('rb') as source:
                subprocess.run(['./scripts/cloud-command', 'sudo', '-n', '-u', 'usenet',
                    'python3', '-', '--collect'], stdin=source, stdout=output, stderr=errors, check=True)
        report = summarize(json.loads((folder / 'snapshot.json').read_text()))
        (folder / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0
    except Exception:
        # SSH/API/JSON exceptions can contain secrets or media names.
        print(json.dumps({'status': 'failed', 'reason': 'preflight_capture_or_validation_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
