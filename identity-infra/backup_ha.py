#!/usr/bin/env python3
"""Cold-back up identity apps, verify their private state, and encrypt off-host."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time

from manage import PRIVATE, ROOT

APPS = {'local_authelia', 'local_home_acme', 'local_directory', 'local_directory_route'}


def ssh(command, timeout=120):
    result = subprocess.run([
        'ssh', '-T', '-i', str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
        '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ConnectTimeout=10', 'root@homeassistant.local', command,
    ], capture_output=True, timeout=timeout)
    if result.returncode:
        (PRIVATE/'ha-backup.log').write_bytes(result.stderr)
        raise RuntimeError('Dedicated HA operation failed; inspect private log. No fallback credentials used.')
    return result.stdout


def main():
    os.umask(0o077)
    pending = PRIVATE/'ha-backup-pending.json'
    if pending.exists():
        slug = json.loads(pending.read_text())['slug']
    else:
        created = json.loads(ssh(
            'ha backups new --app local_authelia --app local_home_acme --app local_directory --app local_directory_route --folders ssl '
            '--name smarthome-identity --raw-json', timeout=600))
        slug = created['data']['slug']
        pending.write_text(json.dumps({'slug': slug})+'\n')
    if not re.fullmatch(r'[a-f0-9]+', slug):
        raise RuntimeError('Unexpected backup slug')
    plain = ssh('chmod 600 /backup/'+slug+'.tar; cat /backup/'+slug+'.tar')
    app_files = {}
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        metadata_member = next(m for m in outer.getmembers() if m.name.removeprefix('./') == 'backup.json')
        metadata = json.load(outer.extractfile(metadata_member))
        if {item['slug'] for item in metadata['addons']} != APPS:
            raise RuntimeError('Unexpected app backup membership')
        for app in sorted(APPS):
            member = next(m for m in outer.getmembers() if m.name in (app+'.tar.gz', app+'.tar'))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as inner:
                app_files[app] = {m.name: inner.extractfile(m).read()
                                  for m in inner.getmembers() if m.isfile()}
        gateway = PRIVATE/'secrets/arr-gateway.json'
        if gateway.exists():
            ssl_member = next(m for m in outer.getmembers() if m.name in ('ssl.tar.gz', 'ssl.tar'))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(ssl_member).read())) as inner:
                matching = [m for m in inner.getmembers() if m.name.endswith('/arr-gateway-authorization')]
                expected_gateway = (json.loads(gateway.read_text())['authorization']+'\n').encode()
                if len(matching) != 1 or inner.extractfile(matching[0]).read() != expected_gateway:
                    raise RuntimeError('Preserved Arr gateway credential missing from SSL backup')
    authelia = app_files['local_authelia']
    acme = app_files['local_home_acme']
    directory = app_files['local_directory']
    def entry(suffix):
        matches = [data for name, data in directory.items() if name.endswith(suffix)]
        if len(matches) != 1:
            raise RuntimeError('Expected one directory backup member: '+suffix)
        return matches[0]
    saved = json.loads(entry('/sysvol-checkpoint.json'))
    if saved['identity']['domain_sid'] != 'S-1-5-21-2612071719-3246555018-4093554428':
        raise RuntimeError('Directory backup SID differs')
    entry('/private/sam.ldb')
    entry('/migration-ready.json')
    if entry('/ssh/ssh_host_ed25519_key') != (PRIVATE/'vm/ssh_host_ed25519_key').read_bytes():
        raise RuntimeError('Directory SSH key differs in native backup')
    if entry('/tls/dc.key') != (PRIVATE/'tls/dc.key').read_bytes():
        raise RuntimeError('Directory LDAPS key differs in native backup')
    expected = (PRIVATE/'authelia-seed/configuration.json').read_bytes()
    if expected not in authelia.values():
        raise RuntimeError('Authelia persistent configuration missing from backup')
    if not any(name.endswith('authelia.sqlite3') for name in authelia):
        raise RuntimeError('Authelia database missing from backup')
    if (PRIVATE/'secrets/dreamhost-api-key').read_bytes() not in acme.values():
        raise RuntimeError('Persistent ACME DNS credential missing from backup')
    if not any('/letsencrypt/accounts/' in '/'+name and name.endswith('.key') for name in acme):
        raise RuntimeError('Production ACME account key missing from backup')
    if not any('/letsencrypt/certificates/' in '/'+name and name.endswith('.key') for name in acme):
        raise RuntimeError('Production certificate key missing from backup')
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    recipient = json.loads((state/'manifest.json').read_text())['recipient']
    cipher = subprocess.check_output([str(age), '-r', recipient], input=plain)
    restored = subprocess.check_output([str(age), '-d', '-i',
        str(Path.home()/'.config/smarthome/recovery.agekey')], input=cipher)
    if restored != plain:
        raise RuntimeError('Encrypted HA backup readback differs')
    path = state/'recovery'/time.strftime('ha-identity-%Y%m%dT%H%M%SZ.tar.age', time.gmtime())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('xb') as stream:
        stream.write(cipher)
    receipt = {'archive': str(path), 'native_slug': slug, 'apps': sorted(APPS),
               'ciphertext_sha256': hashlib.sha256(cipher).hexdigest(),
               'authenticated_decryption': 'passed', 'private_state_membership': 'passed'}
    (PRIVATE/'ha-backup-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    for app in sorted(APPS):
        result = json.loads(ssh('ha apps info '+app+' --raw-json'))
        if result['data']['state'] != 'started':
            raise RuntimeError('Backed-up app did not restart: '+app)
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--max-time', '20',
                    'https://auth.home.rytim.com/api/health'], check=True, capture_output=True)
    print('Verified encrypted HA identity backup:', path)
    print('Persistent app configuration, MFA database, ACME account/certificate keys and app restart checked.')
    pending.unlink()


if __name__ == '__main__':
    main()
