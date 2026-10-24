#!/usr/bin/env python3
"""Encrypt and independently verify identity bootstrap/CA material outside Git."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

os.umask(0o077)
state=Path(os.environ.get('SMARTHOME_STATE_DIR',Path.home()/'.local/share/smarthome'))
key=Path.home()/'.config/smarthome/recovery.agekey'
age=Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
recipient=json.loads((state/'manifest.json').read_text())['recipient']
entries={}
for prefix,root in [('pki',Path.home()/'.config/smarthome/pki'),('identity',state/'tree/build/identity-private')]:
    for p in root.rglob('*'):
        if p.is_file() and not p.is_symlink() and p.suffix not in ('.log','.age'):
            entries[prefix+'/'+p.relative_to(root).as_posix()]=p.read_bytes()
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
    for name,data in entries.items():
        info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
        tar.addfile(info,io.BytesIO(data))
plain=buffer.getvalue()
cipher=subprocess.check_output([str(age),'-r',recipient],input=plain)
restored=subprocess.check_output([str(age),'-d','-i',str(key)],input=cipher,stderr=subprocess.DEVNULL)
if restored!=plain:raise SystemExit('Recovery verification failed.')
archive=state/'recovery'/time.strftime('identity-bootstrap-%Y%m%dT%H%M%SZ.tar.gz.age',time.gmtime())
with archive.open('xb') as f:f.write(cipher)
print('Verified encrypted identity/CA recovery:',archive)
print('Files:',len(entries),'Ciphertext SHA256:',hashlib.sha256(cipher).hexdigest())
