#!/usr/bin/env python3
"""Manage only the isolated NAS Forgejo service with the pinned NAS identity."""
import argparse
import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = '''set -eu
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"
test -x "$docker" || docker="$pkg/usr/bin/docker"
test -x "$docker"
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
root=/share/Container/home-git
compose() { "$docker" compose -f "$root/compose.yaml" "$@"; }
'''


def payload(action):
    if action in ('backup', 'backup-status'):
        return PRELUDE + 'sh "$root/backup.sh" ' + ('force' if action == 'backup' else 'check') + '\n'
    if action in ('backup-deploy', 'backup-schedule', 'backup-update'):
        script = PRELUDE + '''umask 077
mkdir -p /share/Usenet/Backups/automatic/forgejo
chmod 700 /share/Usenet/Backups/automatic/forgejo
test "$(stat -c %u /share/Usenet/Backups/automatic/forgejo)" = 1004
test "$("$docker" inspect --format '{{.State.Running}}' usenet-backups-backups-1)" = true
'''
        for name in ('backup.py', 'backup.sh', 'install-cron.py'):
            encoded = base64.b64encode((ROOT / 'git-host' / name).read_bytes()).decode()
            script += f"printf '%s' {encoded} | base64 -d > \"$root/{name}.new\"\nchmod 700 \"$root/{name}.new\"\nmv \"$root/{name}.new\" \"$root/{name}\"\n"
        if action == 'backup-update':
            return script
        script += '''"$docker" run --rm --network none --read-only --user 0:0 --cap-drop ALL --cap-add DAC_OVERRIDE \
  --security-opt no-new-privileges --memory 128m \
  --mount "type=bind,src=$root,dst=/source" \
  --mount type=bind,src=/etc/config/crontab,dst=/persistent \
  --mount type=bind,src=/tmp/cron/crontabs,dst=/crontabs \
  --entrypoint python3 usenet-catalog-tools:rclone-1.75.1-python-3.14.7 /source/install-cron.py'''
        return script + (' --probe\n' if action == 'backup-deploy' else '\n')
    if action == 'status':
        return PRELUDE + '''compose ps
"$docker" stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} memory={{.MemUsage}}' home-git-forgejo-1
"$docker" exec home-git-forgejo-1 wget -qO- http://127.0.0.1:3000/api/healthz
'''
    if action == 'auth-status':
        return PRELUDE + '''"$docker" exec home-git-forgejo-1 forgejo --config /var/lib/gitea/custom/conf/app.ini admin user list
"$docker" exec home-git-forgejo-1 forgejo --config /var/lib/gitea/custom/conf/app.ini admin auth list
'''
    if action == 'credentials':
        return PRELUDE + 'cat "$root/admin-login.txt"\n'
    if action == 'bootstrap':
        return PRELUDE + '''umask 077
test ! -e "$root/admin-login.txt"
users=$("$docker" exec home-git-forgejo-1 forgejo --config /var/lib/gitea/custom/conf/app.ini admin user list)
printf '%s\\n' "$users" | awk '$1 ~ /^[0-9]+$/ {found=1} END {exit found}'
touch "$root/admin-login.txt"
chmod 600 "$root/admin-login.txt"
"$docker" exec home-git-forgejo-1 forgejo --config /var/lib/gitea/custom/conf/app.ini admin user create --username ryan --email ryan@home.invalid --admin --random-password --random-password-length 32 --must-change-password > "$root/admin-login.txt"
echo 'Administrator created; retrieve credentials into the ignored local file.'
'''
    if action == 'deploy':
        encoded = base64.b64encode((ROOT / 'git-host/compose.yaml').read_bytes()).decode()
        return PRELUDE + '''umask 077
if test ! -e "$root"; then
  # Refuse occupied ports before creating a new installation.
  netstat -ltn | awk '$4 ~ /:(3003|2222)$/ {found=1} END {exit found}'
  mkdir "$root"
fi
test ! -L "$root"
chmod 700 "$root"
mkdir -p "$root/data" "$root/config"
chmod 700 "$root/data" "$root/config"
test "$(stat -c %u "$root/data")" = 1004
test "$(stat -c %u "$root/config")" = 1004
printf '%s' ''' + encoded + ''' | base64 -d > "$root/compose.yaml.new"
"$docker" compose -f "$root/compose.yaml.new" config --quiet
if test -e "$root/compose.yaml"; then cp "$root/compose.yaml" "$root/compose.yaml.previous"; fi
mv "$root/compose.yaml.new" "$root/compose.yaml"
compose up -d --wait --wait-timeout 180
'''
    raise ValueError(action)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('deploy', 'status', 'auth-status', 'bootstrap', 'credentials',
                                         'backup', 'backup-status', 'backup-deploy', 'backup-schedule', 'backup-update',
                                         'backup-verify'))
    action = parser.parse_args().action
    if action == 'backup-verify':
        spec = importlib.util.spec_from_file_location('verify_remote', ROOT / 'git-host/verify-remote.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        return verifier.main()
    spec = importlib.util.spec_from_file_location('qnap_recon', ROOT / 'usenet-infra/scripts/qnap-recon.py')
    recon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recon)
    result = subprocess.run(recon.connection_command(os.environ), input=payload(action).encode(),
                            stdout=subprocess.PIPE if action == 'credentials' else None,
                            stderr=subprocess.PIPE if action == 'credentials' else None, timeout=7200)
    if action == 'credentials':
        if result.returncode:
            print('Credential retrieval failed; no output displayed.', file=sys.stderr)
            return result.returncode
        destination = ROOT / 'build/git-host/admin-login.txt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(result.stdout)
        print(f'Private login saved to {destination}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
