#!/usr/bin/env python3
"""Preserve an idle SAB queue while moving only its metadata to remote staging.

All output is aggregate. Original local metadata and SAB configuration are kept
for recovery. This helper never deletes a download, changes a queue ID or copies
any canonical media. It runs only during the dedicated mount deployment.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from cart_import_sab import SabSource

ROOT = Path('/srv/usenet')
LIMIT = 256 * 1024**2


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        parent = path.parent.stat()
        os.fchown(fd, parent.st_uid, parent.st_gid)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def metadata_inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'metadata_root_invalid')
    files = {}
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'metadata_symlink_refused')
        if path.is_dir():
            continue
        relative = path.relative_to(root)
        require(stat.S_ISREG(path.stat().st_mode) and '__ADMIN__' in relative.parts,
                'payload_present_requires_separate_migration')
        files[str(relative)] = {'size': path.stat().st_size, 'sha256': digest(path)}
        require(len(files) <= 5000 and sum(v['size'] for v in files.values()) <= LIMIT,
                'metadata_migration_exceeds_bound')
    return files


def preflight(root, sab):
    snapshot = sab.snapshot()
    require(not snapshot['postprocessing'] and all(j['status'] == 'Paused' and
            float(j.get('percentage', -1)) == 0 for j in snapshot['queue']), 'queue_not_quiet')
    state = json.loads((root / 'state/catalog/capacity-admission/state.json').read_text())
    require(not state.get('admitted'), 'admission_not_reconciled')
    misc = sab.api('get_config', section='misc')['config']['misc']
    require(misc['download_dir'] == '/data/incomplete' and misc['complete_dir'] == '/data/complete',
            'unexpected_sab_paths')
    receipt = root / 'state/catalog/remote-scratch-setup.json'
    require(not receipt.exists(), 'prior_setup_requires_phase_review')
    value = {'schema_version': 1, 'phase': 'preflight', 'queue': snapshot['queue'],
             'paused': snapshot['paused'], 'source_metadata': metadata_inventory(root / 'downloads/incomplete')}
    save(receipt, value)
    require(sab.api('pause').get('status') is True, 'global_pause_failed')
    require(sab.snapshot()['paused'], 'global_pause_readback_failed')
    return {'status': 'ready', 'queued_jobs': len(snapshot['queue'])}


def preserve_metadata(root):
    # Docker must have stopped SAB before this action. Do not infer quiet from
    # a missing API response and never manipulate a live configuration file.
    result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}',
                             'usenet-cloud-sabnzbd-1'], capture_output=True, text=True, check=True)
    require(result.stdout.strip() == 'false', 'sab_must_be_stopped')
    receipt = root / 'state/catalog/remote-scratch-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] == 'preflight', 'setup_phase_requires_review')
    source = root / 'downloads/incomplete'
    target = root / 'library/.acquisition-staging/incomplete'
    require((root / 'library').is_mount() and not target.is_symlink()
            and not target.parent.is_symlink(), 'remote_mount_required')
    require(source.stat().st_dev != target.stat().st_dev, 'remote_storage_not_distinct')
    files = metadata_inventory(source)
    # A graceful SAB stop can update its metadata; these frozen bytes are the
    # migration inputs. Queue identities were recorded before shutdown.
    require(not metadata_inventory(target), 'remote_metadata_destination_not_empty')
    for relative, proof in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with (source / relative).open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024**2)
        require(digest(destination) == proof['sha256'], 'metadata_copy_hash_mismatch')
    require(metadata_inventory(source) == files == metadata_inventory(target), 'metadata_inventory_changed')
    rollback = root / 'downloads/incomplete-local-before-remote'
    require(not rollback.exists() and not rollback.is_symlink(), 'rollback_path_already_exists')
    value.update(phase='metadata_copied', source_metadata=files)
    save(receipt, value)
    source.rename(rollback)
    source.mkdir(mode=0o000)
    # Keep the original complete tree and all historical media at their paths.
    ini = root / 'config/sabnzbd/sabnzbd.ini'
    original = ini.read_text()
    updated, count = re.subn(r'(?m)^complete_dir\s*=.*$',
                            'complete_dir = /data/complete/remote/complete', original)
    require(count == 1, 'complete_setting_not_unique')
    backup = ini.with_name('sabnzbd.ini.before-remote-scratch')
    require(not backup.exists(), 'original_config_already_preserved')
    shutil.copy2(ini, backup)
    os.chown(backup, ini.stat().st_uid, ini.stat().st_gid)
    descriptor, temporary = tempfile.mkstemp(dir=ini.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(updated); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(ini.stat().st_mode))
        os.chown(temporary, ini.stat().st_uid, ini.stat().st_gid)
        os.replace(temporary, ini)
    finally:
        Path(temporary).unlink(missing_ok=True)
    value['phase'] = 'metadata_preserved_and_configured'; save(receipt, value)
    return {'status': value['phase'], 'metadata_files': len(files),
            'metadata_bytes': sum(v['size'] for v in files.values()), 'media_moved': 0}


def verify(root, sab):
    receipt = root / 'state/catalog/remote-scratch-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] in {'metadata_preserved_and_configured', 'verified'}, 'setup_phase_requires_review')
    require((root / 'downloads/incomplete').is_mount() and
            (root / 'downloads/complete/remote').is_mount(), 'remote_mounts_required')
    misc = sab.api('get_config', section='misc')['config']['misc']
    require(misc['download_dir'] == '/data/incomplete' and
            misc['complete_dir'] == '/data/complete/remote/complete' and
            misc['download_free'] == misc['complete_free'] == '30G', 'sab_path_or_floor_readback_failed')
    snapshot = sab.snapshot(); current = {j['nzo_id']: j for j in snapshot['queue']}
    require(not snapshot['postprocessing'] and all(j['status'] == 'Paused' for j in snapshot['queue']),
            'unexpected_queue_progress_during_setup')
    for before in value['queue']:
        after = current.get(before['nzo_id'])
        require(after and all(before.get(k) == after.get(k) for k in
                ('filename', 'mb', 'mbleft', 'percentage', 'cat')), 'queue_identity_changed')
    if not value['paused']:
        require(sab.api('resume').get('status') is True, 'global_resume_failed')
    require(sab.snapshot()['paused'] == value['paused'], 'global_pause_not_preserved')
    value['phase'] = 'verified'; save(receipt, value)
    return {'status': 'verified', 'preserved_queue_entries': len(value['queue']),
            'global_pause_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'preserve-metadata', 'verify'))
    action = parser.parse_args().action
    locks = [ROOT / 'state/catalog/capacity-admission/lock', ROOT / 'state/catalog/locks/cache.lock']
    with locks[0].open('r+') as admission, locks[1].open('r+') as cache:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(cache, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sab = SabSource(ROOT)
        result = (preserve_metadata(ROOT) if action == 'preserve-metadata' else
                  preflight(ROOT, sab) if action == 'preflight' else verify(ROOT, sab))
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        reason = str(error) if isinstance(error, RuntimeError) and re.fullmatch('[a-z_]+', str(error)) else 'remote_scratch_setup_requires_review'
        print(json.dumps({'status': 'blocked', 'reason': reason, 'error_type': type(error).__name__}))
        sys.exit(1)
