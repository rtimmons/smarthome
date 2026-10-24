#!/usr/bin/env python3
"""Verify a decrypted Forgejo archive without exposing names or secret contents."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile


def verify(archive_path, destination):
    if destination.exists():
        raise RuntimeError('restore destination must be new')
    destination.mkdir(mode=0o700, parents=True)
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        if len({m.name for m in members}) != len(members):
            raise RuntimeError('duplicate archive paths')
        if any(Path(m.name).is_absolute() or '..' in Path(m.name).parts for m in members):
            raise RuntimeError('unsafe archive path')
        if any(not (m.isdir() or m.isfile()) for m in members):
            raise RuntimeError('unsupported archive entry')
        manifest = json.load(archive.extractfile('manifest.json'))
        if manifest.get('schema') != 1 or manifest.get('scope') != 'forgejo':
            raise RuntimeError('unexpected archive manifest')
        expected = {e['path']: e for e in manifest['entries']}
        if set(expected) != {m.name for m in members if m.name != 'manifest.json'}:
            raise RuntimeError('archive membership differs from manifest')
        archive.extractall(destination, filter='data')
    for name, entry in expected.items():
        path = destination / name
        if entry['type'] == 'file':
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != entry['sha256'] or path.stat().st_size != entry['size']:
                raise RuntimeError('restored file integrity mismatch')
    import configparser
    config = configparser.ConfigParser(interpolation=None)
    config.read_string('[DEFAULT]\n' + (destination / 'data/custom/conf/app.ini').read_text())
    relative = Path(config['database']['PATH']).relative_to('/var/lib/gitea')
    if '..' in relative.parts:
        raise RuntimeError('unexpected database path')
    with closing(sqlite3.connect((destination / 'data' / relative).as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('restored SQLite database is invalid')
    repo_setting = config.get('repository', 'ROOT', fallback='/var/lib/gitea/git/repositories')
    repo_relative = Path(repo_setting).relative_to('/var/lib/gitea')
    if '..' in repo_relative.parts:
        raise RuntimeError('unexpected repository storage path')
    repositories = list((destination / 'data' / repo_relative).glob('*/*.git'))
    for repository in repositories:
        result = subprocess.run(['git', '--git-dir', str(repository), 'fsck', '--full'],
                                env={**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull},
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if result.returncode:
            raise RuntimeError('restored Git object integrity check failed')
    return {'verified': True, 'files': len(expected), 'sqlite_integrity': 'ok',
            'git_repositories_verified': len(repositories)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive.resolve(), args.destination.resolve())))
