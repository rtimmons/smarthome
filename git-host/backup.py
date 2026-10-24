#!/usr/bin/env python3
"""Consistent stopped-service snapshots, encrypted replication, and freshness."""
import datetime as dt
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time

OUTPUT = Path('/backups/forgejo')
SOURCE = Path('/source')
NAME = re.compile(r'forgejo-\d{8}T\d{6}Z\.tar\.age')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix + '.new')
    with temp.open('w') as stream:
        # Capture is UID 1004; off-host replication uses the existing backup
        # container's UID 0/GID 100. Both read receipts through the private 0700 root.
        os.chmod(temp, 0o640)
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def database_path(source):
    import configparser
    config = source / 'data/custom/conf/app.ini'
    ini = configparser.ConfigParser(interpolation=None)
    ini.read_string('[DEFAULT]\n' + config.read_text())
    relative = Path(ini['database']['PATH']).relative_to('/var/lib/gitea')
    if '..' in relative.parts:
        raise RuntimeError('database path escapes service storage')
    return source / 'data' / relative


def inventory(source):
    # Validate before hashing: even a read-only SQLite connection can update its
    # transient SHM index when the filesystem permits it (e.g. a restore fixture).
    database = database_path(source)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('Forgejo database integrity check failed')
    entries = []
    for root in ('data', 'config', 'compose.yaml', 'backup.sh', 'backup.py', 'install-cron.py'):
        path = source / root
        if not path.exists() or path.is_symlink():
            raise RuntimeError('missing or unsafe backup root')
        paths = [path, *sorted(path.rglob('*'))] if path.is_dir() else [path]
        for item in paths:
            if item.is_symlink() or not (item.is_dir() or item.is_file()):
                raise RuntimeError('unsupported backup source type')
            st = item.stat()
            entry = {'path': str(item.relative_to(source)), 'mode': st.st_mode & 0o777,
                     'type': 'directory' if item.is_dir() else 'file', 'size': st.st_size,
                     'mtime_ns': st.st_mtime_ns}
            if item.is_file():
                entry['sha256'] = digest(item)
            entries.append(entry)
    return entries


def capture():
    entries = inventory(SOURCE)
    total = sum(e['size'] for e in entries if e['type'] == 'file')
    if shutil.disk_usage(OUTPUT).free < 2 * total + 100 * 1024**3:
        raise RuntimeError('backup would breach NAS free-space reserve')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = 'forgejo-' + stamp + '.tar.age'
    target = OUTPUT / name
    partial = OUTPUT / (name + '.partial')
    if target.exists() or partial.exists():
        raise RuntimeError('backup name already exists')
    recipient = Path('/recipient.pub').read_text().strip()
    if not recipient.startswith('ssh-ed25519 '):
        raise RuntimeError('unexpected encryption recipient')
    version = subprocess.check_output(['/age', '--version']).decode().strip()
    if version != 'v1.3.2':
        raise RuntimeError('unexpected age version')
    manifest = {'schema': 1, 'scope': 'forgejo', 'created_at': int(time.time()),
                'consistency': 'Forgejo stopped; raw SQLite integrity checked', 'entries': entries}
    with subprocess.Popen(['/age', '-r', recipient, '-o', str(partial)], stdin=subprocess.PIPE,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
        try:
            with tarfile.open(fileobj=process.stdin, mode='w|', dereference=True) as archive:
                raw = json.dumps(manifest, sort_keys=True).encode()
                info = tarfile.TarInfo('manifest.json'); info.size = len(raw); info.mode = 0o600
                archive.addfile(info, io.BytesIO(raw))
                for entry in entries:
                    path = SOURCE / entry['path']
                    st = path.stat()
                    if st.st_size != entry['size'] or st.st_mtime_ns != entry['mtime_ns']:
                        raise RuntimeError('backup source changed during capture')
                    archive.add(path, arcname=entry['path'], recursive=False)
            process.stdin.close()
            if process.wait(timeout=120):
                raise RuntimeError('encryption failed')
        except BaseException:
            process.kill(); process.wait()
            partial.unlink(missing_ok=True)
            raise
    os.replace(partial, target)
    target.chmod(0o600)
    receipt = {'schema': 1, 'scope': 'forgejo', 'file': name, 'created_at': manifest['created_at'],
               'sha256': digest(target), 'bytes': target.stat().st_size, 'files': len(entries)}
    save(target.with_suffix('.json'), receipt)
    save(OUTPUT / 'pending.json', receipt)
    print(json.dumps({'capture': 'ok', 'files': len(entries), 'bytes': receipt['bytes']}))


def publish():
    receipt = json.loads((OUTPUT / 'pending.json').read_text())
    name = receipt['file']
    if not NAME.fullmatch(name):
        raise RuntimeError('invalid backup name')
    archive = OUTPUT / name
    if archive.is_symlink() or digest(archive) != receipt['sha256']:
        raise RuntimeError('ciphertext changed')
    config = '/source/usenet/config/backup/offhost/rclone.conf'
    base = ['rclone', '--config', config, '--sftp-connections', '3', '--transfers', '1', '--checkers', '1']
    def run(*args):
        result = subprocess.run([*base, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
        if result.returncode:
            raise RuntimeError('offhost transfer failed')
    remote = 'nasbackup:archives/forgejo/' + name
    run('copyto', str(archive), remote, '--immutable')
    readback = OUTPUT / (name + '.readback')
    try:
        run('copyto', remote, str(readback))
        if digest(readback) != receipt['sha256']:
            raise RuntimeError('offhost readback mismatch')
    finally:
        readback.unlink(missing_ok=True)
    receipt['remote_ciphertext_verified'] = True
    receipt_path = archive.with_suffix('.json')
    save(receipt_path, receipt)
    run('copyto', str(receipt_path), 'nasbackup:archives/forgejo/' + receipt_path.name, '--immutable')
    save(OUTPUT / 'status.json', {'status': 'ok', 'last_success': int(time.time()), 'archive': receipt})
    (OUTPUT / 'pending.json').unlink()
    # Only checksum-matching archives owned by this service; remote retention is indefinite.
    receipts = sorted(OUTPUT.glob('forgejo-*.tar.json'), reverse=True)
    for path in receipts[7:]:
        old = json.loads(path.read_text())
        if NAME.fullmatch(old.get('file', '')) and old['created_at'] < time.time() - 90 * 86400:
            old_archive = OUTPUT / old['file']
            if old_archive.is_file() and not old_archive.is_symlink() and digest(old_archive) == old['sha256']:
                old_archive.unlink(); path.unlink()
    print(json.dumps({'offhost_backup': 'verified', 'archive': name}))


def status():
    path = OUTPUT / 'status.json'
    return json.loads(path.read_text()) if path.exists() else {}


def main():
    os.umask(0o077)
    action = sys.argv[1]
    previous = status()
    if action == 'due':
        if not database_path(SOURCE).is_file():
            raise RuntimeError('configured database is missing')
        return 10 if previous.get('status') == 'ok' and time.time() - previous.get('last_success', 0) < 23 * 3600 else 0
    if action == 'check':
        healthy = (previous.get('status') == 'ok' and time.time() - previous.get('last_success', 0) < 36 * 3600
                   and previous.get('archive', {}).get('remote_ciphertext_verified') is True)
        print(json.dumps({'healthy': healthy, **previous}))
        return 0 if healthy else 1
    try:
        {'capture': capture, 'publish': publish}[action]()
        return 0
    except Exception as error:
        reason = str(error) if type(error) is RuntimeError else type(error).__name__
        save(OUTPUT / 'status.json', {'status': 'failed', 'last_success': previous.get('last_success', 0),
                                     'error_type': type(error).__name__, 'reason': reason})
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'reason': reason}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
