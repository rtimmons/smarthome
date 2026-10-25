#!/usr/bin/env python3
"""Check idle Catalog state, then apply only its prepared OAuth adapter and credentials.

Run via `just usenet identity deploy-catalog [--apply]`. No image rebuild,
backend changes, media operations or unrelated container restarts.
"""
import sys,subprocess,base64,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'identity-infra'))
from manage import PRELUDE,PRIVATE,connection
script=PRELUDE+'''cd /share/Container/usenet/compose/qnap
container=$("$docker" compose ps -q dashboard)
test -n "$container"
"$docker" exec -i "$container" python3 - <<'CHECK'
import sys,json,subprocess
sys.path.insert(0,'/opt/usenet/scripts')
import importlib.util
spec=importlib.util.spec_from_file_location('dashboard','/opt/usenet/scripts/catalog-dashboard.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=m.snapshot()
assert s.get('transfers_in_progress')==0, 'Active transfers; stop here without restarting'
assert not any((i.get('operation') or {}).get('active') for i in s.get('items',[])), 'Active operation'
print('PASS: fresh Catalog snapshot has no active transfers or operations')
CHECK
'''
if '--apply' in sys.argv:
    old=(PRIVATE/'secrets/catalog-auth-before-oauth.json').read_bytes()
    new=(ROOT/'usenet-infra/secrets/dashboard-auth.json').read_bytes()
    script+='''auth=/share/Container/usenet/secrets/dashboard-auth.json
actual=$(sha256sum "$auth" | cut -d ' ' -f 1)
'''
    script+=f"test \"$actual\" = '{hashlib.sha256(old).hexdigest()}' || test \"$actual\" = '{hashlib.sha256(new).hexdigest()}'\n"
    script+='''# Hold the established cache lock across dashboard recreation, using the
# existing tools image without networking, extra privileges or a Docker socket.
lease="usenet-catalog-auth-$(date -u +%Y%m%dT%H%M%SZ)-$$"
ready="/share/Container/usenet/state/$lease.ready"
cleanup() { "$docker" rm -f "$lease" >/dev/null 2>&1 || true; rm -f "$ready"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
"$docker" run -d --name "$lease" --pull=never --network=none --read-only \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 --volumes-from "$container" -e PYTHONDONTWRITEBYTECODE=1 \
 -e UPDATE_READY="/data/state/$lease.ready" --entrypoint python3 \
 usenet-catalog-tools:rclone-1.75.1-python-3.14.7 \
 -c 'import fcntl,os,time; from pathlib import Path; lock=open("/data/state/locks/cache.lock","r+"); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); Path(os.environ["UPDATE_READY"]).touch(mode=0o600); time.sleep(600)' >/dev/null
for attempt in 1 2 3 4 5 6 7 8 9 10; do
 test ! -f "$ready" || break
 sleep 1
done
test -f "$ready" || { echo 'Cache busy; no files changed.' >&2; exit 1; }
backup=/share/Container/usenet/secrets/catalog-pre-sso
mkdir -p "$backup"
chmod 700 "$backup"
'''
    for source,target,mode in [(ROOT/'usenet-infra/scripts/catalog-dashboard.py','/share/Container/usenet/scripts/catalog-dashboard.py','750'),(ROOT/'usenet-infra/secrets/dashboard-auth.json','/share/Container/usenet/secrets/dashboard-auth.json','600')]:
        enc=base64.b64encode(source.read_bytes()).decode()
        script+=f'test -e "$backup/{source.name}" || cp -p "{target}" "$backup/{source.name}"\n'
        script+=f"printf '%s' '{enc}' | base64 -d > '{target}.sso-new'\n"
        script+=f"chown $(stat -c '%u:%g' '{target}') '{target}.sso-new'\nchmod {mode} '{target}.sso-new'\nmv '{target}.sso-new' '{target}'\n"
    script+='''"$docker" compose up -d --no-deps --no-build --force-recreate dashboard
"$docker" compose ps dashboard --format json
'''
r=subprocess.run(connection(),input=script.encode(),capture_output=True,timeout=240)
(PRIVATE/'catalog-rollout.log').write_bytes(r.stdout+r.stderr)
print('Catalog '+('rollout' if '--apply' in sys.argv else 'preflight')+': exit '+str(r.returncode)+'; private log retained')
if r.returncode:sys.exit(r.returncode)
