#!/usr/bin/env python3
import sys,subprocess,json,urllib.request,io,tarfile,hashlib,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'identity-infra'))
from manage import PRELUDE,PRIVATE,connection
os.umask(0o077)
phase='post-ad' if '--post-ad' in sys.argv else 'pre-ad'
if phase == 'pre-ad' and (PRIVATE/'jellyfin-pre-ad-receipt.json').exists():
 raise RuntimeError('Original pre-AD checkpoint is immutable; use --post-ad for a new snapshot')
c=json.loads((ROOT/'usenet-infra/secrets/jellyfin/operator.json').read_text())
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
h={'Content-Type':'application/json','Authorization':'MediaBrowser Client="Smarthome recovery", Device="Controller", DeviceId="smarthome-ldap-backup", Version="1"'}
def api(path,data=None):
 with opener.open(urllib.request.Request('https://jellyfin.home.rytim.com'+path,headers=h,data=None if data is None else json.dumps(data).encode()),timeout=20) as r:
  raw=r.read();return json.loads(raw) if raw else None
result=api('/Users/AuthenticateByName',{'Username':c['username'],'Pw':c['password']})
h['Authorization']+=', Token="'+result['AccessToken']+'"'
try:
 sessions=api('/Sessions')
 assert not any(s.get('NowPlayingItem') for s in sessions),'Active playback; stop before changes'
 assert result['User']['Name']=='ryan' and result['User']['Policy']['IsAdministrator']
finally:api('/Sessions/Logout',{})
script=PRELUDE+'''cd /share/Container/usenet/jellyfin-trial
test -f config/data/jellyfin.db
test "$("$docker" inspect usenet-jellyfin-trial-jellyfin-1 --format '{{.State.Health.Status}}')" = healthy
trap '"$docker" start usenet-jellyfin-trial-jellyfin-1 >/dev/null' EXIT
"$docker" stop -t 30 usenet-jellyfin-trial-jellyfin-1 >/dev/null
extra=
test ! -d config/identity || extra=config/identity
tar -cf - config/data config/config config/plugins compose.yaml .env web-config.json $extra
'''
r=subprocess.run(connection(),input=script.encode(),capture_output=True,timeout=240)
(PRIVATE/'jellyfin-backup.log').write_bytes(r.stderr)
if r.returncode:raise RuntimeError('Scoped backup failed; inspect private log')
with tarfile.open(fileobj=io.BytesIO(r.stdout)) as archive:
 assert 'config/data/jellyfin.db' in archive.getnames()
state=Path(os.environ.get('SMARTHOME_STATE_DIR',Path.home()/'.local/share/smarthome'))
age=Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
recipient=json.loads((state/'manifest.json').read_text())['recipient']
cipher=subprocess.check_output([str(age),'-r',recipient],input=r.stdout)
assert subprocess.check_output([str(age),'-d','-i',str(Path.home()/'.config/smarthome/recovery.agekey')],input=cipher)==r.stdout
path=state/'recovery'/time.strftime('jellyfin-'+phase+'-%Y%m%dT%H%M%SZ.tar.age',time.gmtime())
with path.open('xb') as stream:stream.write(cipher)
receipt={'archive':str(path),'sha256':hashlib.sha256(cipher).hexdigest(),'decryption':'passed','user_id':result['User']['Id'],'policy':result['User']['Policy']}
(PRIVATE/('jellyfin-'+phase+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS: cold Jellyfin settings/database/plugin snapshot encrypted off-host with exact decryption readback; only Jellyfin restarted')
