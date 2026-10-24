"""Restore native HA directory data offline, including portable SYSVOL ACLs."""
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile

from ha_directory import connection
from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    receipt=json.loads((PRIVATE/'ha-backup-receipt.json').read_text())
    if 'local_directory' not in receipt['apps']:
        raise RuntimeError('A native HA directory backup is required')
    cipher=Path(receipt['archive']).read_bytes()
    if hashlib.sha256(cipher).hexdigest()!=receipt['ciphertext_sha256']:
        raise RuntimeError('Encrypted HA archive changed')
    age=Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain=subprocess.check_output([str(age),'-d','-i',str(Path.home()/'.config/smarthome/recovery.agekey')],input=cipher)
    with tarfile.open(fileobj=io.BytesIO(plain)) as outer:
        member=next(m for m in outer.getmembers() if m.name in ('local_directory.tar.gz','local_directory.tar'))
        inner_bytes=outer.extractfile(member).read()
    script = r'''import json,os,subprocess,tarfile
from pathlib import Path
from directory_state import recover_checkpoint, identity, sysvol
os.umask(0o077)
trial=Path('/data/native-restore-trial')
root=trial/'restored'
root.mkdir(mode=0o700)
with tarfile.open(trial/'directory-backup.tar') as archive:
    for member in archive.getmembers():
        name=member.name.removeprefix('./')
        if not name.startswith('data/'):
            continue
        relative=Path(name.removeprefix('data/'))
        if not relative.parts:
            continue
        if relative.is_absolute() or '..' in relative.parts or member.issym() or member.islnk():
            raise RuntimeError('Unexpected native backup entry')
        if member.isdir():
            (root/relative).mkdir(parents=True,exist_ok=True,mode=member.mode)
        elif member.isfile():
            target=root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            os.chmod(target,member.mode)
            os.chown(target,member.uid,member.gid)
        else:
            raise RuntimeError('Unexpected native backup file type')
saved=json.loads((root/'sysvol-checkpoint.json').read_text())
config=root/'etc/smb.conf'
config.write_text(config.read_text().replace('/data/',str(root)+'/'))
assert identity(root)==saved['identity']
assert [root.stat().st_dev,(root/'state/sysvol').stat().st_ino]!=saved['root_device_inode']
recover_checkpoint(root)
assert sysvol(root)==saved['sysvol']
with (trial/'verification.log').open('wb') as log:
    for command in [['samba-tool','dbcheck','-s',str(config)],['samba-tool','ntacl','sysvolcheck','-s',str(config)]]:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
assert identity(root)==saved['identity']
receipt={'native_ha_restore':'passed','domain_and_accounts':'identical','sysvol_content_and_acls':'identical','database_check':'passed','restored_listener_started':False}
(trial/'receipt.json').write_text(json.dumps(receipt)+'\n')
print(json.dumps(receipt))
'''
    bundle=io.BytesIO()
    with tarfile.open(fileobj=bundle,mode='w') as archive:
        for name,data in {'directory-backup.tar':inner_bytes,'trial.py':script.encode(),
                          'directory_state.py':(ROOT/'identity-infra/directory_state.py').read_bytes()}.items():
            item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o600
            archive.addfile(item,io.BytesIO(data))
    command=connection()
    command[-1]='sudo -n sh -c '+shlex.quote('umask 077; test ! -e /data/native-restore-trial && mkdir -m 700 /data/native-restore-trial && tar -xf - -C /data/native-restore-trial')
    result=subprocess.run(command,input=bundle.getvalue(),capture_output=True,timeout=120)
    if result.returncode:
        (PRIVATE/'ha-native-restore-trial.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('Native restore-trial staging failed')
    command[-1]='sudo -n python3 /data/native-restore-trial/trial.py'
    result=subprocess.run(command,capture_output=True,timeout=180)
    (PRIVATE/'ha-native-restore-trial.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('Native HA directory restore trial failed; original directory remains unchanged')
    (PRIVATE/'ha-native-restore-receipt.json').write_bytes(result.stdout)
    print(result.stdout.decode(),end='')


if __name__=='__main__':
    main()
