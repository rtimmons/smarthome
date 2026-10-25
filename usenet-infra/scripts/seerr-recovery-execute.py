#!/usr/bin/env python3
"""Bounded native acquisition of individually mapped, approved missing TV episodes.

No setting changes, deletions, manual imports, season packs or rejection overrides.
Evidence and write-ahead retry budgets remain private and survive restarts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path('/srv/usenet')
STATE = ROOT / 'config/catalog/seerr-recovery'
MAX_GRABS = 3
MAX_SEARCHES = 7
RETRY_SECONDS = 6 * 3600
NO_RESULT_SECONDS = 24 * 3600
MAX_QUEUE = 3
BACKLOG_GRACE_SECONDS = 6 * 3600
LOOKUP_INTERVAL_SECONDS = 15 * 60


def module(name, root=ROOT):
    spec = importlib.util.spec_from_file_location(name, root / 'libexec' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def fingerprint(release):
    # The same named release on another indexer is not a fresh retry.
    return hashlib.sha256(release['title'].strip().casefold().encode()).hexdigest()


def eligible_release(release, series_id, episode_id, free_gib, attempted):
    return (release.get('approved') is True and release.get('downloadAllowed') is True
        and release.get('rejected') is False and not release.get('temporarilyRejected')
        and not release.get('rejections') and release.get('protocol') == 'usenet'
        and release.get('fullSeason') is False and release.get('mappedSeriesId') == series_id
        and [e.get('id') for e in release.get('mappedEpisodeInfo', [])] == [episode_id]
        and isinstance(release.get('size'), int) and 0 < release['size'] <= 100 * 1024**3
        and release['size'] * 2 < (free_gib - 30) * 1024**3
        and bool(release.get('guid')) and isinstance(release.get('indexerId'), int)
        and not re.search(r'(?i)\b(?:AV1|extras?|bonus|samples?)\b', release.get('title', ''))
        and fingerprint(release) not in attempted)


def due(entry, now):
    attempts = entry.get('attempts', [])
    if any(a['status'] in ('pending', 'uncertain') for a in attempts):
        return False
    if len(attempts) >= MAX_GRABS or entry.get('searches', 0) >= MAX_SEARCHES:
        return False
    result = entry.get('last_result')
    delay = (60 if result in ('search_pending', 'deferred') else
             NO_RESULT_SECONDS if result == 'no_eligible_release' else RETRY_SECONDS)
    return now - entry.get('last_search', 0) >= delay


def targets(snapshot, report):
    result = []
    if snapshot.get('blocked') or snapshot.get('processing'):
        return result
    for request in report['requests']:
        if request.get('app') != 'sonarr':
            continue
        source = next(r for r in snapshot['requests'] if r['id'] == request['request_id'])
        # Completed historical requests are never automatically reacquired.
        if source['status'] != 2:
            continue
        item = snapshot.get('items', {}).get(f'sonarr:{request["native_id"]}', {})
        if item.get('monitored') is not True:
            continue
        monitored_seasons = {s['seasonNumber'] for s in item.get('seasons', []) if s.get('monitored') is True}
        permitted = {e['id'] for e in item.get('episodes', [])
                     if e.get('monitored') is True and e['seasonNumber'] in monitored_seasons
                     and not e.get('hasFile') and not e.get('episodeFileId')}
        for proposal in request.get('proposals', []):
            if proposal['kind'] == 'missing_episode_search':
                for episode in proposal['ids']:
                    if episode not in permitted:
                        continue
                    result.append((request['request_id'], request['native_id'], episode))
    return sorted(set(result))


def native_gate(reader, rec):
    linked_jobs = set()
    for app in ('sonarr', 'radarr'):
        kind = 'Series' if app == 'sonarr' else 'Movie'
        page = reader.arr.call(app, f'queue?page=1&pageSize=1000&includeUnknown{kind}Items=true')
        rec.require(page['totalRecords'] == len(page['records']), 'native_queue_truncated')
        for row in page['records']:
            if row.get('status') == 'failed':
                continue
            rec.require(row.get('seriesId' if app == 'sonarr' else 'movieId') is not None
                        and (app != 'sonarr' or row.get('episodeId') is not None), 'unknown_native_queue_scope')
            linked_jobs.add(row.get('downloadId'))
        commands = reader.arr.call(app, 'command')
        rec.require(not any(c.get('status') in ('queued', 'started') for c in commands), 'native_commands_active')
    queue = reader.sab('queue')
    rec.require(int(queue['noofslots']) < MAX_QUEUE and not queue['paused'], 'queue_or_pause_gate')
    rec.require(float(queue['diskspace1']) >= 30 and float(queue['diskspace2']) >= 30, 'reserve_gate')
    rec.require(all(j.get('nzo_id') in linked_jobs for j in queue['slots']), 'unlinked_active_download')
    rec.require(all(j.get('status') not in ('Paused', 'Fetching') for j in queue['slots']), 'paused_or_unknown_job')
    return float(queue['diskspace1'])


def execute(reader, rec, state=STATE, now=None, request_id=None):
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    rec.require(state.is_dir() and not state.is_symlink() and not state.stat().st_mode & 0o077, 'state_not_private')
    with (state / 'execute.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        policy = rec.private_json(state / 'executor-policy.json')
        rec.require(policy == {'schema': 1, 'enabled': True, 'scope': 'approved_missing_tv'}, 'executor_not_enabled')
        previous = rec.private_json(state / 'report.json')
        age = now - rec.stamp(previous['generated_at'])
        rec.require(0 <= age <= 900, 'report_stale')
        journal_path = state / 'executor-journal.json'
        journal = rec.private_json(journal_path) if journal_path.exists() else {'schema': 1, 'episodes': {}}
        rec.require(journal.get('schema') == 1 and isinstance(journal.get('episodes'), dict), 'journal_invalid')
        # The five-minute observer already checks library files. When its fresh
        # report has no missing-TV proposal, avoid another remote filesystem walk.
        # Cached state can only suppress work; it can never authorize a grab.
        if request_id is None and not any(
                p.get('kind') == 'missing_episode_search'
                for request in previous.get('requests', []) for p in request.get('proposals', [])):
            return {'status': 'idle', 'grabs': 0, 'used_fresh_report': True}
        last_lookup = max([journal.get('last_lookup_at', 0)] +
                          [e.get('last_search', 0) for e in journal['episodes'].values()])
        if now - last_lookup < LOOKUP_INTERVAL_SECONDS:
            return {'status': 'lookup_cooldown', 'grabs': 0,
                    'retry_after_seconds': int(LOOKUP_INTERVAL_SECONDS - (now - last_lookup))}
        snapshot = rec.collect(reader)
        grace = 0 if request_id is not None else BACKLOG_GRACE_SECONDS
        report = rec.plan(snapshot, previous, now=now, grace_seconds=grace)
        options = [t for t in targets(snapshot, report) if request_id is None or t[0] == request_id]
        selected = next((t for t in options if due(journal['episodes'].get(f'{t[1]}:{t[2]}', {}), now)), None)
        if not selected:
            return {'status': 'idle', 'eligible_episodes': len(options), 'grabs': 0}
        selected_request_id, series_id, episode_id = selected
        free = native_gate(reader, rec)
        key = f'{series_id}:{episode_id}'
        entry = journal['episodes'].setdefault(key, {'searches': 0, 'attempts': []})
        entry.update(searches=entry['searches'] + 1, last_search=now, last_result='search_pending')
        journal['last_lookup_at'] = now
        rec.atomic_json(journal_path, journal)
        releases = reader.arr.call('sonarr', f'release?episodeId={episode_id}', timeout=120)
        attempted = {a['fingerprint'] for a in entry['attempts']}
        candidates = [r for r in releases if eligible_release(r, series_id, episode_id, free, attempted)]
        candidates.sort(key=lambda r: r.get('releaseWeight', 10**9))
        if not candidates:
            entry['last_result'] = 'no_eligible_release'
            rec.atomic_json(journal_path, journal)
            return {'status': 'no_eligible_release', 'grabs': 0}
        release = candidates[0]
        # A lookup may take minutes. Re-read approvals, file existence, queue,
        # mounts, health and completed imports immediately before the POST.
        try:
            fresh = rec.collect(reader)
            rec.require(selected in targets(fresh, rec.plan(fresh, previous, now=now, grace_seconds=grace)), 'scope_changed')
            free = native_gate(reader, rec)
            rec.require(eligible_release(release, series_id, episode_id, free, attempted), 'release_or_space_changed')
        except rec.RecoveryError:
            # No write was attempted. Reconsider once the changing queue settles,
            # while retaining the lookup count and all durable grab budgets.
            entry['last_result'] = 'deferred'
            rec.atomic_json(journal_path, journal)
            return {'status': 'deferred', 'grabs': 0}
        # Journal before dispatch: a timeout/crash never blindly repeats a grab.
        attempt = {'fingerprint': fingerprint(release), 'status': 'pending', 'at': now,
                   'request_id': selected_request_id, 'guid': release['guid'], 'indexer_id': release['indexerId']}
        entry['attempts'].append(attempt)
        rec.atomic_json(journal_path, journal)
        try:
            reader.arr.call('sonarr', 'release', 'POST',
                            {'guid': release['guid'], 'indexerId': release['indexerId']})
        except Exception:
            attempt['status'] = 'uncertain'
            rec.atomic_json(journal_path, journal)
            raise rec.RecoveryError('grab_outcome_uncertain') from None
        attempt['status'] = 'submitted'
        entry['last_result'] = 'submitted'
        rec.atomic_json(journal_path, journal)
        return {'status': 'submitted', 'grabs': 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'status'))
    parser.add_argument('--request-id', type=int, help='Operator-reviewed request: skip only the initial observation grace')
    args = parser.parse_args()
    rec = module('seerr-recovery')
    try:
        if args.action == 'status':
            policy = rec.private_json(STATE / 'executor-policy.json')
            status = rec.private_json(STATE / 'executor-status.json') if (STATE / 'executor-status.json').exists() else {}
            print(json.dumps({'enabled': policy.get('enabled'), 'budget_scope': 'custom_worker_only', **status}, sort_keys=True))
            return 0
        result = execute(rec.Reader(), rec, request_id=args.request_id)
    except BlockingIOError:
        result = {'status': 'busy', 'grabs': 0}
    except Exception as error:
        result = {'status': 'held', 'reason': str(error) if isinstance(error, rec.RecoveryError) else 'execution_failed', 'error_type': type(error).__name__, 'grabs': 0}
    result['budget_scope'] = 'custom_worker_only'
    result['checked_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    rec.atomic_json(STATE / 'executor-status.json', result)
    print(json.dumps(result, sort_keys=True))
    return 1 if result['status'] == 'held' else 0


if __name__ == '__main__':
    raise SystemExit(main())
