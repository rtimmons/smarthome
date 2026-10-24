#!/usr/bin/env python3
"""Capture QTS configuration read-only and verify an encrypted off-NAS copy."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

from manage import PRELUDE, connection


def main():
    os.umask(0o077)
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    script = PRELUDE + '''"$docker" run --rm --network none --read-only --entrypoint tar \
 --mount type=bind,src=/etc/config,dst=/source,readonly \
 smarthome-samba-ad:20261024 -C /source -chzf - smb.conf uLinux.conf passwd group shadow smbpasswd
'''
    result = subprocess.run(connection(), input=script.encode(), capture_output=True, timeout=300)
    if result.returncode:
        from manage import PRIVATE
        (PRIVATE/'qnap-backup.log').write_bytes(result.stderr)
        raise RuntimeError('QTS rollback capture failed; see private qnap-backup.log')
    plain = result.stdout
    with tarfile.open(fileobj=io.BytesIO(plain), mode='r:gz') as archive:
        names = {item.name.removeprefix('./') for item in archive}
        if not {'smb.conf', 'uLinux.conf', 'passwd', 'group', 'shadow', 'smbpasswd'} <= names:
            raise RuntimeError('QTS authentication rollback archive is incomplete')
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    recipient = json.loads((state/'manifest.json').read_text())['recipient']
    cipher = subprocess.check_output([str(age), '-r', recipient], input=plain)
    recovered = subprocess.check_output([str(age), '-d', '-i', str(Path.home()/'.config/smarthome/recovery.agekey')], input=cipher)
    if recovered != plain:
        raise RuntimeError('QTS rollback archive decrypt verification failed')
    path = state/'recovery'/time.strftime('qnap-pre-ad-%Y%m%dT%H%M%SZ.tar.gz.age', time.gmtime())
    with path.open('xb') as stream:
        stream.write(cipher)
    print('Verified encrypted QTS authentication/settings rollback:', path)
    print('Ciphertext SHA256:', hashlib.sha256(cipher).hexdigest())


if __name__ == '__main__':
    main()
