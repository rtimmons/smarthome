#!/usr/bin/env python3
"""Move only idle queue metadata to a local spool and verify native hardlinks."""
from __future__ import annotations
import argparse
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import uuid

from cart_import_sab import SabSource

ROOT = Path('/srv/usenet')
MARKER = {'schema_version': 2, 'mode': 'hybrid', 'native_hardlinks': True}


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def is_mountpoint(path):
    findmnt = shutil.which('findmnt')
    if findmnt is None:
        return path.is_mount()
    result = subprocess.run([findmnt, '--noheadings', '--output', 'TARGET', '--target', str(path)],
                            capture_output=True, text=True, check=False)
    return any(line.strip() == str(path) for line in result.stdout.splitlines())


def preflight(root, sab):
    old = module('remote-scratch-setup')
    snapshot = sab.snapshot()
    require(not snapshot['postprocessing'] and all(j['status'] == 'Paused' and
            float(j.get('percentage', -1)) == 0 for j in snapshot['queue']), 'queue_not_quiet')
    state = json.loads((root / 'state/catalog/capacity-admission/state.json').read_text())
    require(not state.get('admitted'), 'admission_not_reconciled')
    owned = [j for j in snapshot['queue'] if j['nzo_id'] in state['owned']]
    if owned:
        stats = os.statvfs(root)
        required = max(math.ceil(float(j['mbleft']) * 1024**2) for j in owned) + 35 * 1024**3
        require(stats.f_bavail * stats.f_frsize >= required, 'local_spool_budget_insufficient')
    require(json.loads((root / 'config/catalog/remote-scratch.json').read_text()) ==
            {'schema_version': 1, 'mode': 'storagebox'}, 'expected_previous_staging_mode')
    receipt = root / 'state/catalog/hybrid-scratch-setup.json'
    require(not receipt.exists(), 'prior_setup_requires_phase_review')
    require(is_mountpoint(root / 'downloads/incomplete') and is_mountpoint(root / 'library'), 'mounts_required')
    value = {'schema_version': 1, 'phase': 'preflight', 'queue': snapshot['queue'],
             'paused': snapshot['paused'], 'source_metadata': old.metadata_inventory(root / 'downloads/incomplete')}
    old.save(receipt, value)
    require(sab.api('pause').get('status') is True and sab.snapshot()['paused'], 'pause_readback_failed')
    return {'status': 'ready', 'queued_requests': len(snapshot['queue'])}


def copy_metadata(root):
    old = module('remote-scratch-setup')
    result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', 'usenet-cloud-sabnzbd-1'],
                            capture_output=True, text=True, check=True)
    require(result.stdout.strip() == 'false', 'sab_must_be_stopped')
    receipt = root / 'state/catalog/hybrid-scratch-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] == 'preflight', 'setup_phase_requires_review')
    source, target = root / 'downloads/incomplete', root / 'downloads/incomplete-local-spool'
    require(not target.exists() and not target.is_symlink(), 'spool_destination_exists')
    files = old.metadata_inventory(source)
    target.mkdir(mode=0o700)
    require(target.stat().st_dev == root.stat().st_dev != source.stat().st_dev, 'spool_filesystem_invalid')
    for relative, proof in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with (source / relative).open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024**2)
        require(old.digest(destination) == proof['sha256'], 'metadata_copy_hash_mismatch')
    require(old.metadata_inventory(source) == files == old.metadata_inventory(target), 'metadata_inventory_changed')
    account = pwd.getpwnam('usenet')
    for path in [target, *target.rglob('*')]:
        os.chown(path, account.pw_uid, account.pw_gid)
    value.update(phase='metadata_copied', source_metadata=files)
    old.save(receipt, value)
    return {'status': 'metadata_copied', 'files': len(files), 'bytes': sum(v['size'] for v in files.values()),
            'media_moved': 0, 'remote_original_preserved': True}


def configure_native(root):
    api = module('discovery-config').API(root / 'config')
    account = pwd.getpwnam('usenet')
    for app, kind in [('radarr', 'Movies'), ('sonarr', 'TV')]:
        require(any(r.get('path') == '/library' and r.get('accessible') is True
                    for r in api.call(app, 'rootfolder')), 'native_library_unavailable')
        media = api.call(app, 'config/mediamanagement')
        require(media.get('copyUsingHardlinks') is True,
                'native_hardlinks_must_be_enabled')
        require(str(media.get('fileDate', 'none')).lower() == 'none', 'native_file_date_changes_source')
        clients = [c for c in api.call(app, 'downloadclient') if c.get('implementation') == 'Sabnzbd']
        require(len(clients) == 1, 'sab_client_not_unique')
        hosts = [f.get('value') for f in clients[0]['fields'] if f.get('name') == 'host']
        require(len(hosts) == 1 and isinstance(hosts[0], str) and hosts[0], 'sab_host_missing')
        desired = {'host': hosts[0], 'remotePath': '/data/complete/remote/complete/',
                   'localPath': '/storage/.acquisition-staging/complete/'}
        matches = [m for m in api.call(app, 'remotepathmapping') if m.get('host') == hosts[0]
                   and m.get('remotePath') == desired['remotePath']]
        require(len(matches) <= 1, 'native_mapping_ambiguous')
        if matches:
            require(all(matches[0].get(k) == v for k, v in desired.items()), 'native_mapping_conflict')
        else:
            api.call(app, 'remotepathmapping', 'POST', desired)
        require(any(all(m.get(k) == v for k, v in desired.items())
                    for m in api.call(app, 'remotepathmapping')), 'native_mapping_readback_failed')
        # Exercise the exact container user and /library alias used by Arr.
        # Changed bytes through the second name prove a real hardlink even when
        # SSHFS synthesizes different inode numbers for its pathname aliases.
        token = uuid.uuid4().hex
        source = '/storage/.acquisition-staging/.hardlink-probe-' + token
        target = '/library/.hardlink-probe-' + token
        script = '''set -eu
test "$(readlink /library)" = "/storage/$3"
test ! -e "$1" && test ! -e "$2"
umask 077
set -C
printf initial > "$1"
trap 'rm -f -- "$1" "$2"' EXIT
ln "$1" "$2"
printf changed >| "$1"
test "$(cat "$2")" = changed
'''
        subprocess.run(['docker', 'exec', '--user', f'{account.pw_uid}:{account.pw_gid}',
                        f'usenet-discovery-{app}-1', '/bin/sh', '-c', script, 'probe', source, target, kind],
                       check=True, capture_output=True, text=True)
    receipt = root / 'state/catalog/hybrid-scratch-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] in {'metadata_copied', 'native_verified', 'verified'}, 'setup_phase_requires_review')
    value.update(phase='native_verified', native_hardlinks_verified=['radarr', 'sonarr'])
    module('remote-scratch-setup').save(receipt, value)
    return {'status': 'native_hardlinks_verified', 'applications': 2}


def verify(root, sab):
    receipt = root / 'state/catalog/hybrid-scratch-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] in {'native_verified', 'verified'}, 'native_verification_required')
    require(json.loads((root / 'config/catalog/remote-scratch.json').read_text()) == MARKER, 'marker_invalid')
    incomplete, remote = root / 'downloads/incomplete', root / 'downloads/complete/remote'
    require(is_mountpoint(incomplete) and is_mountpoint(remote) and
            incomplete.stat().st_dev == root.stat().st_dev != remote.stat().st_dev, 'split_mounts_required')
    misc = sab.api('get_config', section='misc')['config']['misc']
    require(misc['download_dir'] == '/data/incomplete' and misc['complete_dir'] == '/data/complete/remote/complete'
            and misc['download_free'] == misc['complete_free'] == '30G', 'sab_paths_or_floors_changed')
    snapshot = sab.snapshot()
    current = {j['nzo_id']: j for j in snapshot['queue']}
    require(not snapshot['postprocessing'] and len(current) == len(value['queue']), 'queue_changed')
    for before in value['queue']:
        after = current.get(before['nzo_id'])
        require(after and after['status'] == 'Paused' and all(before.get(k) == after.get(k)
                for k in ('filename', 'mb', 'mbleft', 'percentage', 'cat')), 'queue_identity_changed')
    if not value['paused']:
        require(sab.api('resume').get('status') is True, 'global_resume_failed')
    require(sab.snapshot()['paused'] == value['paused'], 'global_pause_changed')
    value['phase'] = 'verified'
    module('remote-scratch-setup').save(receipt, value)
    return {'status': 'verified', 'queued_requests_preserved': len(current)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'copy-metadata', 'configure-native', 'verify'))
    action = parser.parse_args().action
    with (ROOT / 'state/catalog/capacity-admission/lock').open('r+') as admission, \
            (ROOT / 'state/catalog/locks/cache.lock').open('r+') as cache:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(cache, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = (copy_metadata(ROOT) if action == 'copy-metadata' else configure_native(ROOT)
                  if action == 'configure-native' else verify(ROOT, SabSource(ROOT))
                  if action == 'verify' else preflight(ROOT, SabSource(ROOT)))
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'error_type': type(error).__name__,
                          'reason': str(error) if isinstance(error, RuntimeError) else 'hybrid_setup_requires_review'}))
        raise SystemExit(1)
