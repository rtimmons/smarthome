#!/usr/bin/env python3
"""Remove transport-only credential copies after verified persistent backup."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

from backup_ha import ssh
from manage import PRIVATE


def main():
    receipt = json.loads((PRIVATE/'ha-backup-receipt.json').read_text())
    if receipt.get('authenticated_decryption') != 'passed' or receipt.get('private_state_membership') != 'passed':
        raise RuntimeError('A verified persistent identity backup is required before seed cleanup')
    cipher = Path(receipt['archive']).read_bytes()
    if hashlib.sha256(cipher).hexdigest() != receipt['ciphertext_sha256']:
        raise RuntimeError('Retained identity backup differs from its verified receipt')
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain = subprocess.check_output([str(age), '-d', '-i',
        str(Path.home()/'.config/smarthome/recovery.agekey')], input=cipher)
    values = {}
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        for app in ('local_authelia', 'local_home_acme'):
            member = next(m for m in outer if m.name in (app+'.tar.gz', app+'.tar'))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as inner:
                values[app] = [inner.extractfile(m).read() for m in inner if m.isfile()]
    seeds = {
        'authelia-seed/configuration.json': PRIVATE/'authelia-seed/configuration.json',
        'authelia-seed/certificates/ca.crt': PRIVATE/'authelia-seed/certificates/ca.crt',
        'authelia-seed/previous.sha256': PRIVATE/'authelia-seed/previous.sha256',
        'acme-seed/dreamhost-api-key': PRIVATE/'secrets/dreamhost-api-key',
    }
    for name, app in (('authelia-seed/configuration.json', 'local_authelia'),
                      ('authelia-seed/certificates/ca.crt', 'local_authelia'),
                      ('acme-seed/dreamhost-api-key', 'local_home_acme')):
        if seeds[name].read_bytes() not in values[app]:
            raise RuntimeError('Current seed is not present in the persistent app backup')
    script = '''set -eu
test ! -L /ssl/smarthome
test ! -L /ssl/smarthome/authelia-seed
test ! -L /ssl/smarthome/authelia-seed/certificates
test ! -L /ssl/smarthome/acme-seed
'''
    for name, source in seeds.items():
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        path = '/ssl/smarthome/'+name
        script += f'''test ! -L '{path}'
if test -e '{path}'; then
 test "$(sha256sum '{path}' | cut -d ' ' -f 1)" = '{digest}'
fi
'''
    # Verify every existing copy before removing any. Exact file paths only;
    # persistent app configuration, ACME data and certificate publication stay.
    for name in seeds:
        script += "rm -f '/ssl/smarthome/"+name+"'\n"
    script += '''for directory in /ssl/smarthome/authelia-seed/certificates /ssl/smarthome/authelia-seed /ssl/smarthome/acme-seed; do
 test ! -d "$directory" || rmdir "$directory"
done
'''
    ssh(script)
    for app in ('local_authelia', 'local_home_acme'):
        ssh('ha apps restart '+app, timeout=180)
        info = json.loads(ssh('ha apps info '+app+' --raw-json'))
        if info['data']['state'] != 'started':
            raise RuntimeError('App did not restart from persistent configuration: '+app)
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--max-time', '30',
                    'https://auth.home.rytim.com/api/health'], check=True, capture_output=True)
    print('Removed matching transport-only HA seeds; both apps restarted from persistent configuration and portal health passed.')


if __name__ == '__main__':
    main()
