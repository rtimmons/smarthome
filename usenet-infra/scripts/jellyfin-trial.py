#!/usr/bin/env python3
"""Operate the existing NAS trial; never bootstrap users or touch media services."""
import argparse
import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/share/Container/usenet/jellyfin-trial'
PRELUDE = r'''set -eu
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"
if test ! -x "$docker"; then docker="$pkg/usr/bin/docker"; fi
test -x "$docker"
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
root=/share/Container/usenet/jellyfin-trial
'''


def payload(action):
    if action == 'status':
        return PRELUDE + '''"$docker" inspect usenet-jellyfin-trial-jellyfin-1 --format '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}'
"$docker" stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} memory={{.MemUsage}}' usenet-jellyfin-trial-jellyfin-1
"$docker" exec usenet-jellyfin-trial-jellyfin-1 curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8096/System/Info/Public
'''
    if action == 'stop':
        return PRELUDE + '''"$docker" compose --env-file "$root/.env" -f "$root/compose.yaml" stop jellyfin
'''
    encoded = base64.b64encode((ROOT / 'compose/jellyfin/compose.yaml').read_bytes()).decode()
    web_config = base64.b64encode((ROOT / 'compose/jellyfin/web-config.json').read_bytes()).decode()
    return PRELUDE + '''# This reconciles an already-configured trial, never an unsecured wizard.
test -s "$root/config/config/system.xml"
test -s "$root/.env"
grep -q '<IsStartupWizardCompleted>true</IsStartupWizardCompleted>' "$root/config/config/system.xml"
grep -qx 'JELLYFIN_BIND_ADDRESS=192.168.1.66' "$root/.env"
awk -v target="$(readlink -f /share/FromDrobo/Remote/files)" '$2 == target && $3 == "fuse.rclone" && $4 ~ /^ro,/ {found=1} END {exit !found}' /proc/mounts
test -c /dev/dri/renderD128
umask 077
cp "$root/compose.yaml" "$root/compose.yaml.previous"
if test -f "$root/web-config.json"; then cp "$root/web-config.json" "$root/web-config.json.previous"; fi
printf '%s' ''' + web_config + ''' | base64 -d > "$root/web-config.json.new"
chmod 644 "$root/web-config.json.new"
mv "$root/web-config.json.new" "$root/web-config.json"
printf '%s' ''' + encoded + ''' | base64 -d > "$root/compose.yaml.new"
"$docker" compose --env-file "$root/.env" -f "$root/compose.yaml.new" config --quiet
mv "$root/compose.yaml.new" "$root/compose.yaml"
"$docker" compose --env-file "$root/.env" -f "$root/compose.yaml" up -d jellyfin
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'deploy', 'stop'))
    action = parser.parse_args().action
    spec = importlib.util.spec_from_file_location('qnap_recon', ROOT / 'scripts/qnap-recon.py')
    recon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recon)
    try:
        result = subprocess.run(recon.connection_command(os.environ), input=payload(action).encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        # Commands deliberately return only service metadata, never env/config/media.
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        return result.returncode
    except (recon.ReconError, subprocess.TimeoutExpired) as error:
        print(type(error).__name__ + ': dedicated NAS command failed; no fallback attempted', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
