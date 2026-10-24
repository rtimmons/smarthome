"""Test only named synthetic fixtures; never list or read household content."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

os.umask(0o077)
fixture=bootstrap['fixture']
payload=bootstrap['payload'].encode()
users={user['username']:user['initial_password'] for user in bootstrap['users']}
users['svc-authelia']=bootstrap['ldap_bind']
passed=[]
with tempfile.TemporaryDirectory(dir='/run') as temporary:
    temporary=Path(temporary)
    source=temporary/'synthetic.txt';source.write_bytes(payload)
    def smb(user,share,operation,denied=False):
        credentials=temporary/'credentials'
        credentials.write_text('username = '+user+'\npassword = '+users[user]+'\ndomain = SMARTHOME\n')
        result=subprocess.run(['smbclient','//192.168.1.66/'+share,'-A',str(credentials),
                               '--client-protection=encrypt','-m','SMB3','-c',operation],
                              capture_output=True,timeout=30)
        output=result.stdout+result.stderr
        if denied:
            if b'NT_STATUS_ACCESS_DENIED' not in output:
                raise RuntimeError('Expected SMB denial did not occur: '+user+'/'+share)
        elif result.returncode or b'NT_STATUS_' in output:
            raise RuntimeError('SMB operation failed: '+user+'/'+share+' '+output.decode(errors='replace'))
    for user in ('ryantimmons','michaellee'):
        for share in ('Container','Usenet'):
            smb(user,share,'quit',denied=True)
            passed.append(user+': '+share+' denied')
        for share in ('Public','Multimedia'):
            destination=temporary/'download.txt'
            smb(user,share,'get '+fixture+'/read.txt '+str(destination))
            if destination.read_bytes()!=payload:
                raise RuntimeError('Synthetic SMB read differs')
            destination.unlink()
            writable=share=='Multimedia' and user=='michaellee'
            name=fixture+'/write-'+user+'.txt'
            smb(user,share,'put '+str(source)+' '+name,denied=not writable)
            if writable:
                smb(user,share,'get '+name+' '+str(destination))
                if destination.read_bytes()!=payload: raise RuntimeError('Synthetic write readback differs')
                destination.unlink()
                smb(user,share,'del '+name)
            passed.append(user+': '+share+(' read/write' if writable else ' read-only'))
        for share in ('FromDrobo','SpaceBlackTimeMachine'):
            if share=='SpaceBlackTimeMachine' and user=='michaellee':
                smb(user,share,'quit',denied=True)
                passed.append(user+': '+share+' denied')
                continue
            owned=fixture+'-'+user
            smb(user,share,'mkdir '+owned)
            name=owned+'/synthetic.txt'
            destination=temporary/'download.txt'
            smb(user,share,'put '+str(source)+' '+name)
            smb(user,share,'get '+name+' '+str(destination))
            if destination.read_bytes()!=payload: raise RuntimeError('Synthetic write readback differs')
            destination.unlink()
            smb(user,share,'del '+name)
            smb(user,share,'rmdir '+owned)
            passed.append(user+': '+share+' create/read/write/delete')
    for share in ('Public','FromDrobo','Multimedia','Container','Usenet','SpaceBlackTimeMachine'):
        smb('svc-authelia',share,'quit',denied=True)
        passed.append('LDAP-only service: '+share+' denied')
for check in passed:
    print('PASS:',check)
print('All SMB checks used encrypted SMB3 and synthetic fixtures only.')
