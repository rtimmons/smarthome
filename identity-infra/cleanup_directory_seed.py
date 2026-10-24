"""Remove only preserved directory transport keys after native backup verification."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from backup_ha import ssh
from manage import PRIVATE


def main():
    receipt=json.loads((PRIVATE/'ha-backup-receipt.json').read_text())
    cipher=Path(receipt['archive']).read_bytes()
    if hashlib.sha256(cipher).hexdigest()!=receipt['ciphertext_sha256']:
        raise RuntimeError('HA recovery archive changed')
    age=Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain=subprocess.check_output([str(age),'-d','-i',str(Path.home()/'.config/smarthome/recovery.agekey')],input=cipher)
    values={}
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        for app in ('local_directory','local_directory_route'):
            member=next(m for m in outer.getmembers() if m.name in (app+'.tar.gz',app+'.tar'))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as inner:
                values[app]=[inner.extractfile(m).read() for m in inner.getmembers() if m.isfile()]
    seeds={name:(PRIVATE/'vm'/name).read_bytes() for name in ('ssh_host_ed25519_key','ssh_host_ed25519_key.pub')}
    seeds['operator.pub']=(PRIVATE/'vm/id_ed25519_dc_vm.pub').read_bytes()
    seeds['preparation.json']=(json.dumps({'address':'192.168.1.11'})+'\n').encode()
    if any(data not in values['local_directory'] for data in seeds.values()):
        raise RuntimeError('Directory seed missing from native persistent backup')
    if seeds['ssh_host_ed25519_key.pub'] not in values['local_directory_route']:
        raise RuntimeError('Route public identity missing from persistent backup')
    script='set -eu\ntest ! -L /ssl/smarthome/directory-seed\n'
    for name,data in seeds.items():
        path='/ssl/smarthome/directory-seed/'+name
        script+=f"test ! -L '{path}'\nif test -e '{path}'; then test \"$(sha256sum '{path}' | cut -d ' ' -f 1)\" = '{hashlib.sha256(data).hexdigest()}'; fi\n"
    for name in seeds:
        script+="rm -f '/ssl/smarthome/directory-seed/"+name+"'\n"
    script+='test ! -d /ssl/smarthome/directory-seed || rmdir /ssl/smarthome/directory-seed\n'
    ssh(script)
    print('Verified directory transport seed removed; persistent app identities and encrypted recovery retained.')


if __name__=='__main__':main()
