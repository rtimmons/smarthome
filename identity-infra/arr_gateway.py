#!/usr/bin/env python3
"""Create once and stage the private HA-to-cloud Arr gateway credential."""
import base64
import hashlib
import json
import os
import secrets
import subprocess

from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    target = PRIVATE/'secrets/arr-gateway.json'
    marker = PRIVATE/'arr-gateway-staged.json'
    if not target.exists():
        if marker.exists():
            raise RuntimeError('Restore the existing Arr gateway credential before staging')
        password = secrets.token_urlsafe(48)
        result = subprocess.run(['uv', 'run', '--with', 'argon2-cffi==25.1.0', 'python', '-c',
            'import sys; from argon2 import PasswordHasher; print(PasswordHasher().hash(sys.stdin.read()))'],
            input=password, capture_output=True, text=True, check=True)
        value = {'username': 'household-sso', 'password_hash': result.stdout.strip(),
                 'authorization': 'Basic '+base64.b64encode(('household-sso:'+password).encode()).decode()}
        with target.open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
    value = json.loads(target.read_text())
    if value['username'] != 'household-sso' or not value['authorization'].startswith('Basic '):
        raise RuntimeError('Unexpected gateway credential format')
    data = (value['authorization']+'\n').encode()
    digest = hashlib.sha256(data).hexdigest()
    script = '''set -eu
umask 077
test ! -L /ssl/smarthome
mkdir -p /ssl/smarthome
test ! -L /ssl/smarthome/arr-gateway-authorization
candidate=$(mktemp /ssl/smarthome/.arr-gateway-XXXXXXXX)
trap 'rm -f "$candidate"' EXIT HUP INT TERM
cat > "$candidate"
if test -e /ssl/smarthome/arr-gateway-authorization; then
 cmp "$candidate" /ssl/smarthome/arr-gateway-authorization
else
 chmod 600 "$candidate"
 mv "$candidate" /ssl/smarthome/arr-gateway-authorization
fi
'''
    result = subprocess.run(['ssh', '-T', '-i', str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
        '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
        'root@homeassistant.local', script], input=data, capture_output=True, timeout=45)
    if result.returncode:
        (PRIVATE/'arr-gateway-stage.log').write_bytes(result.stderr)
        raise RuntimeError('Dedicated HA staging failed; inspect private log. No alternate credentials attempted.')
    marker.write_text(json.dumps({'authorization_sha256': digest})+'\n')
    print('Existing or newly created gateway credential staged with exact-byte preservation.')


if __name__ == '__main__':
    main()
