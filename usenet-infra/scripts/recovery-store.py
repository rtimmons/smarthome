#!/usr/bin/env python3
"""Publish/fetch immutable encrypted recovery bundles on the dedicated QNAP store.

Transport needs only the existing dedicated NAS SSH key and verified host pin.
The private recovery master is never read or forwarded to subprocesses.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import selectors
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

INFRA = Path(__file__).resolve().parents[1]
STORE = '/share/Container/usenet-recovery'
FILES = ('recovery.tar.age', 'receipt.json')
ENV_NAMES = ('QNAP_SSH_TARGET', 'QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS')
SAFE_ENV = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LC_ALL': 'C'}
SNAPSHOT = re.compile(r'[0-9][0-9TZ-]{6,40}(?:-[0-9a-f]{8,32})?')
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_CIPHERTEXT = 512 * 1024**2
MAX_RECEIPT = 1024**2


class StoreError(RuntimeError):
    """Errors deliberately contain no subprocess output or secret values."""


def safe_source(path: Path, root: Path, mode='0600'):
    spec = importlib.util.spec_from_file_location('recovery_store_vault', Path(__file__).with_name('secrets-vault.py'))
    vault = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vault)
    try:
        relative = path.absolute().relative_to(root.absolute()).as_posix()
        descriptor = vault._root_fd(root)
        try:
            return vault._read_source(descriptor, relative, mode)
        finally:
            os.close(descriptor)
    except (vault.VaultError, OSError, ValueError):
        raise StoreError('Recovery connection file has unsafe paths, links, ownership or permissions.') from None


def validate_snapshot(value):
    if not isinstance(value, str) or not SNAPSHOT.fullmatch(value):
        raise StoreError('Invalid recovery snapshot ID.')
    return value


def read_environment(path: Path, root=INFRA.parent) -> dict:
    """Read selected literal assignments; never source/evaluate the dotenv file."""
    result = {}
    for line in safe_source(path, root).decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)', line)
        if match is None:
            raise StoreError('Malformed dotenv assignment; shell syntax is not supported.')
        name, raw = match.groups()
        if name not in ENV_NAMES:
            continue
        try:
            words = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise StoreError('Malformed QNAP dotenv value.') from None
        if name in result or len(words) != 1 or any(c in words[0] for c in '\x00\r\n$`'):
            raise StoreError('QNAP dotenv values must be unique literal values.')
        result[name] = words[0]
    if set(result) != set(ENV_NAMES):
        raise StoreError('Dedicated QNAP SSH target, identity and host pin are required.')
    return result


def connection_command(values, infra=INFRA):
    target = values.get('QNAP_SSH_TARGET', '')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*', target):
        raise StoreError('Invalid dedicated QNAP SSH target.')
    paths = []
    for name, expected in zip(ENV_NAMES[1:], ('secrets/ssh/qnap-admin', 'ansible/files/secrets/qnap-known-hosts')):
        path = Path(values.get(name, ''))
        if not path.is_absolute():
            path = infra / path
        if path.absolute() != (infra / expected).absolute():
            raise StoreError('Only the inventoried dedicated QNAP identity and host pin are permitted.')
        safe_source(path, infra.parent)
        paths.append(str(path.absolute()))
    return ['/usr/bin/ssh', '-F', '/dev/null', '-T', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'IdentityAgent=none', '-o', 'PreferredAuthentications=publickey',
            '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            '-o', 'GlobalKnownHostsFile=/dev/null', '-i', paths[0],
            '-o', 'UserKnownHostsFile=' + paths[1], '--', target]


def read_regular(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise StoreError('Recovery bundle files must be bounded regular files without links.')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise StoreError('Recovery bundle exceeds its size limit.')
    return data


def validate_bundle(ciphertext: bytes, receipt_bytes: bytes, expected=None):
    try:
        receipt = json.loads(receipt_bytes)
    except (ValueError, UnicodeError):
        raise StoreError('Recovery receipt is not valid JSON.') from None
    if not isinstance(receipt, dict) or type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1:
        raise StoreError('Unsupported recovery receipt schema.')
    snapshot = validate_snapshot(receipt.get('snapshot_id'))
    if expected is not None and snapshot != expected:
        raise StoreError('Recovery receipt belongs to a different snapshot.')
    if (receipt.get('deletion_safe') is not False or not isinstance(receipt.get('ciphertext_sha256'), str)
            or not SHA256.fullmatch(receipt['ciphertext_sha256'])
            or type(receipt.get('ciphertext_bytes')) is not int
            or not 0 < receipt['ciphertext_bytes'] <= MAX_CIPHERTEXT):
        raise StoreError('Recovery receipt integrity fields are invalid.')
    if (len(ciphertext) != receipt['ciphertext_bytes']
            or hashlib.sha256(ciphertext).hexdigest() != receipt['ciphertext_sha256']):
        raise StoreError('Recovery ciphertext checksum or size does not match its receipt.')
    if not ciphertext.startswith(b'age-encryption.org/v1\n'):
        raise StoreError('Only native age ciphertext may enter the recovery store.')
    return receipt


def remote_command(script):
    return 'env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/sh -c ' + shlex.quote(script)


def invoke(command, script, *, source=None, destination=None, runner=subprocess.run):
    try:
        result = runner(command + [remote_command(script)],
                        stdin=source if source is not None else subprocess.DEVNULL,
                        stdout=destination if destination is not None else subprocess.DEVNULL,
                        stderr=subprocess.PIPE, env=SAFE_ENV.copy(), timeout=300, check=False)
    except (OSError, subprocess.SubprocessError):
        raise StoreError('Pinned QNAP transfer could not complete; no credential fallback was attempted.') from None
    if result.returncode != 0:
        raise StoreError('QNAP transfer refused or failed; no credential fallback was attempted.')


def receive(command, script, transport, *, popen=subprocess.Popen, timeout=300,
            limit=MAX_CIPHERTEXT + MAX_RECEIPT + 1024**2):
    """Bound both streaming output and total elapsed time from an untrusted peer."""
    process = None
    try:
        process = popen(command + [remote_command(script)], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=SAFE_ENV.copy())
        deadline, total = time.monotonic() + timeout, 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise StoreError('QNAP download exceeded the transfer timeout.')
                data = os.read(process.stdout.fileno(), 64 * 1024)
                if not data:
                    break
                total += len(data)
                if total > limit:
                    raise StoreError('QNAP download exceeded the transport size limit.')
                transport.write(data)
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            raise StoreError('Pinned QNAP download failed; no credential fallback was attempted.')
    except (OSError, subprocess.SubprocessError):
        raise StoreError('Pinned QNAP download failed; no credential fallback was attempted.') from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


REMOTE_CHECKS = '''owner=$(id -u)
metadata() { stat -c '%u:%a:%h' "$1" 2>/dev/null || stat -f '%u:%Lp:%l' "$1"; }
private_dir() {
  test -d "$1" && test ! -L "$1"
  test "$(metadata "$1" | cut -d : -f 1,2)" = "$owner:700"
}
private_file() {
  test -f "$1" && test ! -L "$1"
  test "$(metadata "$1")" = "$owner:600:1"
}
'''


def push_script(snapshot, ciphertext, receipt, root=STORE):
    # All data interpolated into the shell is either quoted or validated hex/digits.
    validate_snapshot(snapshot)
    return f'''set -eu
umask 077
root={shlex.quote(root)}
snapshot={shlex.quote(snapshot)}
{REMOTE_CHECKS}
test ! -L "$root"
if test ! -e "$root"; then mkdir -m 700 "$root"; fi
private_dir "$root"
cd "$root"
command -v sha256sum >/dev/null
lock=".$snapshot.lock"
mkdir "$lock"
stage=
cleanup() {{
  if test -n "$stage"; then rm -f "$stage/recovery.tar.age" "$stage/receipt.json"; rmdir "$stage"; fi
  rmdir "$lock"
}}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
verify() {{
  private_dir "$1"
  for file in recovery.tar.age receipt.json; do private_file "$1/$file"; done
  test "$(find "$1" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')" = 2
  test "$(sha256sum "$1/recovery.tar.age" | cut -d ' ' -f 1)" = {hashlib.sha256(ciphertext).hexdigest()}
  test "$(wc -c < "$1/recovery.tar.age" | tr -d ' ')" = {len(ciphertext)}
  test "$(sha256sum "$1/receipt.json" | cut -d ' ' -f 1)" = {hashlib.sha256(receipt).hexdigest()}
  test "$(wc -c < "$1/receipt.json" | tr -d ' ')" = {len(receipt)}
}}
if test -e "$snapshot" || test -L "$snapshot"; then
  verify "$snapshot"
  cat >/dev/null
  exit 0
fi
stage=$(mktemp -d "$root/.$snapshot.upload.XXXXXXXX")
tar -xf - -C "$stage" recovery.tar.age receipt.json
chmod 700 "$stage"
chmod 600 "$stage/recovery.tar.age" "$stage/receipt.json"
verify "$stage"
test ! -e "$snapshot" && test ! -L "$snapshot"
mv "$stage" "$snapshot"
stage=
'''


def fetch_script(snapshot, root=STORE):
    validate_snapshot(snapshot)
    return f'''set -eu
umask 077
root={shlex.quote(root)}
{REMOTE_CHECKS}
private_dir "$root"
cd "$root"
snapshot={shlex.quote(snapshot)}
private_dir "$snapshot"
cd "$snapshot"
for file in recovery.tar.age receipt.json; do private_file "$file"; done
COPYFILE_DISABLE=1 tar -cf - recovery.tar.age receipt.json
'''


def probe_script(root=STORE):
    return f'''set -eu
root={shlex.quote(root)}
{REMOTE_CHECKS}
for tool in tar sha256sum mktemp cut tr wc find chmod mkdir mv rm rmdir stat id; do
  command -v "$tool" >/dev/null
done
test -d /share/Container
test ! -L "$root"
if test -e "$root"; then private_dir "$root" && test -w "$root";
else test -w /share/Container; fi
'''


def push(bundle: Path, command, runner=subprocess.run):
    if bundle.is_symlink() or not bundle.is_dir():
        raise StoreError('Recovery bundle must be a real directory.')
    ciphertext = read_regular(bundle / FILES[0], MAX_CIPHERTEXT)
    receipt_bytes = read_regular(bundle / FILES[1], MAX_RECEIPT)
    receipt = validate_bundle(ciphertext, receipt_bytes)
    # A private temporary transport contains ciphertext and the public receipt only.
    with tempfile.TemporaryFile() as transport:
        with tarfile.open(fileobj=transport, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in zip(FILES, (ciphertext, receipt_bytes)):
                member = tarfile.TarInfo(name)
                member.mode, member.size = 0o600, len(data)
                archive.addfile(member, io.BytesIO(data))
        transport.seek(0)
        invoke(command, push_script(receipt['snapshot_id'], ciphertext, receipt_bytes),
               source=transport, runner=runner)
    return receipt['snapshot_id']


def unpack(transport, snapshot):
    with tarfile.open(fileobj=transport, mode='r:') as archive:
        members = archive.getmembers()
        if len(members) != 2 or {member.name for member in members} != set(FILES):
            raise StoreError('Remote recovery archive has unexpected entries.')
        values = {}
        for member in members:
            limit = MAX_CIPHERTEXT if member.name == FILES[0] else MAX_RECEIPT
            if not member.isfile() or member.size > limit or member.size <= 0:
                raise StoreError('Remote recovery archive has a link, special file or invalid size.')
            stream = archive.extractfile(member)
            if stream is None:
                raise StoreError('Remote recovery archive is incomplete.')
            with stream:
                values[member.name] = stream.read(limit + 1)
        validate_bundle(values[FILES[0]], values[FILES[1]], snapshot)
        return values


def fetch(snapshot, destination: Path, command, *, popen=subprocess.Popen):
    validate_snapshot(snapshot)
    # mkdir is exclusive; never overwrite even an empty preexisting destination.
    destination.mkdir(mode=0o700)
    created = []
    try:
        with tempfile.TemporaryFile() as transport:
            receive(command, fetch_script(snapshot), transport, popen=popen)
            transport.seek(0)
            values = unpack(transport, snapshot)
        for name in FILES:
            descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(destination / name)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(values[name])
                stream.flush()
                os.fsync(stream.fileno())
        descriptor = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        try:
            destination.rmdir()
        except OSError:
            pass
        raise
    return snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest='operation', required=True)
    publish = operations.add_parser('push')
    publish.add_argument('--bundle', required=True, type=Path)
    retrieve = operations.add_parser('fetch')
    retrieve.add_argument('--snapshot', required=True)
    retrieve.add_argument('--destination', required=True, type=Path)
    operations.add_parser('probe', help='Check pinned access and NAS tools without changing files')
    args = parser.parse_args(argv)
    try:
        command = connection_command(read_environment(INFRA / '.env'))
        if args.operation == 'probe':
            invoke(command, probe_script())
            print('Pinned QNAP recovery-store access and required tools verified (read-only).')
            return 0
        snapshot = (push(args.bundle, command) if args.operation == 'push'
                    else fetch(args.snapshot, args.destination, command))
        print('QNAP recovery ' + args.operation + ' verified: ' + snapshot)
        print('This QNAP copy alone does not make the checkout safe to delete.')
        return 0
    except StoreError as exc:
        print('Recovery store failed: ' + str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, tarfile.TarError):
        print('Recovery store operation failed validation or pinned transport; no fallback attempted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
