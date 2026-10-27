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

from ha_directory import connection as directory_connection
from manage import connection, PRIVATE

SHARES = ('Container', 'FromDrobo', 'homes', 'Multimedia', 'Public',
          'SpaceBlackTimeMachine', 'Usenet')
DENIALS = {'NT_STATUS_ACCESS_DENIED', 'NT_STATUS_ACCOUNT_DISABLED',
           'NT_STATUS_ACCOUNT_RESTRICTION'}


class CheckError(RuntimeError):
    """Only fixed, nonsecret diagnostics may be shown to the operator."""


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


def account_reference():
    script = b'''set -eu
test "$(id -u svc-wiki)" = 1005
test "$(awk -F: '$1=="wiki-reader" {print $3}' /etc/group)" = 1000
package=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
"$package/bin/docker" run --rm --pull=never --network=none --read-only --cap-drop=ALL \\
 --security-opt=no-new-privileges --memory=128m --cpus=0.25 --pids-limit=32 --user 0:0 \\
 --mount type=bind,src=/etc/config,dst=/source,readonly --entrypoint awk \\
 usenet-catalog-tools:rclone-1.75.1-python-3.14.7 -F: '$1=="svc-wiki" {print}' /source/smbpasswd
/sbin/getcfg System 'Server Name' -f /etc/config/uLinux.conf
'''
    result = subprocess.run(connection(), input=script, capture_output=True, timeout=300)
    if result.returncode:
        raise CheckError('Dedicated NAS account inspection failed')
    lines = result.stdout.decode().splitlines()
    if len(lines) != 2:
        raise CheckError('Expected one existing local Samba credential and realm')
    row = lines[0].split(':')
    if (len(row) < 6 or row[:2] != ['svc-wiki', '1005']
            or not re.fullmatch(r'[0-9A-Fa-f]{32}', row[3])
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', lines[1])):
        raise CheckError('Existing wiki credential reference is not qualified')
    return row[3].lower(), lines[1]


def prepare_smb_transport():
    try:
        command = directory_connection()
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
    result = subprocess.run(command, input=probe, capture_output=True, timeout=60)
    if result.returncode or result.stdout.strip() != b'wiki-smb-client-ready':
        raise CheckError('Pinned directory SMB client unavailable; no password requested')
    return command


def smb_checks(password, expected_hash, realm, command):
    # Use the existing pinned directory maintenance transport and installed SMB
    # client. No directory database is opened or changed. The password travels
    # over SSH stdin, never argv, and exists remotely only in private /run temp.
    values = {'password': password, 'expected_hash': expected_hash,
              'realm': realm, 'shares': SHARES}
    remote = 'values = ' + repr(values) + '\n' + '''
import hmac,json,os,subprocess,tempfile
from pathlib import Path
from samba.credentials import Credentials
os.umask(0o077)
c=Credentials();c.set_password(values['password'])
if not hmac.compare_digest(bytes(c.get_nt_hash()).hex(),values['expected_hash']):
 print(json.dumps({'credential_verified':False}));raise SystemExit(0)
results=[]
with tempfile.TemporaryDirectory(prefix='wiki-denial-',dir='/run') as directory:
 auth=Path(directory)/'credentials'
 auth.write_text('username = svc-wiki\\npassword = '+values['password']+'\\ndomain = '+values['realm']+'\\n')
 for share in values['shares']:
  r=subprocess.run(['smbclient','//192.168.1.66/'+share,'-A',str(auth),
    '--client-protection=encrypt','-m','SMB3','-c','quit'],capture_output=True,timeout=30)
  output=(r.stdout+r.stderr).decode(errors='replace')
  results.append({'share':share,'code':r.returncode,'output':output})
  # A session refusal applies before any share selection. Do not repeat it or
  # risk lockout; tree-connect denials qualify the individual share instead.
  if 'tree connect failed:' not in output: break
print(json.dumps({'credential_verified':True,'results':results}))
'''
    result = subprocess.run(command, input=("python3 - <<'WIKI_ACCESS_CHECK'\n" + remote
                            + '\nWIKI_ACCESS_CHECK\n').encode(), capture_output=True, timeout=300)
    if result.returncode:
        raise CheckError('Pinned SMB probe failed; no raw credential-bearing output saved')
    value = json.loads(result.stdout)
    if value.get('credential_verified') is not True:
        raise CheckError('Password does not match the existing account; no login attempted')
    checks = [dict(share=row['share'], **classify_smb(row['code'], row['output']))
              for row in value['results']]
    if not checks or (checks[-1]['phase'] == 'authenticated-tree-connect'
                      and [c['share'] for c in checks] != list(SHARES)):
        raise CheckError('Incomplete SMB share denial check')
    return checks


def ssh_check(password):
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
                '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
                '--', 'svc-wiki@'+target, 'id -u']
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                env=env, timeout=45)
        password_prompted = prompted.exists()
    if not ssh_denied(result):
        raise CheckError('SSH did not return a qualified login denial')
    return {'valid_credential_login_denied': True, 'password_prompted': password_prompted,
            'session_created': False}


def main():
    os.umask(0o077)
    if not sys.stdin.isatty():
        raise CheckError('Run interactively; the password must use a hidden terminal prompt')
    print('Checking the existing dedicated HA/directory SMB transport...', flush=True)
    command = prepare_smb_transport()
    print('Reading the existing wiki credential reference through the dedicated NAS connection...', flush=True)
    expected, realm = account_reference()
    password = getpass.getpass('Existing svc-wiki password (hidden; temporary use only): ')
    if not password or any(c in password for c in '\r\n\x00'):
        raise CheckError('Empty or multiline credentials are not supported')
    print('Checking the password and encrypted SMB denials...', flush=True)
    checks = smb_checks(password, expected, realm, command)
    print('Checking one SSH login denial...', flush=True)
    ssh = ssh_check(password)
    receipt = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
               'account': 'svc-wiki', 'realm': 'QNAP-local', 'uid': 1005,
               'password_matches_existing_samba_credential': True,
               'smb3_encryption_required': True, 'smb': checks, 'ssh': ssh,
               'permissions_changed': False, 'household_files_read': False}
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
    except CheckError as error:
        print(str(error)+'; no access changed.', file=sys.stderr)
        raise SystemExit(1)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Exception details from transport or JSON parsing can contain secrets.
        print('Wiki access check incomplete ('+type(error).__name__+'); no access changed.', file=sys.stderr)
        raise SystemExit(1)
