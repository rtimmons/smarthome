"""Offline identity and SYSVOL evidence, used only inside a Samba runtime."""
import hashlib
import json
import os
from pathlib import Path

from samba.auth import system_session
from samba.auth_util import system_session_unix
from samba.dcerpc import security
from samba.ntacls import NtaclsHelper
from samba.param import LoadParm
from samba.samdb import SamDB

EXPECTED_SID = 'S-1-5-21-2612071719-3246555018-4093554428'


def identity(root=Path('/data')):
    lp = LoadParm()
    lp.load(str(root/'etc/smb.conf'))
    db = SamDB(url=str(root/'private/sam.ldb'), session_info=system_session(), lp=lp)
    sid = str(db.get_domain_sid())
    if sid != EXPECTED_SID:
        raise RuntimeError('Directory SID differs; refusing migration')
    accounts = {}
    for row in db.search(base=str(db.domain_dn()), expression='(objectClass=user)',
                         attrs=['sAMAccountName','objectGUID','objectSid','unicodePwd','supplementalCredentials','memberOf','userAccountControl']):
        name = str(row['sAMAccountName'][0])
        accounts[name] = {key: sorted(hashlib.sha256(bytes(value)).hexdigest() for value in row.get(key, []))
                          for key in ('objectGUID','objectSid','unicodePwd','supplementalCredentials','memberOf','userAccountControl')}
    return {'domain_sid': sid, 'accounts': accounts}


def sysvol(root=Path('/data'), restore=None):
    helper = NtaclsHelper('sysvol', str(root/'etc/smb.conf'), security.dom_sid(EXPECTED_SID))
    session = system_session_unix()
    base = root/'state/sysvol'
    paths = [base, *sorted(base.rglob('*'))]
    if restore is not None:
        contents = {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
                    for path in paths if not path.is_symlink() and (path.is_file() or path.is_dir())}
        if len(contents) != len(paths) or contents != {name: value['sha256'] for name, value in restore.items()}:
            raise RuntimeError('SYSVOL contents differ; refusing to apply saved permissions')
    result = {}
    for path in paths:
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise RuntimeError('Unexpected SYSVOL entry type')
        relative = str(path.relative_to(base))
        if restore is not None:
            helper.setntacl(str(path), restore[relative]['sddl'], session)
        result[relative] = {'sddl': helper.getntacl(str(path), session, as_sddl=True),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}
    if restore is not None and result != restore:
        raise RuntimeError('Restored SYSVOL content or Windows permissions differ')
    return result


def checkpoint(root=Path('/data')):
    """Save portable ACLs after Samba stops, before HA captures a cold backup."""
    directory = (root/'state/sysvol').stat()
    saved = {'identity': identity(root), 'sysvol': sysvol(root),
             'root_device_inode': [directory.st_dev, directory.st_ino]}
    temporary = root/'sysvol-checkpoint.new'
    with temporary.open('w') as output:
        os.chmod(temporary, 0o600)
        json.dump(saved, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(root/'sysvol-checkpoint.json')


def recover_checkpoint(root=Path('/data')):
    """Rebind xattr_tdb ACLs only when a cold restore changed the filesystem."""
    path = root/'sysvol-checkpoint.json'
    if not path.exists():
        # Initial, already verified cold migration; never silently accept an
        # arbitrary restored directory lacking portable permissions.
        saved = json.loads((root/'migration-evidence.json').read_text())
        if sysvol(root) != saved['sysvol']:
            raise RuntimeError('Initial migrated SYSVOL differs')
        checkpoint(root)
        return
    saved = json.loads(path.read_text())
    directory = (root/'state/sysvol').stat()
    if [directory.st_dev, directory.st_ino] == saved['root_device_inode']:
        return
    if identity(root) != saved['identity']:
        raise RuntimeError('Restored identities differ from the cold-backup checkpoint')
    sysvol(root, restore=saved['sysvol'])
    checkpoint(root)
