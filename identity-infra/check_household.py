"""Migration-only verification using the initial private household credentials."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

os.umask(0o077)
environment = {**os.environ, 'LDAPTLS_CACERT': '/tls/ca.crt', 'LDAPTLS_REQCERT': 'demand',
               'LDAPTLS_REQSAN': 'demand', 'KRB5_CONFIG': '/etc/krb5.conf'}
with tempfile.TemporaryDirectory(dir='/run') as temporary:
    temporary = Path(temporary)
    password = temporary/'password'
    for user in bootstrap['users']:
        name = user['username']
        if name not in ('ryantimmons', 'michaellee'):
            raise RuntimeError('Unexpected household principal')
        password.write_text(user['initial_password'])
        result = subprocess.run(['ldapsearch', '-LLL', '-x', '-o', 'nettimeout=10',
            '-H', 'ldaps://dc1.ad.home.arpa', '-D', name+'@ad.home.arpa', '-y', str(password),
            '-b', 'OU=People,DC=ad,DC=home,DC=arpa', '(sAMAccountName='+name+')',
            'sAMAccountName', 'memberOf'], env=environment, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError('Household LDAPS authentication failed; no credential reset attempted')
        groups = set(re.findall(r'^memberOf: CN=([^,]+),', result.stdout.decode(), re.MULTILINE))
        if groups != set(user['groups']):
            raise RuntimeError('Household group memberships differ from approved access')
        environment['KRB5CCNAME'] = 'FILE:'+str(temporary/('ticket-'+name))
        result = subprocess.run(['kinit', name+'@AD.HOME.ARPA'],
            input=(user['initial_password']+'\n').encode(), env=environment,
            capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError('Household Kerberos authentication failed; no credential reset attempted')
        subprocess.run(['klist', '-s'], env=environment, check=True, capture_output=True)
print('PASS: both household LDAPS and Kerberos logins; exact approved group memberships.')
