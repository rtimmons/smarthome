"""Independently inspect the encrypted native backup without exposing MFA secrets."""
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile

from manage import PRIVATE


def main():
    os.umask(0o077)
    receipt = json.loads((PRIVATE/'ha-backup-receipt.json').read_text())
    cipher = Path(receipt['archive']).read_bytes()
    if hashlib.sha256(cipher).hexdigest() != receipt['ciphertext_sha256']:
        raise RuntimeError('Encrypted native backup differs from its verified receipt')
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain = subprocess.check_output([str(age), '-d', '-i',
        str(Path.home()/'.config/smarthome/recovery.agekey')], input=cipher)
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        member = next(m for m in outer if m.name in ('local_authelia.tar.gz', 'local_authelia.tar'))
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as inner:
            files = {m.name: inner.extractfile(m).read() for m in inner if m.isfile()}
    configuration = (PRIVATE/'authelia-seed/configuration.json').read_bytes()
    if configuration not in files.values():
        raise RuntimeError('Original storage/session/OIDC keys and SMTP configuration were not recovered')
    with tempfile.TemporaryDirectory(prefix='authelia-restore-', dir=PRIVATE) as directory:
        directory = Path(directory)
        for name in ('authelia.sqlite3', 'authelia.sqlite3-wal', 'authelia.sqlite3-shm'):
            matching = [value for path, value in files.items() if path.endswith('/'+name)]
            if len(matching) > 1 or (name == 'authelia.sqlite3' and len(matching) != 1):
                raise RuntimeError('Unexpected native database membership')
            if matching:
                (directory/name).write_bytes(matching[0])
        with sqlite3.connect('file:'+str(directory/'authelia.sqlite3')+'?mode=ro', uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Restored Authelia database failed integrity check')
            enrolled = db.execute('SELECT COUNT(*) FROM totp_configurations').fetchone()[0]
    result = {'archive': receipt['archive'], 'database_integrity': 'passed',
              'original_configuration': 'identical', 'totp_enrollments': enrolled,
              'temporary_restore_removed': True}
    (PRIVATE/'authelia-restore-receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
