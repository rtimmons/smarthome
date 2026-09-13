#!/usr/bin/env python3
"""Update only transfer telemetry/presentation on an idle, existing NAS deployment."""
import base64
import argparse
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('backup_qnap', SCRIPTS / 'backup-qnap.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def payload(project: str, assets_only: bool = False) -> str:
    app = str(Path(project).parent.parent)
    if assets_only:
        encoded = base64.b64encode((SCRIPTS / 'catalog-refresh.js').read_bytes()).decode()
        return ('set -eu\napp=' + shlex.quote(app) + '\n' +
                'test -f "$app/scripts/catalog-refresh.js"\n' +
                f"printf '%s' '{encoded}' | base64 -d > \"$app/scripts/catalog-refresh.js.update\"\n" +
                'chmod 750 "$app/scripts/catalog-refresh.js.update"\n' +
                'mv -f "$app/scripts/catalog-refresh.js.update" "$app/scripts/catalog-refresh.js"\n' +
                'cp "$app/scripts/catalog-refresh.js" "$app/state/dashboard/runtime/custom-webui/custom.js.update"\n' +
                'mv -f "$app/state/dashboard/runtime/custom-webui/custom.js.update" "$app/state/dashboard/runtime/custom-webui/custom.js"\n')
    shell = '''set -eu
qnap_package=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
qnap_docker="$qnap_package/bin/docker"
test -x "$qnap_docker"
'''
    shell += 'app=' + shlex.quote(app) + '\n'
    shell += '''export DOCKER_CONFIG="$app/state/docker-client"
cd "$app/compose/qnap"
qnap_dashboard=$("$qnap_docker" --config "$DOCKER_CONFIG" compose ps -q dashboard)
test -n "$qnap_dashboard"
# A small existing-image container holds the same kernel lock across restart.
# No host Python/flock utility or Docker socket inside a container is required.
qnap_lease="usenet-dashboard-update-$(date -u +%Y%m%dT%H%M%SZ)-$$"
ready="$app/state/$qnap_lease.ready"
cleanup() {
  "$qnap_docker" --config "$DOCKER_CONFIG" rm -f "$qnap_lease" >/dev/null 2>&1 || true
  rm -f "$ready"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
"$qnap_docker" --config "$DOCKER_CONFIG" run -d --name "$qnap_lease" --pull=never --network=none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
  --volumes-from "$qnap_dashboard" -e PYTHONDONTWRITEBYTECODE=1 \
  -e UPDATE_READY="/data/state/$qnap_lease.ready" --entrypoint python3 \
  usenet-catalog-tools:rclone-1.75.1-python-3.14.7 \
  -c 'import fcntl,os,time; from pathlib import Path; lock=open("/data/state/locks/cache.lock","r+"); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); lock.seek(0); lock.truncate(); lock.write("{}"); lock.flush(); Path(os.environ["UPDATE_READY"]).touch(mode=0o600); time.sleep(600)' >/dev/null
for _attempt in 1 2 3 4 5 6 7 8 9 10; do
  if test -f "$ready"; then break; fi
  sleep 1
done
test -f "$ready" || { echo 'Cache busy or maintenance lock unavailable; no scripts changed.' >&2; exit 1; }
backup_dir="$app/state/dashboard-status-backups/$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -p "$app/state/dashboard-status-backups"
mkdir -m 700 "$backup_dir"
'''
    for name in ('catalogctl.py', 'catalog-dashboard.py', 'catalog-refresh.js', 'native_library.py'):
        encoded = base64.b64encode((SCRIPTS / name).read_bytes()).decode()
        if name == 'native_library.py':
            shell += 'if test -f "$app/scripts/native_library.py"; then\n'
        shell += f'cp -p "$app/scripts/{name}" "$backup_dir/{name}"\n'
        shell += f"printf '%s' '{encoded}' | base64 -d > \"$app/scripts/{name}.update\"\n"
        shell += f'chmod 750 "$app/scripts/{name}.update"\nmv -f "$app/scripts/{name}.update" "$app/scripts/{name}"\n'
        if name == 'native_library.py':
            shell += 'fi\n'
    shell += '''"$qnap_docker" --config "$DOCKER_CONFIG" restart --time 30 "$qnap_dashboard"
cleanup
trap - EXIT
"$qnap_docker" --config "$DOCKER_CONFIG" exec "$qnap_dashboard" python3 /opt/usenet/scripts/catalog-dashboard.py refresh
"$qnap_docker" --config "$DOCKER_CONFIG" exec "$qnap_dashboard" python3 /opt/usenet/scripts/catalog-dashboard.py healthcheck
printf 'Dashboard telemetry deployed; rollback scripts: %s\n' "$backup_dir"
'''
    return shell


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['all', 'assets'], default='all')
    args = parser.parse_args()
    command, _ = backup.connection(dict(os.environ))
    raise SystemExit(subprocess.run([*command[:-1], 'exec /bin/sh -s'],
                                    input=payload(os.environ['QNAP_PROJECT_DIR'], args.mode == 'assets'), text=True).returncode)
