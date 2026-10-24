#!/usr/bin/env python3
"""Stage private bootstrap files over the dedicated HA SSH connection."""
import io
import hashlib
import os
import subprocess
import tarfile

from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    files = {path.relative_to(PRIVATE/'authelia-seed').as_posix(): path.read_bytes()
             for path in (PRIVATE/'authelia-seed').rglob('*') if path.is_file()}
    if 'configuration.json' not in files:
        raise RuntimeError('Render the private bootstrap configuration first')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        for name, data in files.items():
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(data), 0o600
            archive.addfile(item, io.BytesIO(data))
    previous = files.get('previous.sha256', b'').decode().strip()
    current = hashlib.sha256(files['configuration.json']).hexdigest()
    if previous and (len(previous) != 64 or any(c not in '0123456789abcdef' for c in previous)):
        raise RuntimeError('Invalid prior configuration fingerprint')
    script = '''set -eu
umask 077
test ! -L /ssl/smarthome
mkdir -p /ssl/smarthome
if test -e /ssl/smarthome/authelia-seed; then
 test ! -L /ssl/smarthome/authelia-seed
 actual=$(sha256sum /ssl/smarthome/authelia-seed/configuration.json | cut -d ' ' -f 1)
 test "$actual" = 'PREVIOUS' || test "$actual" = 'CURRENT'
fi
stage=$(mktemp -d /ssl/smarthome/.authelia-incoming-XXXXXXXX)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
tar -xf - -C "$stage"
mkdir -p /ssl/smarthome/authelia-seed
cp -R "$stage/." /ssl/smarthome/authelia-seed/
chmod 700 /ssl/smarthome/authelia-seed /ssl/smarthome/authelia-seed/certificates
test -s /ssl/smarthome/authelia-seed/configuration.json
'''.replace('PREVIOUS', previous).replace('CURRENT', current)
    args = ['ssh','-T','-i',str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
            '-o','IdentitiesOnly=yes','-o','IdentityAgent=none','-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
            'root@homeassistant.local',script]
    result = subprocess.run(args, input=payload.getvalue(), capture_output=True, timeout=60)
    if result.returncode:
        (PRIVATE/'stage-authelia.log').write_bytes(result.stderr)
        raise RuntimeError('HA staging failed; inspect private log. No alternate credentials attempted.')
    print('Private Authelia bootstrap staged on HA; remove the seed after verified startup.')


if __name__ == '__main__': main()
