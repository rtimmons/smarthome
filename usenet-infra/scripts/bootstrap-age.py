#!/usr/bin/env python3
"""Install verified age 1.3.2 binaries only into this repository's ignored build.

Both the controller's Darwin/arm64 and cloud host's Linux/amd64 binaries are
provisioned. A retained, pinned archive is rehashed on every run, including
offline runs; an existing executable is never trusted from a marker file.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request


VERSION = '1.3.2'
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_ROOT = REPO_ROOT / 'build' / 'tools' / ('age-' + VERSION)
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_BINARY_BYTES = 64 * 1024 * 1024
# Official GitHub release asset digests for FiloSottile/age v1.3.2.
RELEASES = {
    'darwin-arm64': {
        'url': 'https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-darwin-arm64.tar.gz',
        'sha256': 'e2020b073c44f692685a24d6abc378817eb81ffaaf49fd0531ef8565f767f2f5',
    },
    'linux-amd64': {
        'url': 'https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz',
        'sha256': 'cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10',
    },
}


class BootstrapError(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def allowed_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in {
        'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com',
    } and parsed.port in (None, 443) and not parsed.username and not parsed.password)


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise BootstrapError('Refused an unexpected age release redirect.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str) -> bytes:
    if not allowed_url(url):
        raise BootstrapError('Refused an unexpected age release URL.')
    opener = urllib.request.build_opener(OfficialRedirects())
    try:
        with opener.open(url, timeout=60) as response:
            if not allowed_url(response.geturl()):
                raise BootstrapError('Refused an unexpected age release response URL.')
            payload = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(payload) > MAX_ARCHIVE_BYTES:
            raise BootstrapError('Age release archive exceeds the size limit.')
        return payload
    except BootstrapError:
        raise
    except Exception:
        raise BootstrapError('Could not download the pinned official age release.') from None


def binary_from_archive(payload: bytes, expected_sha256: str) -> bytes:
    if len(payload) > MAX_ARCHIVE_BYTES or sha256(payload) != expected_sha256:
        raise BootstrapError('Age archive SHA-256 verification failed; no executable was replaced.')
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            members = archive.getmembers()
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts:
                    raise BootstrapError('Unsafe path in age release archive.')
            matches = [member for member in members if member.name == 'age/age']
            if len(matches) != 1 or not matches[0].isfile():
                raise BootstrapError('Age archive must contain exactly one regular age/age file.')
            member = matches[0]
            if member.size < 1 or member.size > MAX_BINARY_BYTES:
                raise BootstrapError('Age binary size is outside the accepted bounds.')
            stream = archive.extractfile(member)
            if stream is None:
                raise BootstrapError('Age binary could not be read from the verified archive.')
            binary = stream.read(MAX_BINARY_BYTES + 1)
            if len(binary) != member.size:
                raise BootstrapError('Age binary length does not match its verified archive.')
            return binary
    except BootstrapError:
        raise
    except (tarfile.TarError, OSError, EOFError, ValueError):
        raise BootstrapError('Malformed age release archive; no executable was replaced.') from None


def atomic_write(path: Path, payload: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(platform: str, release: dict, root: Path, *, offline: bool = False, fetch=download) -> dict:
    destination = root / platform
    if destination.is_symlink():
        raise BootstrapError('Refused a symlinked age installation directory.')
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / 'archive.tar.gz'
    binary_path = destination / 'age'
    if archive_path.is_symlink() or binary_path.is_symlink():
        raise BootstrapError('Refused a symlinked age archive or executable.')
    cached = archive_path.read_bytes() if archive_path.exists() else None
    cache_valid = cached is not None and len(cached) <= MAX_ARCHIVE_BYTES and sha256(cached) == release['sha256']
    if cache_valid:
        payload = cached
    elif offline:
        raise BootstrapError('Offline bootstrap needs the intact pinned archive for ' + platform + '.')
    else:
        payload = fetch(release['url'])
    # Validate both digest and archive layout before replacing either artifact.
    binary = binary_from_archive(payload, release['sha256'])
    if not cache_valid:
        atomic_write(archive_path, payload, 0o600)
    expected_binary_hash = sha256(binary)
    changed = not binary_path.is_file() or sha256(binary_path.read_bytes()) != expected_binary_hash
    if changed:
        atomic_write(binary_path, binary, 0o755)
    elif stat.S_IMODE(binary_path.stat().st_mode) != 0o755:
        binary_path.chmod(0o755)
        changed = True
    return {'platform': platform, 'version': VERSION, 'path': str(binary_path),
            'archive_sha256': release['sha256'], 'binary_sha256': expected_binary_hash, 'changed': changed}


def bootstrap(root: Path = INSTALL_ROOT, *, offline: bool = False, releases=None, fetch=download) -> list[dict]:
    releases = RELEASES if releases is None else releases
    if set(releases) != {'darwin-arm64', 'linux-amd64'}:
        raise BootstrapError('Both pinned controller and cloud platforms are required.')
    if root.is_symlink():
        raise BootstrapError('Refused a symlinked age bootstrap directory.')
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root / '.bootstrap.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BootstrapError('Another age bootstrap is running.') from None
        return [install(platform, releases[platform], root, offline=offline, fetch=fetch)
                for platform in ('darwin-arm64', 'linux-amd64')]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Use only verified archives already in ignored build/.')
    args = parser.parse_args(argv)
    try:
        if not INSTALL_ROOT.resolve().is_relative_to(REPO_ROOT):
            raise BootstrapError('Age installation must remain inside the repository build directory.')
        print(json.dumps({'binaries': bootstrap(offline=args.offline)}, indent=2, sort_keys=True))
        return 0
    except (BootstrapError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
