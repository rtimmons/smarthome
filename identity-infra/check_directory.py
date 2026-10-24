"""Verify authenticated LDAPS, denial cases, Kerberos, and AD's own SYSVOL.

This runs inside the DC with bootstrap credentials supplied only over stdin.
It never enumerates NAS share contents or prints credentials.
"""
import os
from pathlib import Path
import subprocess
import tempfile

os.umask(0o077)
environment = {**os.environ, 'LDAPTLS_CACERT': '/tls/ca.crt', 'LDAPTLS_REQCERT': 'demand',
               'LDAPTLS_REQSAN': 'demand', 'KRB5_CONFIG': '/etc/krb5.conf'}
with tempfile.TemporaryDirectory(dir='/run') as directory:
    directory = Path(directory)
    password = directory/'bind-password'
    password.write_text(bootstrap['ldap_bind'])
    dn = 'CN=svc-authelia,OU=Services,DC=ad,DC=home,DC=arpa'
    def bind(url, path):
        return subprocess.run(['ldapsearch','-LLL','-x','-o','nettimeout=10','-H',url,'-D',dn,
                               '-y',str(path),'-b','DC=ad,DC=home,DC=arpa',
                               '(sAMAccountName=svc-authelia)','sAMAccountName','memberOf'],
                              env=environment, capture_output=True, timeout=30)
    secure = bind('ldaps://dc1.ad.home.arpa', password)
    if secure.returncode or b'sAMAccountName: svc-authelia' not in secure.stdout:
        raise SystemExit('Verified LDAPS bind/search failed: '+secure.stderr.decode(errors='replace'))
    if b'Admins' in secure.stdout or b'Operators' in secure.stdout:
        raise SystemExit('LDAP bind account unexpectedly has administrative membership')
    wrong = directory/'wrong-password'; wrong.write_text('Synthetic-Wrong-Password-Only')
    if bind('ldaps://dc1.ad.home.arpa', wrong).returncode != 49:
        raise SystemExit('Wrong LDAP password was not rejected as invalid credentials')
    if bind('ldap://dc1.ad.home.arpa', password).returncode not in (8, 13):
        raise SystemExit('Unencrypted simple LDAP bind was not rejected')
    cache = 'FILE:'+str(directory/'ticket')
    environment['KRB5CCNAME'] = cache
    result = subprocess.run(['kinit','Administrator@AD.HOME.ARPA'],
                            input=(bootstrap['domain_admin']+'\n').encode(),
                            env=environment, capture_output=True, timeout=30)
    if result.returncode:
        raise SystemExit('Kerberos TGT acquisition failed: '+result.stderr.decode(errors='replace'))
    subprocess.run(['klist','-s'], env=environment, check=True, capture_output=True)
    result = subprocess.run(['smbclient','//dc1.ad.home.arpa/sysvol','-s','/data/etc/smb.conf',
                             '--use-kerberos=required','--use-krb5-ccache='+cache,
                             '-c','quit'],
                            env=environment, capture_output=True, timeout=30)
    if result.returncode:
        raise SystemExit('Kerberos-authenticated SYSVOL access failed: '+(result.stdout+result.stderr).decode(errors='replace'))
print('PASS: verified LDAPS; non-admin bind; wrong-password denial; cleartext-bind denial; Kerberos TGT; SYSVOL via Kerberos.')
