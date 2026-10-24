"""Complete ACL initialization of the new, unused directory without reprovisioning."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

os.umask(0o077)
root = Path('/data')
config = root/'etc/smb.conf'
lp = LoadParm(); lp.load(str(config))
db = SamDB(url=str(root/'private/sam.ldb'), session_info=system_session(), lp=lp)
base = str(db.domain_dn())
if db.search(base='OU=People,'+base, expression='(objectClass=user)'):
    raise RuntimeError('Human accounts exist; review SYSVOL migration separately')
policies = db.search(base='CN=Policies,CN=System,'+base,
                     expression='(objectClass=groupPolicyContainer)', attrs=['cn'])
expected = {'{31B2F340-016D-11D2-945F-00C04FB984F9}', '{6AC1786C-016F-11D2-945F-00C04FB984F9}'}
if {str(row['cn'][0]).upper() for row in policies} != expected:
    raise RuntimeError('Non-default policies exist; refusing initialization repair')
marker = root/'sysvol-acl.json'
if marker.exists():
    subprocess.run(['samba-tool','ntacl','sysvolcheck','-s',str(config)], check=True)
    raise SystemExit(0)
if lp.get('vfs objects') or lp.get('xattr_tdb:file'):
    raise RuntimeError('An existing ACL backend requires explicit review')
backup = root/'backups'/('sysvol-before-acl-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.tar.gz')
with tarfile.open(backup, 'x:gz') as archive:
    archive.add(config, arcname='etc/smb.conf')
    archive.add(root/'state/sysvol', arcname='state/sysvol')
original = config.read_text()
updated = original.replace('[global]', '[global]\n    vfs objects = dfs_samba4 acl_xattr xattr_tdb\n    xattr_tdb:file = /data/state/xattr.tdb\n', 1)
if updated == original:
    raise RuntimeError('Expected global configuration section is missing')
config.write_text(updated)
try:
    subprocess.run(['samba-tool','ntacl','sysvolreset','-s',str(config)], check=True)
    subprocess.run(['samba-tool','ntacl','sysvolcheck','-s',str(config)], check=True)
except Exception:
    config.write_text(original)
    raise
marker.write_text(json.dumps({'backend': 'xattr_tdb', 'previous_sysvol': str(backup),
                              'sysvolcheck': 'passed'})+'\n')
print('Default SYSVOL permissions initialized and verified; account identities unchanged.')
