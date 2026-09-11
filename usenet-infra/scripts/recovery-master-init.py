#!/usr/bin/env python3
"""Record public SOPS configuration from an injected age recovery identity.

The private identity exists only as SOPS_AGE_KEY supplied by the operator's
password-manager launcher. This program never creates a durable key file; it
uses a private temporary file only because native age-keygen needs one to derive
the public recipient.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / 'usenet-infra'
AGE_VERSION = '1.3.2'
RECIPIENT_PATH = INFRA / 'recovery' / 'age-recipient.txt'
SOPS_CONFIG_PATH = REPO_ROOT / '.sops.yaml'
RECIPIENT_RE = re.compile(r'age1[ac-hj-np-z02-9]{20,}')


class RecoveryError(Exception):
    pass


def platform_name() -> str:
    name = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get(
        (platform.system(), platform.machine()))
    if name is None:
        raise RecoveryError('This controller has no reviewed native age-keygen binary.')
    return name


def age_keygen_path() -> Path:
    return REPO_ROOT / 'build' / 'tools' / ('age-' + AGE_VERSION) / platform_name() / 'age-keygen'


def regular_private(path: Path) -> None:
    item = path.lstat()
    if (not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or item.st_nlink != 1
            or stat.S_IMODE(item.st_mode) != 0o600):
        raise RecoveryError('The recovery identity was not created as one private mode-0600 regular file.')


def check_keygen(binary: Path, runner=subprocess.run) -> None:
    try:
        result = runner([str(binary), '--version'], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise RecoveryError('The reviewed native age-keygen binary is unavailable.') from None
    if result.stdout.strip().removeprefix(b'v') != AGE_VERSION.encode():
        raise RecoveryError('The reviewed native age-keygen version is required.')


def recipient_from_identity(binary: Path, identity: Path, runner=subprocess.run) -> str:
    try:
        result = runner([str(binary), '-y', str(identity)], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise RecoveryError('Could not derive the public recovery recipient.') from None
    recipient = result.stdout.decode('ascii', 'strict').strip()
    if not RECIPIENT_RE.fullmatch(recipient):
        raise RecoveryError('Native age-keygen returned an invalid public recovery recipient.')
    return recipient


def atomic_public_write(path: Path, value: str) -> None:
    if path.is_symlink():
        raise RecoveryError('Refused a symlinked public recovery configuration path.')
    if path.exists():
        if not path.is_file() or path.read_text(encoding='utf-8') != value:
            raise RecoveryError('Refused to replace divergent public recovery configuration.')
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def sops_config(recipient: str) -> str:
    return ('# Public recipient only; private recovery identities never belong in this checkout.\n'
            'creation_rules:\n'
            '  - path_regex: ^usenet-infra/vault/[A-Za-z0-9][A-Za-z0-9._/-]*\\.sops\\.(yaml|yml|json|env|ini|bin)$\n'
            '    age: ' + recipient + '\n')


def initialize_from_environment(*, confirmed_second_copy: bool, keygen=None, runner=subprocess.run,
                                environ=None, recipient_path: Path = RECIPIENT_PATH,
                                sops_path: Path = SOPS_CONFIG_PATH) -> str:
    """Record public SOPS configuration from a one-process age identity value.

    age-keygen derives a recipient from an identity file, so use a mode-0600
    file inside a private temporary directory only.  It is removed before this
    command returns and is never in the checkout, an argument, or output.
    """
    if not confirmed_second_copy:
        raise RecoveryError('Refusing to initialize a master until the operator confirms a second independent copy plan.')
    environ = os.environ if environ is None else environ
    identity = environ.get('SOPS_AGE_KEY')
    if not identity:
        raise RecoveryError('Set only SOPS_AGE_KEY for environment-based master initialization.')
    if '\x00' in identity or not identity.startswith('AGE-SECRET-KEY-1'):
        raise RecoveryError('SOPS_AGE_KEY is not a native age identity.')
    keygen = age_keygen_path() if keygen is None else Path(keygen)
    check_keygen(keygen, runner)
    with tempfile.TemporaryDirectory(prefix='smarthome-age-master-') as directory:
        temporary = Path(directory) / 'identity.agekey'
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(identity)
                if not identity.endswith('\n'):
                    stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            regular_private(temporary)
            recipient = recipient_from_identity(keygen, temporary, runner)
        finally:
            temporary.unlink(missing_ok=True)
    atomic_public_write(recipient_path, recipient + '\n')
    atomic_public_write(sops_path, sops_config(recipient))
    return recipient


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-second-copy', action='store_true',
                        help='Confirm a second independently retrievable private copy will be made immediately')
    args = parser.parse_args(argv)
    try:
        recipient = initialize_from_environment(confirmed_second_copy=args.confirm_second_copy)
        print('Public SOPS recipient initialized: ' + recipient)
        print('This checkout is still not safe to delete.')
        return 0
    except (RecoveryError, OSError, UnicodeError) as exc:
        print('Recovery master bootstrap failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
