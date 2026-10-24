"""Restore an exact cold copy, compare identities and rebind inode-based ACLs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

from directory_state import identity, sysvol, EXPECTED_SID

os.umask(0o077)
root = Path('/data')
staged = root/'cold-transfer'
if (root/'migration-ready.json').exists() or (root/'private/sam.ldb').exists():
    raise RuntimeError('Directory already restored; refusing replacement')
with tarfile.open(staged/'directory.tar.gz') as archive:
    members = archive.getmembers()
    allowed = {'etc','private','state','bind-dns','tls','identity.json','authelia-bind.json',
               'household-users.json','sysvol-acl.json','migration-evidence.json'}
    for item in members:
        path = Path(item.name)
        if path.is_absolute() or '..' in path.parts or path.parts[0] not in allowed or not (item.isfile() or item.isdir()):
            raise RuntimeError('Unexpected archive member')
        if (root/path).exists():
            raise RuntimeError('Restore destination exists; refusing overwrite')
    archive.extractall(root, filter='fully_trusted')
evidence = json.loads((root/'migration-evidence.json').read_text())
for name, digest in evidence['files'].items():
    path = root/name
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Cold-copy bytes differ: '+name)
# SSH and TLS material retain their bytes; TLS ownership must match Samba's UID.
for path in (root/'tls').iterdir():
    os.chown(path, 0, 0)
    path.chmod(0o600)
config = root/'etc/smb.conf'
original = config.read_text()
config.write_text(re.sub(r'^\s*interfaces\s*=.*$', '    interfaces = lo 192.168.1.10/32', original, flags=re.MULTILINE)
                  .replace(' = /run/identity-tls/', ' = /tls/'))
if identity() != evidence['identity']:
    raise RuntimeError('Domain/account identities, credentials or memberships differ')
sysvol(restore=evidence['sysvol'])
with (staged/'verification.log').open('wb') as log:
    for command in [['samba-tool','dbcheck','-s',str(config)],
                    ['samba-tool','ntacl','sysvolcheck','-s',str(config)]]:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
if identity() != evidence['identity']:
    raise RuntimeError('Directory identity changed during offline checks')
receipt={'domain_sid': EXPECTED_SID,'source_file_bytes':'identical','accounts_and_credentials':'identical',
         'sysvol_content_and_acls':'identical','database_check':'passed','activated':False}
(staged/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
