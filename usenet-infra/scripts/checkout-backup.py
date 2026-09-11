#!/usr/bin/env python3
"""Preserve unique checkout-local files in an additive encrypted NAS snapshot.

Excludes only named rebuildable caches. Never deletes the checkout. Restores only
to a new isolated directory; the immutable original SOPS inventory is unchanged.
"""
import argparse
from contextlib import closing
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CACHE_PARTS = {'.git', 'node_modules', '.venv', '__pycache__', '.pytest_cache',
               '.mypy_cache', '.ruff_cache', '.terraform', '.collections'}
CACHE_ROOTS = ('build/nvm', 'build/tools', 'build/home-assistant-addon',
               'build/checkout-backups', 'talos/build', 'snapshot-service/dist',
               'tinyurl-service/dist', 'sonos-api/dist', 'new-hass-configs/config-generator/dist')
MAX_TOTAL = 2 * 1024**3


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError('checkout backup subcommand failed')
    return result.stdout


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def excluded(name):
    parts = PurePosixPath(name).parts
    return (any(part in CACHE_PARTS for part in parts) or parts[-1] == '.DS_Store'
            or name.endswith('.tfplan')
            or any(name == root or name.startswith(root + '/') for root in CACHE_ROOTS))


def inventory(root):
    tracked = set(run(['git', 'ls-files', '-z'], cwd=root).decode().split('\0'))
    # Clean submodules are reproducible from their pinned commits. Refuse to omit
    # uncommitted submodule work, including untracked files.
    submodules = []
    for row in run(['git', 'ls-files', '--stage'], cwd=root).decode().splitlines():
        if row.startswith('160000 '):
            name = row.split('\t', 1)[1]
            if (root / name).is_dir():
                if run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=root / name):
                    raise RuntimeError('dirty submodule must be preserved separately')
                submodules.append(name)
    entries, skipped = [], 0
    for directory, folders, files in os.walk(root, followlinks=False):
        relative = Path(directory).relative_to(root)
        keep = []
        for folder in folders:
            name = (relative / folder).as_posix()
            if excluded(name) or name in submodules:
                continue
            if (root / name).is_symlink():
                raise RuntimeError('unclassified directory symlink')
            keep.append(folder)
        folders[:] = keep
        for filename in files:
            name = (relative / filename).as_posix()
            if name in tracked:
                continue
            if excluded(name):
                skipped += 1
                continue
            path = root / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise RuntimeError('unclassified local link or special file')
            entries.append({'path': name, 'size': info.st_size, 'sha256': digest(path),
                            'mode': stat.S_IMODE(info.st_mode)})
    entries.sort(key=lambda item: item['path'])
    if sum(item['size'] for item in entries) > MAX_TOTAL:
        raise RuntimeError('local file backup exceeds reviewed size limit')
    return entries


def verify(archive, identity, age, destination=None):
    if destination is not None and (not destination.is_absolute() or destination.exists()):
        raise RuntimeError('restore requires a new absolute destination')
    with tempfile.TemporaryDirectory(prefix='.checkout-verify-', dir=destination.parent if destination else None) as temporary:
        # Ciphertext is decrypted through a pipe; no plaintext tar is persisted.
        with subprocess.Popen([str(age), '-d', '-i', str(identity), str(archive)],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|gz') as tar:
                    members = iter(tar)
                    first = next(members, None)
                    if first is None or first.name != 'MANIFEST.json' or not first.isfile() or first.size > 16 * 1024**2:
                        raise RuntimeError('invalid checkout manifest')
                    manifest = json.load(tar.extractfile(first))
                    if manifest['scope'] != 'checkout-local-files' or manifest['schema_version'] != 1:
                        raise RuntimeError('unsupported checkout backup')
                    entries = {v['path']: v for v in manifest['entries']}
                    if len(entries) != len(manifest['entries']) or sum(v['size'] for v in entries.values()) > MAX_TOTAL:
                        raise RuntimeError('invalid checkout file inventory')
                    restored = Path(temporary) / 'restored'
                    restored.mkdir(mode=0o700)
                    seen = set()
                    for member in members:
                        name = member.name.removeprefix('payload/')
                        path = PurePosixPath(name)
                        if (not member.name.startswith('payload/') or name not in entries or name in seen
                                or not member.isfile() or path.is_absolute() or '..' in path.parts
                                or str(path) != name or member.size != entries[name]['size']):
                            raise RuntimeError('unsafe checkout archive member')
                        seen.add(name)
                        h = hashlib.sha256()
                        target = restored / name
                        if destination:
                            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        with closing(tar.extractfile(member)) as stream:
                            with (target.open('xb') if destination else open(os.devnull, 'wb')) as output:
                                for block in iter(lambda: stream.read(1024**2), b''):
                                    h.update(block)
                                    output.write(block)
                        if h.hexdigest() != entries[name]['sha256']:
                            raise RuntimeError('checkout checksum mismatch')
                        if destination:
                            target.chmod(entries[name]['mode'] & 0o700)
                    if seen != set(entries):
                        raise RuntimeError('incomplete checkout archive')
                if process.wait(timeout=30):
                    raise RuntimeError('checkout decryption failed')
                if destination:
                    os.rename(restored, destination)
                return manifest
            except BaseException:
                process.kill()
                process.wait()
                raise


def age_binary():
    import platform
    machine = (platform.system(), platform.machine())
    name = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(machine)
    if name is None:
        raise RuntimeError('unsupported recovery platform')
    return ROOT / ('build/tools/age-1.3.2/' + name + '/age')


def capture(identity):
    os.umask(0o077)
    # Physical local MongoDB files may only be captured while no mongod is running.
    probe = subprocess.run(['pgrep', '-x', 'mongod'], capture_output=True)
    if probe.returncode != 1 or probe.stderr:
        raise RuntimeError('cannot prove local MongoDB is stopped')
    entries = inventory(ROOT)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot = stamp + '-' + secrets.token_hex(8)
    folder = ROOT / 'build/checkout-backups' / snapshot
    folder.mkdir(mode=0o700, parents=True)
    age = age_binary()
    archive = folder / 'recovery.tar.age'
    manifest = {'schema_version': 1, 'scope': 'checkout-local-files', 'entries': entries,
                'source_revision': run(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                'mongodb_consistency': 'mongod absent; repeated whole-file checks',
                'rebuildable_exclusions': sorted(CACHE_PARTS) + list(CACHE_ROOTS),
                'created_at': stamp}
    import io
    with subprocess.Popen([str(age), '-R', str(identity) + '.pub', '-o', str(archive)],
                          stdin=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            with tarfile.open(fileobj=process.stdin, mode='w|gz') as tar:
                data = json.dumps(manifest, sort_keys=True).encode()
                item = tarfile.TarInfo('MANIFEST.json'); item.size = len(data); item.mode = 0o600
                tar.addfile(item, io.BytesIO(data))
                for entry in entries:
                    path = ROOT / entry['path']
                    if path.is_symlink() or digest(path) != entry['sha256']:
                        raise RuntimeError('local file changed during backup')
                    with path.open('rb') as stream:
                        item = tarfile.TarInfo('payload/' + entry['path']); item.size = entry['size']; item.mode = 0o600
                        tar.addfile(item, stream)
                    if digest(path) != entry['sha256']:
                        raise RuntimeError('local file changed during backup')
            process.stdin.close()
            if process.wait(timeout=180):
                raise RuntimeError('checkout encryption failed')
        except BaseException:
            process.kill(); process.wait(); raise
    if inventory(ROOT) != entries:
        raise RuntimeError('checkout local inventory changed during backup')
    if verify(archive, identity, age) != manifest:
        raise RuntimeError('checkout verification mismatch')
    receipt = {'schema_version': 1, 'snapshot_id': snapshot, 'deletion_safe': False,
               'scope': 'checkout-local-files', 'ciphertext_bytes': archive.stat().st_size,
               'ciphertext_sha256': digest(archive), 'files': len(entries),
               'source_revision': manifest['source_revision']}
    (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    spec = importlib.util.spec_from_file_location('store', ROOT / 'usenet-infra/scripts/recovery-store.py')
    store = importlib.util.module_from_spec(spec); spec.loader.exec_module(store)
    connection = store.connection_command(store.read_environment(ROOT / 'usenet-infra/.env'))
    store.push(folder, connection)
    fetched = folder.with_name(snapshot + '-fetched')
    store.fetch(snapshot, fetched, connection)
    if verify(fetched / 'recovery.tar.age', identity, age) != manifest:
        raise RuntimeError('NAS checkout backup failed validation')
    evidence = dict(receipt, nas_roundtrip_verified=True)
    (folder / 'verified.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inventory', 'capture', 'verify', 'restore'])
    parser.add_argument('--identity', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'inventory':
        items = inventory(ROOT)
        print(json.dumps({'files': len(items), 'bytes': sum(v['size'] for v in items), 'paths': [v['path'] for v in items]}, indent=2))
    elif args.action == 'capture':
        capture(args.identity)
    else:
        value = verify(args.archive, args.identity, age_binary(), args.destination if args.action == 'restore' else None)
        print(json.dumps({'status': 'verified', 'files': len(value['entries']), 'source_revision': value['source_revision']}))
