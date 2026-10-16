#!/usr/bin/env python3
"""Build, idle-deploy or roll back the pinned SAB copy image. Redacted output only."""
import argparse
from contextlib import ExitStack
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

BASE = 'lscr.io/linuxserver/sabnzbd@sha256:7f173ced3541b46c57c4eb6854765243095c8c8a7563a878044fa0ccfb1f4004'
ORIGINAL_TAG = 'lscr.io/linuxserver/sabnzbd:5.1.3-ls272'
TAG = 'smarthome/sabnzbd:5.1.3-buffered-v1'
ROOT = Path('/srv/usenet')
PROJECT = ROOT / 'compose/cloud'
CONTEXT = PROJECT / 'sab-buffered'
STATE = ROOT / 'state/catalog/sab-buffered.json'
CANDIDATE = ROOT / 'state/catalog/sab-buffered-candidate.json'
SAB_UNIT = 'usenet-sab-remote.service'
ARR_UNIT = 'usenet-discovery.service'


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def run(*args, timeout=60, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('command_failed_' + args[0].split('/')[-1])
    return result.stdout if check else result


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o640)
    if os.geteuid() == 0:
        os.chown(temporary, 0, 1991)  # Existing settings backup runs as usenet.
    os.replace(temporary, path)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def image_info(reference):
    return json.loads(run('docker', 'image', 'inspect', reference))[0]


def live():
    ids = run('docker', 'ps', '--filter', 'label=com.docker.compose.service=sabnzbd', '--format', '{{.ID}}').split()
    require(len(ids) == 1, 'sab_container_not_unique')
    return json.loads(run('docker', 'inspect', ids[0]))[0]


def active(unit):
    return run('systemctl', 'show', unit, '--property=ActiveState', '--value').strip() == 'active'


def idle(sab, api, *, include_arr=True):
    queue = sab.api('queue', start=0, limit=1000)['queue']
    history = sab.api('history', start=0, limit=1, archive=0)['history']
    require(int(history['ppslots']) == 0 and not queue['slots'] and not float(queue['kbpersec']),
            'sab_busy_retry_when_idle')
    require(queue['status'] in ('Idle', 'Paused') and type(queue['paused']) is bool,
            'sab_idle_state_unknown')
    if include_arr:
        for app in ('radarr', 'sonarr'):
            require(not any(c.get('status') in ('started', 'queued') for c in api.call(app, 'command')),
                    'arr_busy_retry_when_idle')
    require(run('systemctl', 'show', 'usenet-backup.service', '--property=ActiveState', '--value').strip()
            in ('inactive', 'failed'), 'backup_busy_retry_when_idle')
    for path, reserve in ((ROOT / 'library', 34), (ROOT / 'repair', 30), (ROOT, 30)):
        require(shutil.disk_usage(path).free >= reserve * 1024 ** 3, 'free_space_reserve_failed')
    for path in ('library', 'repair', 'downloads/incomplete', 'downloads/complete/remote'):
        require(run('mountpoint', '-q', str(ROOT / path), check=False).returncode == 0, 'required_mount_missing')
    require(run('findmnt', '-n', '-o', 'FSTYPE', '--target', str(ROOT / 'library')).strip() == 'fuse.sshfs',
            'library_mount_type_changed')
    return queue['paused']


def config_fingerprint(sab, *, captured=None):
    # No secrets or media fields are persisted: hash the complete config in memory.
    value = sab.api('get_config')['config']
    # SAB 5.1.3 returns a boolean after setting this option through the API and
    # integer 0/1 after reading the same saved value on startup. Only normalize
    # this verified representation difference; policy changes still change hash.
    for field in ('pause_on_post_processing', 'start_paused'):
        pause = value['misc'][field]
        require(type(pause) in (bool, int) and pause in (0, 1), 'sab_pause_policy_type_changed')
        value['misc'][field] = bool(pause)
    if captured is not None:
        captured.update(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def config_differences(before, after, path=()):
    """Report only positions/types; never configuration values or dynamic keys."""
    if type(before) is type(after) and isinstance(before, dict) and before.keys() == after.keys():
        return [change for index, key in enumerate(sorted(before))
                for change in config_differences(before[key], after[key], path + (index,))]
    if type(before) is type(after) and isinstance(before, list) and len(before) == len(after):
        return [change for index, (left, right) in enumerate(zip(before, after))
                for change in config_differences(left, right, path + (index,))]
    if type(before) is type(after) and before == after:
        return []
    return [{'position': list(path), 'before_type': type(before).__name__, 'after_type': type(after).__name__}]


def restore_maintenance_pause(sab, config_before):
    require(sab.api('resume').get('status') is True, 'maintenance_pause_restore_failed')
    misc = config_before['misc']
    if misc['preserve_paused_state']:
        # resume() restores only the in-memory flag. SAB's supported setting
        # API persists that same original value, undoing our maintenance pause
        # on disk as well. No acquisition setting is changed.
        expected = int(misc['start_paused'])
        result = sab.api('set_config', section='misc', keyword='start_paused', value=expected)
        require(result.get('config', {}).get('misc', {}).get('start_paused') == expected,
                'maintenance_pause_save_failed')


def build():
    require(shutil.disk_usage(ROOT).free > 34 * 1024 ** 3, 'build_free_space_insufficient')
    run('docker', 'build', '--network=none', '--pull=false', '-t', TAG, str(CONTEXT), timeout=300)
    candidate = image_info(TAG)['Id']
    name = 'sab-buffered-test-' + str(os.getpid())
    try:
        run('docker', 'run', '--name', name, '--network=none', '--read-only', '--user', '1991:1991',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=256m',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m,uid=1991,gid=1991,mode=0700',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python3', candidate,
            '/opt/sab-buffered/integration_test.py', timeout=90)
        info = json.loads(run('docker', 'inspect', name))[0]
        require(info['Image'] == candidate and info['State']['ExitCode'] == 0, 'candidate_tests_failed')
    finally:
        # Only this exact test name and candidate image are eligible for removal.
        found = run('docker', 'inspect', name, check=False)
        if found.returncode == 0:
            info = json.loads(found.stdout)[0]
            require(info['Image'] == candidate and not any(m['Type'] == 'bind' for m in info['Mounts']),
                    'test_cleanup_identity_failed')
            run('docker', 'rm', '-f', info['Id'])
    value = {'image_id': candidate, 'tag': TAG, 'tested_at': time.time(),
             'context': {p.name: digest(p) for p in CONTEXT.iterdir() if p.is_file()},
             'compose_sha256': digest(PROJECT / 'compose.buffered.yaml')}
    save(CANDIDATE, value)
    return {'status': 'candidate_tested', 'image_id': candidate}


def compose_document(path, overrides=()):
    args = ['docker', 'compose', '--project-directory', str(PROJECT), '--env-file', str(PROJECT / '.env')]
    for source in (path, *overrides):
        args += ['-f', str(source)]
    return json.loads(run(*args, 'config', '--format', 'json'))


def check_override_change(before, after):
    # The reviewed live override only disables SAB's Docker restart policy;
    # mount-dependent systemd startup must retain ownership of its lifecycle.
    before['services']['sabnzbd']['restart'] = 'no'
    require(before == after, 'compose_override_requires_review')


def reviewed_overrides():
    paths = [PROJECT / name for name in
             ('compose.override.yaml', 'compose.override.yml', 'docker-compose.override.yaml', 'docker-compose.override.yml')
             if (PROJECT / name).exists() or (PROJECT / name).is_symlink()]
    if paths:
        require(len(paths) == 1 and paths[0].name == 'compose.override.yaml'
                and paths[0].is_file() and not paths[0].is_symlink(), 'compose_override_requires_review')
        check_override_change(compose_document(PROJECT / 'compose.yaml'),
                              compose_document(PROJECT / 'compose.yaml', paths))
    return paths


def check_compose_change(before, after):
    require(set(before['services']) == set(after['services']), 'compose_services_changed')
    require(before['services']['sabnzbd']['image'] == ORIGINAL_TAG, 'original_image_reference_changed')
    require(after['services']['sabnzbd']['image'] == TAG, 'candidate_image_reference_invalid')
    require(after['services']['sabnzbd'].get('pull_policy') == 'never', 'candidate_pull_policy_invalid')
    for document in (before, after):
        document['services']['sabnzbd'].pop('image', None)
        document['services']['sabnzbd'].pop('healthcheck', None)
        document['services']['sabnzbd'].pop('pull_policy', None)
    require(before == after, 'unrelated_compose_change_refused')


def healthy_image(expected, *, buffered):
    info = live()
    require(info['Image'] == expected and info['State']['Health']['Status'] == 'healthy', 'sab_image_not_healthy')
    if buffered:
        run('docker', 'exec', info['Id'], 'python3', '/opt/sab-buffered/verify.py')


def restart_services(arr_active):
    run('systemctl', 'start', SAB_UNIT, timeout=260)
    if arr_active:
        run('systemctl', 'start', ARR_UNIT, timeout=260)


def deploy():
    candidate = json.loads(CANDIDATE.read_text())
    require(candidate['context'] == {p.name: digest(p) for p in CONTEXT.iterdir() if p.is_file()},
            'candidate_sources_changed_rebuild_required')
    require(candidate['compose_sha256'] == digest(PROJECT / 'compose.buffered.yaml'), 'candidate_compose_changed')
    require(image_info(TAG)['Id'] == candidate['image_id'], 'candidate_image_changed')
    current = live()
    if current['Image'] == candidate['image_id'] and STATE.exists():
        healthy_image(candidate['image_id'], buffered=True)
        return {'status': 'already_deployed', 'image_id': candidate['image_id']}
    require(not STATE.exists() or json.loads(STATE.read_text())['status'] in ('rolled_back', 'aborted'),
            'existing_deployment_requires_review')
    require(current['Image'] == image_info(BASE)['Id'], 'current_image_not_reviewed_base')
    overrides = reviewed_overrides()
    override_hashes = {p.name: digest(p) for p in overrides}
    check_compose_change(compose_document(PROJECT / 'compose.yaml', overrides),
                         compose_document(PROJECT / 'compose.buffered.yaml', overrides))
    sab, api = module('cart_import_sab').SabSource(), module('discovery-config').API()
    paused = idle(sab, api)
    backup = json.loads((ROOT / 'backups/scheduled/cloud-status.json').read_text())
    require(backup['status'] == 'ok' and 0 <= time.time() - backup['last_success'] < 36 * 3600
            and all(a.get('remote_ciphertext_verified') for a in backup['archives']) and bool(backup['archives']),
            'verified_recent_backup_required')
    config_before = {}
    fingerprint = config_fingerprint(sab, captured=config_before)
    config_file_hash = digest(ROOT / 'config/sabnzbd/sabnzbd.ini')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    keep = ROOT / 'images/sab-buffered' / stamp
    keep.mkdir(parents=True, mode=0o700)
    keep.chmod(0o700)
    shutil.copyfile(PROJECT / 'compose.yaml', keep / 'compose.yaml')
    old_tag = 'smarthome/sabnzbd:rollback-' + stamp.lower()
    run('docker', 'tag', current['Image'], old_tag)
    run('docker', 'image', 'save', '--output', str(keep / 'image.tar'), old_tag, timeout=300)
    value = {'status': 'prepared', 'created_at': time.time(), 'old_image_id': current['Image'],
             'old_image_tag': old_tag, 'image_archive': str(keep / 'image.tar'),
             'image_archive_sha256': digest(keep / 'image.tar'), 'compose_backup': str(keep / 'compose.yaml'),
             'old_compose_sha256': digest(keep / 'compose.yaml'), 'new_image_id': candidate['image_id'],
             'paused_before': paused, 'arr_active_before': active(ARR_UNIT),
             'preserved_override_sha256': override_hashes,
             'config_fingerprint': fingerprint, 'verification': 'awaiting_next_real_download'}
    value['config_file_sha256'] = config_file_hash
    require(idle(sab, api) == paused, 'manual_pause_changed_during_preparation')
    require(override_hashes == {p.name: digest(p) for p in reviewed_overrides()}, 'compose_override_changed')
    save(STATE, value)
    stopped = False
    pause_owned = False
    try:
        # Stop idle import owners first, preventing a new request during maintenance.
        if value['arr_active_before']:
            run('systemctl', 'stop', ARR_UNIT, timeout=120)
        if not paused:
            require(sab.api('pause').get('status') is True, 'maintenance_pause_failed')
            pause_owned = True
        idle(sab, api, include_arr=False)
        stopped = True
        run('systemctl', 'stop', SAB_UNIT, timeout=120)
        shutil.copyfile(PROJECT / 'compose.buffered.yaml', PROJECT / 'compose.next.yaml')
        os.chown(PROJECT / 'compose.next.yaml', 1991, 1991)
        (PROJECT / 'compose.next.yaml').chmod(0o640)
        os.replace(PROJECT / 'compose.next.yaml', PROJECT / 'compose.yaml')
        value['activated_at'] = time.time()
        run('systemctl', 'start', SAB_UNIT, timeout=260)
        healthy_image(candidate['image_id'], buffered=True)
        # SAB persists its paused state in misc.start_paused. Restore only our
        # own maintenance pause before comparing configuration, keeping Arr
        # stopped so it cannot submit new work during these checks.
        if pause_owned:
            restore_maintenance_pause(sab, config_before)
            pause_owned = False
        config_after = {}
        if config_fingerprint(sab, captured=config_after) != fingerprint:
            value['configuration_difference_positions'] = config_differences(config_before, config_after)
            raise RuntimeError('sab_configuration_changed')
        require(digest(ROOT / 'config/sabnzbd/sabnzbd.ini') == config_file_hash, 'sab_saved_configuration_changed')
        if value['arr_active_before']:
            run('systemctl', 'start', ARR_UNIT, timeout=260)
        run('python3', str(ROOT / 'libexec/native-cutover.py'), 'inspect')
        value.update(status='deployed', deployed_at=time.time())
        save(STATE, value)
    except Exception:
        try:
            if stopped:
                run('systemctl', 'stop', ARR_UNIT, timeout=120)
                run('systemctl', 'stop', SAB_UNIT, timeout=120)
                run('docker', 'tag', current['Image'], ORIGINAL_TAG)
                shutil.copyfile(keep / 'compose.yaml', PROJECT / 'compose.yaml')
                restart_services(value['arr_active_before'])
                healthy_image(current['Image'], buffered=False)
            elif value['arr_active_before']:
                run('systemctl', 'start', ARR_UNIT, timeout=260)
            value['status'] = 'rolled_back' if stopped else 'aborted'
        except Exception:
            value['status'] = 'rollback_failed_requires_review'
            raise
        finally:
            save(STATE, value)
        raise
    finally:
        if pause_owned:
            restore_maintenance_pause(sab, config_before)
        require(sab.api('queue')['queue']['paused'] == paused, 'manual_pause_state_changed')
        save(STATE, value)
    return {'status': value['status'], 'image_id': candidate['image_id'], 'rollback_image_retained': True,
            'verification': value['verification']}


def rollback():
    value = json.loads(STATE.read_text())
    require(value['status'] == 'deployed', 'no_deployed_candidate_to_rollback')
    sab, api = module('cart_import_sab').SabSource(), module('discovery-config').API()
    paused = idle(sab, api)
    config_before = {}
    config_fingerprint(sab, captured=config_before)
    require(live()['Image'] == value['new_image_id'], 'running_image_changed')
    require(value.get('preserved_override_sha256', {}) == {p.name: digest(p) for p in reviewed_overrides()},
            'compose_override_changed')
    backup = Path(value['compose_backup'])
    require(digest(backup) == value['old_compose_sha256'], 'rollback_compose_changed')
    if run('docker', 'image', 'inspect', value['old_image_id'], check=False).returncode:
        archive = Path(value['image_archive'])
        require(digest(archive) == value['image_archive_sha256'], 'rollback_archive_changed')
        run('docker', 'image', 'load', '--input', str(archive), timeout=300)
    require(image_info(value['old_image_tag'])['Id'] == value['old_image_id'], 'rollback_image_changed')
    # Loading a saved image may restore only our rollback tag. Restore the exact
    # original Compose reference locally so rollback never fetches another image.
    run('docker', 'tag', value['old_image_id'], ORIGINAL_TAG)
    arr_active = active(ARR_UNIT)
    pause_owned = False
    try:
        if arr_active:
            run('systemctl', 'stop', ARR_UNIT, timeout=120)
        if not paused:
            require(sab.api('pause').get('status') is True, 'maintenance_pause_failed')
            pause_owned = True
        idle(sab, api, include_arr=False)
        run('systemctl', 'stop', SAB_UNIT, timeout=120)
        shutil.copyfile(backup, PROJECT / 'compose.yaml')
        restart_services(arr_active)
        healthy_image(value['old_image_id'], buffered=False)
        value.update(status='rolled_back', rolled_back_at=time.time())
        save(STATE, value)
    finally:
        if pause_owned:
            restore_maintenance_pause(sab, config_before)
        if arr_active and not active(ARR_UNIT):
            run('systemctl', 'start', ARR_UNIT, timeout=260)
        require(sab.api('queue')['queue']['paused'] == paused, 'manual_pause_state_changed')
    return {'status': 'rolled_back', 'image_id': value['old_image_id']}


def status():
    if not STATE.exists():
        return {'status': 'not_deployed'}
    value = json.loads(STATE.read_text())
    return {key: value[key] for key in ('status', 'verification', 'deployed_at', 'new_image_id') if key in value}


def library_path(value, app):
    """Translate only existing native library mappings; never arbitrary host paths."""
    path = Path(value)
    if path.is_relative_to('/library'):
        result = ROOT / 'library' / ('Movies' if app == 'radarr' else 'TV') / path.relative_to('/library')
    elif path.is_relative_to('/storage'):
        result = ROOT / 'library' / path.relative_to('/storage')
    else:
        raise RuntimeError('import_path_mapping_unknown')
    require(result.resolve().is_relative_to(ROOT / 'library' / ('Movies' if app == 'radarr' else 'TV')),
            'import_path_outside_library')
    return result


def verify_import():
    value = json.loads(STATE.read_text())
    require(value['status'] == 'deployed', 'buffered_image_not_deployed')
    healthy_image(value['new_image_id'], buffered=True)
    if value['verification'] == 'verified':
        return {'status': 'verified', 'imported_files': value['imported_files']}
    sab, api = module('cart_import_sab').SabSource(), module('discovery-config').API()
    snapshot = sab.snapshot()
    if not value.get('next_job'):
        candidates = []
        for job in snapshot['queue'] + snapshot['history']:
            app = job.get('cat', job.get('category'))
            if app in ('radarr', 'sonarr') and job.get('time_added', 0) >= int(value['activated_at']):
                candidates.append({'id': job['nzo_id'], 'app': app, 'added_at': job['time_added']})
        if not candidates:
            return {'status': 'awaiting_next_real_download'}
        value['next_job'] = min(candidates, key=lambda j: (j['added_at'], j['id']))
        save(STATE, value)
    selected = value['next_job']
    job = next((j for j in snapshot['history'] if j['nzo_id'] == selected['id']), None)
    if not job:
        return {'status': 'download_or_processing_active'}
    if job['status'] == 'Failed':
        return {'status': 'real_download_failed_requires_review'}
    if job['status'] != 'Completed':
        return {'status': 'download_or_processing_active'}
    # Arr's downloadId is the stable SAB NZO ID, not a title-based match.
    records = []
    for page in range(1, 11):
        payload = api.call(selected['app'], f'history?page={page}&pageSize=100&sortKey=date&sortDirection=descending')
        entries = payload['records']
        records.extend(r for r in entries if r.get('downloadId') == selected['id']
                       and r.get('eventType') == 'downloadFolderImported')
        if page * 100 >= payload['totalRecords']:
            break
    if not records:
        return {'status': 'awaiting_native_import'}
    paths = set()
    for record in records:
        name = record.get('data', {}).get('importedPath')
        require(isinstance(name, str) and bool(name), 'imported_file_evidence_missing')
        path = library_path(name, selected['app'])
        require(path.is_file() and not path.is_symlink() and path.stat().st_size > 0,
                'imported_file_missing_or_empty')
        expected_size = record.get('data', {}).get('size')
        require(str(expected_size).isdigit() and path.stat().st_size == int(expected_size),
                'imported_file_size_mismatch')
        paths.add(path)
    if not job['archive']:
        return {'status': 'awaiting_native_source_cleanup', 'imported_files': len(paths)}
    storage = Path(job['storage'])
    require(storage != Path('/data/complete/remote/complete') and
            storage.is_relative_to('/data/complete/remote/complete'), 'completed_source_path_unknown')
    source = ROOT / 'library/.acquisition-staging/complete' / storage.relative_to('/data/complete/remote/complete')
    require(source.resolve().is_relative_to(ROOT / 'library/.acquisition-staging/complete'), 'source_path_escape')
    if source.exists():
        return {'status': 'awaiting_native_source_cleanup', 'imported_files': len(paths)}
    value.update(verification='verified', verified_at=time.time(), imported_files=len(paths),
                 import_event_ids=sorted({r['id'] for r in records}),
                 import_file_evidence=[{'path_sha256': hashlib.sha256(os.fsencode(p)).hexdigest(),
                                       'bytes': p.stat().st_size, 'device': p.stat().st_dev,
                                       'inode': p.stat().st_ino} for p in sorted(paths)],
                 sab_completed=True, sab_archived=True, completed_source_removed=True)
    save(STATE, value)
    return {'status': 'verified', 'imported_files': len(paths), 'source_cleanup_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'deploy', 'rollback', 'status', 'verify-import'))
    args = parser.parse_args()
    os.umask(0o077)
    with ExitStack() as stack:
        lock = stack.enter_context((ROOT / 'state/catalog/sab-buffered.lock').open('a'))
        os.fchmod(lock.fileno(), 0o640)
        if os.geteuid() == 0:
            os.fchown(lock.fileno(), 0, 1991)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action in ('deploy', 'rollback'):
            # The scheduler uses this same lock and quietly skips a busy attempt.
            backup_lock = stack.enter_context((ROOT / 'backups/scheduled/cloud.lock').open('a'))
            fcntl.flock(backup_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(globals()[args.action.replace('-', '_')]()))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        reason = str(error) if type(error) is RuntimeError else type(error).__name__
        print(json.dumps({'status': 'failed', 'reason': reason}), file=sys.stderr)
        sys.exit(1)
