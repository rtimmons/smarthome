#!/usr/bin/env python3
"""Check the existing wiki credential and network denials without changing access."""
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from ha_directory import connection as directory_connection
from manage import PRIVATE
from wiki_credentials import CredentialError, password_from_vault

SHARES = ('Container', 'FromDrobo', 'homes', 'Multimedia', 'Public',
          'SpaceBlackTimeMachine', 'Usenet')
DENIALS = {'NT_STATUS_ACCESS_DENIED', 'NT_STATUS_ACCOUNT_DISABLED',
           'NT_STATUS_ACCOUNT_RESTRICTION'}


class CheckError(RuntimeError):
    """Only fixed, nonsecret diagnostics may be shown to the operator."""


AUTOMATED_BUDGET = 55


class Budget:
    """Bound network work across stages; hidden password entry is not timed."""
    def __init__(self):
        self.elapsed = 0.0
        self.stages = {}

    def call(self, stage, operation, limit):
        remaining = AUTOMATED_BUDGET - self.elapsed
        if remaining <= 0:
            raise CheckError('Automated access-check budget exhausted; result inconclusive')
        started = time.monotonic()
        try:
            return operation(min(limit, remaining))
        except subprocess.TimeoutExpired:
            raise CheckError(stage + ' timed out; access result inconclusive') from None
        finally:
            duration = time.monotonic() - started
            self.elapsed += duration
            self.stages[stage] = round(duration, 3)

    def run(self, stage, command, *, limit, **kwargs):
        return self.call(stage, lambda timeout: subprocess.run(command, timeout=timeout, **kwargs), limit)


def classify_smb(code, output):
    """A bad password, timeout or transport error is never a passing denial."""
    statuses = re.findall(r'NT_STATUS_[A-Z0-9_]+', output)
    if code == 0 or len(statuses) != 1 or statuses[0] not in DENIALS:
        raise CheckError('SMB result is not a qualified access denial')
    if 'tree connect failed:' in output:
        return {'phase': 'authenticated-tree-connect', 'status': statuses[0]}
    if 'session setup failed:' in output:
        return {'phase': 'session-setup', 'status': statuses[0]}
    raise CheckError('SMB denial phase is unknown')


def ssh_denied(result):
    return (result.returncode == 255 and not result.stdout
            and b'Permission denied (' in result.stderr
            and b'Host key verification failed' not in result.stderr)


def prepare_smb_transport(budget=None):
    budget = budget or Budget()
    try:
        command = budget.call('HA directory discovery', lambda timeout: directory_connection(timeout=timeout), 10)
    except CheckError:
        raise
    except RuntimeError:
        raise CheckError('Dedicated HA/directory transport unavailable; no password requested. '
                         'Follow AGENTS.md for dedicated-key repair before retrying') from None
    probe = b'''python3 - <<'WIKI_CLIENT_CHECK'
import shutil
from samba.credentials import Credentials
assert shutil.which('smbclient')
c=Credentials();c.set_password('synthetic-readiness-check')
assert len(c.get_nt_hash())==16
print('wiki-smb-client-ready')
WIKI_CLIENT_CHECK
'''
    result = budget.run('SMB client readiness', command, input=probe, capture_output=True, limit=10)
    if result.returncode or result.stdout.strip() != b'wiki-smb-client-ready':
        raise CheckError('Pinned directory SMB client unavailable; no password requested')
    return command


def smb_checks(password, command, budget=None):
    budget = budget or Budget()
    # Use the existing pinned directory maintenance transport and installed SMB
    # client. No directory database is opened or changed. The password travels
    # over SSH stdin, never argv, and exists remotely only in private /run temp.
    # Observed QNAP local SAM realm; do not send this local account through AD.
    values = {'password': password, 'realm': 'RYNAPQNAP', 'shares': SHARES}
    remote = 'values = ' + repr(values) + '\n' + '''
import json,os,subprocess,tempfile,time
from pathlib import Path
os.umask(0o077)
results=[]
deadline=time.monotonic()+25
with tempfile.TemporaryDirectory(prefix='wiki-denial-',dir='/run') as directory:
 auth=Path(directory)/'credentials'
 auth.write_text('username = svc-wiki\\npassword = '+values['password']+'\\ndomain = '+values['realm']+'\\n')
 for share in values['shares']:
  try:
   r=subprocess.run(['smbclient','//192.168.1.66/'+share,'-A',str(auth),
    '--client-protection=encrypt','-m','SMB3','-c','quit'],capture_output=True,
    timeout=max(0.01,min(20,deadline-time.monotonic())))
  except subprocess.TimeoutExpired:
   print(json.dumps({'error':'SMB client timed out'}));raise SystemExit(0)
  output=(r.stdout+r.stderr).decode(errors='replace')
  results.append({'share':share,'code':r.returncode,'output':output})
  # A session refusal applies before any share selection. Do not repeat it or
  # risk lockout; tree-connect denials qualify the individual share instead.
  if 'tree connect failed:' not in output: break
print(json.dumps({'results':results}))
'''
    result = budget.run('SMB denial probes', command, input=("python3 - <<'WIKI_ACCESS_CHECK'\n" + remote
                            + '\nWIKI_ACCESS_CHECK\n').encode(), capture_output=True, limit=30)
    if result.returncode:
        raise CheckError('Pinned SMB probe failed; no raw credential-bearing output saved')
    value = json.loads(result.stdout)
    if value.get('error') == 'SMB client timed out':
        raise CheckError('SMB client timed out; access result inconclusive')
    checks = [dict(share=row['share'], **classify_smb(row['code'], row['output']))
              for row in value['results']]
    if not checks or (checks[-1]['phase'] == 'authenticated-tree-connect'
                      and [c['share'] for c in checks] != list(SHARES)):
        raise CheckError('Incomplete SMB share denial check')
    return checks


def ssh_check(password, budget=None):
    budget = budget or Budget()
    target = os.environ['QNAP_SSH_TARGET'].split('@', 1)[1]
    hosts = Path(os.environ['QNAP_SSH_KNOWN_HOSTS']).expanduser().resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='wiki-ssh-denial-') as directory:
        root = Path(directory)
        secret = root/'password'; secret.write_text(password+'\n'); secret.chmod(0o600)
        prompted = root/'prompted'
        askpass = root/'askpass'
        askpass.write_text('#!/bin/sh\n: > "$WIKI_CHECK_PROMPT_MARKER"\nexec /bin/cat "$WIKI_CHECK_PASSWORD_FILE"\n')
        askpass.chmod(0o700)
        env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force',
                   DISPLAY='wiki-access-check', WIKI_CHECK_PASSWORD_FILE=str(secret),
                   WIKI_CHECK_PROMPT_MARKER=str(prompted))
        args = ['ssh', '-F', '/dev/null', '-T', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile='+str(hosts), '-o', 'GlobalKnownHostsFile=/dev/null',
                '-o', 'IdentityAgent=none', '-o', 'IdentitiesOnly=yes',
                '-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=password',
                '-o', 'KbdInteractiveAuthentication=no', '-o', 'NumberOfPasswordPrompts=1',
                '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
                '--', 'svc-wiki@'+target, 'id -u']
        result = budget.run('SSH login denial', args, stdin=subprocess.DEVNULL, capture_output=True,
                            env=env, limit=10)
        password_prompted = prompted.exists()
    if not password_prompted or not ssh_denied(result):
        raise CheckError('SSH did not return a qualified login denial')
    return {'stored_credential_login_denied': True, 'password_prompted': password_prompted,
            'session_created': False}


def main():
    os.umask(0o077)
    budget = Budget()
    print('Checking the SOPS-backed wiki credential...', flush=True)
    password = password_from_vault(budget)
    print('Checking dedicated transports (55-second automated budget; password entry excluded)...', flush=True)
    command = prepare_smb_transport(budget)
    print('Checking the password and encrypted SMB denials...', flush=True)
    checks = smb_checks(password, command, budget)
    print('Checking one SSH login denial...', flush=True)
    ssh = ssh_check(password, budget)
    receipt = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
               'account': 'svc-wiki', 'realm': 'QNAP-local', 'uid': 1005,
               'credential_source': 'SOPS',
               'password_matches_existing_samba_credential': None,
               'smb3_encryption_required': True, 'smb': checks, 'ssh': ssh,
               'permissions_changed': False, 'household_files_read': False,
               'automated_seconds': round(budget.elapsed, 3), 'stage_seconds': budget.stages}
    output = PRIVATE/'wiki-access'
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = output/(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    with path.open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    print(json.dumps(receipt, indent=2))
    print('Private sanitized receipt:', path)


if __name__ == '__main__':
    try:
        main()
    except (CheckError, CredentialError) as error:
        print(str(error)+'; no access changed.', file=sys.stderr)
        raise SystemExit(1)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Exception details from transport or JSON parsing can contain secrets.
        print('Wiki access check incomplete ('+type(error).__name__+'); no access changed.', file=sys.stderr)
        raise SystemExit(1)
