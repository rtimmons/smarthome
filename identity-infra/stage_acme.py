#!/usr/bin/env python3
"""Transfer the DNS-only renewal credential using the dedicated HA identity."""
import io
import os
import subprocess
import tarfile

from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    data = (PRIVATE/'secrets/dreamhost-api-key').read_bytes()
    value = data.decode().strip()
    if len(value) < 16 or any(c.isspace() for c in value):
        raise RuntimeError('Missing or invalid DNS credential')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        item = tarfile.TarInfo('dreamhost-api-key')
        item.size, item.mode = len(data), 0o600
        archive.addfile(item, io.BytesIO(data))
    script = '''set -eu
umask 077
test ! -L /ssl/smarthome
mkdir -p /ssl/smarthome
test ! -L /ssl/smarthome/acme-seed
stage=$(mktemp -d /ssl/smarthome/.acme-incoming-XXXXXXXX)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
tar -xf - -C "$stage"
if test -e /ssl/smarthome/acme-seed/dreamhost-api-key; then
 cmp -s "$stage/dreamhost-api-key" /ssl/smarthome/acme-seed/dreamhost-api-key
else
 mkdir -p /ssl/smarthome/acme-seed
 cp "$stage/dreamhost-api-key" /ssl/smarthome/acme-seed/dreamhost-api-key
fi
chmod 700 /ssl/smarthome/acme-seed
chmod 600 /ssl/smarthome/acme-seed/dreamhost-api-key
'''
    args = ['ssh','-T','-i',str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
            '-o','IdentitiesOnly=yes','-o','IdentityAgent=none','-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
            'root@homeassistant.local',script]
    result = subprocess.run(args, input=payload.getvalue(), capture_output=True, timeout=60)
    if result.returncode:
        (PRIVATE/'stage-acme.log').write_bytes(result.stderr)
        raise RuntimeError('HA staging failed; inspect private log. No alternate credentials attempted.')
    print('DNS credential seed staged; remove it after verified persistent add-on startup.')


if __name__ == '__main__':
    main()
