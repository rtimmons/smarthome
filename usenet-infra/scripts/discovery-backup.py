#!/usr/bin/env python3
"""Capture and round-trip a supplemental cloud backup using existing escrowed keys.

The bound SOPS inventory and original full-clone snapshot remain unchanged.
The immutable store transports native age ciphertext; this supplemental archive
uses the existing cloud-admin recipient, recovered through the original vault.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

INFRA = Path(__file__).resolve().parents[1]
BUILD = INFRA.parent / 'build/discovery-backups'


def run(arguments, output=None):
    result = subprocess.run(arguments, cwd=INFRA, stdout=output or subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=300)
    if result.returncode:
        raise RuntimeError('backup_subcommand_failed')
    return json.loads(result.stdout) if output is None else None


def verify(archive):
    identity = Path(os.environ['CLOUD_SSH_KEY'])
    if not identity.is_absolute():
        identity = INFRA / identity
    return run([str(INFRA / 'scripts/config-backup-local'), 'verify',
                '--identity-file', str(identity), '--archive', str(archive)])


def main():
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot = stamp + '-' + secrets.token_hex(8)
    BUILD.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BUILD.is_symlink() or BUILD.stat().st_mode & 0o077:
        raise RuntimeError('backup_directory_not_private')
    bundle = BUILD / snapshot
    bundle.mkdir(mode=0o700)
    remote = '/srv/usenet/backups/discovery-' + snapshot + '.tar.age'
    cloud = [str(INFRA / 'scripts/cloud-command'), 'sudo', '-n', '-u', 'usenet']
    captured = run([*cloud, 'python3', '/srv/usenet/libexec/config-backup.py',
        '--age-binary', '/srv/usenet/libexec/age', 'capture',
        '--recipient-file', '/srv/usenet/config/backup-recipient.pub', '--output', remote])
    archive = bundle / 'recovery.tar.age'
    with archive.open('xb') as stream:
        run([*cloud, 'cat', '--', remote], stream)
    verified = verify(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if (captured.get('status') != 'captured' or verified.get('status') != 'verified'
            or captured.get('archive_sha256') != digest or verified.get('archive_sha256') != digest):
        raise RuntimeError('capture_verification_mismatch')
    receipt = {'schema_version': 1, 'snapshot_id': snapshot, 'deletion_safe': False,
        'scope': 'supplemental-cloud-config', 'ciphertext_sha256': digest,
        'ciphertext_bytes': archive.stat().st_size,
        'recipient': 'existing cloud-admin SSH identity; restored by the SOPS vault',
        'restore_tool': 'config-backup.py; not recovery-bundle.py',
        'baseline_snapshot_id': '20260911T191749Z-5150bea3423e3707',
        'nas_path': '/share/Container/usenet-recovery/' + snapshot,
        'verification': verified}
    (bundle / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    spec = importlib.util.spec_from_file_location('store', INFRA / 'scripts/recovery-store.py')
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    command = store.connection_command(store.read_environment(INFRA / '.env'))
    store.push(bundle, command)
    fetched = BUILD / (snapshot + '-fetched')
    store.fetch(snapshot, fetched, command)
    downloaded = fetched / 'recovery.tar.age'
    if downloaded.read_bytes() != archive.read_bytes() or verify(downloaded) != verified:
        raise RuntimeError('nas_backup_roundtrip_mismatch')
    # Remote source and local ciphertext are retained; no cleanup can erase the
    # only copy after a partial failure. This operation installs no retention job.
    evidence = dict(receipt, nas_roundtrip_verified=True)
    path = bundle / 'verified.json'
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': 'verified', 'snapshot_id': snapshot,
                      'report': str(path), 'ciphertext_sha256': digest}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Supplemental backup failed; existing backups were retained. No credential values are logged.', file=sys.stderr)
        sys.exit(1)
