#!/usr/bin/env python3
"""Manual, encrypted cloud configuration backup and isolated verified restore.

Capture runs on the cloud host and needs only an SSH public recipient. Decrypt
and restore run on the workstation; its private identity never leaves it.
Requires age 1.3.2. This command never restores over a running installation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

AGE_VERSION = '1.3.2'
ROOT = Path('/srv/usenet')
MAX_BYTES = 2 * 1024**3
MAX_FILES = 100_000
TREES = ('config/sabnzbd', 'config/prowlarr', 'config/rclone', 'config/catalog',
         'state/catalog', 'scripts', 'libexec', 'compose/cloud')
SINGLES = ('config/catalog.env', 'config/catalog.env.defaults', 'config/backup-recipient.pub',
           'state/sab-smoke-test.json',
           'secrets/storagebox/id_ed25519', 'secrets/storagebox/known_hosts')
REQUIRED = ('config/sabnzbd/sabnzbd.ini', 'config/prowlarr/config.xml',
            'config/prowlarr/prowlarr.db', 'config/catalog.env',
            'config/rclone/rclone.conf', 'compose/cloud/compose.yaml')
OMIT_DIRS = {'logs', 'log', 'backups', '__pycache__', 'cache', 'nzbcache', 'nzb_backup',
             'download', 'downloads', 'incomplete', 'complete', 'nzb', 'mediacover', 'updates', 'updatelogs'}
SQLITE_HEADER = b'SQLite format 3\x00'


class BackupError(RuntimeError):
    """Only fixed, nonsecret error messages cross the command boundary."""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def ordinary(path: Path) -> os.stat_result:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise BackupError('Only ordinary files may be captured; links and special files are refused.')
    return info


def allowed(name: str) -> bool:
    return (name in SINGLES or any(name.startswith(tree + '/') for tree in TREES)
            or re.fullmatch(r'metadata/manifests/[a-z0-9][a-z0-9._-]{2,127}\.json', name) is not None)


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and str(path) == name and '..' not in path.parts and '\\' not in name


def inventory(root: Path) -> dict[str, Path]:
    paths = {}
    for tree in TREES:
        base = root / tree
        if not base.exists():
            continue
        if base.is_symlink() or not base.is_dir():
            raise BackupError('A configured source directory is not an ordinary directory.')
        for parent in base.parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise BackupError('Source directory links are refused.')
        for directory, folders, files in os.walk(base, followlinks=False):
            for folder in folders:
                if (Path(directory) / folder).is_symlink():
                    raise BackupError('Source directory links are refused.')
            folders[:] = [folder for folder in folders if folder.lower() not in OMIT_DIRS]
            for filename in files:
                if filename.endswith(('-wal', '-shm', '-journal', '.log', '.pyc')) or filename.lower() in {'logs.db', 'log.db'}:
                    continue
                path = Path(directory) / filename
                ordinary(path)
                paths[path.relative_to(root).as_posix()] = path
    for name in SINGLES:
        path = root / name
        if path.exists() or path.is_symlink():
            for parent in path.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise BackupError('Source directory links are refused.')
            ordinary(path)
            paths[name] = path
    if not set(REQUIRED) <= paths.keys():
        raise BackupError('Required cloud configuration is missing; no complete backup was produced.')
    if len(paths) > MAX_FILES or sum(path.stat().st_size for path in paths.values()) > MAX_BYTES:
        raise BackupError('Configuration exceeds the bounded backup size or file-count limit.')
    return dict(sorted(paths.items()))


def read_environment(root: Path) -> dict[str, str]:
    path = root / 'config/catalog.env'
    if ordinary(path).st_mode & 0o027:
        raise BackupError('Catalog environment permissions must exclude group writes and all world access.')
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if separator and key in ('SABNZBD_API_KEY', 'CATALOG_REMOTE'):
            if key in values or not value.strip():
                raise BackupError('The protected catalog environment has missing or duplicate required values.')
            values[key] = value.strip()
    if len(values) != 2:
        raise BackupError('The protected catalog environment lacks required backup settings.')
    return values


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BackupError('Application API redirects are refused.')


def require_idle(key: str) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
    counts = []
    for mode, section, field, parameters in (
            ('queue', 'queue', 'noofslots_total', {}),
            ('history', 'history', 'ppslots', {'archive': 0, 'last_history_update': -1})):
        data = urllib.parse.urlencode(dict(parameters, mode=mode, output='json', apikey=key, start=0, limit=1)).encode()
        request = urllib.request.Request('http://127.0.0.1:8080/api', data=data)
        with opener.open(request, timeout=15) as response:
            result = json.load(response)
        value = result[section][field]
        if isinstance(value, bool) or not str(value).isdigit():
            raise BackupError('Application job counts could not be verified.')
        counts.append(int(value))
    if any(counts):
        raise BackupError('Backup refused while SAB has queued or post-processing jobs.')


def capture_manifests(root: Path, remote: str) -> dict[str, bytes]:
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_/-]+', remote) or '..' in remote.split('/'):
        raise BackupError('Catalog remote is not a supported explicit path.')
    base = remote.rstrip('/') + '/manifests'
    prefix = ['rclone', '--config', str(root / 'config/rclone/rclone.conf'),
              '--contimeout', '10s', '--timeout', '30s', '--retries', '1', '--low-level-retries', '1']
    def run(*args):
        return subprocess.run([*prefix, *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=60).stdout
    names = run('lsf', base, '--files-only', '--max-depth', '1', '--format', 'p').decode().splitlines()
    if len(names) > MAX_FILES or len(names) != len(set(names)):
        raise BackupError('Remote manifest inventory is invalid or exceeds the limit.')
    result = {}
    for name in sorted(names):
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,127}\.json', name):
            raise BackupError('Remote manifest inventory contains an unexpected filename.')
        content = run('cat', base + '/' + name)
        if len(content) > 16 * 1024**2 or not isinstance(json.loads(content), dict):
            raise BackupError('A remote manifest is invalid or exceeds the limit.')
        result['metadata/manifests/' + name] = content
    if sum(map(len, result.values())) > MAX_BYTES:
        raise BackupError('Remote metadata exceeds the bounded backup size.')
    return result


def sqlite_integrity(path: Path) -> None:
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise BackupError('A settings database failed its integrity check.')


def stage_snapshot(root: Path, stage: Path, idle=require_idle, manifests=capture_manifests) -> dict:
    paths = inventory(root)
    environment = read_environment(root)
    idle(environment['SABNZBD_API_KEY'])
    entries, fingerprints, databases = [], {}, []
    with ExitStack() as stack:
        for name, source in paths.items():
            info = ordinary(source)
            target = stage / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with source.open('rb') as stream:
                is_sqlite = stream.read(16) == SQLITE_HEADER
            if source.suffix == '.db' and not is_sqlite:
                raise BackupError('A settings database has an invalid SQLite header.')
            if is_sqlite:
                connection = stack.enter_context(closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)))
                version = connection.execute('PRAGMA data_version').fetchone()[0]
                deadline = time.monotonic() + 60
                def progress(*unused):
                    if time.monotonic() > deadline:
                        raise BackupError('Settings database snapshot timed out.')
                with closing(sqlite3.connect(target)) as destination:
                    connection.backup(destination, pages=128, progress=progress, sleep=0.05)
                    # Materialize a standalone database. A WAL-mode source
                    # otherwise leaves a WAL header in the copied main file.
                    destination.execute('PRAGMA journal_mode=DELETE')
                databases.append((connection, version, source, info.st_dev, info.st_ino))
                sqlite_integrity(target)
            else:
                # Never turn a source link introduced during capture into a
                # staged link: chmod/tar must only see ordinary private files.
                descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'rb') as original:
                    if not stat.S_ISREG(os.fstat(original.fileno()).st_mode):
                        raise BackupError('Source files changed type during capture.')
                    with target.open('wb') as copied:
                        shutil.copyfileobj(original, copied)
                fingerprints[name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, digest(target))
            target.chmod(0o600)
            entries.append({'path': name, 'size': target.stat().st_size, 'sha256': digest(target),
                            'sqlite': is_sqlite, 'source_mode': stat.S_IMODE(info.st_mode),
                            'source_uid': info.st_uid, 'source_gid': info.st_gid})
        remote = manifests(root, environment['CATALOG_REMOTE'])
        for name, content in remote.items():
            if not safe_name(name) or not allowed(name):
                raise BackupError('Remote metadata path was not allowlisted.')
            target = stage / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o600)
            entries.append({'path': name, 'size': len(content), 'sha256': digest(target),
                            'sqlite': False, 'source_mode': 0o600, 'source_uid': None, 'source_gid': None})
        idle(environment['SABNZBD_API_KEY'])
        if paths.keys() != inventory(root).keys() or remote != manifests(root, environment['CATALOG_REMOTE']):
            raise BackupError('Configuration or catalog metadata changed during capture; retry while idle.')
        for name, before in fingerprints.items():
            info = ordinary(paths[name])
            after = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, digest(paths[name]))
            if before != after:
                raise BackupError('Configuration changed during capture; retry while idle.')
        for connection, version, source, device, inode in databases:
            current = ordinary(source)
            if ((current.st_dev, current.st_ino) != (device, inode)
                    or connection.execute('PRAGMA data_version').fetchone()[0] != version):
                raise BackupError('A settings database changed during capture; retry during a quiet interval.')
    if len(entries) > MAX_FILES or sum(entry['size'] for entry in entries) > MAX_BYTES:
        raise BackupError('Combined configuration and metadata exceeds the bounded backup limits.')
    result = {'schema_version': 1, 'created_at': int(time.time()), 'scope': 'cloud-config',
              'age_version': AGE_VERSION, 'entries': entries}
    (stage / 'MANIFEST.json').write_text(json.dumps(result, sort_keys=True))
    (stage / 'MANIFEST.json').chmod(0o600)
    return result


def check_age(executable: str) -> None:
    result = subprocess.run([executable, '--version'], check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=10)
    if result.stdout.decode().strip().removeprefix('v') != AGE_VERSION:
        raise BackupError('The reviewed age version 1.3.2 is required.')


def private_file(path: Path) -> None:
    if ordinary(path).st_mode & 0o077:
        raise BackupError('Private key and encrypted archive files must have mode 0600 or stricter.')


def encrypt(stage: Path, recipient: Path, output: Path, age: str) -> None:
    ordinary(recipient)
    lines = [line for line in recipient.read_text().splitlines() if line and not line.startswith('#')]
    if len(lines) != 1 or not lines[0].startswith('ssh-ed25519 '):
        raise BackupError('Capture requires exactly one existing administrator Ed25519 public recipient.')
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise BackupError('Choose a new absolute encrypted archive path; existing files are never replaced.')
    if output.parent.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise BackupError('The archive parent directory must be private with mode 0700.')
    with tempfile.TemporaryDirectory(prefix='.config-backup-', dir=output.parent) as directory:
        target = Path(directory) / 'archive.age'
        with subprocess.Popen([age, '--encrypt', '--recipients-file', str(recipient), '--output', str(target)],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            try:
                with tarfile.open(fileobj=process.stdin, mode='w|') as archive:
                    archive.add(stage / 'MANIFEST.json', arcname='MANIFEST.json', recursive=False)
                    manifest = json.loads((stage / 'MANIFEST.json').read_text())
                    for entry in manifest['entries']:
                        archive.add(stage / entry['path'], arcname='payload/' + entry['path'], recursive=False)
                process.stdin.close()
                if process.wait(timeout=120):
                    raise BackupError('Encryption failed; no backup was published.')
            except BaseException:
                process.kill()
                process.wait()
                raise
        target.chmod(0o600)
        # Exclusive publication: a racing invocation cannot replace a backup.
        os.link(target, output)


def extract_verified(tar_path: Path, destination: Path) -> dict:
    if destination.exists() or destination.is_symlink():
        raise BackupError('Restore requires a fresh destination; existing files are never overwritten.')
    destination.mkdir(mode=0o700)
    try:
        with tarfile.open(tar_path, mode='r:') as archive:
            members = archive.getmembers()
            if len(members) > MAX_FILES + 1 or sum(member.size for member in members) > MAX_BYTES:
                raise BackupError('Archive exceeds bounded restore limits.')
            names = [member.name for member in members]
            if len(names) != len(set(names)) or names.count('MANIFEST.json') != 1:
                raise BackupError('Archive inventory is missing or contains duplicates.')
            if any(not member.isfile() or member.issparse() or not safe_name(member.name) for member in members):
                raise BackupError('Archive contains an unsafe path, link, or special file.')
            manifest_member = archive.getmember('MANIFEST.json')
            if manifest_member.size > 32 * 1024**2:
                raise BackupError('Archive inventory exceeds the size limit.')
            manifest = json.load(archive.extractfile(manifest_member))
            if manifest.get('schema_version') != 1 or manifest.get('scope') != 'cloud-config':
                raise BackupError('Unsupported configuration archive schema.')
            entries = manifest['entries']
            paths = [entry['path'] for entry in entries]
            if (len(paths) != len(set(paths)) or not set(REQUIRED) <= set(paths)
                    or any(not safe_name(name) or not allowed(name) for name in paths)
                    or set(names) != {'MANIFEST.json', *('payload/' + name for name in paths)}):
                raise BackupError('Archive does not match its allowlisted inventory.')
            for entry in entries:
                member = archive.getmember('payload/' + entry['path'])
                if member.size != entry['size']:
                    raise BackupError('Archive file size does not match the inventory.')
                target = destination / entry['path']
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream)
                target.chmod(0o600)
                if digest(target) != entry['sha256']:
                    raise BackupError('Archive checksum verification failed.')
                if entry['sqlite']:
                    sqlite_integrity(target)
            (destination / 'MANIFEST.json').write_text(json.dumps(manifest, sort_keys=True))
            (destination / 'MANIFEST.json').chmod(0o600)
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def decrypt_verify(archive: Path, identity: Path, destination: Path | None, age: str) -> dict:
    private_file(identity)
    private_file(archive)
    if destination is not None and (not destination.is_absolute() or destination.exists() or destination.is_symlink()):
        raise BackupError('Restore requires a new absolute destination directory.')
    # age may emit authenticated partial plaintext before a later failure.
    # Do not parse/extract anything until decryption has exited successfully.
    with tempfile.TemporaryDirectory(prefix='usenet-config-restore-', dir=destination.parent if destination else None) as directory:
        work = Path(directory)
        plaintext = work / 'archive.tar'
        subprocess.run([age, '--decrypt', '--identity', str(identity), '--output', str(plaintext), str(archive)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        plaintext.chmod(0o600)
        if plaintext.stat().st_size > MAX_BYTES + 128 * 1024**2:
            raise BackupError('Decrypted archive exceeds the restore size limit.')
        manifest = extract_verified(plaintext, work / 'restored')
        if destination is not None:
            # rename into a nonexistent empty-name target after full verification.
            # mkdir provides exclusive reservation against a competing restore.
            destination.mkdir(mode=0o700)
            try:
                os.rename(work / 'restored', destination)
            except BaseException:
                destination.rmdir()
                raise
        return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--age-binary', '--age', dest='age', default='age', help='Path to the pinned age 1.3.2 executable')
    commands = parser.add_subparsers(dest='operation', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--recipient-file', type=Path, required=True)
    capture.add_argument('--output', type=Path, required=True)
    for operation in ('verify', 'restore'):
        command = commands.add_parser(operation)
        command.add_argument('--identity-file', type=Path, required=True)
        command.add_argument('--archive', type=Path, required=True)
        if operation == 'restore':
            command.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        check_age(args.age)
        if args.operation == 'capture':
            with tempfile.TemporaryDirectory(prefix='usenet-config-capture-') as directory:
                manifest = stage_snapshot(ROOT, Path(directory))
                encrypt(Path(directory), args.recipient_file, args.output, args.age)
            archive = args.output
        else:
            archive = args.archive
            manifest = decrypt_verify(archive, args.identity_file, getattr(args, 'destination', None), args.age)
        print(json.dumps({'status': 'captured' if args.operation == 'capture' else 'verified',
                          'files': len(manifest['entries']),
                          'sqlite_databases': sum(entry['sqlite'] for entry in manifest['entries']),
                          'archive_sha256': digest(archive)}))
        return 0
    except BackupError as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({'error': 'Configuration backup operation failed; no raw response or secret was displayed.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
