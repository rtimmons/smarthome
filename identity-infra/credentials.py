#!/usr/bin/env python3
"""SOPS escrow for current controller credentials; never overwrite live inputs."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT/'identity-infra/credentials.sops.json'
CONFIG = ROOT/'identity-infra/.sops.yaml'
DIRECTORIES = ('.ssh', 'usenet-infra/secrets', 'usenet-infra/ansible/files',
               'build/identity-private/secrets', 'build/identity-private/tls')
FILES = ('usenet-infra/.env', 'usenet-infra/ansible/inventory.yml',
         'usenet-infra/terraform/cloud/terraform.tfvars',
         'usenet-infra/terraform/storage/terraform.tfvars',
         'new-hass-configs/secrets.yaml', 'pebble-home-assistant-token.txt',
         'build/git-host/admin-login.txt', 'build/identity-private/human-logins.json',
         'build/identity-private/household-logins.1password.csv',
         'build/identity-private/authelia-seed/configuration.json',
         'build/identity-private/ha-cutover.json',
         'build/identity-private/vm/id_ed25519_dc_vm',
         'build/identity-private/vm/id_ed25519_dc_vm.pub',
         'build/identity-private/vm/ssh_host_ed25519_key',
         'build/identity-private/vm/ssh_host_ed25519_key.pub',
         'build/identity-private/vm/known_hosts')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(name):
    if (not isinstance(name, str) or not name or '\\' in name or '\0' in name
            or name != str(PurePosixPath(name)) or name.startswith('/')
            or any(p in ('', '.', '..') for p in name.split('/'))
            or name.split('/')[0] not in ('tree', 'pki')):
        raise ValueError('Unsafe credential recovery path')
    return name


def capture(state, pki):
    paths = [(state/'tree'/name, 'tree/'+name) for name in FILES]
    for name in DIRECTORIES:
        directory = state/'tree'/name
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError('Required credential directory missing or linked')
        paths += [(p, 'tree/'+p.relative_to(state/'tree').as_posix())
                  for p in directory.rglob('*') if not p.is_dir()]
    if not pki.is_dir() or pki.is_symlink():
        raise ValueError('Original PKI directory required')
    paths += [(p, 'pki/'+p.relative_to(pki).as_posix()) for p in pki.rglob('*') if not p.is_dir()]
    entries = {}
    for path, name in sorted(paths, key=lambda pair: pair[1]):
        safe_path(name)
        source_root = pki if name.startswith('pki/') else state/'tree'
        if source_root.is_symlink() or any((source_root/parent).is_symlink()
                for parent in path.relative_to(source_root).parents):
            raise ValueError('Linked credential parent refused')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 4*1024**2:
            raise ValueError('Credential must be an owned regular bounded file')
        data = path.read_bytes()
        if b'AGE-SECRET-KEY-1' in data:
            raise ValueError('Recovery masters must remain outside the credential vault')
        after = path.stat()
        if (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
            raise ValueError('Credential changed during capture')
        entries[name] = {'content': base64.b64encode(data).decode(), 'sha256': digest(data)}
    return {'schema': 1, 'entries': entries}


def unpack(document):
    if set(document) != {'schema', 'entries'} or document['schema'] != 1:
        raise ValueError('Unknown credential envelope')
    entries = document['entries']
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 1000:
        raise ValueError('Invalid credential inventory')
    result = {}
    for name, entry in entries.items():
        safe_path(name)
        if set(entry) != {'content', 'sha256'}:
            raise ValueError('Invalid credential entry')
        data = base64.b64decode(entry['content'], validate=True)
        if len(data) > 4*1024**2 or digest(data) != entry['sha256']:
            raise ValueError('Credential checksum mismatch')
        result[name] = data
    return result


def historical_vault():
    spec = importlib.util.spec_from_file_location('historical_vault', ROOT/'usenet-infra/scripts/secrets-vault.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def binary():
    return historical_vault()._default_sops(ROOT)


def crypt(data, key, encrypt=False, timeout=60):
    if not encrypt:
        historical_vault()._validate_ciphertext(data)
    with tempfile.TemporaryDirectory(prefix='smarthome-sops-') as temp:
        env = {'PATH': os.defpath, 'HOME': temp, 'XDG_CONFIG_HOME': temp,
               'LANG': 'C', 'SOPS_AGE_KEY_FILE': str(key)}
        args = [str(binary()), '--input-type', 'json', '--output-type', 'json']
        if encrypt:
            args += ['--config', str(CONFIG), '--filename-override', str(VAULT), '--encrypt']
        else:
            args += ['--decrypt']
        result = subprocess.run(args+['/dev/stdin'], input=data, capture_output=True, env=env, timeout=timeout)
        if result.returncode:
            raise ValueError('SOPS operation failed; credential contents and provider diagnostics suppressed')
        return result.stdout


def decrypt(cipher, key, timeout=60):
    if len(cipher) > 32*1024**2:
        raise ValueError('Oversized ciphertext')
    # Authenticate the SOPS MAC before interpreting any restoration path.
    outer = json.loads(crypt(cipher, key, timeout=timeout))
    if set(outer) != {'payload'}:
        raise ValueError('Invalid SOPS envelope')
    document = json.loads(outer['payload'])
    unpack(document)
    return document


def restore(document, destination):
    entries = unpack(document)
    destination = Path(os.path.abspath(destination))
    if destination.exists() or destination.is_symlink() or destination.parent.resolve() != destination.parent:
        raise ValueError('Restore requires a new destination with a real parent')
    with tempfile.TemporaryDirectory(prefix='.credential-restore-', dir=destination.parent) as temp:
        stage = Path(temp)/'restored'
        stage.mkdir(mode=0o700)
        for name, data in entries.items():
            path = stage/name
            for parent in reversed(path.relative_to(stage).parents):
                (stage/parent).mkdir(mode=0o700, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(0o600)
            if path.read_bytes() != data:
                raise ValueError('Independent file readback failed')
        stage.rename(destination)
    return len(entries)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'verify', 'restore'))
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    key = Path(os.environ.get('SMARTHOME_RECOVERY_KEY', Path.home()/'.config/smarthome/recovery.agekey'))
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    if args.action == 'restore':
        if args.destination is None:
            parser.error('restore requires --destination outside the checkout')
        if args.destination.resolve().is_relative_to(ROOT):
            parser.error('restore destination must be outside the checkout')
        count = restore(decrypt(VAULT.read_bytes(), key), args.destination)
    else:
        current = capture(state, Path.home()/'.config/smarthome/pki')
        if args.action == 'capture':
            plain = json.dumps({'payload': json.dumps(current, sort_keys=True)}).encode()
            cipher = crypt(plain, key, encrypt=True)
            if decrypt(cipher, key) != current or capture(state, Path.home()/'.config/smarthome/pki') != current:
                raise ValueError('Credential preservation verification failed')
            temporary = VAULT.with_suffix('.new')
            with temporary.open('xb') as stream:
                stream.write(cipher)
            temporary.chmod(0o644)
            temporary.replace(VAULT)
        restored = decrypt(VAULT.read_bytes(), key)
        if restored != current:
            raise ValueError('Current credentials differ from SOPS; recapture after reviewing the change')
        with tempfile.TemporaryDirectory(prefix='smarthome-credential-drill-') as temp:
            count = restore(restored, Path(temp).resolve()/'restored')
    print(f'SOPS {args.action} verified: {count} exact-byte credential/configuration files; no keys replaced.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise SystemExit(type(error).__name__+': credential operation refused; no credential values displayed') from None
