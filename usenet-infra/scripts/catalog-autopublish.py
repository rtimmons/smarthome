#!/usr/bin/env python3
"""Publish completed SAB jobs, verify canonical bytes, then reclaim cloud scratch.

A stable job ID and durable cleanup receipt make retries safe. Failed or active
jobs are never candidates. The NAS retains its explicit, selective Download action.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from types import SimpleNamespace

import catalogctl as catalog

spec = importlib.util.spec_from_file_location('sab_settings', Path(__file__).with_name('sab-settings.py'))
sab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sab)


def job_id(job):
    value = job.get('nzo_id')
    if not isinstance(value, str) or not value or len(value) > 200:
        raise catalog.CatalogError('invalid SAB job identity')
    return 'sab-' + hashlib.sha256(value.encode()).hexdigest()[:32]


def source_path(job, root):
    value = PurePosixPath(job.get('storage', ''))
    if '..' in value.parts:
        raise catalog.CatalogError('unsafe completed path')
    try:
        relative = value.relative_to('/data/complete')
    except ValueError:
        raise catalog.CatalogError('completed job is outside SAB completed storage') from None
    if not relative.parts or relative.parts[0].startswith('.'):
        raise catalog.CatalogError('refusing completed root or internal directory')
    candidate = root / relative
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            raise catalog.CatalogError('completed path contains a symbolic link')
        if component == root:
            break
    return catalog.confined(candidate, root)


def history(api):
    jobs = []
    seen = set()
    for start in range(0, 100000, 100):
        page = api.call('history', start=start, limit=100, archive=0,
                        last_history_update=-1)['history']['slots']
        for job in page:
            if job.get('status') == 'Completed' and job_id(job) not in seen:
                jobs.append(job)
                seen.add(job_id(job))
        if len(page) < 100:
            return sorted(jobs, key=lambda job: float(job.get('completed', 0)))
    raise catalog.CatalogError('SAB history exceeds pagination bound')


def load_receipt(path):
    if path.is_symlink():
        raise catalog.CatalogError('receipt may not be a symbolic link')
    return json.loads(path.read_text()) if path.exists() else None


def publish_job(job, settings, rclone, known, receipt_root):
    identity = job_id(job)
    receipt_file = receipt_root / (identity + '.json')
    receipt = load_receipt(receipt_file)
    if receipt and receipt.get('status') == 'cleaned':
        return 'already_published'
    source = source_path(job, settings.promotion_root)
    quarantine_root = settings.promotion_root / '.catalog-published'
    if quarantine_root.is_symlink():
        raise catalog.CatalogError('cleanup root may not be a symbolic link')
    quarantine = quarantine_root / identity
    if quarantine.is_symlink():
        raise catalog.CatalogError('cleanup path may not be a symbolic link')
    manifest = known.get(identity)
    # A previous process may have stopped during removal. Only a durable verified
    # receipt plus the matching canonical manifest permits finishing that cleanup.
    if receipt and receipt.get('status') == 'verified' and quarantine.exists():
        if manifest != receipt.get('manifest'):
            raise catalog.CatalogError('canonical manifest differs from cleanup receipt')
    else:
        if quarantine.exists():
            raise catalog.CatalogError('unowned cleanup directory')
        if not source.is_dir():
            return 'source_absent'
        if manifest is None:
            completed = dt.datetime.fromtimestamp(float(job['completed']), dt.timezone.utc).isoformat()
            category = 'video' if any(p.suffix.lower() in ('.mkv', '.mp4', '.avi', '.m4v', '.ts')
                                      for p in source.rglob('*')) else 'other'
            args = SimpleNamespace(path=str(source), id=identity, title=job['name'],
                category=category, source='SABnzbd completed job ' + job['nzo_id'],
                authorization='User-authorized automatic publication of their completed downloads',
                notes='Published automatically after SAB repair/unpack completed.',
                acquired_at=completed, delete_local=False)
            catalog.cmd_promote(args, settings, rclone)
            manifest = rclone.read_json(catalog.remote_join(settings.remote, 'manifests', identity + '.json'))
            catalog.validate_manifest(manifest)
            if manifest['id'] != identity:
                raise catalog.CatalogError('published manifest identity mismatch')
            known[identity] = manifest
        else:
            # Retry after publication but before local receipt: verify canonical
            # bytes again, not merely the existence of a remote filename.
            rclone.run('check', str(source), catalog.remote_join(settings.remote, manifest['remote_path']),
                       '--download')
        catalog.verify_local(source, manifest)
        actual_files, _ = catalog.inventory_files(source)
        if actual_files != manifest['files']:
            raise catalog.CatalogError('completed directory changed since publication')
        receipt = {'job_id': job['nzo_id'], 'id': identity, 'status': 'verified',
                   'source': str(source), 'manifest': manifest, 'verified_at': catalog.utc_now()}
        catalog.atomic_json(receipt_file, receipt)
        quarantine_root.mkdir(mode=0o700, exist_ok=True)
        # Same-filesystem rename means a crash cannot leave a partially deleted
        # directory at the original SAB path or erase a later replacement job.
        source.rename(quarantine)
    shutil.rmtree(quarantine)
    receipt.update(status='cleaned', cleaned_at=catalog.utc_now())
    catalog.atomic_json(receipt_file, receipt)
    catalog.resolve_failures(settings, identity)
    return 'published'


def run(api, settings, rclone):
    if os.environ.get('CATALOG_ROLE') != 'cloud':
        raise catalog.CatalogError('automatic publication requires cloud role')
    receipt_root = settings.state_root / 'auto-publish'
    receipt_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    counts = {'published': 0, 'already_published': 0, 'source_absent': 0, 'failed': 0}
    with catalog.cache_lock(settings, rclone):
        jobs = history(api)
        known = {item['id']: item for item in catalog.manifests(rclone, settings)}
        for job in jobs:
            identity = job_id(job)
            catalog.atomic_json(receipt_root / 'status.json',
                {'status': 'publishing', 'current_item': identity, 'updated_at': catalog.utc_now(), **counts})
            try:
                counts[publish_job(job, settings, rclone, known, receipt_root)] += 1
            except Exception as error:
                # Never place provider responses, URLs or credentials into logs.
                counts['failed'] += 1
                catalog.record_failure(settings, 'auto-publish', identity,
                    catalog.CatalogError('publication or verified cleanup failed; source retained for retry'))
                print(json.dumps({'item': identity, 'status': 'failed', 'error_type': type(error).__name__}), flush=True)
        result = {'status': 'failed' if counts['failed'] else 'idle',
                  'updated_at': catalog.utc_now(), **counts}
        catalog.atomic_json(receipt_root / 'status.json', result)
        return result


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'configure', 'status'))
    args = parser.parse_args()
    try:
        settings = catalog.Settings.from_env()
        if args.action == 'status':
            path = settings.state_root / 'auto-publish/status.json'
            print(path.read_text() if path.exists() else '{"status":"not_started"}')
            return 0
        api = sab.SabAPI(sab.read_api_key(Path('/srv/usenet/config/catalog.env')))
        if api.call('version').get('version') != sab.VERSION:
            raise catalog.CatalogError('unreviewed SAB version')
        if args.action == 'configure':
            # Let SAB recover from its own disk-space pause; a manual pause stays
            # paused. Existing 30 GiB reserves are preserved and verified.
            for name in ('download_free', 'complete_free'):
                if sab.misc_value(api, name) != '30G':
                    raise catalog.CatalogError('unexpected SAB disk reserve')
            if not sab.equivalent(sab.misc_value(api, 'fulldisk_autoresume'), 1):
                api.call('set_config', section='misc', keyword='fulldisk_autoresume', value=1)
            if not sab.equivalent(sab.misc_value(api, 'fulldisk_autoresume'), 1):
                raise catalog.CatalogError('disk autoresume readback failed')
            print('{"status":"configured","disk_autoresume":true,"reserve":"30G"}')
            return 0
        result = run(api, settings, catalog.Rclone(settings))
        print(json.dumps(result), flush=True)
        return 1 if result['failed'] else 0
    except catalog.CatalogBusy:
        print('{"status":"busy"}')
        return 0
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
