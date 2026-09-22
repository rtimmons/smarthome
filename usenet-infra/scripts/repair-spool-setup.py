#!/usr/bin/env python3
"""Prepare the approved blank volume and relocate only an idle incomplete spool.

Every mutation is bound to a provider volume ID and a durable private receipt.
Original spool bytes, holds, queue identities and the hybrid marker are retained.
Interrupted migrations require phase review; they are never blindly replayed.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import tempfile
import time
import uuid

ROOT = Path('/srv/usenet')
TIMERS = ('usenet-capacity-admission.timer', 'usenet-cart-import.timer',
          'usenet-incomplete-maintenance.timer')
MOUNT_UNIT = 'srv-usenet-repair.mount'
BIND_UNIT = 'srv-usenet-downloads-incomplete.mount'
SAB_UNIT = 'usenet-sab-remote.service'
GIB = 1024 ** 3


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def save(path, value, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(json.dumps(value, sort_keys=True) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_receipt(path, value):
    # The existing encrypted backup runs as usenet. Keep root-only writes while
    # allowing that account to capture setup/rollback evidence.
    save(path, value, 0o640)
    os.chown(path, 0, pwd.getpwnam('usenet').pw_gid)


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'spool_root_invalid')
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'spool_symlink_refused')
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'spool_shared_or_special_file_refused')
        result[str(path.relative_to(root))] = {
            'sha256': digest(path), 'size': info.st_size, 'mode': stat.S_IMODE(info.st_mode),
            'mtime_ns': info.st_mtime_ns, 'uid': info.st_uid, 'gid': info.st_gid,
        }
    return result


def validate_blank_device(row, volume_id):
    require(row['type'] == 'disk' and str(row['serial']) == str(volume_id)
            and row['size'] == 300 * GIB and not row.get('children')
            and not any(row.get('mountpoints', [])) and not row.get('fstype'),
            'new_blank_300gb_volume_identity_required')


def capacity_module(root):
    spec = importlib.util.spec_from_file_location('spool_capacity', root / 'libexec/capacity-admission.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state_fingerprints(root):
    paths = [root / 'state/catalog/cart-import/armed.json',
             root / 'config/catalog/remote-scratch.json',
             *sorted((root / 'state/catalog/cart-import/jobs').glob('*.json'))]
    capacity = json.loads((root / 'state/catalog/capacity-admission/state.json').read_text())
    require(not capacity.get('admitted'), 'admission_active')
    return {'files': {str(p.relative_to(root)): digest(p) for p in paths},
            'held': capacity['held'], 'owned': capacity['owned']}


def quiet(sab):
    snapshot = sab.snapshot()
    require(not snapshot['postprocessing'] and all(j['status'] == 'Paused' for j in snapshot['queue']),
            'sab_not_idle')
    return snapshot


def set_feed(sab, name, enabled):
    result = sab.api('set_config', section='rss', keyword=name, enable=enabled)
    # SAB returns a config object for settings writes, not a status=True receipt.
    require(isinstance(result, dict) and result.get('status') is not False and not result.get('error'), 'feed_update_rejected')
    matches = [f for f in sab.api('get_config', section='rss')['config']['rss'] if f['name'] == name]
    require(len(matches) == 1 and str(int(matches[0]['enable'])) == str(int(enabled)), 'feed_setting_readback_failed')


def finish_bound(root, sab, value, receipt):
    require((root / 'downloads/incomplete').samefile(root / 'repair/incomplete'), 'new_spool_binding_not_verified')
    controller = capacity_module(root).Controller(root)
    controller.require_resources()
    # Discovery is bound to incomplete.mount too; stopping that mount stops Arr.
    require('discovery_was_active' in value, 'discovery_baseline_required')
    if value['discovery_was_active']:
        command('systemctl', 'start', 'usenet-discovery.service')
    controller.require_dependencies()
    after = quiet(sab)
    require(after['queue'] == value['queue'] and after['history'] == value['history'], 'sab_state_changed')
    require(state_fingerprints(root) == value['fingerprints'], 'historical_state_changed')
    require(inventory(root / 'downloads/incomplete-local-spool') == value['source_inventory'], 'original_spool_changed')
    for feed in value['feeds']:
        set_feed(sab, feed['name'], feed['enable'])
    if not value['paused']:
        require(sab.api('resume').get('status') is True, 'global_pause_restore_failed')
    require(sab.snapshot()['paused'] == value['paused'], 'global_pause_changed')
    value['phase'] = 'verified'
    value['verified_at'] = time.time()
    save_receipt(receipt, value)


def restore_timers(value):
    for timer, was_active in value['timers'].items():
        if was_active:
            command('systemctl', 'start', timer)


def inspect(root, volume_id):
    value = json.loads((root / 'state/catalog/repair-spool-setup.json').read_text())
    require(value['phase'] == 'verified' and value['volume_id'] == volume_id, 'verified_volume_required')
    marker = json.loads((root / 'config/catalog/repair-spool.json').read_text())
    require(marker['volume_id'] == volume_id and marker['filesystem_uuid'] == value['filesystem_uuid'], 'volume_marker_changed')
    controller = capacity_module(root).Controller(root)
    controller.require_resources()
    controller.require_dependencies()
    return {'status': 'verified', 'available_spool_bytes': controller.available()}


def resume_bound(root, volume_id):
    import cart_import_sab
    receipt = root / 'state/catalog/repair-spool-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] == 'bound' and value['volume_id'] == volume_id, 'bound_resume_requires_review')
    with (root / 'state/catalog/capacity-admission/lock').open('r+') as admission, \
            (root / 'state/catalog/locks/cache.lock').open('r+') as cache:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(cache, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finish_bound(root, cart_import_sab.SabSource(root), value, receipt)
    restore_timers(value)
    return {'status': 'verified', 'original_preserved': True,
            'verified_files': len(value['source_inventory']),
            'verified_bytes': sum(v['size'] for v in value['source_inventory'].values())}


def prepare(root, volume_id):
    receipt = root / 'state/catalog/repair-spool-setup.json'
    require(not receipt.exists(), 'existing_receipt_requires_phase_review')
    device = Path('/dev/disk/by-id') / ('scsi-0HC_Volume_' + str(volume_id))
    require(device.exists() and stat.S_ISBLK(device.stat().st_mode), 'volume_device_missing')
    rows = json.loads(command('lsblk', '-J', '-b', '-o', 'TYPE,SIZE,SERIAL,FSTYPE,MOUNTPOINTS', str(device)))['blockdevices']
    require(len(rows) == 1, 'volume_device_ambiguous')
    validate_blank_device(rows[0], volume_id)
    require(not json.loads(command('wipefs', '--json', str(device))).get('signatures'), 'device_has_signature')
    mount = root / 'repair'
    require(not mount.exists() or (not mount.is_symlink() and not any(mount.iterdir())), 'mount_directory_not_empty')
    require(not Path('/etc/systemd/system', MOUNT_UNIT).exists(), 'mount_unit_already_exists')
    mount.mkdir(exist_ok=True, mode=0o000)
    mount.chmod(0o000)
    value = {'schema_version': 1, 'phase': 'format_intent', 'volume_id': volume_id,
             'filesystem_uuid': str(uuid.uuid4()), 'created_at': time.time()}
    save_receipt(receipt, value)
    # No force flag: only the new, independently identified blank device is formatted.
    command('mkfs.ext4', '-q', '-m', '1', '-L', 'usenet-repair', '-U', value['filesystem_uuid'], str(device))
    require(command('blkid', '-s', 'UUID', '-o', 'value', str(device)) == value['filesystem_uuid'], 'filesystem_uuid_mismatch')
    value['phase'] = 'formatted'
    save_receipt(receipt, value)
    unit = ('[Unit]\nDescription=Approved Usenet repair volume\nAfter=network-online.target\n'
            '[Mount]\nWhat=/dev/disk/by-uuid/' + value['filesystem_uuid'] + '\nWhere=' + str(mount) +
            '\nType=ext4\nOptions=nodev,nosuid,noexec\nTimeoutSec=90\n'
            '[Install]\nWantedBy=multi-user.target\n')
    Path('/etc/systemd/system', MOUNT_UNIT).write_text(unit)
    Path('/etc/systemd/system', MOUNT_UNIT).chmod(0o644)
    command('systemd-analyze', 'verify', '/etc/systemd/system/' + MOUNT_UNIT)
    command('systemctl', 'daemon-reload')
    command('systemctl', 'enable', '--now', MOUNT_UNIT)
    require(mount.stat().st_dev == device.stat().st_rdev, 'mounted_device_mismatch')
    user = pwd.getpwnam('usenet')
    destination = mount / 'incomplete'
    destination.mkdir(mode=0o700)
    os.chown(destination, user.pw_uid, user.pw_gid)
    require(os.statvfs(mount).f_bavail * os.statvfs(mount).f_frsize >= 235 * GIB, 'formatted_capacity_insufficient')
    value['phase'] = 'prepared'
    save_receipt(receipt, value)
    return {'status': 'prepared', 'size_gb': 300}


def migrate(root, volume_id, controller_source, resume_quiesce=False):
    import cart_import_sab
    receipt = root / 'state/catalog/repair-spool-setup.json'
    value = json.loads(receipt.read_text())
    require(value['phase'] == ('quiesce_intent' if resume_quiesce else 'prepared')
            and value['volume_id'] == volume_id, 'migration_phase_requires_review')
    sab = cart_import_sab.SabSource(root)
    before = quiet(sab)
    original = root / 'downloads/incomplete-local-spool'
    source = root / 'downloads/incomplete'
    destination = root / 'repair/incomplete'
    require(source.samefile(original), 'original_spool_binding_changed')
    require(not destination.is_symlink() and not any(destination.iterdir()), 'destination_not_empty')
    if resume_quiesce:
        require(before['queue'] == value['queue'] and before['history'] == value['history']
                and state_fingerprints(root) == value['fingerprints']
                and not (root / 'config/catalog/repair-spool.json').exists()
                and not (root / 'state/catalog/repair-spool-controller-before.py').exists(),
                'quiesce_resume_state_changed')
    else:
        value.update(phase='quiesce_intent', queue=before['queue'], history=before['history'],
                     paused=before['paused'], fingerprints=state_fingerprints(root),
                     discovery_was_active=command('systemctl', 'show', 'usenet-discovery.service', '--property=ActiveState', '--value') == 'active',
                     timers={t: command('systemctl', 'show', t, '--property=ActiveState', '--value') == 'active' for t in TIMERS},
                     feeds=[{'name': f['name'], 'enable': f['enable']} for f in sab.api('get_config', section='rss')['config']['rss']])
        save_receipt(receipt, value)
    command('systemctl', 'stop', *TIMERS)
    deadline = time.monotonic() + 150
    while any(command('systemctl', 'show', t.replace('.timer', '.service'), '--property=ActiveState', '--value')
              not in ('inactive', 'failed') for t in TIMERS):
        require(time.monotonic() < deadline, 'scratch_worker_still_active')
        time.sleep(1)
    with (root / 'state/catalog/capacity-admission/lock').open('r+') as admission, \
            (root / 'state/catalog/locks/cache.lock').open('r+') as cache:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(cache, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(state_fingerprints(root) == value['fingerprints'], 'historical_state_changed')
        for feed in value['feeds']:
            set_feed(sab, feed['name'], 0)
        require(sab.api('pause').get('status') is True, 'global_pause_failed')
        require(quiet(sab)['queue'] == value['queue'], 'queue_changed_before_copy')
        command('systemctl', 'stop', SAB_UNIT)
        require(command('docker', 'inspect', '-f', '{{.State.Running}}', 'usenet-cloud-sabnzbd-1') == 'false', 'sab_not_stopped')
        value['source_inventory'] = inventory(source)
        value['phase'] = 'copy_intent'
        save_receipt(receipt, value)
        command('rsync', '-a', '--numeric-ids', '--', str(source) + '/', str(destination) + '/')
        require(inventory(source) == inventory(destination) == value['source_inventory'], 'copy_integrity_failed')
        require(state_fingerprints(root) == value['fingerprints'], 'historical_state_changed')
        value['phase'] = 'copied'
        save_receipt(receipt, value)
        # Preserve the old controller for rollback, then replace it atomically.
        target = root / 'libexec/capacity-admission.py'
        backup = root / 'state/catalog/repair-spool-controller-before.py'
        require(not backup.exists(), 'controller_backup_already_exists')
        shutil.copy2(target, backup)
        backup.chmod(0o640)
        os.chown(backup, 0, pwd.getpwnam('usenet').pw_gid)
        code = controller_source.read_bytes()
        compile(code, 'capacity-admission.py', 'exec')
        fd, temp = tempfile.mkstemp(dir=target.parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(code); stream.flush(); os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o550)
            os.fchown(stream.fileno(), 0, pwd.getpwnam('usenet').pw_gid)
        os.replace(temp, target)
        command('systemctl', 'stop', BIND_UNIT)
        require(stat.S_IMODE(source.stat().st_mode) == 0, 'unmounted_spool_not_protected')
        dropin = Path('/etc/systemd/system', BIND_UNIT + '.d/repair-spool.conf')
        require(not dropin.exists(), 'binding_override_already_exists')
        dropin.parent.mkdir(exist_ok=True)
        dropin.write_text('[Unit]\nRequires=' + MOUNT_UNIT + '\nBindsTo=' + MOUNT_UNIT +
                          '\nAfter=' + MOUNT_UNIT + '\n[Mount]\nWhat=' + str(destination) + '\n')
        dropin.chmod(0o644)
        marker = root / 'config/catalog/repair-spool.json'
        require(not marker.exists(), 'repair_spool_marker_already_exists')
        save(marker, {k: value[k] for k in ('schema_version', 'volume_id', 'filesystem_uuid')}, 0o640)
        os.chown(marker, 0, pwd.getpwnam('usenet').pw_gid)
        command('systemctl', 'daemon-reload')
        command('systemd-analyze', 'verify', '/etc/systemd/system/' + MOUNT_UNIT,
                '/etc/systemd/system/' + BIND_UNIT, '/etc/systemd/system/' + SAB_UNIT)
        command('systemctl', 'start', BIND_UNIT)
        require(source.samefile(destination), 'new_spool_binding_not_verified')
        value['phase'] = 'bound'
        save_receipt(receipt, value)
        command('systemctl', 'start', SAB_UNIT)
        finish_bound(root, sab, value, receipt)
    restore_timers(value)
    return {'status': 'verified', 'original_preserved': True,
            'verified_files': len(value['source_inventory']),
            'verified_bytes': sum(v['size'] for v in value['source_inventory'].values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'migrate', 'resume-quiesce', 'resume-bound', 'inspect'))
    parser.add_argument('--volume-id', type=int, required=True)
    parser.add_argument('--controller-source', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        require(args.volume_id > 0 and os.geteuid() == 0, 'root_and_provider_identity_required')
        result = (prepare(ROOT, args.volume_id) if args.action == 'prepare' else
                  inspect(ROOT, args.volume_id) if args.action == 'inspect' else
                  resume_bound(ROOT, args.volume_id) if args.action == 'resume-bound' else
                  migrate(ROOT, args.volume_id, args.controller_source, args.action == 'resume-quiesce'))
        print(json.dumps(result))
    except Exception as error:
        # No raw command output, media identifiers or secrets leave this boundary.
        print(json.dumps({'status': 'blocked', 'reason': str(error) if type(error) is RuntimeError
                          else 'repair_spool_phase_requires_review', 'error_type': type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
