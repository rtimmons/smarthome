#!/usr/bin/env python3
"""Encrypt the four root-owned VPN/proxy files without local plaintext files.

The only remote reads are sudo cat of four fixed paths through cloud-command
and its dedicated pinned SSH identity. A bounded tar and its checksum manifest
stay in memory until encrypted; the private key stays on this controller. No
restore-to-live operation or arbitrary remote path is supported.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading

INFRA = Path(__file__).resolve().parents[1]
SOURCES = ('/etc/usenet-vpn/swanctl.conf', '/etc/usenet-cloud-ui/Caddyfile',
           '/etc/usenet-cloud-ui/compose.yaml', '/etc/usenet-cloud-ui/Dockerfile')
MAX_VPN_BYTES = 64 * 1024
MAX_BYTES = 1024 * 1024
MAX_TAR_BYTES = MAX_BYTES + 64 * 1024
MAX_ARCHIVE_BYTES = MAX_TAR_BYTES + 8192
AGE_VERSION = '1.3.2'


class BackupError(RuntimeError):
    """Only fixed, nonsecret messages are shown."""


def ordinary_private(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise BackupError('The identity and archive must be ordinary private files.')


def identity_path(environment: dict) -> Path:
    value = environment.get('CLOUD_SSH_KEY')
    if not value:
        raise BackupError('Set the existing dedicated CLOUD_SSH_KEY through the environment wrapper.')
    identity = Path(value).expanduser().absolute()
    ordinary_private(identity)
    return identity


def age_binary() -> Path:
    target = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (platform.system(), platform.machine()))
    if target is None:
        raise BackupError('This controller has no reviewed age binary.')
    return INFRA.parent / 'build/tools' / ('age-' + AGE_VERSION) / target / 'age'


def kill_group(process) -> None:
    # The parent may already have exited while a descendant retains stdout.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def read_bounded(command: list[str], limit: int, *, environment=None, timeout=30) -> bytes:
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, env=environment,
                          cwd=INFRA, start_new_session=True) as process:
        timed_out = threading.Event()
        def expire():
            timed_out.set()
            kill_group(process)
        timer = threading.Timer(timeout, expire)
        timer.start()
        try:
            content = process.stdout.read(limit + 1)
            if len(content) > limit:
                raise BackupError('VPN configuration or encrypted archive exceeds its size limit.')
            if process.wait(timeout=5) or timed_out.is_set():
                raise BackupError('VPN backup read or authenticated decryption failed; raw output withheld.')
            return content
        finally:
            timer.cancel()
            if process.poll() is None:
                kill_group(process)
                process.wait()


def check_age(age: Path) -> None:
    value = read_bounded([str(age), '--version'], 128)
    if value.strip().removeprefix(b'v') != AGE_VERSION.encode():
        raise BackupError('The reviewed age 1.3.2 binary is required.')


def decrypt(archive: Path, identity: Path, age: Path) -> bytes:
    archive = archive.absolute()
    ordinary_private(archive)
    ordinary_private(identity)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise BackupError('VPN encrypted archive exceeds its size limit.')
    content = read_bounded([str(age), '--decrypt', '--identity', str(identity), str(archive)], MAX_TAR_BYTES)
    # read_bounded requires successful final age authentication before returning
    # even a complete-looking plaintext prefix to this caller.
    if not content:
        raise BackupError('The VPN configuration is empty; backup refused.')
    return content


def read_sources(environment: dict) -> dict[str, bytes]:
    contents = {}
    total = 0
    for source in SOURCES:
        limit = min(MAX_BYTES - total, MAX_VPN_BYTES if source == SOURCES[0] else MAX_BYTES)
        content = read_bounded([str(INFRA / 'scripts/cloud-command'), 'sudo', '-n', 'cat', '--', source],
                               limit, environment=environment)
        if not content:
            raise BackupError('A required VPN or proxy configuration is empty; backup refused.')
        contents[source] = content
        total += len(content)
    return contents


def package(contents: dict[str, bytes]) -> bytes:
    manifest = {'schema_version': 1, 'scope': 'cloud-vpn-config',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'files': [{'path': path, 'size_bytes': len(contents[path]),
                           'sha256': hashlib.sha256(contents[path]).hexdigest()} for path in SOURCES]}
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as archive:
        values = [('MANIFEST.json', json.dumps(manifest, sort_keys=True).encode()),
                  *(('payload/' + path.lstrip('/'), contents[path]) for path in SOURCES)]
        for name, value in values:
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(value), 0o600
            archive.addfile(member, io.BytesIO(value))
    return output.getvalue()


def verify_tar(content: bytes) -> dict:
    if len(content) > MAX_TAR_BYTES:
        raise BackupError('VPN archive exceeds its size limit.')
    expected = {'MANIFEST.json', *('payload/' + path.lstrip('/') for path in SOURCES)}
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:') as archive:
        names = set()
        for member in archive:
            if (member.name not in expected or member.name in names or not member.isfile() or member.issparse()
                    or member.size < 0 or member.size > MAX_BYTES):
                raise BackupError('VPN archive contains an unexpected, duplicate or unsafe member.')
            names.add(member.name)
        if names != expected or archive.getmember('MANIFEST.json').size > 8192:
            raise BackupError('VPN archive is missing required files or its bounded manifest.')
        manifest = json.load(archive.extractfile('MANIFEST.json'))
        if manifest.get('schema_version') != 1 or manifest.get('scope') != 'cloud-vpn-config':
            raise BackupError('Unsupported VPN archive manifest.')
        entries = manifest.get('files', [])
        if len(entries) != len(SOURCES) or {entry.get('path') for entry in entries} != set(SOURCES):
            raise BackupError('VPN archive manifest does not match the fixed source allowlist.')
        total = 0
        for entry in entries:
            size = entry.get('size_bytes')
            limit = MAX_VPN_BYTES if entry['path'] == SOURCES[0] else MAX_BYTES
            if type(size) is not int or not 0 < size <= limit or not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', '')):
                raise BackupError('VPN archive manifest contains invalid sizes or hashes.')
            total += size
            if total > MAX_BYTES:
                raise BackupError('VPN configuration exceeds its combined size limit.')
            member = archive.getmember('payload/' + entry['path'].lstrip('/'))
            if member.size != size or hashlib.sha256(archive.extractfile(member).read()).hexdigest() != entry['sha256']:
                raise BackupError('VPN backup checksum verification failed.')
    return manifest


def capture(environment: dict, age: Path, destination: Path) -> tuple[Path, dict]:
    identity = identity_path(environment)
    if not all(environment.get(key) for key in ('CLOUD_SSH_TARGET', 'CLOUD_SSH_KNOWN_HOSTS')):
        raise BackupError('The dedicated pinned cloud connection settings are required.')
    recipient = Path(str(identity) + '.pub')
    if recipient.is_symlink() or not recipient.is_file():
        raise BackupError('The dedicated cloud administrator public recipient is missing.')
    lines = recipient.read_text().splitlines()
    if len(lines) != 1 or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: .*)?', lines[0]):
        raise BackupError('The existing dedicated Ed25519 public recipient is required.')
    environment = dict(environment, CLOUD_SSH_KEY=str(identity))
    contents = read_sources(environment)
    if read_sources(environment) != contents:
        raise BackupError('VPN or proxy configuration changed during capture; retry after deployment completes.')
    content = package(contents)
    verify_tar(content)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_symlink() or destination.stat().st_mode & 0o077:
        raise BackupError('The backup directory must be private with mode 0700.')
    with tempfile.TemporaryDirectory(prefix='.vpn-capture-', dir=destination) as directory:
        encrypted = Path(directory) / 'archive.age'
        with subprocess.Popen([str(age), '--encrypt', '--recipients-file', str(recipient), '--output', str(encrypted)],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True) as process:
            try:
                process.communicate(content, timeout=30)
                if process.returncode:
                    raise BackupError('VPN backup encryption failed; no archive was published.')
            finally:
                if process.poll() is None:
                    kill_group(process)
                    process.wait()
        encrypted.chmod(0o600)
        verified = decrypt(encrypted, identity, age)
        if hashlib.sha256(verified).digest() != hashlib.sha256(content).digest():
            raise BackupError('VPN backup checksum verification failed; no archive was published.')
        manifest = verify_tar(verified)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        archive = destination / ('cloud-vpn-' + timestamp + '.tar.age')
        os.link(encrypted, archive)
    return archive, manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('capture')
    verify = commands.add_parser('verify')
    verify.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        age = age_binary()
        check_age(age)
        if args.command in (None, 'capture'):
            archive, manifest = capture(dict(os.environ), age, INFRA / 'backups')
            status = 'captured'
        else:
            archive = args.archive
            manifest = verify_tar(decrypt(archive, identity_path(os.environ), age))
            status = 'verified'
        print(json.dumps({'status': status, 'scope': 'cloud-vpn-config',
                          'archive': str(archive), 'files': len(manifest['files']),
                          'size_bytes': sum(entry['size_bytes'] for entry in manifest['files']),
                          'inventory_sha256': hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest(),
                          'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))
        return 0
    except BackupError as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({'error': 'VPN backup failed; no raw error or secret was displayed.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
