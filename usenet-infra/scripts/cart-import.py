#!/usr/bin/env python3
"""Journaled native imports of newly completed cart jobs; never a download mover.

Arr copies media into the mounted canonical library. Only an independently
hash-verified source can enter the private, same-filesystem cleanup quarantine.
Existing jobs are excluded by explicit activation, not rediscovered from disk.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import time

import catalogctl as catalog
from cart_import_arr import CartImportHold, NativeArr
from cart_import_sab import SabSource

SCHEMA = 1
MAX_FILES = 10000
TERMINAL = {'cleaned', 'cleaned_with_retained_files'}


class Hold(RuntimeError):
    """Fixed nonsecret reason suitable for operator status."""


def ref(value):
    if not isinstance(value, str) or not value or len(value) > 1000:
        raise Hold('invalid_job_identity')
    return hashlib.sha256(value.encode()).hexdigest()


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise Hold('nonregular_file')
    return [info.st_size, info.st_dev, info.st_ino, str(info.st_mtime_ns)]


def confined(path, root, *, missing=False):
    path, root = Path(path), Path(root)
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise Hold('path_outside_managed_root') from None
    if not relative.parts or any(part in {'.', '..'} or any(ord(c) < 32 for c in part)
                                 for part in relative.parts):
        raise Hold('invalid_managed_path')
    if root.is_symlink() or not root.is_dir():
        raise Hold('invalid_managed_root')
    for entry in [root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)]:
        if entry.is_symlink():
            raise Hold('symlink_refused')
        if not missing and not entry.exists():
            raise Hold('managed_path_missing')
    return path


def ensure_dir(path, root):
    confined(path, root, missing=True)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    confined(path, root)
    if not path.is_dir():
        raise Hold('state_directory_invalid')


def atomic(path, value):
    if path.is_symlink():
        raise Hold('state_symlink_refused')
    # Persist the pre-submit intent and verified cleanup receipt through power loss.
    # The general catalog helper is atomic but does not fsync its writes.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_json(path):
    regular(path)
    if path.stat().st_size > 16 * 1024**2:
        raise Hold('state_too_large')
    try:
        value = json.loads(path.read_text())
    except (ValueError, UnicodeError):
        raise Hold('state_invalid') from None
    if not isinstance(value, dict) or value.get('schema_version') != SCHEMA:
        raise Hold('state_schema_invalid')
    return value


def inventory(directory, *, allow_empty=False):
    result = {}
    for parent, dirs, files in os.walk(directory, followlinks=False):
        for name in dirs:
            path = confined(Path(parent) / name, directory)
            if not path.is_dir():
                raise Hold('source_directory_invalid')
        for name in files:
            path = confined(Path(parent) / name, directory)
            result[str(path.relative_to(directory))] = regular(path)
            if len(result) > MAX_FILES:
                raise Hold('source_inventory_too_large')
    if not result and not allow_empty:
        raise Hold('source_inventory_empty')
    return result


def source_directory(job, root):
    storage = job.get('storage', '')
    if not isinstance(storage, str):
        raise Hold('source_path_invalid')
    value = PurePosixPath(storage)
    if '..' in value.parts:
        raise Hold('source_path_invalid')
    try:
        relative = value.relative_to('/data/complete')
    except ValueError:
        raise Hold('source_outside_completed') from None
    if not relative.parts or relative.parts[0].startswith('.'):
        raise Hold('source_root_refused')
    path = confined(root / relative, root)
    if path.is_file():
        path = path.parent
    confined(path, root)
    if not path.is_dir():
        raise Hold('source_directory_invalid')
    return path


def selected_inventory(directory, selection=None):
    if selection is None:
        return inventory(directory)
    # A file-valued SAB receipt authorizes only that file, never its siblings.
    if not isinstance(selection, str) or Path(selection).name != selection:
        raise Hold('source_selection_invalid')
    path = confined(directory / selection, directory)
    return {selection: regular(path)}


def exclusive_rename(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        fn = libc.renameat2
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        result = fn(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    elif sys.platform == 'darwin' and hasattr(libc, 'renamex_np'):
        fn = libc.renamex_np
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        result = fn(os.fsencode(source), os.fsencode(target), 4)
    else:
        raise Hold('exclusive_rename_unavailable')
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


class RemoteVerifier:
    def __init__(self, settings, rclone, library):
        self.settings, self.rclone, self.library = settings, rclone, library

    def verify(self, path, size, digest):
        path = confined(path, self.library)
        relative = path.relative_to(self.library)
        if len(relative.parts) < 3 or relative.parts[0] not in {'Movies', 'TV'}:
            raise Hold('canonical_path_invalid')
        before = regular(path)
        if before[0] != size:
            raise Hold('canonical_size_mismatch')
        remote = catalog.remote_join(self.settings.remote, 'library', str(relative))
        first = json.loads(self.rclone.run('lsjson', remote, '--stat', capture=True))
        if first.get('IsDir') is not False or first.get('Size') != size:
            raise Hold('remote_metadata_mismatch')
        output = self.rclone.run('hashsum', 'sha256', remote, '--checkers', '1',
                                 '--sftp-disable-hashcheck=false', capture=True)
        lines = output.strip().splitlines()
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', lines[0]) if len(lines) == 1 else None
        if not match or match[1] != digest:
            raise Hold('canonical_sha256_mismatch')
        last = json.loads(self.rclone.run('lsjson', remote, '--stat', capture=True))
        if first != last or regular(path) != before:
            raise Hold('canonical_changed_during_verification')
        return {'path': str(path), 'signature': before, 'sha256': digest}


class Coordinator:
    def __init__(self, settings, sab=None, arr=None, remote=None, *, library=None,
                 clock=time.time, sleep=time.sleep, mounted=None, rclone=None):
        self.settings = settings
        self.sab, self.arr = sab or SabSource(), arr or NativeArr()
        self.library = Path(library or '/srv/usenet/library')
        self.base = settings.state_root / 'cart-import'
        self.jobs = self.base / 'jobs'
        self.root = settings.promotion_root
        self.rclone = rclone or catalog.Rclone(settings)
        self.remote = remote or RemoteVerifier(settings, self.rclone, self.library)
        self.clock, self.sleep = clock, sleep
        self.mounted = mounted or self.library.is_mount
        self.counts = {'completed': 0, 'held': 0, 'errors': 0}
        self.started = self.clock()

    def directories(self):
        if not self.settings.state_root.is_dir() or self.settings.state_root.is_symlink():
            raise Hold('catalog_state_root_invalid')
        ensure_dir(self.base, self.settings.state_root)
        ensure_dir(self.jobs, self.settings.state_root)

    def heartbeat(self, status, **extra):
        atomic(self.base / 'status.json', {'schema_version': SCHEMA, 'status': status,
            'updated_at': self.clock(), 'started_at': self.started, 'pid': os.getpid(),
            **self.counts, **extra})

    def activation(self):
        state = read_json(self.base / 'armed.json')
        if (not isinstance(state.get('armed_at'), (int, float)) or
            not isinstance(state.get('excluded_ids'), list) or
            not isinstance(state.get('excluded_rss_hashes'), list) or
            any(not isinstance(v, str) for v in state['excluded_ids']) or
            any(not re.fullmatch('[0-9a-f]{64}', v) for v in state['excluded_rss_hashes'])):
            raise Hold('activation_invalid')
        return state

    def arm(self):
        self.directories()
        if (self.base / 'armed.json').exists() or (self.base / 'armed.json').is_symlink():
            self.activation()
            return {'status': 'already_armed'}
        if any(self.jobs.iterdir()):
            raise Hold('activation_missing_with_existing_journals')
        cutoff = self.clock()
        snapshot = self.sab.snapshot()
        if snapshot['postprocessing'] or any(j.get('status') != 'Paused' for j in snapshot['queue']):
            raise Hold('activation_requires_idle_or_individually_paused_queue')
        excluded = {j['nzo_id'] for j in snapshot['queue'] + snapshot['history']}
        hashes = snapshot['rss_hashes']
        if any(not re.fullmatch('[0-9a-f]{64}', v) for v in hashes):
            raise Hold('activation_provenance_invalid')
        state = {'schema_version': SCHEMA, 'armed_at': cutoff,
                 'excluded_ids': sorted(excluded), 'excluded_rss_hashes': sorted(set(hashes))}
        atomic(self.base / 'armed.json', state)
        self.heartbeat('idle')
        return {'status': 'armed', 'excluded_jobs': len(excluded), 'excluded_feed_entries': len(hashes)}

    def eligible(self, job, activation):
        provenance = job.get('provenance') or {}
        return (job.get('nzo_id') not in activation['excluded_ids'] and
                job.get('status') == 'Completed' and job.get('category') in {'*', '', 'Default'} and
                job.get('archive') in (None, 0, False) and
                isinstance(job.get('time_added'), (int, float)) and job['time_added'] >= activation['armed_at'] and
                provenance.get('feed') == 'NZBGeek Cart' and provenance.get('unique') is True and
                isinstance(provenance.get('downloaded_at'), (int, float)) and
                provenance['downloaded_at'] >= activation['armed_at'] and
                re.fullmatch('[0-9a-f]{64}', str(provenance.get('url_sha256', ''))) is not None and
                provenance['url_sha256'] not in activation['excluded_rss_hashes'])

    def persist(self, record):
        record['updated_at'] = self.clock()
        atomic(self.jobs / (ref(record['job']['nzo_id']) + '.json'), record)

    def guard_job(self, record):
        if not self.mounted():
            raise Hold('canonical_mount_unavailable')
        current = self.sab.job(record['job']['nzo_id'])
        if not current or current.get('status') != 'Completed' or current.get('archive') not in (None, 0, False):
            raise Hold('completed_job_changed')
        for key in ('nzo_id', 'storage', 'category', 'completed'):
            if current.get(key) != record['job'].get(key):
                raise Hold('completed_job_identity_changed')
        if current['nzo_id'] in self.arr.owned_download_ids():
            raise Hold('arr_owned_download')
        return current

    def source_unchanged(self, record):
        directory = confined(Path(record['source_dir']), self.root)
        actual = selected_inventory(directory, record.get('source_selection'))
        expected = {k: v['signature'] for k, v in record['sources'].items()}
        if actual != expected:
            raise Hold('source_inventory_changed')

    def advance(self, record):
        self.guard_job(record)
        if record['phase'] == 'admitted':
            directory = source_directory(record['job'], self.root)
            storage = self.root / PurePosixPath(record['job']['storage']).relative_to('/data/complete')
            selection = storage.name if storage.is_file() else None
            entries = selected_inventory(directory, selection)
            sources = {}
            for name, signature in entries.items():
                self.heartbeat('processing', item=ref(record['job']['nzo_id']), phase='hashing_source')
                digest = catalog.sha256_file(directory / name)
                if regular(directory / name) != signature:
                    raise Hold('source_changed_during_hash')
                sources[name] = {'signature': signature, 'sha256': digest}
            if selected_inventory(directory, selection) != entries:
                raise Hold('source_inventory_changed')
            record.update(source_dir=str(directory), source_selection=selection,
                          sources=sources, phase='source_verified')
            self.persist(record)
        if record['phase'] == 'source_verified':
            self.source_unchanged(record)
            directory = Path(record['source_dir'])
            plan = self.arr.prepare(record['job'], directory, [directory / n for n in record['sources']])
            record.update(plan=plan, phase='prepared')
            self.persist(record)
        if record['phase'] == 'prepared':
            self.guard_job(record)
            self.source_unchanged(record)
            record['phase'] = 'submitting'
            self.persist(record)
            command_id = self.arr.submit(record['plan'])
            record.update(command_id=command_id, phase='importing')
            self.persist(record)
        if record['phase'] == 'submitting':
            command = self.arr.command(record['plan'], None)
            record.update(command_id=command['id'], phase='importing')
            self.persist(record)
        if record['phase'] == 'importing':
            deadline = self.clock() + 5 * 3600
            while True:
                self.heartbeat('processing', item=ref(record['job']['nzo_id']), phase='native_import')
                state = self.arr.command(record['plan'], record['command_id'])
                self.persist(record)
                if state.get('status') == 'completed':
                    break
                if state.get('status') in {'failed', 'aborted', 'cancelled'}:
                    raise Hold('native_import_failed')
                if self.clock() >= deadline:
                    raise Hold('native_import_still_running')
                self.sleep(5)
            record['phase'] = 'imported'
            self.persist(record)
        verified_now = False
        if record['phase'] == 'imported':
            self.guard_job(record)
            self.source_unchanged(record)
            files = self.arr.imported_files(record['plan'])
            if not files or len({f['source'] for f in files}) != len(files) or len({f['destination'] for f in files}) != len(files):
                raise Hold('imported_mapping_invalid')
            verified = []
            for entry in files:
                source = confined(Path(entry['source']), Path(record['source_dir']))
                relative = str(source.relative_to(record['source_dir']))
                if relative not in record['sources']:
                    raise Hold('unowned_imported_source')
                expected = record['sources'][relative]
                self.heartbeat('processing', item=ref(record['job']['nzo_id']), phase='verifying_canonical')
                proof = self.remote.verify(Path(entry['destination']), expected['signature'][0], expected['sha256'])
                verified.append({'source': relative, 'canonical': proof})
            self.source_unchanged(record)
            record.update(verified=verified, phase='verified', verified_at=self.clock())
            self.persist(record)
            verified_now = True
        if record['phase'] == 'verified':
            self.cleanup(record, reverify=not verified_now)
        if record['phase'] not in TERMINAL:
            raise Hold('journal_phase_invalid')

    def cleanup(self, record, *, reverify=True):
        self.guard_job(record)
        directory = Path(record['source_dir'])
        confined(directory, self.root, missing=True)
        quarantine = self.root / '.cart-import-cleanup' / ref(record['job']['nzo_id'])
        ensure_dir(quarantine, self.root)
        # On recovery, verify every canonical destination before further deletion.
        for item in record['verified']:
            source = record['sources'][item['source']]
            path = Path(item['canonical']['path'])
            confined(path, self.library)
            if reverify:
                item['canonical'] = self.remote.verify(path, source['signature'][0], source['sha256'])
            if regular(path) != item['canonical']['signature']:
                raise Hold('canonical_changed_before_cleanup')
        self.persist(record)
        for item in record['verified']:
            self.guard_job(record)
            source = confined(directory / item['source'], self.root, missing=True)
            expected = record['sources'][item['source']]['signature']
            pending = quarantine / (ref(item['source']) + '.pending')
            confined(pending, self.root, missing=True)
            if pending.exists() and source.exists():
                raise Hold('cleanup_collision')
            if source.exists():
                if regular(source) != expected:
                    raise Hold('source_changed_before_cleanup')
                exclusive_rename(source, pending)
            if pending.exists():
                if regular(pending) != expected:
                    raise Hold('quarantine_identity_changed')
                if regular(Path(item['canonical']['path'])) != item['canonical']['signature']:
                    raise Hold('canonical_changed_before_cleanup')
                pending.unlink()
            item['source_removed'] = True
            self.persist(record)
            parent = source.parent
            while parent != self.root and (parent == directory or directory in parent.parents):
                try:
                    parent.rmdir()
                except OSError as error:
                    if error.errno in (errno.ENOTEMPTY, errno.ENOENT, errno.EEXIST):
                        break
                    raise
                parent = parent.parent
        try:
            quarantine.rmdir()
        except OSError as error:
            if error.errno not in (errno.ENOTEMPTY, errno.ENOENT):
                raise
        remaining = inventory(directory, allow_empty=True) if directory.exists() else {}
        record.update(phase='cleaned_with_retained_files' if remaining else 'cleaned',
                      cleaned_at=self.clock(), retained_files=len(remaining),
                      reclaimed_payload_bytes=sum(record['sources'][i['source']]['signature'][0] for i in record['verified']))
        self.persist(record)

    def run(self):
        self.directories()
        activation = self.activation()
        if not self.mounted():
            raise Hold('canonical_mount_unavailable')
        snapshot = self.sab.snapshot()
        for job in snapshot['history']:
            eligible = self.eligible(job, activation)
            provenance = job.get('provenance') or {}
            # New unowned Default completions with uncertain provenance stay
            # visible, but this category alone can never authorize an import.
            needs_review = (job.get('nzo_id') not in activation['excluded_ids'] and
                job.get('status') == 'Completed' and job.get('category') in {'*', '', 'Default'} and
                job.get('archive') in (None, 0, False) and
                isinstance(job.get('time_added'), (int, float)) and job['time_added'] >= activation['armed_at'] and
                provenance.get('url_sha256') not in activation['excluded_rss_hashes'])
            if eligible or needs_review:
                path = self.jobs / (ref(job['nzo_id']) + '.json')
                if not path.exists() and not path.is_symlink():
                    clean_job = {k: job.get(k) for k in ('nzo_id', 'name', 'storage', 'category', 'completed', 'time_added', 'provenance')}
                    record = {'schema_version': SCHEMA, 'phase': 'admitted', 'job': clean_job,
                              'admitted_at': self.clock(), 'updated_at': self.clock()}
                    if not eligible:
                        record['hold'] = 'cart_provenance_unproven'
                    atomic(path, record)
        for path in sorted(self.jobs.glob('*.json')):
            record = read_json(path)
            if path.stem != ref(record['job']['nzo_id']):
                raise Hold('journal_identity_mismatch')
            if record['phase'] in TERMINAL:
                self.counts['completed'] += 1
                if record['phase'] == 'cleaned_with_retained_files':
                    self.counts['held'] += 1
                continue
            if record.get('hold'):
                self.counts['held'] += 1
                continue
            self.heartbeat('processing', item=path.stem, phase=record['phase'])
            try:
                self.advance(record)
                record.pop('last_error', None)
                self.persist(record)
                self.counts['completed'] += 1
                self.counts['held'] += record['phase'] == 'cleaned_with_retained_files'
                catalog.resolve_failures(self.settings, 'cart-' + path.stem)
            except (Hold, CartImportHold) as error:
                reason = str(error)
                if not re.fullmatch('[a-z0-9_]{1,100}', reason):
                    reason = 'native_import_requires_review'
                if reason == 'arr_request_failed' or (
                        reason == 'episode_metadata_not_ready' and record['phase'] == 'source_verified'):
                    record['last_error'] = reason
                    self.persist(record)
                    self.counts['errors'] += 1
                    continue
                record['hold'] = reason
                self.persist(record)
                self.counts['held'] += 1
                catalog.record_failure(self.settings, 'cart-import', 'cart-' + path.stem,
                    catalog.CatalogError('cart import held; inspect its private journal and preserve source'))
            except Exception:
                first_failure = not record.get('last_error')
                record['last_error'] = 'operation_failed_retry_pending'
                self.persist(record)
                self.counts['errors'] += 1
                if first_failure:
                    catalog.record_failure(self.settings, 'cart-import', 'cart-' + path.stem,
                        catalog.CatalogError('cart import interrupted; source preserved for a guarded retry'))
        status = 'failed' if self.counts['errors'] else 'held' if self.counts['held'] else 'idle'
        self.heartbeat(status)
        return {'status': status, **self.counts}

    def retry(self, identity):
        self.directories()
        self.activation()
        if not re.fullmatch('[0-9a-f]{64}', identity):
            raise Hold('invalid_retry_reference')
        record = read_json(self.jobs / (identity + '.json'))
        if ref(record['job']['nzo_id']) != identity:
            raise Hold('journal_identity_mismatch')
        if record.get('hold') == 'cart_provenance_unproven':
            current = self.sab.job(record['job']['nzo_id'])
            if not current or not self.eligible(current, self.activation()):
                raise Hold('cart_provenance_unproven')
            for key in ('storage', 'category', 'completed', 'time_added'):
                if current.get(key) != record['job'].get(key):
                    raise Hold('completed_job_identity_changed')
            record['job']['provenance'] = current['provenance']
        if record['phase'] == 'cleaned_with_retained_files':
            directory = confined(Path(record['source_dir']), self.root, missing=True)
            remaining = inventory(directory, allow_empty=True) if directory.exists() else {}
            record['retained_files'] = len(remaining)
            if not remaining:
                record['phase'] = 'cleaned'
        record.pop('hold', None)
        record.pop('last_error', None)
        self.persist(record)
        return {'status': 'retry_enabled', 'item': identity}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('arm', 'run', 'status', 'retry'))
    parser.add_argument('item', nargs='?')
    args = parser.parse_args()
    coordinator = None
    try:
        settings = catalog.Settings.from_env()
        if os.environ.get('CATALOG_ROLE') != 'cloud':
            raise Hold('cloud_role_required')
        coordinator = Coordinator(settings)
        if args.action == 'status':
            path = coordinator.base / 'status.json'
            print(json.dumps(read_json(path)) if path.exists() else '{"status":"not_armed"}')
            return 0
        with catalog.cache_lock(settings, coordinator.rclone):
            if args.action == 'arm':
                result = coordinator.arm()
            elif args.action == 'retry':
                result = coordinator.retry(args.item or '')
            else:
                result = coordinator.run()
        print(json.dumps(result), flush=True)
        return 1 if result.get('status') in {'failed', 'held'} else 0
    except catalog.CatalogBusy:
        print('{"status":"busy"}')
        return 0
    except Exception:
        if coordinator and coordinator.base.is_dir() and not coordinator.base.is_symlink():
            try:
                coordinator.heartbeat('failed', reason='configuration_or_state_requires_review')
            except Exception:
                pass
        print('{"status":"failed","reason":"configuration_or_state_requires_review"}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
