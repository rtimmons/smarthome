#!/usr/bin/env python3
import sys,json,secrets,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'identity-infra'))
from manage import PRIVATE
from ha_directory import execute
os.umask(0o077)
p=PRIVATE/'secrets/jellyfin-ldap.json'
if not p.exists():
 with p.open('x') as stream:stream.write(json.dumps({'username':'svc-jellyfin','password':secrets.token_urlsafe(48)})+'\n')
account=json.loads(p.read_text())
script='bootstrap='+repr(account)+'\n'+r'''
import json,hashlib,tempfile,subprocess
from pathlib import Path
import ldb
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB
lp=LoadParm();lp.load('/data/etc/smb.conf')
db=SamDB(url='/data/private/sam.ldb',session_info=system_session(),lp=lp)
base=str(db.domain_dn())
assert base=='DC=ad,DC=home,DC=arpa'
marker=Path('/data/jellyfin-bind.json')
identity={'username':bootstrap['username'],'password_sha256':hashlib.sha256(bootstrap['password'].encode()).hexdigest()}
found=db.search(base=base,expression='(sAMAccountName=svc-jellyfin)',attrs=['memberOf','userAccountControl'])
if marker.exists():
 assert json.loads(marker.read_text())==identity and len(found)==1
else:
 assert not found,'Existing unmanaged service account; refusing takeover'
 db.newuser('svc-jellyfin',bootstrap['password'],userou='OU=Services',description='Read-only directory lookup for household Jellyfin',useusernameascn=True)
 db.setexpiry('(sAMAccountName=svc-jellyfin)',0,no_expiry_req=True)
 found=db.search(base=base,expression='(sAMAccountName=svc-jellyfin)',attrs=['memberOf','userAccountControl'])
 db.modify(ldb.Message.from_dict(db,{'dn':found[0].dn,'userAccountControl':str(int(found[0]['userAccountControl'][0])|0x10000)},ldb.FLAG_MOD_REPLACE))
 marker.write_text(json.dumps(identity)+'\n');marker.chmod(0o600)
assert not found[0].get('memberOf'), 'Service account must not have access groups'
with tempfile.TemporaryDirectory(dir='/run') as tmp:
 p=Path(tmp)/'credentials';p.write_text('username = svc-jellyfin\npassword = '+bootstrap['password']+'\ndomain = SMARTHOME\n');p.chmod(0o600)
 for share in ('Public','FromDrobo','Multimedia','Container','Usenet','SpaceBlackTimeMachine'):
  r=subprocess.run(['smbclient','//192.168.1.66/'+share,'-A',str(p),'--client-protection=encrypt','-m','SMB3','-c','quit'],capture_output=True,timeout=30)
  if b'NT_STATUS_ACCESS_DENIED' not in r.stdout+r.stderr:
   db.disable_account('(sAMAccountName=svc-jellyfin)')
   raise RuntimeError('Service account disabled: unexpected NAS access or verification failure on '+share)
print('PASS: dedicated LDAP service identity has no groups and is denied all six NAS shares')
users=db.search(base=base,expression='(sAMAccountName=ryantimmons)',attrs=['uid'])
assert len(users)==1
matches=db.search(base=base,expression='(uid=ryan)',attrs=['dn'])
assert not matches or len(matches)==1 and str(matches[0].dn)==str(users[0].dn)
assert not users[0].get('uid') or bytes(users[0]['uid'][0])==b'ryan'
if not users[0].get('uid'):
 db.modify(ldb.Message.from_dict(db,{'dn':users[0].dn,'uid':'ryan'},ldb.FLAG_MOD_ADD))
print('PASS: existing Ryan account gains only the Jellyfin username alias; password and memberships unchanged')
'''
r=execute(("python3 - <<'JELLYFIN'\n"+script+"\nJELLYFIN\n").encode(),timeout=240)
(PRIVATE/'jellyfin-directory.log').write_bytes(r.stdout+r.stderr)
print('Jellyfin directory preparation exit',r.returncode)
if r.returncode:raise SystemExit(1)
print(r.stdout.decode())
