#!/usr/bin/env python3
"""Create or restore the small, SOPS-encrypted recovery vault.

Plaintext is intentionally opaque: this program never sources dotenv files or
interprets YAML/INI/key material.  It only moves bytes named by the public
recovery inventory.  The only persisted vault is a SOPS ciphertext; decryption
is performed by SOPS into an owner-only temporary directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / 'usenet-infra/recovery/inventory.json'
DEFAULT_VAULT = REPO_ROOT / 'usenet-infra/vault/secrets.sops.json'
MAX_ENTRY_BYTES = 4 * 1024 * 1024
MAX_BUNDLE_BYTES = 32 * 1024 * 1024


class VaultError(Exception):
    pass


def _load_checker():
    spec = importlib.util.spec_from_file_location('secrets_check', Path(__file__).with_name('secrets-check.py'))
    if spec is None or spec.loader is None:
        raise VaultError('The recovery inventory validator is unavailable.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative(value: str) -> str:
    if (not isinstance(value, str) or not value or value.startswith('/') or '\x00' in value or '\\' in value
            or value != str(PurePosixPath(value)) or any(part in ('.', '..') for part in value.split('/'))):
        raise VaultError('Vault contains an unsafe repository-relative path.')
    return value


def _vault_entries(manifest: dict) -> list[dict]:
    return [entry for entry in manifest['files'] if entry['category'] == 'vault']


def _manifest_digest(manifest: dict) -> str:
    # Bind all policy fields, not merely destination names.  A vault cannot be
    # restored after a policy change until it has been deliberately re-encrypted.
    return _digest(_canonical_json(manifest))


def _root_fd(root: Path) -> int:
    root = Path(os.path.abspath(root))
    item = root.lstat()
    if not stat.S_ISDIR(item.st_mode) or stat.S_ISLNK(item.st_mode) or item.st_uid != os.getuid():
        raise VaultError('Repository root must be an operator-owned, non-symlinked directory.')
    if stat.S_IMODE(item.st_mode) & 0o022:
        raise VaultError('Repository root must not be group- or world-writable.')
    return os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def _open_parent(root_fd: int, relative: str, *, create: bool = False) -> tuple[int, str]:
    parts = PurePosixPath(_safe_relative(relative)).parts
    current = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise VaultError('Vault source parent directory is missing.') from None
                os.mkdir(part, 0o700, dir_fd=current)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            except OSError:
                raise VaultError('Vault path has an unsafe parent directory.') from None
            item = os.fstat(child)
            if (not stat.S_ISDIR(item.st_mode) or item.st_uid != os.getuid()
                    or stat.S_IMODE(item.st_mode) & 0o022):
                os.close(child)
                raise VaultError('Vault path has an unsafe parent directory.')
            os.close(current)
            current = child
        return current, parts[-1]
    except BaseException:
        os.close(current)
        raise


def _read_source(root_fd: int, relative: str, expected_mode: str) -> bytes:
    parent, leaf = _open_parent(root_fd, relative)
    try:
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except FileNotFoundError:
        os.close(parent)
        raise
    try:
        item = os.fstat(fd)
        if (not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or item.st_nlink != 1
                or stat.S_IMODE(item.st_mode) != int(expected_mode, 8)):
            raise VaultError('Vault source is not an owner-only regular file with inventoried permissions.')
        if item.st_size < 1 or item.st_size > MAX_ENTRY_BYTES:
            raise VaultError('Vault source is empty or exceeds the per-file size limit.')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            content = stream.read(MAX_ENTRY_BYTES + 1)
        if len(content) != item.st_size:
            raise VaultError('Vault source changed while it was being read.')
        return content
    finally:
        os.close(fd)
        os.close(parent)


def _identity_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    key_file = environ.get('SOPS_AGE_KEY_FILE')
    key_text = environ.get('SOPS_AGE_KEY')
    if key_file and key_text:
        raise VaultError('Set only one SOPS age identity mechanism, not both.')
    # A caller's other SOPS_* settings could select a different config or
    # identity provider.  Keep the normal process environment (PATH, locale,
    # proxy settings) but pass SOPS only the one explicitly selected identity.
    result = {key: value for key, value in environ.items() if not key.startswith('SOPS_')}
    if key_file:
        path = Path(key_file)
        try:
            item = path.lstat()
        except OSError:
            raise VaultError('SOPS_AGE_KEY_FILE is unavailable.') from None
        if (not path.is_absolute() or stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode)
                or item.st_uid != os.getuid() or item.st_nlink != 1 or stat.S_IMODE(item.st_mode) != 0o600):
            raise VaultError('SOPS_AGE_KEY_FILE must name an owner-only mode-0600 regular file.')
        result['SOPS_AGE_KEY_FILE'] = str(path)
        return result
    if key_text:
        # Do not print, store, or parse the identity.  SOPS receives it only in
        # the child environment for this one invocation.
        result['SOPS_AGE_KEY'] = key_text
        return result
    raise VaultError('Set SOPS_AGE_KEY_FILE (preferred) or SOPS_AGE_KEY for this command.')


def _default_sops(root: Path) -> Path:
    name = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (platform.system(), platform.machine()))
    if name is None:
        raise VaultError('No reviewed SOPS binary is pinned for this controller platform.')
    path = root / 'build/tools/sops-3.13.3' / name / 'sops'
    try:
        item = path.lstat()
        if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or not item.st_mode & stat.S_IXUSR:
            raise VaultError('Pinned SOPS binary is unsafe.')
        bootstrap = importlib.util.spec_from_file_location('bootstrap_sops', root / 'usenet-infra/scripts/bootstrap-sops.py')
        if bootstrap is None or bootstrap.loader is None:
            raise VaultError('Pinned SOPS verifier is unavailable.')
        module = importlib.util.module_from_spec(bootstrap)
        bootstrap.loader.exec_module(module)
        if _digest(path.read_bytes()) != module.RELEASES[name]['sha256']:
            raise VaultError('Pinned SOPS binary hash is not verified; run crypto-bootstrap.')
    except OSError:
        raise VaultError('Pinned SOPS binary is unavailable; run crypto-bootstrap.') from None
    return path


def _sops_config(root: Path) -> Path:
    path = root / '.sops.yaml'
    try:
        item = path.lstat()
    except OSError:
        raise VaultError('Public SOPS configuration is unavailable; initialize the recovery master first.') from None
    if (stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode)
            or item.st_uid != os.getuid() or stat.S_IMODE(item.st_mode) & 0o022):
        raise VaultError('Public SOPS configuration is unsafe.')
    return path


def _run_sops(args: list[str], *, env: dict[str, str]) -> None:
    try:
        subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       env=env, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VaultError('SOPS could not complete the vault operation.') from exc


def _vault_relative(root: Path, vault_path: Path) -> str:
    try:
        relative = os.path.relpath(os.path.abspath(vault_path), os.path.abspath(root))
    except (TypeError, ValueError):
        raise VaultError('Encrypted vault destination is invalid.') from None
    if relative == '..' or relative.startswith('../'):
        raise VaultError('Encrypted vault must remain inside the repository.')
    return _safe_relative(relative)


def _preflight_destination(root_fd: int, relative: str, *, replace: bool) -> None:
    """Create only safe empty parents and reject every conflicting leaf first."""
    parent, leaf = _open_parent(root_fd, relative, create=True)
    try:
        try:
            existing = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode)
                or existing.st_uid != os.getuid() or existing.st_nlink != 1):
            raise VaultError('Refusing an unsafe existing restore destination.')
        if not replace:
            raise VaultError('Restore destination already exists; use --replace only after review.')
    finally:
        os.close(parent)


def _private_directory() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix='smarthome-secrets-', ignore_cleanup_errors=True)


def _read_bundle(path: Path, manifest: dict) -> dict:
    try:
        item = path.lstat()
        if (not stat.S_ISREG(item.st_mode) or stat.S_ISLNK(item.st_mode) or item.st_uid != os.getuid()
                or stat.S_IMODE(item.st_mode) != 0o600 or item.st_size < 2 or item.st_size > MAX_BUNDLE_BYTES):
            raise VaultError('SOPS produced an unsafe decrypted vault bundle.')
        raw = path.read_bytes()
        data = json.loads(raw, object_pairs_hook=lambda pairs: _no_duplicates(pairs))
    except (OSError, UnicodeError, ValueError, TypeError):
        raise VaultError('Decrypted vault bundle is not valid JSON.') from None
    if not isinstance(data, dict) or set(data) != {'schema_version', 'inventory_sha256', 'source_checkout', 'entries'}:
        raise VaultError('Decrypted vault bundle has an unsupported schema.')
    if data['schema_version'] != 1 or data['inventory_sha256'] != _manifest_digest(manifest):
        raise VaultError('Decrypted vault bundle is not bound to this recovery inventory.')
    source = data['source_checkout']
    if not isinstance(source, str) or not source.startswith('/') or '\x00' in source or source != os.path.normpath(source):
        raise VaultError('Decrypted vault has an unsafe source checkout path.')
    if not isinstance(data['entries'], list):
        raise VaultError('Decrypted vault entries are invalid.')
    expected = {entry['id']: entry for entry in _vault_entries(manifest)}
    found: dict[str, dict] = {}
    for entry in data['entries']:
        if not isinstance(entry, dict) or set(entry) != {'id', 'sha256', 'content'}:
            raise VaultError('Decrypted vault entry has an unsupported schema.')
        identifier, encoded = entry['id'], entry['content']
        if identifier not in expected or identifier in found or not isinstance(encoded, str):
            raise VaultError('Decrypted vault entries do not match the recovery inventory.')
        try:
            import base64
            content = base64.b64decode(encoded.encode('ascii'), validate=True)
        except (UnicodeError, ValueError):
            raise VaultError('Decrypted vault entry is not valid base64.') from None
        if not (0 < len(content) <= MAX_ENTRY_BYTES) or entry['sha256'] != _digest(content):
            raise VaultError('Decrypted vault entry checksum is invalid.')
        found[identifier] = {'metadata': expected[identifier], 'content': content}
    if any(entry['required'] and entry['id'] not in found for entry in expected.values()):
        raise VaultError('Decrypted vault is missing a required recovery entry.')
    return {'source_checkout': source, 'entries': found}


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _rebase(content: bytes, source_checkout: str, destination_root: Path, policy: str) -> bytes:
    if policy == 'exact-bytes':
        return content
    source = source_checkout.encode('utf-8')
    target = str(destination_root).encode('utf-8')
    # Rebase only the exact, absolute checkout prefix captured during encryption.
    # This intentionally leaves remote host paths and unrelated text untouched.
    # A prefix match is not sufficient: ``/old/checkout-extra`` is a distinct
    # path and must not be silently rewritten.  The accepted delimiters cover
    # values in the inventory formats without treating arbitrary prose as a
    # checkout path.
    return re.sub(re.escape(source) + rb'(?=$|[/:,=\"\'\s])', target, content)


def _install(root_fd: int, relative: str, content: bytes, mode: int, *, replace: bool) -> None:
    parent, leaf = _open_parent(root_fd, relative, create=True)
    temporary = '.' + leaf + '.restore-' + next(tempfile._get_candidate_names())
    fd = None
    try:
        try:
            existing = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid() or existing.st_nlink != 1:
                raise VaultError('Refusing an unsafe existing restore destination.')
            if not replace:
                raise VaultError('Restore destination already exists; use --replace only after review.')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.close(fd)
        fd = None
        if existing is None:
            # link(2) provides no-clobber atomic publication on POSIX filesystems.
            os.link(temporary, leaf, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            os.unlink(temporary, dir_fd=parent)
        else:
            os.replace(temporary, leaf, src_dir_fd=parent, dst_dir_fd=parent)
        os.chmod(leaf, mode, dir_fd=parent, follow_symlinks=False)
        os.fsync(parent)
    except FileExistsError:
        raise VaultError('Restore destination appeared concurrently; nothing was overwritten.') from None
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def encrypt(root: Path, manifest_path: Path, vault_path: Path, *, replace: bool = False, sops: Path | None = None,
            environ: dict[str, str] | None = None) -> int:
    checker = _load_checker()
    manifest = checker.load_manifest(manifest_path)
    root = Path(os.path.abspath(root))
    root_fd = _root_fd(root)
    try:
        vault_relative = _vault_relative(root, vault_path)
        # The ciphertext directory is public repository structure, but create it
        # through anchored descriptors so a checkout symlink cannot redirect SOPS.
        vault_parent, vault_leaf = _open_parent(root_fd, vault_relative, create=True)
        try:
            try:
                existing = os.stat(vault_leaf, dir_fd=vault_parent, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            if existing is not None and (stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode)):
                raise VaultError('Encrypted vault destination is unsafe.')
            if existing is not None and not replace:
                raise VaultError('Encrypted vault already exists; use --replace only after review.')
        finally:
            os.close(vault_parent)
        import base64
        entries = []
        for entry in _vault_entries(manifest):
            try:
                content = _read_source(root_fd, entry['path'], entry['mode'])
            except FileNotFoundError:
                if entry['required']:
                    raise VaultError('A required vault source is missing: ' + entry['id']) from None
                continue
            entries.append({'id': entry['id'], 'sha256': _digest(content),
                            'content': base64.b64encode(content).decode('ascii')})
    finally:
        os.close(root_fd)
    bundle = {'schema_version': 1, 'inventory_sha256': _manifest_digest(manifest),
              'source_checkout': str(root), 'entries': entries}
    env = _identity_env(environ)
    binary = _default_sops(root) if sops is None else Path(sops)
    config = _sops_config(root)
    with _private_directory() as temporary:
        plaintext = Path(temporary) / 'bundle.json'
        verified = Path(temporary) / 'verified.json'
        plaintext.write_bytes(_canonical_json(bundle))
        plaintext.chmod(0o600)
        _run_sops([str(binary), '--config', str(config), '--filename-override', vault_relative,
                   '--encrypt', '--input-type', 'json',
                   '--output', str(vault_path), str(plaintext)], env=env)
        # Encryption needs only the public recipient, so authenticate the
        # resulting ciphertext with the supplied identity before publishing a
        # success result.  The verified plaintext stays in the private tempdir.
        _run_sops([str(binary), '--decrypt', '--output', str(verified), str(vault_path)], env=env)
        verified.chmod(0o600)
        _read_bundle(verified, manifest)
    return len(entries)


def restore(root: Path, manifest_path: Path, vault_path: Path, *, replace: bool = False, sops: Path | None = None,
            environ: dict[str, str] | None = None) -> int:
    checker = _load_checker()
    manifest = checker.load_manifest(manifest_path)
    root = Path(os.path.abspath(root))
    root_fd = _root_fd(root)
    try:
        vault_parent, vault_leaf = _open_parent(root_fd, _vault_relative(root, vault_path))
        try:
            item = os.stat(vault_leaf, dir_fd=vault_parent, follow_symlinks=False)
            if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode) or item.st_size < 2:
                raise VaultError('Encrypted vault must be a regular non-symlinked file.')
        finally:
            os.close(vault_parent)
    finally:
        os.close(root_fd)
    env = _identity_env(environ)
    binary = _default_sops(root) if sops is None else Path(sops)
    with _private_directory() as temporary:
        plaintext = Path(temporary) / 'bundle.json'
        _run_sops([str(binary), '--decrypt', '--output', str(plaintext), str(vault_path)], env=env)
        plaintext.chmod(0o600)
        bundle = _read_bundle(plaintext, manifest)
        root_fd = _root_fd(root)
        try:
            # Refuse every known conflict before publishing the first byte.  This
            # avoids a partly restored checkout simply because a later file was
            # already present.
            for restored in bundle['entries'].values():
                _preflight_destination(root_fd, restored['metadata']['restore_path'], replace=replace)
            for restored in bundle['entries'].values():
                entry = restored['metadata']
                content = _rebase(restored['content'], bundle['source_checkout'], root, entry['path_policy'])
                _install(root_fd, entry['restore_path'], content, int(entry['mode'], 8), replace=replace)
        finally:
            os.close(root_fd)
    return len(bundle['entries'])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('encrypt', 'restore'))
    parser.add_argument('--root', type=Path, default=REPO_ROOT)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    parser.add_argument('--replace', action='store_true', help='Deliberately replace an existing ciphertext or local recovery file.')
    args = parser.parse_args(argv)
    try:
        operation = encrypt if args.operation == 'encrypt' else restore
        count = operation(args.root, args.manifest, args.vault, replace=args.replace)
        print(args.operation + ' completed for ' + str(count) + ' inventory entries.')
        return 0
    except VaultError as exc:
        print('Secrets vault ' + args.operation + ' failed: ' + str(exc), file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print('Secrets vault ' + args.operation + ' failed due to an unsafe or unavailable local path.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
