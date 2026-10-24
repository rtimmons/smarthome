#!/usr/bin/env python3
"""Retain a decrypt-verified, restore-checked AD backup outside the NAS."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

from manage import connection, PRELUDE, PRIVATE, ROOT


def main():
    os.umask(0o077)
    remote = (ROOT/'identity-infra/backup_directory_remote.py').read_text()
    marker = PRIVATE/'ha-cutover.json'
    if marker.exists():
        if json.loads(marker.read_text()).get('phase') not in ('activated', 'verified'):
            raise RuntimeError('Directory migration is incomplete; inspect its journal before selecting a backup source')
        from ha_directory import execute
        result = execute(('python3 - <<\'BACKUP\'\n'+remote+'\nBACKUP\n').encode(), timeout=900)
    else:
        script = PRELUDE+'"$docker" exec -i home-identity-dc-1 python3 - <<\'BACKUP\'\n'+remote+'\nBACKUP\n'
        result = subprocess.run(connection(), input=script.encode(), capture_output=True, timeout=900)
    if result.returncode:
        (PRIVATE/'directory-backup.log').write_bytes(result.stderr)
        raise RuntimeError('Directory backup/restore check failed; see private local and NAS backup logs')
    plain = result.stdout
    with tarfile.open(fileobj=io.BytesIO(plain)) as archive:
        receipt = json.load(archive.extractfile('latest-verification.json'))
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    recipient = json.loads((state/'manifest.json').read_text())['recipient']
    cipher = subprocess.check_output([str(age),'-r',recipient],input=plain)
    restored = subprocess.check_output([str(age),'-d','-i',str(Path.home()/'.config/smarthome/recovery.agekey')],input=cipher)
    if restored != plain:
        raise RuntimeError('Encrypted directory recovery readback differs')
    path = state/'recovery'/time.strftime('ad-restore-verified-%Y%m%dT%H%M%SZ.tar.age',time.gmtime())
    with path.open('xb') as stream: stream.write(cipher)
    receipt.update({'archive': str(path), 'ciphertext_sha256': hashlib.sha256(cipher).hexdigest(),
                    'authenticated_decryption': 'passed'})
    (PRIVATE/'directory-backup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Verified AD recovery backup:', path)
    print('Domain/account identities and password material matched the isolated restore; no restored listener was started.')


if __name__ == '__main__': main()
