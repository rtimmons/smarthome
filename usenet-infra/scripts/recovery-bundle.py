#!/usr/bin/env python3
"""Capture and authenticate exact inventoried state/archive recovery packages.

Capture uses only the public age recipient. Verify/restore require the master
through SOPS_AGE_KEY (or a private terminal prompt), plus the restored vault.
No command applies Terraform, contacts a live service, or restores applications.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import secrets
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE = 256 * 1024**2
MAX_PACKAGE = 512 * 1024**2
MAX_METADATA = 128 * 1024
SNAPSHOT = re.compile(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{16}')


class RecoveryError(Exception):
    """Only fixed, nonsecret diagnostics cross the CLI boundary."""


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


vault = module('secrets-vault')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=vault._no_duplicates)
    except (ValueError, UnicodeError, TypeError):
        raise RecoveryError('Recovery metadata is invalid JSON.') from None


def validate_header(header):
    if (type(header.get('schema_version')) is not int or header['schema_version'] != 1
            or not isinstance(header.get('snapshot_id'), str) or not SNAPSHOT.fullmatch(header['snapshot_id'])
            or any(not isinstance(header.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', header[key])
                   for key in ('inventory_sha256', 'vault_sha256'))
            or not isinstance(header.get('source_revision'), str)
            or not re.fullmatch(r'[0-9a-f]{40,64}', header['source_revision'])
            or not isinstance(header.get('recipient'), str)
            or not re.fullmatch(r'age1[ac-hj-np-z02-9]{58}', header['recipient'])):
        raise RecoveryError('Recovery metadata fields have invalid types or formats.')
    try:
        timestamp = datetime.fromisoformat(header['created_at'])
        if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise RecoveryError('Recovery creation timestamp must identify a UTC instant.') from None


def child_env():
    # Never propagate credentials, SSH agents, Terraform settings, or SOPS keys.
    return {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C'}


def private_write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def checked_read(root_fd, relative, mode, limit=MAX_FILE):
    parent, leaf = vault._open_parent(root_fd, relative)
    try:
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            return read_fd(fd, mode, limit)
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_fd(fd, mode, limit):
    before = os.fstat(fd)
    modes = (mode,) if isinstance(mode, str) else mode
    accepted_modes = {int(value, 8) for value in modes}
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) not in accepted_modes or not 0 < before.st_size <= limit):
        raise RecoveryError('Recovery input must be a bounded regular file with inventoried ownership and mode.')
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(fd, 'rb', closefd=False) as stream:
        content = stream.read(limit + 1)
    if len(content) != before.st_size or fingerprint(before) != fingerprint(os.fstat(fd)):
        raise RecoveryError('Recovery input changed during capture.')
    return content


def pinned_age(root):
    target = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (platform.system(), platform.machine()))
    if target is None:
        raise RecoveryError('No reviewed age binary exists for this platform.')
    bootstrap = module('bootstrap-age')
    base = 'build/tools/age-' + bootstrap.VERSION + '/' + target
    fd = vault._root_fd(root)
    try:
        archive = checked_read(fd, base + '/archive.tar.gz', '0600', bootstrap.MAX_ARCHIVE_BYTES)
        binaries = bootstrap.binaries_from_archive(archive, bootstrap.RELEASES[target]['sha256'])
        for name in ('age', 'age-keygen'):
            installed = checked_read(fd, base + '/' + name, '0755', bootstrap.MAX_BINARY_BYTES)
            if digest(installed) != digest(binaries[name]):
                raise RecoveryError('Pinned age binary checksum failed; run crypto-bootstrap.')
    finally:
        os.close(fd)
    return root / base / 'age'


def crypto(age, arguments, *, identity=None):
    try:
        result = subprocess.run([str(age), *arguments], input=identity,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=child_env(), timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        raise RecoveryError('Age operation could not complete; raw output withheld.') from None
    if result.returncode:
        raise RecoveryError('Age authentication or encryption failed; raw output withheld.')


def policy(root):
    manifest = module('secrets-check').load_manifest(root / 'usenet-infra/recovery/inventory.json')
    root_fd = vault._root_fd(root)
    try:
        # Git honors the caller's umask. Public files may legitimately be 0600
        # in a private clone; secret inputs still require their exact modes.
        recipient = checked_read(root_fd, 'usenet-infra/recovery/age-recipient.txt', ('0600', '0644'), 256).decode().strip()
        vault_bytes = checked_read(root_fd, 'usenet-infra/vault/secrets.sops.json', ('0600', '0644'), 32 * 1024**2)
    finally:
        os.close(root_fd)
    if not re.fullmatch(r'age1[ac-hj-np-z02-9]{58}', recipient):
        raise RecoveryError('The committed native age recipient is invalid.')
    return manifest, recipient, digest(vault_bytes)


def source_revision(root):
    try:
        output = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True,
                                env=child_env(), timeout=10, check=True).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise RecoveryError('The source Git revision could not be established.') from None
    if not re.fullmatch(r'[0-9a-f]{40,64}', output):
        raise RecoveryError('The source Git revision is invalid.')
    return output


def collect(root, manifest, age):
    """Hold Terraform-compatible POSIX read locks across BOTH current states.

    Keep one open descriptor per locked inode: closing ANY descriptor to the
    same inode would release this process's POSIX locks. Never invoke Terraform.
    """
    contents, evidence = {}, {}
    validator = module('recovery-contents')
    with ExitStack() as stack:
        root_fd = vault._root_fd(root)
        stack.callback(os.close, root_fd)
        locked = {}
        for entry in manifest['files']:
            if entry['id'] not in ('cloud-tfstate', 'storage-tfstate'):
                continue
            parent, leaf = vault._open_parent(root_fd, entry['path'])
            stack.callback(os.close, parent)
            try:
                os.stat('.terraform.tfstate.lock.info', dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise RecoveryError('Terraform has a lock record; finish or investigate that operation before capture.')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            stack.callback(os.close, fd)
            try:
                fcntl.lockf(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                raise RecoveryError('Terraform state is locked; capture refused.') from None
            locked[entry['id']] = (fd, parent, leaf, fingerprint(os.fstat(fd)))
        for entry in manifest['files']:
            if entry['category'] == 'vault':
                continue
            try:
                if entry['id'] in locked:
                    content = read_fd(locked[entry['id']][0], entry['mode'], MAX_FILE)
                else:
                    content = checked_read(root_fd, entry['path'], entry['mode'])
            except FileNotFoundError:
                if entry['required']:
                    raise RecoveryError('A required inventoried recovery input is missing.') from None
                continue
            contents[entry['id']] = content
            if sum(map(len, contents.values())) > MAX_PACKAGE - 1024**2:
                raise RecoveryError('Recovery inputs exceed the package size limit.')
            evidence[entry['id']] = validator.validate_entry(entry, content, root, age)
        for identifier, (fd, parent, leaf, before) in locked.items():
            if (fingerprint(os.stat(leaf, dir_fd=parent, follow_symlinks=False)) != before
                    or fingerprint(os.fstat(fd)) != before
                    or read_fd(fd, '0600', MAX_FILE) != contents[identifier]):
                raise RecoveryError('Terraform state changed or was replaced during capture.')
    return contents, evidence


def write_package(path, header, contents):
    with open(path, 'xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            records = [('MANIFEST.json', encode(header))]
            records.extend(('payload/' + key, value) for key, value in sorted(contents.items()))
            for name, value in records:
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(value), 0o600
                archive.addfile(info, io.BytesIO(value))
        stream.flush()
        os.fsync(stream.fileno())


def snapshot_receipt_path(snapshot_id):
    if not isinstance(snapshot_id, str) or not SNAPSHOT.fullmatch(snapshot_id):
        raise RecoveryError('Recovery snapshot identifier is invalid.')
    return 'usenet-infra/recovery/snapshots/' + snapshot_id + '.json'


def publish_snapshot_receipt(root, receipt):
    """Create public recovery evidence for review and inclusion in Git."""
    relative = snapshot_receipt_path(receipt['snapshot_id'])
    root_fd = vault._root_fd(root)
    try:
        vault._preflight_destination(root_fd, relative, replace=False)
        vault._install(root_fd, relative, encode(receipt) + b'\n', 0o644, replace=False)
    finally:
        os.close(root_fd)


def verify_snapshot_receipt(root, receipt):
    """Anchor the untrusted package in the independently retained Git receipt.

    Encryption to a public recipient does not authenticate the sender. Even a
    decryptable package must match the complete receipt carried by this checkout.
    """
    relative = snapshot_receipt_path(receipt.get('snapshot_id'))
    root_fd = vault._root_fd(root)
    try:
        try:
            trusted = parse(checked_read(root_fd, relative, ('0600', '0644'), MAX_METADATA))
        except (OSError, vault.VaultError):
            raise RecoveryError('The trusted Git snapshot receipt is missing or unsafe; recover the reviewed Git revision first.') from None
    finally:
        os.close(root_fd)
    # Canonical JSON preserves exact scalar types, unlike Python equality where
    # True == 1. Whitespace and object field order have no security significance.
    if not isinstance(trusted, dict) or encode(trusted) != encode(receipt):
        raise RecoveryError('Recovery package receipt does not exactly match the trusted Git snapshot receipt.')


def capture(root, output):
    root, output = Path(os.path.abspath(root)), Path(os.path.abspath(output))
    manifest, recipient, vault_hash = policy(root)
    age = pinned_age(root)
    contents, evidence = collect(root, manifest, age)
    created = datetime.now(timezone.utc)
    snapshot_id = created.strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(8)
    header = {'schema_version': 1, 'snapshot_id': snapshot_id, 'created_at': created.isoformat(),
              'inventory_sha256': vault._manifest_digest(manifest), 'vault_sha256': vault_hash,
              'recipient': recipient, 'source_revision': source_revision(root),
              'entries': [{'id': key, 'sha256': digest(value), 'bytes': len(value)}
                          for key, value in sorted(contents.items())]}
    # Destination is a new private directory; no existing package can be replaced.
    parent_fd = vault._root_fd(output.parent)
    try:
        with tempfile.TemporaryDirectory(prefix='smarthome-recovery-') as temporary:
            temporary = Path(temporary)
            plain, encrypted = temporary / 'payload.tar', temporary / 'recovery.tar.age'
            write_package(plain, header, contents)
            crypto(age, ['--encrypt', '--recipient', recipient, '--output', str(encrypted), str(plain)])
            encrypted.chmod(0o600)
            ciphertext = encrypted.read_bytes()
            if not ciphertext.startswith(b'age-encryption.org/v1\n') or len(ciphertext) > MAX_PACKAGE:
                raise RecoveryError('Age did not produce a bounded recovery ciphertext.')
            receipt = {key: value for key, value in header.items() if key != 'entries'}
            receipt.update(ciphertext_sha256=digest(ciphertext), ciphertext_bytes=len(ciphertext),
                           entry_ids=sorted(contents), deletion_safe=False)
            # Publish the complete directory atomically, without overwriting.
            staged = tempfile.mkdtemp(prefix='.recovery-publish-', dir=output.parent)
            try:
                private_write(Path(staged) / 'recovery.tar.age', ciphertext)
                private_write(Path(staged) / 'receipt.json', encode(receipt) + b'\n')
                staged_fd = os.open(staged, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(staged_fd)
                finally:
                    os.close(staged_fd)
                # mkdir reserves the final name; an existing (even empty) path is refused.
                os.mkdir(output.name, 0o700, dir_fd=parent_fd)
                try:
                    os.rename(staged, output.name, dst_dir_fd=parent_fd)
                except BaseException:
                    os.rmdir(output.name, dir_fd=parent_fd)
                    raise
                os.fsync(parent_fd)
            finally:
                if Path(staged).exists():
                    import shutil
                    shutil.rmtree(staged)
    finally:
        os.close(parent_fd)
    publish_snapshot_receipt(root, receipt)
    return {'snapshot_id': snapshot_id, 'entries': len(contents), 'capture_content_checks': evidence,
            'master_decryption_verified': False, 'deletion_safe': False}


def receipt_and_ciphertext(bundle):
    fd = vault._root_fd(bundle)
    try:
        receipt = parse(checked_read(fd, 'receipt.json', '0600', MAX_METADATA))
        ciphertext = checked_read(fd, 'recovery.tar.age', '0600', MAX_PACKAGE)
    finally:
        os.close(fd)
    expected = {'schema_version', 'snapshot_id', 'created_at', 'inventory_sha256', 'vault_sha256',
                'recipient', 'source_revision', 'ciphertext_sha256', 'ciphertext_bytes', 'entry_ids', 'deletion_safe'}
    if (not isinstance(receipt, dict) or set(receipt) != expected or type(receipt['schema_version']) is not int
            or receipt['schema_version'] != 1 or receipt['deletion_safe'] is not False
            or not isinstance(receipt['snapshot_id'], str) or not SNAPSHOT.fullmatch(receipt['snapshot_id'])
            or receipt['ciphertext_sha256'] != digest(ciphertext)
            or type(receipt['ciphertext_bytes']) is not int or receipt['ciphertext_bytes'] != len(ciphertext)):
        raise RecoveryError('Recovery receipt or ciphertext checksum is invalid.')
    validate_header(receipt)
    return receipt, ciphertext


def read_package(path, manifest, receipt):
    if path.stat().st_size > MAX_PACKAGE:
        raise RecoveryError('Authenticated recovery package exceeds the size limit.')
    expected = {e['id']: e for e in manifest['files'] if e['category'] != 'vault'}
    with tarfile.open(path, 'r:') as archive:
        found = {}
        for info in archive:
            if (len(found) > len(expected) or not info.isfile() or info.issparse() or info.pax_headers
                    or info.name in found or not 0 < info.size <= MAX_FILE
                    or info.name not in {'MANIFEST.json', *('payload/' + key for key in expected)}):
                raise RecoveryError('Recovery package contains unexpected or unsafe members.')
            found[info.name] = info
        if 'MANIFEST.json' not in found or found['MANIFEST.json'].size > MAX_METADATA:
            raise RecoveryError('Recovery package manifest is missing or exceeds its size limit.')
        header = parse(archive.extractfile(found['MANIFEST.json']).read())
        fields = {'schema_version', 'snapshot_id', 'created_at', 'inventory_sha256', 'vault_sha256',
                  'recipient', 'source_revision', 'entries'}
        if not isinstance(header, dict) or set(header) != fields:
            raise RecoveryError('Authenticated recovery manifest has an unsupported schema.')
        validate_header(header)
        for field in fields - {'entries'}:
            if header[field] != receipt[field]:
                raise RecoveryError('Public receipt does not match the authenticated package.')
        if header['inventory_sha256'] != vault._manifest_digest(manifest) or not isinstance(header['entries'], list):
            raise RecoveryError('Recovery package does not match this inventory.')
        contents = {}
        for entry in header['entries']:
            if (not isinstance(entry, dict) or set(entry) != {'id', 'bytes', 'sha256'}
                    or not isinstance(entry['id'], str) or entry['id'] not in expected
                    or entry['id'] in contents or type(entry['bytes']) is not int
                    or not 0 < entry['bytes'] <= MAX_FILE):
                raise RecoveryError('Recovery package entry policy is invalid.')
            name = 'payload/' + entry['id']
            if name not in found or found[name].size != entry['bytes']:
                raise RecoveryError('An inventoried recovery member is missing or has the wrong size.')
            value = archive.extractfile(found[name]).read()
            if digest(value) != entry['sha256']:
                raise RecoveryError('An authenticated recovery member checksum is invalid.')
            contents[entry['id']] = value
        if (set(found) != {'MANIFEST.json', *('payload/' + key for key in contents)}
                or sorted(contents) != receipt['entry_ids']
                or any(e['required'] and key not in contents for key, e in expected.items())):
            raise RecoveryError('Recovery package is missing required entries or contains unmanifested files.')
    return contents


def restore_contents(root, manifest, contents):
    """Validate ALL conflicts first; repeat/interrupted restores are resumable.

    Only absent or byte-identical entries are accepted. There is deliberately
    no overwrite flag for Terraform state or historical controller snapshots.
    """
    entries = {e['id']: e for e in manifest['files'] if e['category'] != 'vault'}
    fd = vault._root_fd(root)
    try:
        pending = []
        for key, value in contents.items():
            entry = entries[key]
            parent, leaf = vault._open_parent(fd, entry['restore_path'], create=True)
            try:
                try:
                    existing = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                except FileNotFoundError:
                    pending.append(key)
                    continue
                try:
                    if read_fd(existing, entry['mode'], MAX_FILE) != value:
                        raise RecoveryError('A recovery destination differs; preserve it and restore into a clean checkout.')
                finally:
                    os.close(existing)
            finally:
                os.close(parent)
        for key in pending:
            entry = entries[key]
            vault._install(fd, entry['restore_path'], contents[key], int(entry['mode'], 8), replace=False)
    finally:
        os.close(fd)
    return len(pending)


def verify(root, bundle, *, identity, restore=False):
    manifest, recipient, vault_hash = policy(root)
    receipt, ciphertext = receipt_and_ciphertext(bundle)
    verify_snapshot_receipt(root, receipt)
    if receipt['recipient'] != recipient or receipt['vault_sha256'] != vault_hash:
        raise RecoveryError('Recovery package is paired with a different committed vault or public recipient.')
    if not identity or not identity.startswith('AGE-SECRET-KEY-1') or '\x00' in identity:
        raise RecoveryError('Supply SOPS_AGE_KEY or use --prompt-master from a private terminal.')
    age = pinned_age(root)
    with tempfile.TemporaryDirectory(prefix='smarthome-recovery-') as temporary:
        temporary = Path(temporary)
        encrypted, plain = temporary / 'recovery.age', temporary / 'payload.tar'
        private_write(encrypted, ciphertext)
        crypto(age, ['--decrypt', '--identity', '-', '--output', str(plain), str(encrypted)],
               identity=(identity.strip() + '\n').encode())
        plain.chmod(0o600)
        contents = read_package(plain, manifest, receipt)
        validator = module('recovery-contents')
        pairs = validator.verify_keypairs(root, manifest)
        entries = {e['id']: e for e in manifest['files']}
        evidence = {key: validator.validate_entry(entries[key], value, root, age) for key, value in contents.items()}
        installed = restore_contents(root, manifest, contents) if restore else 0
    return {'snapshot_id': receipt['snapshot_id'], 'entries': len(contents), 'keypairs_verified': pairs,
            'content_checks': evidence, 'new_files_restored': installed, 'master_decryption_verified': True,
            'deletion_safe': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('capture', 'verify', 'restore'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bundle', type=Path, required=True, help='New output directory for capture, existing directory for verify/restore.')
    parser.add_argument('--prompt-master', action='store_true', help='Read the existing master privately from the terminal, without echo.')
    args = parser.parse_args(argv)
    # Pop the master before loading tools or launching ANY subprocess.
    identity = os.environ.pop('SOPS_AGE_KEY', None)
    try:
        if args.prompt_master:
            if not sys.stdin.isatty():
                raise RecoveryError('Private master entry requires an interactive terminal.')
            identity = getpass.getpass('Existing recovery master (hidden): ')
        if args.operation == 'capture':
            result = capture(args.root, args.bundle)
        else:
            result = verify(args.root, args.bundle, identity=identity, restore=args.operation == 'restore')
        print(json.dumps(result, indent=2))
        return 0
    except (RecoveryError, vault.VaultError) as exc:
        print('Recovery failed: ' + str(exc), file=sys.stderr)
        return 1
    except Exception:
        # Imported verifiers and parsers may include plaintext in exception text.
        print('Recovery failed during input validation or authenticated content checks; raw details withheld.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Recovery interrupted; no existing recovery files were replaced.', file=sys.stderr)
        raise SystemExit(130)
