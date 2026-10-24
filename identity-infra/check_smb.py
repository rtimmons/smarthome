"""Create bounded SMB fixtures, check approved grants, then remove our own files."""
import json
import os
import re
import subprocess
import uuid

from ha_directory import execute
from manage import connection, PRIVATE, ROOT


def main():
    os.umask(0o077)
    marker=PRIVATE/'smb-check-pending.json'
    if marker.exists():
        raise RuntimeError('A previous fixture check needs review/cleanup before repeating')
    identifier=uuid.uuid4().hex
    fixture='.smarthome-auth-check-'+identifier
    payload='Synthetic household SMB access check '+identifier+'\n'
    marker.write_text(json.dumps({'fixture':fixture,'payload':payload})+'\n')
    setup='''set -eu
umask 077
for share in Public Multimedia; do
 directory="/share/$share/'''+fixture+'''"
 test ! -e "$directory"
 mkdir "$directory"
 chmod 777 "$directory"
 printf '%s' '''+repr(payload)+''' > "$directory/read.txt"
 chmod 666 "$directory/read.txt"
done
'''
    # Use shell quoting that preserves a real newline in the synthetic payload.
    import shlex
    setup=setup.replace(repr(payload),shlex.quote(payload))
    result=subprocess.run(connection(),input=setup.encode(),capture_output=True,timeout=90)
    if result.returncode:
        (PRIVATE/'smb-check.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('Synthetic fixture setup failed; inspect pending marker')
    bootstrap=json.loads((PRIVATE/'human-logins.json').read_text())
    bootstrap.update(fixture=fixture,payload=payload,ldap_bind=(PRIVATE/'secrets/ldap-bind').read_text().strip())
    script='bootstrap = '+repr(bootstrap)+'\n'+(ROOT/'identity-infra/check_smb_remote.py').read_text()
    result=execute(('python3 - <<\'CHECK\'\n'+script+'\nCHECK\n').encode(),timeout=300)
    (PRIVATE/'smb-check.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('SMB access checks failed; synthetic fixture paths retained in private pending marker')
    cleanup='''set -eu
for share in Public Multimedia; do
 directory="/share/$share/'''+fixture+'''"
 test ! -L "$directory"
 test "$(cat "$directory/read.txt")" = '''+shlex.quote(payload.strip())+'''
 rm "$directory/read.txt"
 rmdir "$directory"
done
'''
    removed=subprocess.run(connection(),input=cleanup.encode(),capture_output=True,timeout=90)
    if removed.returncode:
        (PRIVATE/'smb-cleanup.log').write_bytes(removed.stdout+removed.stderr)
        raise RuntimeError('SMB checks passed but fixture cleanup requires review')
    (PRIVATE/'smb-check-receipt.json').write_text(json.dumps({'approved_grants':'passed','encrypted_smb3':True,'synthetic_fixtures_removed':True})+'\n')
    marker.unlink()
    print(result.stdout.decode(),end='')


if __name__=='__main__':main()
