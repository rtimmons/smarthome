#!/usr/bin/python3
"""Provision once; no secret in command arguments, environment, or logs."""
import json
import logging
import os
import re
from pathlib import Path
from samba.auth import system_session
from samba.param import LoadParm
from samba.provision import provision

os.umask(0o077)
state = Path('/data')
marker = state / 'identity.json'
settings = {'realm': 'AD.HOME.ARPA', 'domain': 'SMARTHOME', 'hostname': 'dc1', 'hostip': '192.168.1.10'}
if marker.exists():
    if json.loads(marker.read_text()) != settings:
        raise SystemExit('Existing domain identity differs; refusing reprovision.')
    if not (state / 'private/sam.ldb').is_file():
        raise SystemExit('Existing domain is incomplete; restore it, never reprovision.')
    raise SystemExit(0)
if any(state.iterdir()):
    raise SystemExit('Provision requires an empty state directory.')
password = Path('/run/secrets/domain-admin').read_text().strip()
if len(password) < 32:
    raise SystemExit('Domain administrator password is missing or too short.')
logger = logging.getLogger('provision')
logger.addHandler(logging.NullHandler())
logger.propagate = False
parameters = LoadParm()
# Samba's database-backed extended attributes retain Windows ACLs without
# granting this container CAP_SYS_ADMIN on the NAS.
parameters.set('vfs objects', 'dfs_samba4 acl_xattr xattr_tdb')
parameters.set('xattr_tdb:file', '/data/state/xattr.tdb')
result = provision(logger, session_info=system_session(), targetdir=str(state),
                   realm=settings['realm'], domain=settings['domain'],
                   hostname=settings['hostname'], hostip=settings['hostip'],
                   serverrole='active directory domain controller', dns_backend='SAMBA_INTERNAL',
                   use_rfc2307=True, adminpass=password, lp=parameters,
                   skip_sysvolacl=False)
config = state / 'etc/smb.conf'
text = config.read_text()
text = re.sub(r'^\s*dns forwarder\s*=.*$', '', text, flags=re.MULTILINE)
text = text.replace('[global]', '''[global]
    dns forwarder = 192.168.1.1
    interfaces = lo eth0
    bind interfaces only = yes
    rpc server dynamic port range = 50000-50050
    ldap server require strong auth = yes
    server min protocol = SMB2_02
    ntlm auth = ntlmv2-only
    tls keyfile = /tls/dc.key
    tls certfile = /tls/dc-chain.crt
    tls cafile = /tls/ca.crt
''')
config.write_text(text)
marker.write_text(json.dumps(settings, indent=2) + '\n')
print('Domain provisioned; existing identities are never overwritten.')
