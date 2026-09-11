#!/usr/bin/env python3
"""Scan main-repository source/index/history without printing credential bytes.

Ignored private inputs and submodule repositories are outside this source gate.
This is a high-confidence detector, not a certification that all data is public.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

VAULT_PATH = 'usenet-infra/vault/secrets.sops.json'
MAX_JSON = 32 * 1024**2
CHUNK = 1024**2
OVERLAP = 8192
PATTERNS = (
    ('native age private identity', re.compile(rb'(?<![A-Z0-9-])AGE-SECRET-KEY-1[023456789ACDEFGHJKLMNPQRSTUVWXYZ]{58}(?![A-Z0-9])')),
    ('armored private key', re.compile(rb'-----BEGIN (?:(?:OPENSSH|RSA|EC|DSA|ENCRYPTED) )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]{32,}')),
    ('named service token', re.compile(rb'\b(?:HCLOUD_TOKEN|SABNZBD_API_KEY|PROWLARR_API_KEY)[ \t]*=[ \t]*[\"\']?[A-Za-z0-9_-]{20,}')),
)
ENC = re.compile(r'ENC\[AES256_GCM,data:([A-Za-z0-9+/]*={0,2}),iv:([A-Za-z0-9+/]+={0,2}),tag:([A-Za-z0-9+/]+={0,2}),type:(str|int|float|bool|bytes|null)\]')
AGE_RECIPIENT = re.compile(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}')


class ScanError(Exception):
    pass


def _json(content):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate field')
            value[key] = item
        return value
    return json.loads(content, object_pairs_hook=unique)


def _encrypted(value):
    match = ENC.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return False
    try:
        data, iv, tag = [base64.b64decode(v, validate=True) for v in match.groups()[:3]]
        return bool(data) and len(iv) == 32 and len(tag) == 16
    except ValueError:
        return False


def valid_sops(content: bytes) -> bool:
    """Accept exactly the reviewed small-vault shape, with every payload leaf encrypted."""
    try:
        if len(content) > MAX_JSON:
            return False
        value = _json(content)
        if not isinstance(value, dict) or set(value) != {'entries', 'inventory_sha256', 'schema_version', 'source_checkout', 'sops'}:
            return False
        if any(not _encrypted(value[key]) for key in ('inventory_sha256', 'schema_version', 'source_checkout')):
            return False
        if not isinstance(value['entries'], list) or not 1 <= len(value['entries']) <= 1000:
            return False
        for entry in value['entries']:
            if not isinstance(entry, dict) or set(entry) != {'id', 'sha256', 'content'} or not all(_encrypted(v) for v in entry.values()):
                return False
        metadata = value['sops']
        if not isinstance(metadata, dict) or set(metadata) != {'age', 'lastmodified', 'mac', 'unencrypted_suffix', 'version'}:
            return False
        if (metadata['unencrypted_suffix'] != '_unencrypted' or not _encrypted(metadata['mac'])
                or not isinstance(metadata['lastmodified'], str)
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', metadata['lastmodified'])
                or not isinstance(metadata['version'], str) or not re.fullmatch(r'3\.\d+\.\d+', metadata['version'])
                or not isinstance(metadata['age'], list) or not 1 <= len(metadata['age']) <= 10):
            return False
        recipients = set()
        for record in metadata['age']:
            if not isinstance(record, dict) or set(record) != {'recipient', 'enc'}:
                return False
            recipient = record['recipient']
            if not isinstance(recipient, str) or not AGE_RECIPIENT.fullmatch(recipient) or recipient in recipients:
                return False
            recipients.add(recipient)
            wrapped = record['enc']
            if not isinstance(wrapped, str):
                return False
            match = re.fullmatch(r'-----BEGIN AGE ENCRYPTED FILE-----\n([A-Za-z0-9+/=\n]+)-----END AGE ENCRYPTED FILE-----\n?', wrapped)
            if not match:
                return False
            decoded = base64.b64decode(match[1].replace('\n', ''), validate=True)
            if not decoded.startswith(b'age-encryption.org/v1\n-> X25519 ') or len(decoded) > 8192:
                return False
        return True
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False


def forbidden_path(path):
    """Existing Usenet runtime-path policy, including renamed decrypted vault copies."""
    pure = PurePosixPath(path)
    if path.startswith('usenet-infra/vault/'):
        return path != VAULT_PATH and pure.name not in ('README.md', '.gitkeep')
    if not path.startswith('usenet-infra/'):
        return False
    name = pure.name
    return ('secrets' in pure.parts or '.secrets' in pure.parts or 'backups' in pure.parts
            or name == '.env' or (name.startswith('.env.') and name != '.env.example')
            or name == 'dashboard-auth.json' or '.tfstate' in name or name.endswith(('.tfplan', '.tfvars'))
            or path == 'usenet-infra/ansible/inventory.yml' or '/config/runtime/' in path)


def inspect_content(path, content):
    findings = {label for label, pattern in PATTERNS if pattern.search(content)}
    if path == VAULT_PATH and not valid_sops(content):
        findings.add('invalid or plaintext SOPS vault envelope')
    if len(content) <= MAX_JSON and content.lstrip().startswith(b'{'):
        try:
            value = _json(content)
            if (isinstance(value, dict) and {'entries', 'inventory_sha256', 'schema_version', 'source_checkout'} <= set(value)
                    and not valid_sops(content)):
                findings.add('plaintext or malformed recovery bundle')
            if isinstance(value, dict) and 'sops' in value and path != VAULT_PATH:
                findings.add('SOPS ciphertext outside the exact reviewed vault path')
        except (ValueError, TypeError, UnicodeError):
            pass
    return findings


def inspect_stream(path, stream, size):
    if size <= MAX_JSON:
        content = stream.read(size)
        if len(content) != size:
            raise ScanError('Source content changed or Git returned a truncated blob.')
        return inspect_content(path, content)
    findings = {'reviewed JSON size limit exceeded'} if path == VAULT_PATH or path.endswith('.json') else set()
    remaining, tail = size, b''
    while remaining:
        content = stream.read(min(CHUNK, remaining))
        if not content:
            raise ScanError('Source content changed or Git returned a truncated blob.')
        remaining -= len(content)
        joined = tail + content
        findings.update(label for label, pattern in PATTERNS if pattern.search(joined))
        tail = joined[-OVERLAP:]
    return findings


def _git(root, args):
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout


def _paths(raw):
    return [value.decode('utf-8', 'surrogateescape') for value in raw.split(b'\0') if value]


def _source_fd(root, path):
    """Open source bytes without traversing a replaced parent or leaf symlink."""
    parts = PurePosixPath(path).parts
    if not parts or path.startswith('/') or any(part in ('.', '..') for part in parts):
        raise ScanError('Git returned an unsafe source path.')
    current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ScanError('Source file changed to an unsafe type.')
        return descriptor
    finally:
        os.close(current)


def scan(root, *, history=True):
    findings = set()
    paths = _paths(_git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard']))
    checked = 0
    for path in sorted(set(paths)):
        if forbidden_path(path):
            findings.add(('source', path, 'runtime/private path is source-visible'))
        actual = root / path
        try:
            item = actual.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(item.st_mode):
            continue
        if stat.S_ISLNK(item.st_mode):
            result = inspect_content(path, os.fsencode(os.readlink(actual)))
        elif stat.S_ISREG(item.st_mode):
            try:
                with os.fdopen(_source_fd(root, path), 'rb') as stream:
                    result = inspect_stream(path, stream, os.fstat(stream.fileno()).st_size)
            except (OSError, ScanError):
                findings.add(('source', path, 'source path could not be opened without following links'))
                continue
        else:
            findings.add(('source', path, 'unsafe source file type'))
            continue
        checked += 1
        findings.update(('source', path, reason) for reason in result)
    objects = {}
    for raw in _git(root, ['ls-files', '--stage', '-z']).split(b'\0'):
        if raw:
            fields, path = raw.split(b'\t', 1)
            mode, oid, stage = fields.split()
            if mode != b'160000':
                objects[(oid.decode(), path.decode('utf-8', 'surrogateescape'))] = 'index'
    if history:
        for raw in _git(root, ['rev-list', '--objects', '--all']).splitlines():
            fields = raw.split(b' ', 1)
            if len(fields) == 2:
                oid, path = fields
                objects.setdefault((oid.decode(), path.decode('utf-8', 'surrogateescape')), 'history')
    blobs = 0
    with subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        for (oid, path), scope in sorted(objects.items()):
            if not re.fullmatch(r'[0-9a-f]{40,64}', oid):
                raise ScanError('Git returned an invalid object identity.')
            process.stdin.write(oid.encode() + b'\n')
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or not header[2].isdigit():
                raise ScanError('Git source object is unavailable.')
            size = int(header[2])
            if header[1] == b'blob':
                result = inspect_stream(path, process.stdout, size)
                blobs += 1
                findings.update((scope, path, reason) for reason in result)
                if forbidden_path(path):
                    findings.add((scope, path, 'runtime/private path is source-visible'))
            else:
                remaining = size
                while remaining:
                    chunk = process.stdout.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ScanError('Git returned a truncated source object.')
                    remaining -= len(chunk)
            if process.stdout.read(1) != b'\n':
                raise ScanError('Git returned an invalid source object boundary.')
        process.stdin.close()
        if process.wait(timeout=30):
            raise ScanError('Git source scan could not complete.')
    return sorted(findings), checked, blobs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--no-history', action='store_true', help='Scan worktree and index only; explicitly omits history.')
    args = parser.parse_args(argv)
    try:
        findings, files, blobs = scan(args.root.resolve(), history=not args.no_history)
        for scope, path, reason in findings:
            print(scope + ': ' + json.dumps(path, ensure_ascii=True) + ': ' + reason, file=sys.stderr)
        if findings:
            print('Secret scan failed; diagnostics contain paths and classifications only.', file=sys.stderr)
            return 1
        print('No high-confidence credentials or invalid vaults found in ' + str(files) +
              ' main-repository source files and ' + str(blobs) + ' index/history blobs' +
              (' (history omitted).' if args.no_history else '.'))
        return 0
    except Exception:
        print('Secret scan could not complete safely; no raw diagnostic content was retained.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
