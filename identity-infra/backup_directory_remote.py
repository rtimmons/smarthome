"""Consistent Samba backup and an isolated, non-listening restore verification."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

os.umask(0o077)
root = Path('/data/backups')
root.mkdir(exist_ok=True, mode=0o700)
before = set(root.glob('samba-backup-*.tar.bz2'))


def identity(path):
    lp = LoadParm(); lp.load(str(path/'etc/smb.conf'))
    db = SamDB(url=str(path/'private/sam.ldb'), session_info=system_session(), lp=lp)
    accounts = {}
    names = ['Administrator', 'svc-authelia']
    # Restore creates a replacement DC. Human and member-machine credentials
    # must retain their exact values, including QNAP's domain trust secret.
    people = db.search(base='OU=People,'+str(db.domain_dn()),
                       expression='(objectClass=user)', attrs=['sAMAccountName'])
    machines = db.search(base=str(db.domain_dn()),
        expression='(&(objectClass=computer)(!(userAccountControl:1.2.840.113556.1.4.803:=8192)))',
        attrs=['sAMAccountName'])
    names.extend(str(row['sAMAccountName'][0]) for row in [*people, *machines])
    for name in names:
        rows = db.search(base=str(db.domain_dn()), expression=f'(sAMAccountName={name})',
                         attrs=['objectSid','unicodePwd','supplementalCredentials','memberOf'])
        if len(rows) != 1 or len(rows[0].get('unicodePwd', [b''])[0]) != 16:
            raise RuntimeError('Could not verify account credentials in the backup')
        accounts[name] = {attribute: hashlib.sha256(bytes(rows[0][attribute][0])).hexdigest()
                          for attribute in ('objectSid','unicodePwd','supplementalCredentials')}
        accounts[name]['groups'] = sorted(str(value) for value in rows[0].get('memberOf', []))
    return {'domain_sid': str(db.get_domain_sid()), 'accounts': accounts}


original = identity(Path('/data'))
with (root/'verification.log').open('wb') as log:
    subprocess.run(['samba-tool','domain','backup','offline','--targetdir='+str(root),
                    '-s','/data/etc/smb.conf'], stdout=log, stderr=subprocess.STDOUT, check=True)
    created = set(root.glob('samba-backup-*.tar.bz2')) - before
    if len(created) != 1:
        raise RuntimeError('Backup did not produce exactly one new archive')
    backup = created.pop()
    # Use a separate directory and ACL database; never point the restored
    # configuration at the live domain's customized state paths.
    with tempfile.TemporaryDirectory(prefix='.identity-restore-', dir=root) as temporary:
        restored = Path(temporary)/'restored'
        restore_config = Path(temporary)/'restore.conf'
        restore_config.write_text(Path('/data/etc/smb.conf').read_text().replace('/data/', str(restored)+'/'))
        subprocess.run(['samba-tool','domain','backup','restore','--backup-file='+str(backup),
                        '--targetdir='+str(restored),'--newservername=restore-dc',
                        '--host-ip=127.0.0.2','--configfile='+str(restore_config)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['samba-tool','dbcheck','-s',str(restored/'etc/smb.conf')],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['samba-tool','ntacl','sysvolcheck','-s',str(restored/'etc/smb.conf')],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        if identity(restored) != original:
            raise RuntimeError('Restored domain SID, account SIDs, or credentials differ')
    receipt = {'domain_sid': original['domain_sid'], 'restore_database_check': 'passed',
               'restored_sysvol_permissions': 'passed',
               'account_sids_and_password_material': 'identical',
               'restored_directory_started': False, 'archive': backup.name}
    (root/'latest-verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
output = io.BytesIO()
with tarfile.open(fileobj=output, mode='w') as archive:
    for path in (backup, Path('/data/identity.json'), Path('/data/authelia-bind.json'), root/'latest-verification.json'):
        archive.add(path, arcname=path.name, recursive=False)
    for name in ('household-users.json', 'sysvol-acl.json'):
        path = Path('/data')/name
        if path.exists():
            archive.add(path, arcname=name, recursive=False)
sys.stdout.buffer.write(output.getvalue())
