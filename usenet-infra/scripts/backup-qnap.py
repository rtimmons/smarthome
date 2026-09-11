#!/usr/bin/env python3
"""Manual encrypted QNAP configuration capture and isolated verified restore.

Capture reads the existing application root from a temporary, network-disabled
container. Plaintext stays in memory and the pinned SSH stream into local age;
only ciphertext is written locally. No service is restarted or reconfigured.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

AGE_VERSION = '1.3.2'
IMAGE = 'usenet-catalog-tools:rclone-1.75.1-python-3.14.7'
MAX_BYTES = 128 * 1024**2
MAX_FILES = 25_000
MAX_TAR_BYTES = MAX_BYTES + 32 * 1024**2
TREES = ('compose/qnap', 'scripts', 'config/catalog', 'config/backup', 'state/items',
         'state/failures', 'state/operations', 'state/dashboard')
SINGLES = ('secrets/dashboard-auth.json', 'secrets/storagebox/id_ed25519',
           'secrets/storagebox/known_hosts')
REQUIRED = ('compose/qnap/compose.yaml', 'compose/qnap/.env', 'compose/qnap/Dockerfile.catalog',
            'compose/qnap/Dockerfile.dashboard', 'compose/qnap/catalog-run',
            'compose/qnap/olivetin/config.yaml', 'scripts/catalogctl.py',
            'scripts/catalog-dashboard.py', 'scripts/healthcheck.py',
            'state/dashboard/runtime/config.yaml', 'state/dashboard/status.json',
            'state/dashboard/catalog.json', *SINGLES)
LOCKS = ('state/locks/cache.lock', 'state/dashboard/refresh.lock')


class BackupError(RuntimeError):
    """Only fixed, nonsecret errors cross the command boundary."""


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and str(path) == name
            and '..' not in path.parts and '\\' not in name and '\x00' not in name)


def allowed(name: str) -> bool:
    if not safe_name(name):
        return False
    parts = PurePosixPath(name).parts
    if (any(part in {'docker-client', '__pycache__', 'cache', '.staging'} for part in parts)
            or any(part.startswith('.') for part in parts) and name != 'compose/qnap/.env'
            or name.endswith(('.lock', '.pyc', '.ansible'))):
        return False
    return name in SINGLES or any(name.startswith(tree + '/') for tree in TREES)


def fingerprint(info) -> tuple:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def secure_open(root: Path, name: str):
    if not safe_name(name):
        raise BackupError('Unsafe configuration path refused.')
    with ExitStack() as stack:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        parts = PurePosixPath(name).parts
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, fd)
        result = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(result).st_mode):
            os.close(result)
            raise BackupError('Links and special configuration files are refused.')
        return os.fdopen(result, 'rb')


def inventory(root: Path) -> dict[str, os.stat_result]:
    result = {}
    for tree in TREES:
        base = root / tree
        if not base.exists():
            if base.is_symlink():
                raise BackupError('Configuration directory links are refused.')
            continue
        for parent in (base, *base.parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise BackupError('Configuration directory links are refused.')
        if not base.is_dir():
            raise BackupError('Configuration directory is invalid.')
        for directory, folders, files in os.walk(base, followlinks=False):
            for folder in folders:
                if (Path(directory) / folder).is_symlink():
                    raise BackupError('Configuration directory links are refused.')
            folders[:] = [folder for folder in folders if folder not in {'docker-client', '__pycache__', 'cache', '.staging'} and not folder.startswith('.')]
            for filename in files:
                path = Path(directory) / filename
                name = path.relative_to(root).as_posix()
                if allowed(name):
                    with secure_open(root, name) as source:
                        result[name] = os.fstat(source.fileno())
    for name in SINGLES:
        with secure_open(root, name) as source:
            result[name] = os.fstat(source.fileno())
    if not set(REQUIRED) <= result.keys():
        raise BackupError('Required QNAP configuration is missing; backup refused.')
    if len(result) > MAX_FILES or sum(info.st_size for info in result.values()) > MAX_BYTES:
        raise BackupError('QNAP configuration exceeds the 128 MiB or file-count limit.')
    return dict(sorted(result.items()))


def validate_layout(content: bytes, host_root: str) -> None:
    values = {}
    for line in content.decode().splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise BackupError('QNAP environment layout is invalid.')
        values[key] = json.loads(value) if value.startswith('"') else value
    expected = {
        'QNAP_CATALOG_STATE_DIR': '/state', 'QNAP_CATALOG_SCRIPTS_DIR': '/scripts',
        'QNAP_DASHBOARD_CONFIG_DIR': '/compose/qnap/olivetin',
        'QNAP_DASHBOARD_STATE_DIR': '/state/dashboard',
        'QNAP_DASHBOARD_AUTH_FILE': '/secrets/dashboard-auth.json',
        'QNAP_STORAGEBOX_KEY_FILE': '/secrets/storagebox/id_ed25519',
        'QNAP_STORAGEBOX_KNOWN_HOSTS_FILE': '/secrets/storagebox/known_hosts',
    }
    if any(values.get(key) != host_root + suffix for key, suffix in expected.items()):
        raise BackupError('Custom QNAP paths require a reviewed backup mapping.')
    cache = PurePosixPath(values.get('QNAP_CATALOG_CACHE_DIR', ''))
    if not cache.is_absolute() or '..' in cache.parts or cache.is_relative_to(PurePosixPath(host_root)):
        raise BackupError('The media cache must be outside the backed-up application root.')


def snapshot(root: Path, host_root: str, after_copy=None) -> tuple[dict, dict[str, bytes]]:
    with ExitStack() as stack:
        locked = {}
        for name in LOCKS:
            try:
                stream = stack.enter_context(secure_open(root, name))
            except FileNotFoundError:
                continue
            try:
                # Linux flock permits shared locks on read-only descriptors.
                # Never create/truncate lock files through the read-only bind.
                fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BackupError('A catalog operation or refresh is active; retry when idle.') from None
            locked[name] = fingerprint(os.fstat(stream.fileno()))
        before = inventory(root)
        contents, entries = {}, []
        total = 0
        for name, info in before.items():
            with secure_open(root, name) as source:
                if fingerprint(os.fstat(source.fileno())) != fingerprint(info):
                    raise BackupError('Configuration changed during capture; retry when idle.')
                content = source.read(MAX_BYTES - total + 1)
                total += len(content)
                if total > MAX_BYTES or fingerprint(os.fstat(source.fileno())) != fingerprint(info):
                    raise BackupError('Configuration changed or exceeded the capture limit.')
            if content.startswith(b'SQLite format 3\x00'):
                raise BackupError('Unexpected QNAP database requires a reviewed snapshot strategy.')
            contents[name] = content
            entries.append({'path': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                            'source_mode': stat.S_IMODE(info.st_mode), 'source_uid': info.st_uid, 'source_gid': info.st_gid})
        validate_layout(contents['compose/qnap/.env'], host_root)
        if after_copy:
            after_copy()
        after = inventory(root)
        if before.keys() != after.keys() or any(fingerprint(before[name]) != fingerprint(after[name]) for name in before):
            raise BackupError('Configuration or execution history changed during capture; retry when idle.')
        for entry in entries:
            with secure_open(root, entry['path']) as source:
                value = hashlib.sha256()
                size = 0
                while block := source.read(1024 * 1024):
                    size += len(block)
                    if size > entry['size']:
                        raise BackupError('Execution history changed during capture; retry when idle.')
                    value.update(block)
                if size != entry['size'] or value.hexdigest() != entry['sha256']:
                    raise BackupError('Execution history changed during capture; retry when idle.')
        for name in LOCKS:
            if name not in locked:
                if (root / name).exists():
                    raise BackupError('Catalog activity began during capture; retry when idle.')
            else:
                with secure_open(root, name) as stream:
                    if fingerprint(os.fstat(stream.fileno())) != locked[name]:
                        raise BackupError('Catalog locks changed during capture; retry when idle.')
        return {'schema_version': 1, 'scope': 'qnap-config', 'created_at': int(time.time()),
                'age_version': AGE_VERSION, 'source_root': host_root,
                'consistency': 'existing shared locks plus repeated inventory and content checks',
                'cache_content_included': False, 'entries': entries}, contents


def write_tar(manifest: dict, contents: dict[str, bytes], output) -> None:
    with tarfile.open(fileobj=output, mode='w|', format=tarfile.PAX_FORMAT) as archive:
        values = [('MANIFEST.json', json.dumps(manifest, sort_keys=True).encode()),
                  *(('payload/' + entry['path'], contents[entry['path']]) for entry in manifest['entries'])]
        for name, content in values:
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(content), 0o600
            archive.addfile(member, io.BytesIO(content))


def verify_tar(content: bytes, destination: Path | None = None) -> dict:
    if len(content) > MAX_TAR_BYTES:
        raise BackupError('Decrypted backup exceeds the bounded archive limit.')
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:') as archive:
        members = []
        for member in archive:
            members.append(member)
            if len(members) > MAX_FILES + 1:
                raise BackupError('Archive exceeds the file-count limit.')
        names = [member.name for member in members]
        if (len(names) > MAX_FILES + 1 or len(names) != len(set(names)) or names.count('MANIFEST.json') != 1
                or any(not member.isfile() or member.issparse() or not safe_name(member.name) for member in members)
                or sum(member.size for member in members) > MAX_TAR_BYTES):
            raise BackupError('Archive contains invalid, duplicate, oversized or unsafe members.')
        inventory_member = archive.getmember('MANIFEST.json')
        if inventory_member.size > 16 * 1024**2:
            raise BackupError('Archive inventory exceeds its limit.')
        manifest = json.load(archive.extractfile(inventory_member))
        if manifest.get('schema_version') != 1 or manifest.get('scope') != 'qnap-config':
            raise BackupError('Unsupported QNAP configuration archive schema.')
        entries = manifest['entries']
        paths = [entry['path'] for entry in entries]
        if (len(paths) != len(set(paths)) or not set(REQUIRED) <= set(paths)
                or any(not allowed(name) for name in paths)
                or set(names) != {'MANIFEST.json', *('payload/' + name for name in paths)}):
            raise BackupError('Archive does not match its allowlisted inventory.')
        for entry in entries:
            member = archive.getmember('payload/' + entry['path'])
            if member.size != entry['size']:
                raise BackupError('Archive size does not match the inventory.')
            if hashlib.sha256(archive.extractfile(member).read()).hexdigest() != entry['sha256']:
                raise BackupError('Archive checksum verification failed.')
        if destination is not None:
            if not destination.is_absolute() or destination.exists() or destination.is_symlink():
                raise BackupError('Restore requires a new absolute destination; existing files are never replaced.')
            # Only an explicitly requested isolated restore writes plaintext.
            # Publish after all members/checksums pass; never restore directly to NAS.
            with tempfile.TemporaryDirectory(prefix='.qnap-restore-', dir=destination.parent) as temporary:
                staged = Path(temporary) / 'restored'
                staged.mkdir(mode=0o700)
                for entry in entries:
                    target = staged / entry['path']
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile('payload/' + entry['path']).read())
                    target.chmod(0o600)
                (staged / 'MANIFEST.json').write_text(json.dumps(manifest, sort_keys=True))
                (staged / 'MANIFEST.json').chmod(0o600)
                destination.mkdir(mode=0o700)
                try:
                    os.rename(staged, destination)
                except BaseException:
                    destination.rmdir()
                    raise
        return manifest


def private_file(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_mode & 0o077:
        raise BackupError('The identity and encrypted archive must be ordinary private files.')


def age_binary() -> Path:
    names = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}
    target = names.get((platform.system(), platform.machine()))
    if target is None:
        raise BackupError('No reviewed age binary exists for this controller platform.')
    return Path(__file__).resolve().parents[2] / 'build/tools/age-1.3.2' / target / 'age'


def check_age(age: Path) -> None:
    result = subprocess.run([str(age), '--version'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=10)
    if result.stdout.decode().strip().removeprefix('v') != AGE_VERSION:
        raise BackupError('The reviewed age 1.3.2 binary is required.')


def stop_group(process) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def decrypt_verify(archive: Path, identity: Path, age: Path, destination: Path | None = None) -> dict:
    private_file(identity)
    private_file(archive)
    with subprocess.Popen([str(age), '--decrypt', '--identity', str(identity), str(archive)],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True) as process:
        timer = threading.Timer(120, stop_group, (process,))
        timer.start()
        try:
            plaintext = process.stdout.read(MAX_TAR_BYTES + 1)
            if len(plaintext) > MAX_TAR_BYTES:
                raise BackupError('Decrypted backup exceeds the bounded archive limit.')
            if process.wait(timeout=10):
                raise BackupError('Backup decryption or authentication failed.')
            # age must authenticate the entire ciphertext before parsing any tar.
            return verify_tar(plaintext, destination)
        finally:
            timer.cancel()
            stop_group(process)


def connection(environment: dict) -> tuple[list[str], Path]:
    values = {key: environment.get(key, '') for key in ('QNAP_SSH_TARGET', 'QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS', 'QNAP_PROJECT_DIR')}
    if (not all(values.values()) or not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9][A-Za-z0-9.-]*', values['QNAP_SSH_TARGET'])):
        raise BackupError('Dedicated pinned QNAP connection settings are required.')
    identity, known_hosts = Path(values['QNAP_SSH_KEY']).expanduser(), Path(values['QNAP_SSH_KNOWN_HOSTS']).expanduser()
    private_file(identity)
    if not known_hosts.is_file() or known_hosts.is_symlink():
        raise BackupError('The dedicated QNAP host-key pin is missing.')
    project = PurePosixPath(values['QNAP_PROJECT_DIR'])
    if (not project.is_absolute() or str(project) != values['QNAP_PROJECT_DIR'] or '..' in project.parts
            or project.parts[1:2] != ('share',) or project.parts[-2:] != ('compose', 'qnap')
            or len(project.parts) < 6 or any(character in str(project) for character in ',\n\r\x00')):
        raise BackupError('QNAP backup requires the reviewed application/compose/qnap layout.')
    host_root = str(project.parent.parent)
    docker_config = environment.get('QNAP_DOCKER_CONFIG_DIR', host_root + '/state/docker-client')
    if docker_config != host_root + '/state/docker-client':
        raise BackupError('Custom Docker client paths require a reviewed backup mapping.')
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'IdentityAgent=none', '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
               '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-i', str(identity),
               '-o', 'UserKnownHostsFile=' + str(known_hosts), '--', values['QNAP_SSH_TARGET']]
    discovery = '''set -eu
qnap_docker=$(command -v docker 2>/dev/null || true)
case "$qnap_docker" in /*) ;; *) qnap_docker= ;; esac
if test ! -x "$qnap_docker" && test -x /sbin/getcfg; then
  qnap_package=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf 2>/dev/null)
  case "$qnap_package" in /share/*)
    for candidate in "$qnap_package/bin/docker" "$qnap_package/usr/bin/docker"; do
      if test -x "$candidate"; then qnap_docker=$candidate; break; fi
    done;;
  esac
fi
test -x "$qnap_docker"
'''
    mount = 'type=bind,src=' + host_root + ',dst=/source,readonly'
    remote = discovery + ('exec "$qnap_docker" --config ' + shlex.quote(docker_config)
        + ' run --rm --pull=never --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges'
        + ' --memory=512m --cpus=0.5 --pids-limit=64 --user "$(id -u):$(id -g)"'
        + ' --env PYTHONDONTWRITEBYTECODE=1 --mount ' + shlex.quote(mount)
        + ' --entrypoint python3 -i ' + shlex.quote(IMAGE) + ' - remote-capture --host-root ' + shlex.quote(host_root))
    return [*command, remote], identity


def capture(environment: dict, age: Path, output_dir: Path) -> tuple[Path, dict]:
    command, identity = connection(environment)
    recipient = Path(str(identity) + '.pub')
    lines = recipient.read_text().splitlines()
    if len(lines) != 1 or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: .*)?', lines[0]):
        raise BackupError('The existing dedicated QNAP Ed25519 public recipient is required.')
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output_dir.is_symlink() or output_dir.stat().st_mode & 0o077:
        raise BackupError('The backup directory must be private with mode 0700.')
    with tempfile.TemporaryDirectory(prefix='.qnap-capture-', dir=output_dir) as temporary:
        work = Path(temporary)
        encrypted = work / 'archive.age'
        with subprocess.Popen([str(age), '--encrypt', '--recipients-file', str(recipient), '--output', str(encrypted)],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True) as encryption:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=encryption.stdin, stderr=subprocess.DEVNULL,
                                  start_new_session=True) as remote:
                encryption.stdin.close()
                timer = threading.Timer(180, stop_group, (remote,))
                timer.start()
                try:
                    remote.communicate(Path(__file__).read_bytes(), timeout=190)
                    if remote.returncode:
                        raise BackupError('QNAP capture failed or was busy; no archive was published.')
                    if encryption.wait(timeout=30):
                        raise BackupError('Backup encryption failed; no archive was published.')
                finally:
                    timer.cancel()
                    stop_group(remote)
                    stop_group(encryption)
        encrypted.chmod(0o600)
        manifest = decrypt_verify(encrypted, identity, age)
        name = 'qnap-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + work.name.rsplit('-', 1)[-1] + '.tar.age'
        output = output_dir / name
        os.link(encrypted, output)
        return output, manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('capture')
    for operation in ('verify', 'restore'):
        sub = commands.add_parser(operation)
        sub.add_argument('--archive', type=Path, required=True)
        sub.add_argument('--identity-file', type=Path)
        if operation == 'restore':
            sub.add_argument('--destination', type=Path, required=True)
    remote = commands.add_parser('remote-capture', help=argparse.SUPPRESS)
    remote.add_argument('--host-root', required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.operation == 'remote-capture':
            # The container exits independently of the SSH client, even if the
            # connection disappears while reading a slow filesystem.
            signal.alarm(150)
            manifest, contents = snapshot(Path('/source'), args.host_root)
            write_tar(manifest, contents, sys.stdout.buffer)
            signal.alarm(0)
            return 0
        age = age_binary()
        check_age(age)
        if args.operation == 'capture':
            archive, manifest = capture(os.environ, age, Path(__file__).resolve().parents[1] / 'backups')
        else:
            archive = args.archive
            identity = args.identity_file or Path(os.environ.get('QNAP_SSH_KEY', ''))
            manifest = decrypt_verify(archive, identity, age, getattr(args, 'destination', None))
        print(json.dumps({'status': 'captured' if args.operation == 'capture' else 'verified',
                          'scope': 'qnap-config', 'files': len(manifest['entries']),
                          'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                          'cache_content_included': False, 'archive': str(archive)}))
        return 0
    except BackupError as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({'error': 'QNAP backup failed; no raw error or secret was displayed.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
