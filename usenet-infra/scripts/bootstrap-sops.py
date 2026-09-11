#!/usr/bin/env python3
"""Install a pinned, verified SOPS binary in this repository's ignored build.

The recovery master never belongs in this checkout.  This utility only caches a
reviewed controller binary, rehashes it on every use, and supports an offline
repeat once the verified release has been retained locally.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import platform as host_platform
import re
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request


VERSION = '3.13.3'
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_ROOT = REPO_ROOT / 'build' / 'tools' / ('sops-' + VERSION)
MAX_BINARY_BYTES = 128 * 1024 * 1024
# Official getsops/sops v3.13.3 release-asset SHA-256 values.  The release
# checksum manifest is signed with Sigstore; these reviewed values keep the
# bootstrap self-contained and allow verified offline repeats.
RELEASES = {
    'darwin-arm64': {
        'url': 'https://github.com/getsops/sops/releases/download/v3.13.3/sops-v3.13.3.darwin.arm64',
        'sha256': 'b97c0d434aab577dc40310e8d22ff9e45eef4c80638ab978daae9b4681c59286',
    },
    'linux-amd64': {
        'url': 'https://github.com/getsops/sops/releases/download/v3.13.3/sops-v3.13.3.linux.amd64',
        'sha256': 'e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b',
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
            raise BootstrapError('Refused an unexpected SOPS release redirect.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str) -> bytes:
    if not allowed_url(url):
        raise BootstrapError('Refused an unexpected SOPS release URL.')
    opener = urllib.request.build_opener(OfficialRedirects())
    try:
        with opener.open(url, timeout=60) as response:
            if not allowed_url(response.geturl()):
                raise BootstrapError('Refused an unexpected SOPS release response URL.')
            payload = response.read(MAX_BINARY_BYTES + 1)
        if len(payload) < 1 or len(payload) > MAX_BINARY_BYTES:
            raise BootstrapError('SOPS release binary is outside the accepted size limit.')
        return payload
    except BootstrapError:
        raise
    except Exception:
        raise BootstrapError('Could not download the pinned official SOPS release.') from None


def atomic_write(path: Path, payload: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
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


def check_version(binary: Path) -> None:
    try:
        result = subprocess.run([str(binary), '--version'], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise BootstrapError('Pinned SOPS binary did not pass its version check.') from None
    first_line = result.stdout.decode('utf-8', 'replace').splitlines()[0:1]
    if len(first_line) != 1 or not re.fullmatch(r'sops ' + re.escape(VERSION) + r'( \(latest\))?', first_line[0]):
        raise BootstrapError('Pinned SOPS binary reported an unexpected version.')


def local_platform() -> str | None:
    return {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (host_platform.system(), host_platform.machine()))


def install(platform: str, release: dict, root: Path, *, offline: bool = False,
            fetch=download, verify=check_version) -> dict:
    destination = root / platform
    if destination.is_symlink():
        raise BootstrapError('Refused a symlinked SOPS installation directory.')
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / 'release.bin'
    binary_path = destination / 'sops'
    if archive_path.is_symlink() or binary_path.is_symlink():
        raise BootstrapError('Refused a symlinked SOPS release cache or executable.')
    cached = archive_path.read_bytes() if archive_path.exists() else None
    cache_valid = cached is not None and len(cached) <= MAX_BINARY_BYTES and sha256(cached) == release['sha256']
    if cache_valid:
        payload = cached
    elif offline:
        raise BootstrapError('Offline bootstrap needs the intact pinned release for ' + platform + '.')
    else:
        payload = fetch(release['url'])
    if len(payload) < 1 or len(payload) > MAX_BINARY_BYTES or sha256(payload) != release['sha256']:
        raise BootstrapError('SOPS release SHA-256 verification failed; no executable was replaced.')
    if not cache_valid:
        atomic_write(archive_path, payload, 0o600)
    changed = not binary_path.is_file() or sha256(binary_path.read_bytes()) != release['sha256']
    if changed:
        atomic_write(binary_path, payload, 0o755)
    elif stat.S_IMODE(binary_path.stat().st_mode) != 0o755:
        binary_path.chmod(0o755)
        changed = True
    # The cache deliberately retains both recovery architectures, but a binary
    # can only be executed on its matching controller architecture.
    version_checked = platform == local_platform()
    if version_checked:
        verify(binary_path)
    return {'platform': platform, 'version': VERSION, 'path': str(binary_path),
            'release_sha256': release['sha256'], 'version_checked': version_checked, 'changed': changed}


def bootstrap(root: Path = INSTALL_ROOT, *, offline: bool = False, releases=None,
              fetch=download, verify=check_version) -> list[dict]:
    releases = RELEASES if releases is None else releases
    if set(releases) != {'darwin-arm64', 'linux-amd64'}:
        raise BootstrapError('Both pinned controller and recovery platforms are required.')
    if root.is_symlink():
        raise BootstrapError('Refused a symlinked SOPS bootstrap directory.')
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root / '.bootstrap.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BootstrapError('Another SOPS bootstrap is running.') from None
        return [install(platform, releases[platform], root, offline=offline, fetch=fetch, verify=verify)
                for platform in ('darwin-arm64', 'linux-amd64')]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Use only verified releases already in ignored build/.')
    args = parser.parse_args(argv)
    try:
        if not INSTALL_ROOT.resolve().is_relative_to(REPO_ROOT):
            raise BootstrapError('SOPS installation must remain inside the repository build directory.')
        import json
        print(json.dumps({'binaries': bootstrap(offline=args.offline)}, indent=2, sort_keys=True))
        return 0
    except (BootstrapError, OSError) as exc:
        print('{"error":"' + str(exc).replace('"', '') + '"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
