#!/usr/bin/env python3
"""External workstation state and authenticated, exact-byte age recovery.

Only reviewed disposable caches are excluded. Private names/hashes stay in the
external manifest and encrypted archive, never in diagnostics or source control.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import sys
import subprocess
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home() / '.local/share/smarthome')).expanduser()
KEY = Path(os.environ.get('SMARTHOME_RECOVERY_KEY', Path.home() / '.config/smarthome/recovery.agekey')).expanduser()
CACHE_PARTS = {'node_modules', '.venv', '__pycache__', '.mypy_cache', '.ruff_cache', '.pytest_cache', '.terraform', '.collections'}
CACHE_PREFIXES = ('build/nvm/', 'build/wiki/venv/', 'build/wiki/uv-cache/',
                  'build/wiki/candidates/', 'build/unifi-mcp/venv/', 'build/unifi-mcp/uv-cache/',
                  'talos/build/', 'new-hass-configs/generated/',
                  'new-hass-configs/config-generator/dist/', 'sonos-api/dist/',
                  'snapshot-service/dist/', 'tinyurl-service/dist/')
GENERATED = {'build/wiki/model.json', 'new-hass-configs/scripts.yaml', 'new-hass-configs/scenes.yaml'}

class StateError(Exception): pass

def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise StateError('Unsafe external directory.')
    path.chmod(0o700)

def outside(path, repo=REPO):
    path = path.resolve()
    if path == repo.resolve() or repo.resolve() in path.parents:
        raise StateError('Durable state and the recovery master must be outside the checkout.')
    return path

def safe_name(value):
    p = PurePosixPath(value)
    if not value or p.as_posix() != value or p.is_absolute() or '..' in p.parts or '.' == value or p.parts[0] == '.git':
        raise StateError('Unsafe manifest path.')
    return value

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write_json(path, data):
    private_dir(path.parent)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def git_paths(*args):
    return {os.fsdecode(p) for p in subprocess.check_output(['git', '-C', str(REPO), 'ls-files', '-z', *args]).split(b'\0') if p}

def disposable(name):
    return bool(set(Path(name).parts) & CACHE_PARTS or name.startswith(CACHE_PREFIXES)
                or Path(name).name == '.DS_Store' or name in GENERATED)

def plan():
    ignored = git_paths('--others', '--ignored', '--exclude-standard')
    tracked = git_paths('--cached')
    selected = {p for p in ignored if not disposable(p)}
    # Select complete untracked directories where possible so future writes also
    # land outside the checkout. Never link over tracked source or excluded caches.
    blocked = tracked | (ignored - selected)
    blocked_dirs = {str(parent) for p in blocked for parent in Path(p).parents}
    roots = set()
    for name in sorted(selected):
        parts = Path(name).parts
        chosen = name
        for n in range(1, len(parts)):
            candidate = '/'.join(parts[:n])
            if candidate not in blocked and candidate not in blocked_dirs:
                chosen = candidate; break
        roots.add(chosen)
    roots = sorted(p for p in roots if not any(str(parent) in roots for parent in Path(p).parents))
    return roots

def records(tree, exclude_caches=False):
    result = {}
    for path in sorted(tree.rglob('*')):
        if exclude_caches and disposable(path.relative_to(tree).as_posix()): continue
        if path.is_symlink():
            result[path.relative_to(tree).as_posix()] = {'symlink':os.readlink(path)}
            continue
        if path.is_dir(): continue
        info = path.stat()
        if not stat.S_ISREG(info.st_mode): raise StateError('Special files cannot be archived.')
        result[path.relative_to(tree).as_posix()] = {'sha256': digest(path), 'mode': stat.S_IMODE(info.st_mode), 'bytes': info.st_size}
    return result

def age_tools():
    spec = importlib.util.spec_from_file_location('bootstrap_age', REPO / 'usenet-infra/scripts/bootstrap-age.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # A fresh-clone restore must not create build/ before prepare links it.
    # Reuse the reviewed bootstrap library in an independent external tool cache.
    cache = outside(Path(os.environ.get('SMARTHOME_CRYPTO_CACHE', Path.home() / '.cache/smarthome/crypto')))
    private_dir(cache)
    root = cache / ('age-' + module.VERSION)
    if not root.exists() and module.INSTALL_ROOT.is_dir():
        shutil.copytree(module.INSTALL_ROOT, root, symlinks=True)
    try:
        module.bootstrap(root=root)
    except module.BootstrapError:
        raise StateError('Pinned age bootstrap verification failed.') from None
    arch = {('Darwin','arm64'):'darwin-arm64', ('Linux','x86_64'):'linux-amd64'}[(platform.system(),platform.machine())]
    return root / arch / 'age', root / arch / 'age-keygen'


def check_key(key):
    info = key.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise StateError('Recovery key must be an owner-only regular file (0600).')

def ensure_key(key, keygen):
    outside(key); private_dir(key.parent)
    if not key.exists():
        subprocess.run([str(keygen), '-o', str(key)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        key.chmod(0o600)
    check_key(key)
    return subprocess.check_output([str(keygen), '-y', str(key)], stderr=subprocess.DEVNULL).decode().strip()

def check_idle():
    for root in (REPO / 'usenet-infra/terraform', STATE / 'tree/usenet-infra/terraform'):
        if root.exists() and any(root.rglob('.terraform.tfstate.lock.info')):
            raise StateError('Terraform has a state lock; wait for it to finish before capturing state.')
    # Copying a running WiredTiger directory is not a consistent backup.
    result = subprocess.run(['pgrep', '-x', 'mongod'], capture_output=True)
    if result.returncode != 1:
        raise StateError('Cannot establish that local MongoDB is stopped; migration/snapshot refused.')

def load_manifest(state):
    if not (state / 'manifest.json').is_file():
        raise StateError('External state is missing; migrate existing inputs or restore a recovery bundle first.')
    manifest = json.loads((state / 'manifest.json').read_text())
    if manifest.get('schema') != 1: raise StateError('Unknown manifest schema.')
    roots = [p.rstrip('/') for p in manifest['roots']]
    manifest['roots'] = roots
    for p in roots: safe_name(p)
    if len(roots) != len(set(roots)) or any(p.startswith(q + '/') for p in roots for q in roots if p != q):
        raise StateError('Overlapping state roots.')
    return manifest

def prepare(state, repo=REPO):
    outside(state, repo)
    manifest = load_manifest(state)
    tracked = set(os.fsdecode(p) for p in subprocess.check_output(['git','-C',str(repo),'ls-files','-z']).split(b'\0') if p)
    for name in manifest['roots']:
        if any(p == name or p.startswith(name + '/') for p in tracked):
            raise StateError('A durable path conflicts with tracked source.')
        source = state / 'tree' / name
        if not source.exists() or source.is_symlink(): raise StateError('A durable input is missing or unsafe.')
        target = repo / name
        for parent in target.relative_to(repo).parents:
            if parent != Path('.') and (repo / parent).is_symlink(): raise StateError('Symlinked checkout parent refused.')
        if target.is_symlink():
            if target.resolve() != source.resolve(): raise StateError('Conflicting checkout link.')
        elif target.exists(): raise StateError('Existing checkout input refused; migrate or reconcile it first.')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=source.is_dir())
    print('External state linked; existing credentials preserved.', file=sys.stderr)

def backup(state, key, age, recipient):
    check_idle()
    manifest = load_manifest(state)
    current = records(state / 'tree', exclude_caches=True)
    envelope = {'manifest':manifest, 'files':current}
    private_dir(state / 'recovery')
    archive = state / 'recovery' / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.tar.gz.age')
    if archive.exists(): raise StateError('Recovery archive already exists; refusing overwrite.')
    temporary = archive.with_suffix('.partial')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            proc = subprocess.Popen([str(age), '-r', recipient], stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL)
            try:
                import io
                with tarfile.open(fileobj=proc.stdin, mode='w|gz', compresslevel=1) as tar:
                    data = json.dumps(envelope).encode(); info = tarfile.TarInfo('envelope.json');info.size=len(data);info.mode=0o600
                    tar.addfile(info, io.BytesIO(data))
                    for name, rec in current.items():
                        if 'symlink' not in rec: tar.add(state / 'tree' / name, arcname='tree/' + name, recursive=False)
                proc.stdin.close()
                if proc.wait(): raise StateError('Encryption failed.')
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()
        # Independent decryption and byte verification before accepting the bundle.
        with tempfile.TemporaryDirectory(prefix='verify-', dir=state) as directory:
            restore(temporary, key, Path(directory) / 'restored', age)
        after = records(state / 'tree', exclude_caches=True)
        if after != current:
            changed = sorted(name for name in set(current) | set(after) if current.get(name) != after.get(name))
            write_json(state / 'recovery/changed-during-backup.json', {'paths':changed})
            raise StateError('State changed while backing up; exact paths saved in private recovery diagnostics.')
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(state / 'recovery/latest.json', {'archive':str(archive),'sha256':digest(archive),'files':len(current)})
    print('Encrypted recovery bundle verified:', archive)
    return archive

def restore(archive, key, destination, age):
    outside(destination); check_key(key)
    if destination.exists(): raise StateError('Restore requires a new destination.')
    private_dir(destination.parent)
    # Decrypt fully before parsing/extracting: age authentication must succeed.
    with tempfile.TemporaryDirectory(prefix='restore-', dir=destination.parent) as temp:
        temp = Path(temp); plain = temp / 'archive.tar.gz'
        with plain.open('xb') as output:
            plain.chmod(0o600)
            result = subprocess.run([str(age), '-d', '-i', str(key), str(archive)], stdout=output, stderr=subprocess.DEVNULL)
        if result.returncode: raise StateError('Recovery authentication failed; no restore installed.')
        staging = temp / 'state'; private_dir(staging); private_dir(staging / 'tree')
        with tarfile.open(plain, 'r:gz') as tar:
            members = tar.getmembers()
            if len({m.name for m in members}) != len(members): raise StateError('Duplicate archive paths.')
            for m in members:
                safe_name(m.name)
                if not m.isfile(): raise StateError('Only regular files are permitted in recovery archives.')
            envelope_member = tar.getmember('envelope.json')
            if envelope_member.size > 64 * 1024 * 1024: raise StateError('Recovery manifest too large.')
            envelope = json.load(tar.extractfile(envelope_member))
            links = {safe_name(n) for n, rec in envelope['files'].items() if 'symlink' in rec}
            for name in envelope['files']:
                if any(str(parent) in links for parent in PurePosixPath(name).parents):
                    raise StateError('Archive entries beneath symlinks are forbidden.')
            expected = {'tree/' + safe_name(n) for n, rec in envelope['files'].items() if 'symlink' not in rec} | {'envelope.json'}
            if expected != {m.name for m in members}: raise StateError('Archive inventory mismatch.')
            write_json(staging / 'manifest.json', envelope['manifest']); load_manifest(staging)
            for name, rec in envelope['files'].items():
                safe_name(name)
                if 'symlink' in rec: continue
                target = staging / 'tree' / name; private_dir(target.parent)
                with target.open('xb') as out, tar.extractfile('tree/' + name) as inp: shutil.copyfileobj(inp,out)
                target.chmod(rec['mode'] & 0o700)  # never restore group/world access
                if digest(target) != rec['sha256'] or target.stat().st_size != rec['bytes']: raise StateError('Restored bytes differ.')
        # Recreate links last, after all regular files, so extraction never follows them.
        for name, rec in envelope['files'].items():
            if 'symlink' in rec:
                target = staging / 'tree' / safe_name(name)
                private_dir(target.parent)
                target.symlink_to(rec['symlink'])
        # Only these two configuration files contain controller paths. Preserve
        # all credential bytes; rebase configuration after byte verification.
        manifest = envelope['manifest']
        for name in ('usenet-infra/.env','usenet-infra/ansible/inventory.yml'):
            p = staging / 'tree' / name
            if name in envelope['files']:
                if p.is_symlink(): raise StateError('Workstation configuration must be a regular file.')
                text = p.read_text()
                for prefix in (manifest['source_checkout'], manifest.get('source_state','') + '/tree'):
                    text = text.replace(prefix + '/', str(destination / 'tree') + '/')
                p.write_text(text); p.chmod(0o600)
        manifest['source_state'] = str(destination)
        write_json(staging / 'manifest.json', manifest)
        os.replace(staging, destination)
    return destination

def promote_build_roots(state):
    """Move only proven caches; durable inputs must already be verified external links."""
    manifest = load_manifest(state)
    tracked = git_paths('--cached')
    containers = tuple(name for name in ('build', 'usenet-infra/build')
                       if not any(name.startswith(p + '/') for p in manifest['roots']))
    # Complete a read-only preflight before any move. Unknown local files stop it.
    for name in containers:
        if any(p == name or p.startswith(name + '/') for p in tracked):
            raise StateError('Tracked source prevents build-root promotion.')
        source = REPO / name
        if source.is_symlink():
            if source.resolve() != (state/'tree'/name).resolve(): raise StateError('Conflicting build link.')
            continue
        for path, dirs, files in os.walk(source, followlinks=False):
            for leaf in dirs + files:
                p=Path(path)/leaf; relative=p.relative_to(REPO).as_posix()
                if p.is_symlink():
                    if disposable(relative): continue
                    if p.resolve() != (state/'tree'/relative).resolve(): raise StateError('Unexpected build link.')
                elif p.is_file() and not disposable(relative):
                    raise StateError('Unpreserved local data prevents promotion; no files moved.')
    def merge(source, target):
        if source.is_symlink() and disposable(source.relative_to(REPO).as_posix()):
            if target.exists() or target.is_symlink(): raise StateError('Cache destination exists.')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.move(source,target)
        elif source.is_symlink():
            if source.resolve() != target.resolve(): raise StateError('Build link changed after preflight.')
            source.unlink()
        elif source.is_dir():
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            for child in source.iterdir(): merge(child, target/child.name)
            source.rmdir()
        else:
            if not disposable(source.relative_to(REPO).as_posix()) or target.exists():
                raise StateError('Cache changed or destination occupied; stopped without overwrite.')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.move(source,target)
    for name in containers:
        source,target=REPO/name,state/'tree'/name
        if not source.is_symlink():
            if source.exists(): merge(source,target)
            else: private_dir(target)
            source.symlink_to(target,target_is_directory=True)
        manifest['roots']=[p for p in manifest['roots'] if p != name and not p.startswith(name+'/')]+[name]
    manifest['roots'].sort();write_json(state/'manifest.json',manifest)
    print('Only disposable caches moved; verified durable links consolidated.')

def migrate(state, key):
    outside(state); outside(key); check_idle()
    if (state / 'manifest.json').exists(): raise StateError('Migration already initialized; use prepare.')
    age, keygen = age_tools(); recipient = ensure_key(key, keygen)
    roots = plan()
    if not roots: raise StateError('No durable inputs discovered.')
    private_dir(state); private_dir(state / 'tree')
    for name in roots:
        source, target = REPO / name, state / 'tree' / name
        if source.is_symlink(): raise StateError('Migration requires original inputs.')
        if target.exists():
            if source.is_dir() and records(source) == records(target): continue
            if source.is_file() and digest(source) == digest(target): continue
            raise StateError('Migration destination differs; refusing overwrite.')
        private_dir(target.parent)
        if source.is_dir(): shutil.copytree(source,target,symlinks=True)
        else: shutil.copy2(source,target)
    # Verify every byte before changing anything in the checkout.
    for name in roots:
        a,b=REPO/name,state/'tree'/name
        if a.is_dir():
            if records(a)!=records(b): raise StateError('Migration copy verification failed.')
        elif digest(a)!=digest(b): raise StateError('Migration copy verification failed.')
    manifest={'schema':1,'source_state':str(state),'source_checkout':str(REPO),'roots':roots,'recipient':recipient}
    write_json(state/'manifest.json',manifest)
    # This first archive preserves original bytes, including path-dependent configs.
    backup(state,key,age,recipient)
    # A long encryption/restore pass must not race later writes in the checkout.
    for name in roots:
        a,b=REPO/name,state/'tree'/name
        if a.is_dir():
            if records(a)!=records(b): raise StateError('Original state changed during verification; migration stopped.')
        elif digest(a)!=digest(b): raise StateError('Original input changed during verification; migration stopped.')
    # Rebase only the known workstation configuration files. Keys are never edited.
    for name in ('usenet-infra/.env','usenet-infra/ansible/inventory.yml'):
        p=state/'tree'/name
        if p.exists():
            text=p.read_text(); text=text.replace(str(REPO)+'/',str(state/'tree')+'/')
            p.write_text(text);p.chmod(0o600)
    for name in roots:
        source=REPO/name
        if source.is_dir(): shutil.rmtree(source)
        else: source.unlink()
    prepare(state)
    print('Recovery master file for 1Password:',key)
    print('Save its full contents as a password-manager document; never commit it.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan','migrate','prepare','backup','restore','status','promote-build-roots'])
    parser.add_argument('--archive',type=Path);parser.add_argument('--destination',type=Path)
    args=parser.parse_args();os.umask(0o077)
    state=outside(STATE)
    if args.action=='plan':
        roots=plan(); print(json.dumps({'durable_roots':len(roots),'state':str(state),'key':str(KEY)}));return
    if args.action=='restore':
        if not args.archive or not args.destination: parser.error('restore needs --archive and --destination')
        age,_=age_tools();restore(args.archive,KEY,args.destination,age);print('Authenticated restore verified:',args.destination);return
    private_dir(state)
    with (state/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='migrate':migrate(state,KEY)
        elif args.action=='prepare':prepare(state)
        elif args.action=='promote-build-roots':promote_build_roots(state)
        elif args.action=='backup':
            age,keygen=age_tools();check_key(KEY)
            recipient=subprocess.check_output([str(keygen),'-y',str(KEY)],stderr=subprocess.DEVNULL).decode().strip()
            if recipient != load_manifest(state)['recipient']: raise StateError('Recovery master does not match the existing state.')
            backup(state,KEY,age,recipient)
        elif args.action=='status':
            manifest=load_manifest(state); print(json.dumps({'roots':len(manifest['roots']),'state':str(state),'key_present':KEY.is_file()}))

if __name__=='__main__':
    try:main()
    except (StateError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,tarfile.TarError) as e:
        # Paths and subprocess output can contain private operational names.
        print('Checkout state operation failed:',str(e) if isinstance(e,StateError) else type(e).__name__)
        raise SystemExit(1)
