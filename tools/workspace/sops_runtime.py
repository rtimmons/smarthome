"""Verify the pinned SOPS tool and require single-recipient native age envelopes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import stat


class VaultError(Exception):
    pass


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def pinned_sops(root: Path) -> Path:
    name = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (platform.system(), platform.machine()))
    if name is None:
        raise VaultError('No reviewed SOPS binary is pinned for this controller platform.')
    path = root / 'build/tools/sops-3.13.3' / name / 'sops'
    try:
        item = path.lstat()
        if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or not item.st_mode & stat.S_IXUSR:
            raise VaultError('Pinned SOPS binary is unsafe.')
        bootstrap = importlib.util.spec_from_file_location('bootstrap_sops', Path(__file__).resolve().with_name('bootstrap-sops.py'))
        if bootstrap is None or bootstrap.loader is None:
            raise VaultError('Pinned SOPS verifier is unavailable.')
        module = importlib.util.module_from_spec(bootstrap)
        bootstrap.loader.exec_module(module)
        if hashlib.sha256(path.read_bytes()).hexdigest() != module.RELEASES[name]['sha256']:
            raise VaultError('Pinned SOPS binary hash is not verified; run crypto-bootstrap.')
    except OSError:
        raise VaultError('Pinned SOPS binary is unavailable; run crypto-bootstrap.') from None
    return path


def validate_ciphertext(content: bytes) -> None:
    """Reject every backend except one native age recipient before SOPS runs."""
    try:
        if not 2 <= len(content) <= 64 * 1024**2:
            raise ValueError
        document = json.loads(content, object_pairs_hook=_no_duplicates)
        metadata = document['sops']
        if (not isinstance(document, dict) or not isinstance(metadata, dict)
                or set(metadata) != {'age', 'lastmodified', 'mac', 'unencrypted_suffix', 'version'}
                or metadata['unencrypted_suffix'] != '_unencrypted'
                or not isinstance(metadata['age'], list) or len(metadata['age']) != 1):
            raise ValueError
        recipient = metadata['age'][0]
        if (not isinstance(recipient, dict) or set(recipient) != {'recipient', 'enc'}
                or not isinstance(recipient['recipient'], str)
                or not re.fullmatch(r'age1[ac-hj-np-z02-9]{58}', recipient['recipient'])
                or not isinstance(recipient['enc'], str)
                or not recipient['enc'].startswith('-----BEGIN AGE ENCRYPTED FILE-----\n')
                or not recipient['enc'].rstrip().endswith('-----END AGE ENCRYPTED FILE-----')):
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise VaultError('Encrypted vault must contain exactly one native age recipient and no other identity providers.') from None
