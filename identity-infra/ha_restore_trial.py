"""Verify the existing encrypted AD backup inside HA without starting a DC."""
import hashlib
import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

from ha_directory import connection
from manage import PRIVATE


def main():
    os.umask(0o077)
    receipt = json.loads((PRIVATE/'directory-backup-receipt.json').read_text())
    encrypted = Path(receipt['archive']).read_bytes()
    if hashlib.sha256(encrypted).hexdigest() != receipt['ciphertext_sha256']:
        raise RuntimeError('Encrypted recovery archive changed')
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain = subprocess.check_output([str(age), '-d', '-i', str(Path.home()/'.config/smarthome/recovery.agekey')], input=encrypted)
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        backups = [member for member in outer.getmembers() if member.name.startswith('samba-backup-') and member.name.endswith('.tar.bz2') and member.isfile()]
        if len(backups) != 1:
            raise RuntimeError('Expected one verified Samba archive')
        backup = outer.extractfile(backups[0]).read()
    with tarfile.open(fileobj=io.BytesIO(backup), mode='r:bz2') as archive:
        config = archive.extractfile('etc/smb.conf').read().decode()
    root = '/data/restore-trial'
    config = config.replace('/data/', root+'/restored/')
    script = '''import json, subprocess
from pathlib import Path
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB
root = Path('/data/restore-trial')
assert not Path('/data/private/sam.ldb').exists()
assert not Path('/data/migration-ready.json').exists()
with (root/'trial.log').open('wb') as log:
    for command in [
        ['samba-tool','domain','backup','restore','--backup-file='+str(root/'backup.tar.bz2'),
         '--targetdir='+str(root/'restored'),'--newservername=restore-test','--host-ip=127.0.0.2','--configfile='+str(root/'restore.conf')],
        ['samba-tool','dbcheck','-s',str(root/'restored/etc/smb.conf')],
        ['samba-tool','ntacl','sysvolcheck','-s',str(root/'restored/etc/smb.conf')]]:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
lp=LoadParm(); lp.load(str(root/'restored/etc/smb.conf'))
db=SamDB(url=str(root/'restored/private/sam.ldb'),session_info=system_session(),lp=lp)
assert str(db.get_domain_sid()) == 'S-1-5-21-2612071719-3246555018-4093554428'
receipt={'database_check':'passed','sysvol_permissions':'passed','domain_sid':'preserved','restored_listener_started':False}
(root/'receipt.json').write_text(json.dumps(receipt)+'\\n')
print(json.dumps(receipt))
'''
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode='w') as archive:
        for name, data in {'backup.tar.bz2': backup, 'restore.conf': config.encode(), 'trial.py': script.encode()}.items():
            item=tarfile.TarInfo(name); item.size=len(data); item.mode=0o600
            archive.addfile(item, io.BytesIO(data))
    command = connection()
    command[-1] = "sudo -n sh -c "+shlex.quote(f'umask 077; test ! -e {root} && mkdir -m 700 {root} && tar -xf - -C {root}')
    result = subprocess.run(command, input=bundle.getvalue(), capture_output=True, timeout=120)
    if result.returncode:
        (PRIVATE/'ha-restore-trial.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('HA restore trial staging failed')
    command[-1] = 'sudo -n python3 /data/restore-trial/trial.py'
    result = subprocess.run(command, capture_output=True, timeout=300)
    (PRIVATE/'ha-restore-trial.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('HA offline restore trial failed; see private log')
    print(result.stdout.decode(), end='')


if __name__ == '__main__':
    main()
