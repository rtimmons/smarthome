"""Initialize only the dedicated read-only LDAP identity and empty access groups.

The caller supplies bootstrap over stdin, never command arguments.
"""
import hashlib
import json
from pathlib import Path

import ldb
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

lp = LoadParm()
lp.load('/data/etc/smb.conf')
db = SamDB(url='/data/private/sam.ldb', session_info=system_session(), lp=lp)
base = str(db.domain_dn())
marker = Path('/data/authelia-bind.json')
identity = {'username': 'svc-authelia', 'password_sha256': hashlib.sha256(bootstrap['ldap_bind'].encode()).hexdigest()}
if marker.exists():
    if json.loads(marker.read_text()) != identity:
        raise SystemExit('LDAP identity differs; refusing an implicit credential change.')
    if len(db.search(base=base, expression='(sAMAccountName=svc-authelia)', attrs=['dn'])) != 1:
        raise SystemExit('Saved LDAP identity is absent; manual recovery required.')
else:
    existing = db.search(base=base, expression='(sAMAccountName=svc-authelia)', attrs=['description', 'memberOf'])
    if existing:
        if not bootstrap.get('resume_created_identity'):
            raise SystemExit('An unmanaged LDAP identity already exists; refusing to take it over.')
        account = existing[0]
        if (str(account.dn) != 'CN=svc-authelia,OU=Services,'+base or
                bytes(account.get('description', [b''])[0]) != b'Read-only directory lookup for household Authelia' or
                account.get('memberOf')):
            raise SystemExit('Partial identity differs from the known failed initialization; refusing recovery.')
    for unit in ('People', 'Groups', 'Services'):
        dn = f'OU={unit},{base}'
        try:
            db.search(base=dn, scope=ldb.SCOPE_BASE, attrs=['dn'])
        except ldb.LdbError as error:
            if error.args[0] != ldb.ERR_NO_SUCH_OBJECT:
                raise
            db.create_ou(dn)
    if not existing:
        db.newuser('svc-authelia', bootstrap['ldap_bind'], userou='OU=Services',
                   description='Read-only directory lookup for household Authelia',
                   useusernameascn=True)
    # No administrative membership or password-write delegation is granted.
    db.setexpiry('(sAMAccountName=svc-authelia)', 0, no_expiry_req=True)
    account = db.search(base=base, expression='(sAMAccountName=svc-authelia)', attrs=['userAccountControl'])[0]
    db.modify(ldb.Message.from_dict(db, {'dn': account.dn,
              'userAccountControl': str(int(account['userAccountControl'][0]) | 0x10000)}, ldb.FLAG_MOD_REPLACE))
    # Ordinary accounts must not be able to enroll arbitrary domain machines.
    db.modify(ldb.Message.from_dict(db, {'dn': ldb.Dn(db, base),
              'ms-DS-MachineAccountQuota': '0'}, ldb.FLAG_MOD_REPLACE))
    marker.write_text(json.dumps(identity, indent=2)+'\n')
    marker.chmod(0o600)
for group in ('nas-users', 'git-users', 'arr-users'):
    if not db.search(base=base, expression=f'(sAMAccountName={group})', attrs=['dn']):
        db.newgroup(group, groupou='OU=Groups', description='Explicit household access group')
print('LDAP service identity and empty access groups verified; no human access changed.')
