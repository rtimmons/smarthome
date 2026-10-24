"""Cold-transfer the existing DC after successful HA preparation and restore trial.

The source stays disabled on any error. Recovery must explicitly confirm the
HA copy is stopped before restarting it; no automatic rollback can start two DCs.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import time

from ha_directory import connection as target_connection, ha_connection, execute
from manage import connection as source_connection, PRELUDE, PRIVATE, ROOT, upload

JOURNAL = PRIVATE/'ha-cutover.json'
SID = 'S-1-5-21-2612071719-3246555018-4093554428'


def record(phase, **extra):
    value = json.loads(JOURNAL.read_text()) if JOURNAL.exists() else {'domain_sid': SID}
    value.update(extra, phase=phase, updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    temporary = JOURNAL.with_suffix('.new')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(JOURNAL)


def run(command, data=None, timeout=180, label='migration'):
    result = subprocess.run(command, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        (PRIVATE/(label+'.log')).write_bytes(result.stdout+result.stderr)
        raise RuntimeError(label+' failed; see private log. Source/target state must be checked before rollback.')
    return result.stdout


def encrypt(plain):
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    recipient = json.loads((state/'manifest.json').read_text())['recipient']
    cipher = subprocess.check_output([str(age), '-r', recipient], input=plain)
    restored = subprocess.check_output([str(age), '-d', '-i', str(Path.home()/'.config/smarthome/recovery.agekey')], input=cipher)
    if restored != plain:
        raise RuntimeError('Cold-copy encrypted readback differs')
    path = state/'recovery'/time.strftime('ad-exact-cold-%Y%m%dT%H%M%SZ.tar.gz.age', time.gmtime())
    with path.open('xb') as output:
        output.write(cipher)
    return str(path), hashlib.sha256(cipher).hexdigest()


def stage_target(plain):
    bundle = io.BytesIO()
    files = {'directory.tar.gz': plain}
    for name in ('cold_import.py', 'directory_state.py'):
        files[name] = (ROOT/'identity-infra'/name).read_bytes()
    with tarfile.open(fileobj=bundle, mode='w') as archive:
        for name, data in files.items():
            item=tarfile.TarInfo(name); item.size=len(data); item.mode=0o600
            archive.addfile(item, io.BytesIO(data))
    command = target_connection()
    command[-1] = 'sudo -n sh -c '+shlex.quote('umask 077; test ! -e /data/cold-transfer && mkdir -m 700 /data/cold-transfer && tar -xf - -C /data/cold-transfer')
    run(command, bundle.getvalue(), label='ha-cold-stage')
    command[-1] = 'sudo -n python3 /data/cold-transfer/cold_import.py'
    return json.loads(run(command, timeout=180, label='ha-cold-import'))


def activate():
    # Recheck the original source immediately before allowing the target to run.
    check = PRELUDE+'''test -s "$root/ha-cutover.json"
test "$("$docker" inspect --format '{{.State.Running}}' home-identity-dc-1)" = false
test "$("$docker" inspect --format '{{.HostConfig.RestartPolicy.Name}}' home-identity-dc-1)" = no
'''
    run(source_connection(), check.encode(), label='source-stopped-check')
    command = target_connection()
    activation = '''import json, os
from pathlib import Path
os.umask(0o077)
root=Path('/data')
receipt=json.loads((root/'cold-transfer/receipt.json').read_text())
assert receipt['accounts_and_credentials']=='identical' and receipt['sysvol_content_and_acls']=='identical'
with (root/'migration-ready.json').open('x') as output:
    json.dump(receipt, output)
'''
    command[-1] = 'sudo -n python3 -c '+shlex.quote(activation)
    run(command, label='target-activation')
    record('activation-marked')
    script = '''set -eu
ha apps stop local_directory_route
curl -fsS -H "Authorization: Bearer $SUPERVISOR_TOKEN" -H 'Content-Type: application/json' \
 -X POST -d '{"options":{"address":"192.168.1.10"}}' \
 http://supervisor/addons/local_directory_route/options | jq -e '.result == "ok"' >/dev/null
ha apps restart local_directory
ha apps start local_directory_route
'''
    run(ha_connection()+[script], timeout=120, label='ha-directory-activation')
    record('activated')


def main():
    os.umask(0o077)
    if JOURNAL.exists():
        if json.loads(JOURNAL.read_text()).get('phase') == 'source-stopped':
            resume = PRELUDE+'''test "$("$docker" inspect --format '{{.State.Running}}' home-identity-dc-1)" = false
test "$("$docker" inspect --format '{{.HostConfig.RestartPolicy.Name}}' home-identity-dc-1)" = no
chmod 700 "$root/ha-migration"
if test ! -e "$root/ha-migration/directory.tar.gz"; then
 test -s "$root/ha-migration/directory.tar.gz.new"
 chmod 600 "$root/ha-migration/directory.tar.gz.new"
 gzip -t "$root/ha-migration/directory.tar.gz.new"
 mv "$root/ha-migration/directory.tar.gz.new" "$root/ha-migration/directory.tar.gz"
fi
chmod 600 "$root/ha-migration/directory.tar.gz"
cat "$root/ha-migration/directory.tar.gz"
'''
            plain = run(source_connection(), resume.encode(), label='source-cold-resume')
            return finish(plain)
        raise RuntimeError('Migration journal already exists; inspect its exact phase instead of repeating a cold copy')
    receipt = json.loads((PRIVATE/'directory-backup-receipt.json').read_text())
    if receipt['restore_database_check'] != 'passed' or time.time()-Path(receipt['archive']).stat().st_mtime > 3600:
        raise RuntimeError('A fresh verified AD recovery backup is required')
    for mode in ([], ['+tcp']):
        output = run(['dig','@192.168.1.11','+time=3','+tries=1','+short',*mode,'probe.directory-preparation.invalid'])
        if output.strip() != b'192.0.2.1':
            raise RuntimeError('HA preparation DNS failed')
    result = execute(b'''set -eu
test ! -e /data/private/sam.ldb
test ! -e /data/migration-ready.json
python3 - <<'CHECK'
import json
from pathlib import Path
r=json.loads(Path('/data/restore-trial/receipt.json').read_text())
assert r['database_check']=='passed' and r['sysvol_permissions']=='passed' and r['restored_listener_started'] is False
CHECK
''')
    if result.returncode:
        raise RuntimeError('HA preparation or restore-trial gate failed')
    record('prepared')
    source = PRELUDE+'mkdir -p "$root/ha-migration"\nchmod 700 "$root/ha-migration"\n'
    for name in ('directory_state.py','cold_export.py'):
        source += upload('ha-migration/'+name, (ROOT/'identity-infra'/name).read_bytes())
    source += '''test ! -e "$root/ha-cutover.json"
test ! -e "$root/ha-migration/directory.tar.gz"
printf '%s\\n' '{"target":"homeassistant.local","domain_sid":"'''+SID+'''","phase":"source-disabled"}' > "$root/ha-cutover.json"
"$docker" update --restart=no home-identity-dc-1 >/dev/null
"$docker" stop -t 60 home-identity-dc-1 >/dev/null
test "$("$docker" inspect --format '{{.State.Running}}' home-identity-dc-1)" = false
: > "$root/ha-migration/directory.tar.gz.new"
chmod 600 "$root/ha-migration/directory.tar.gz.new"
"$docker" run --rm --name home-identity-cold-export --network none --memory 768m --cpus 1 \
 -v "$root/dc-state:/data" -v "$root/tls:/tls:ro" -v "$root/ha-migration:/migration:ro" \
 --entrypoint python3 smarthome-samba-ad:20261024 /migration/cold_export.py > "$root/ha-migration/directory.tar.gz.new"
chmod 600 "$root/ha-migration/directory.tar.gz.new"
mv "$root/ha-migration/directory.tar.gz.new" "$root/ha-migration/directory.tar.gz"
cat "$root/ha-migration/directory.tar.gz"
'''
    plain = run(source_connection(), source.encode(), timeout=300, label='source-cold-export')
    finish(plain)


def finish(plain):
    record('source-stopped', cold_sha256=hashlib.sha256(plain).hexdigest())
    with tarfile.open(fileobj=io.BytesIO(plain), mode='r:gz') as archive:
        evidence = json.load(archive.extractfile('migration-evidence.json'))
    if evidence['identity']['domain_sid'] != SID:
        raise RuntimeError('Source identity changed')
    path, digest = encrypt(plain)
    record('source-encrypted', archive=path, ciphertext_sha256=digest)
    receipt = stage_target(plain)
    record('target-verified', verification=receipt)
    activate()
    print('Exact directory transferred and activated on HA; source is stopped with restart disabled.')
    print('Encrypted cold recovery:', path)
    print('Run authenticated AD, household, QNAP trust, DNS and browser checks before accepting cutover.')


if __name__ == '__main__':
    main()
