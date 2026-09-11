#!/usr/bin/env python3
"""Host-owned encrypted backups, verified replication, and bounded retention.

Schedules use systemd on the cloud and cron on the NAS. No workstation private
key is installed on either host. Restore verification uses the escrowed keys.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
AGE = os.environ.get('BACKUP_AGE', '/opt/usenet/bin/age')
OUTPUT = Path(os.environ.get('BACKUP_OUTPUT', '/backups'))
RETENTION_DAYS = 90
PLEX_FILES = ('Preferences.xml', 'Plug-in Support/Databases/com.plexapp.plugins.library.db',
              'Plug-in Support/Databases/com.plexapp.plugins.library.blobs.db')


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def run(args):
    result = subprocess.run(args, capture_output=True, timeout=900)
    if result.returncode:
        raise RuntimeError('backup subcommand failed')
    return result.stdout


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    with temporary.open('w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    path.chmod(0o640)


def encrypt_contents(name, manifest, contents, recipient):
    qnap = module('backup-qnap')
    path = OUTPUT / name
    temporary = path.with_suffix('.partial')
    if path.exists() or temporary.exists():
        raise RuntimeError('backup filename already exists')
    with subprocess.Popen([AGE, '-r', recipient, '-o', str(temporary)], stdin=subprocess.PIPE,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
        try:
            qnap.write_tar(manifest, contents, process.stdin)
            process.stdin.close()
            if process.wait(timeout=180):
                raise RuntimeError('backup encryption failed')
        except BaseException:
            process.kill()
            process.wait()
            raise
    os.replace(temporary, path)
    path.chmod(0o640)
    receipt = {'scope': manifest['scope'], 'created_at': manifest['created_at'],
               'file': name, 'bytes': path.stat().st_size, 'sha256': digest(path),
               'files': len(manifest['entries'])}
    atomic_json(path.with_suffix('.json'), receipt)
    return receipt


def plex_snapshot(source):
    contents, entries = {}, []
    before = (source / 'Preferences.xml').read_bytes()
    with tempfile.TemporaryDirectory(prefix='plex-backup-') as scratch:
        for name in PLEX_FILES:
            path = source / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024**2:
                raise RuntimeError('unsafe or oversized Plex backup source')
            if name.endswith('.db'):
                destination = Path(scratch) / path.name
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=30)) as db:
                    with closing(sqlite3.connect(destination)) as target:
                        deadline = time.monotonic() + 90
                        def progress(*_):
                            if time.monotonic() > deadline:
                                raise RuntimeError('Plex snapshot timed out')
                        db.backup(target, pages=128, progress=progress, sleep=0.05)
                        target.execute('PRAGMA journal_mode=DELETE')
                data = destination.read_bytes()
                if not data.startswith(b'SQLite format 3\0'):
                    raise RuntimeError('invalid Plex database snapshot')
            else:
                data = before
            contents[name] = data
            entries.append({'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                            'source_mode': 0o600})
    if (source / 'Preferences.xml').read_bytes() != before:
        raise RuntimeError('Plex preferences changed during capture')
    return {'schema_version': 1, 'scope': 'plex-config', 'created_at': int(time.time()),
            'consistency': 'SQLite online backup; stable preferences; media and artwork excluded',
            'entries': entries}, contents


def prune_local(scope, root=None):
    # Only this scheduler's receipts authorize deletion, after a fresh success.
    # Keep at least seven generations regardless of age. Never touch master bundles.
    root = root or OUTPUT
    receipts = []
    for path in root.glob(scope + '-*.tar.json'):
        value = json.loads(path.read_text())
        if re.fullmatch(scope + r'-\d{8}T\d{6}Z\.tar\.age', value.get('file', '')):
            receipts.append((value['created_at'], path, value))
    for created, receipt, value in sorted(receipts, reverse=True)[7:]:
        archive = root / value['file']
        if created < time.time() - RETENTION_DAYS * 86400 and archive.is_file() and not archive.is_symlink():
            if digest(archive) != value['sha256']:
                raise RuntimeError('retention receipt mismatch')
            archive.unlink()
            receipt.unlink()


def cloud(stamp):
    backup = module('config-backup')
    catalog = module('catalogctl')
    settings = catalog.Settings.from_env()
    rclone = catalog.Rclone(settings)
    path = OUTPUT / ('cloud-' + stamp + '.tar.age')
    with catalog.cache_lock(settings, rclone):
        with tempfile.TemporaryDirectory(prefix='scheduled-cloud-') as scratch:
            manifest = backup.stage_snapshot(backup.ROOT, Path(scratch))
            backup.encrypt(Path(scratch), Path('/srv/usenet/config/backup-recipient.pub'), path, AGE)
        remote_dir = catalog.remote_join(settings.remote, '.backups', 'cloud')
        remote = catalog.remote_join(remote_dir, path.name)
        rclone.run('copyto', str(path), remote, '--immutable')
        with tempfile.TemporaryDirectory(prefix='backup-readback-') as scratch:
            readback = Path(scratch) / path.name
            rclone.run('copyto', remote, str(readback))
            if digest(path) != digest(readback):
                raise RuntimeError('remote backup readback mismatch')
        receipt = {'scope': 'cloud-config', 'created_at': int(time.time()), 'file': path.name,
                   'bytes': path.stat().st_size, 'sha256': digest(path), 'files': len(manifest['entries']),
                   'remote_ciphertext_verified': True}
        receipt_file = path.with_suffix('.json')
        atomic_json(receipt_file, receipt)
        rclone.run('copyto', str(receipt_file), catalog.remote_join(remote_dir, receipt_file.name), '--immutable')
    prune_local('cloud')
    return [receipt]


def nas(stamp):
    qnap = module('backup-qnap')
    recipient = Path('/run/backup-recipient.pub').read_text().strip()
    if not recipient.startswith('ssh-ed25519 '):
        raise RuntimeError('unexpected NAS public backup recipient')
    manifest, contents = qnap.snapshot(Path('/source/usenet'), '/share/Container/usenet')
    receipts = [encrypt_contents('qnap-' + stamp + '.tar.age', manifest, contents, recipient)]
    manifest, contents = plex_snapshot(Path('/source/plex'))
    receipts.append(encrypt_contents('plex-' + stamp + '.tar.age', manifest, contents, recipient))
    # Existing read-only Storage Box access mirrors encrypted cloud backups.
    mirror = OUTPUT / 'cloud'
    mirror.mkdir(mode=0o750, exist_ok=True)
    mirror.chmod(0o750)
    run(['rclone', 'copy', 'catalog:.backups/cloud', str(mirror), '--include', 'cloud-*.tar.*', '--max-depth', '1', '--transfers', '1', '--checkers', '1', '--sftp-connections', '3', '--immutable'])
    for path in mirror.glob('cloud-*.tar.json'):
        path.chmod(0o640)
        value = json.loads(path.read_text())
        filename = value.get('file', '')
        if not re.fullmatch(r'cloud-\d{8}T\d{6}Z\.tar\.age', filename):
            raise RuntimeError('unexpected cloud backup receipt')
        archive = mirror / filename
        archive.chmod(0o640)
        if archive.is_symlink() or digest(archive) != value['sha256']:
            raise RuntimeError('NAS cloud replica verification failed')
    for scope in ('qnap', 'plex'):
        prune_local(scope)
    prune_local('cloud', mirror)
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', choices=('cloud', 'nas'))
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    status_file = OUTPUT / (args.host + '-status.json')
    # Serialize cron/manual invocations before reading freshness or creating files.
    lock = (OUTPUT / (args.host + '.lock')).open('a')
    if not args.check:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
    previous = json.loads(status_file.read_text()) if status_file.exists() else {}
    last_success = previous.get('last_success', 0)
    if args.check:
        healthy = previous.get('status') == 'ok' and time.time() - last_success < 36 * 3600
        print(json.dumps({'host': args.host, 'healthy': healthy, 'last_success': last_success}))
        return 0 if healthy else 1
    if not args.force and time.time() - last_success < 23 * 3600:
        return 0
    try:
        if run([AGE, '--version']).decode().strip().lstrip('v') != '1.3.2':
            raise RuntimeError('unreviewed age version')
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        receipts = cloud(stamp) if args.host == 'cloud' else nas(stamp)
        result = {'host': args.host, 'status': 'ok', 'last_success': int(time.time()),
                  'checked_at': int(time.time()), 'archives': receipts, 'retention_days': RETENTION_DAYS}
        atomic_json(status_file, result)
        print(json.dumps({'host': args.host, 'status': 'ok', 'archives': len(receipts)}))
        return 0
    except Exception as error:
        atomic_json(status_file, {'host': args.host, 'status': 'failed', 'last_success': last_success,
                    'checked_at': int(time.time()), 'error_type': type(error).__name__})
        print(json.dumps({'host': args.host, 'status': 'failed', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
