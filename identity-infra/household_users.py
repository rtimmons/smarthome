"""Create explicitly selected human identities once, without resetting passwords.

Executed inside Samba with private bootstrap supplied over SSH stdin.
"""
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
marker = Path('/data/household-users.json')
users = bootstrap['users']
allowed = {'nas-users', 'nas-timemachine', 'nas-multimedia-writers', 'git-users', 'arr-users'}
for user in users:
    if user['username'] not in ('ryantimmons', 'michaellee') or set(user['groups']) - allowed:
        raise RuntimeError('Unreviewed account or access group')


def account(username):
    result = db.search(base=base, expression='(sAMAccountName='+username+')',
                       attrs=['objectGUID', 'memberOf', 'userAccountControl'])
    return result[0] if result else None


if marker.exists():
    saved = json.loads(marker.read_text())
    if set(saved) != {user['username'] for user in users}:
        raise RuntimeError('Existing household identity inventory differs')
    for user in users:
        found = account(user['username'])
        if found is None or bytes(found['objectGUID'][0]).hex() != saved[user['username']]:
            raise RuntimeError('Existing household identity differs; restore it instead of recreating it')
    print('Existing human identities preserved; no passwords or memberships changed.')
else:
    if any(account(user['username']) is not None for user in users):
        raise RuntimeError('Unmanaged existing human account; refusing takeover')
    db.transaction_start()
    try:
        for group in sorted({group for user in users for group in user['groups']}):
            if not db.search(base=base, expression='(sAMAccountName='+group+')', attrs=['dn']):
                db.newgroup(group, groupou='OU=Groups', description='Explicit household access group')
        for user in users:
            db.newuser(user['username'], user['initial_password'], userou='OU=People',
                       givenname=user['given_name'], surname=user['surname'],
                       mailaddress=user.get('email'), useusernameascn=True,
                       description='Household identity; existing local NAS access retained during migration')
            found = account(user['username'])
            # Long unique passwords are retained until deliberately changed;
            # unattended expiry must not strand SMB clients. Browser use adds MFA.
            db.modify(ldb.Message.from_dict(db, {'dn': found.dn,
                'userAccountControl': str(int(found['userAccountControl'][0]) | 0x10000)}, ldb.FLAG_MOD_REPLACE))
            for group in user['groups']:
                db.add_remove_group_members(group, [user['username']])
        identities = {user['username']: bytes(account(user['username'])['objectGUID'][0]).hex()
                      for user in users}
        db.transaction_commit()
    except Exception:
        db.transaction_cancel()
        raise
    marker.write_text(json.dumps(identities, indent=2)+'\n')
    marker.chmod(0o600)
    print('Two household AD identities created; no NAS share permissions changed.')
