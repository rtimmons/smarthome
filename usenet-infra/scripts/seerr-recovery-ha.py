#!/usr/bin/env python3
"""Install only the recovery notification package through the dedicated HA identity."""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / 'usenet-infra/secrets/seerr-recovery/notify.json'
KEY = 'usenet_recovery_webhook_id'


def command(argv, data=None, timeout=120):
    result = subprocess.run(argv, input=data, text=True, capture_output=True, timeout=timeout, cwd=REPO)
    if result.returncode:
        # SSH authentication errors must stop the workflow, never use alternate credentials.
        if 'Permission denied' in result.stderr and argv[0] == 'ssh':
            raise RuntimeError('Dedicated HA SSH authentication failed; Ryan must rerun just ha-ssh-key-copy')
        raise RuntimeError('Recovery notification setup failed: ' + Path(argv[0]).name)
    return result.stdout


def ssh(script, data=None):
    identity = REPO / '.ssh/id_ed25519_codex_smarthome'
    if not identity.is_file():
        raise RuntimeError('Dedicated HA SSH key is missing; follow just ha-ssh-key-create and human-only copy setup')
    return command(['ssh', '-i', str(identity), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                    '-o', 'ConnectTimeout=10', 'root@homeassistant.local', script], data, 180)


def existing_secret(content):
    values = re.findall(r'^' + KEY + r':\s*[\'"]?([a-f0-9]{64})[\'"]?\s*$', content, re.M)
    declarations = re.findall(r'^' + KEY + r':', content, re.M)
    if len(declarations) != len(values) or len(values) > 1:
        raise RuntimeError('Existing recovery webhook secret needs review')
    return values[0] if values else None


def install(host):
    address = ipaddress.ip_address(host)
    if address not in ipaddress.ip_network('192.168.1.0/24'):
        raise RuntimeError('HA notification host must be on the private LAN')
    old_secrets = ssh('cat /config/secrets.yaml')
    saved = json.loads(PRIVATE.read_text()) if PRIVATE.exists() else {}
    token = existing_secret(old_secrets) or saved.get('webhook_id') or secrets.token_hex(32)
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise RuntimeError('Invalid private webhook configuration')
    if saved.get('webhook_id', token) != token:
        raise RuntimeError('Local and HA webhook secrets differ; refusing rotation')
    local = REPO / 'new-hass-configs/secrets.yaml'
    previous = existing_secret(local.read_text()) if local.exists() else None
    if previous and previous != token:
        raise RuntimeError('Local HA secret differs; refusing rotation')
    PRIVATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(PRIVATE.parent, 0o700)
    descriptor = os.open(PRIVATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump({'host': host, 'webhook_id': token}, stream)
    package = (REPO / 'new-hass-configs/packages/usenet_recovery.yaml').read_bytes()
    addition = '' if existing_secret(old_secrets) else '\n' + KEY + ': "' + token + '"\n'
    # The private input travels over stdin, never in argv or logs. Roll back only our files.
    script = '''set -eu
umask 077
recovery_backup=$(mktemp -d /config/.recovery-notify-XXXXXX)
cp -p /config/secrets.yaml "$recovery_backup/secrets.yaml"
if test -f /config/packages/usenet_recovery.yaml; then
 cp -p /config/packages/usenet_recovery.yaml "$recovery_backup/package.yaml"
fi
printf '%s' 'PACKAGE' | base64 -d > /config/packages/usenet_recovery.yaml
printf '%s' 'ADDITION' | base64 -d >> /config/secrets.yaml
if ! ha core check > "$recovery_backup/check.log" 2>&1; then
 cp -p "$recovery_backup/secrets.yaml" /config/secrets.yaml
 if test -f "$recovery_backup/package.yaml"; then
  cp -p "$recovery_backup/package.yaml" /config/packages/usenet_recovery.yaml
 else
  rm /config/packages/usenet_recovery.yaml
 fi
 exit 1
fi
printf 'configuration_validated\\n'
'''.replace('PACKAGE', base64.b64encode(package).decode()).replace('ADDITION', base64.b64encode(addition.encode()).decode())
    ssh('sh -s', script)
    # Preserve the secret in the ignored workstation configuration for future full deployments.
    if local.exists():
        if not previous:
            with local.open('a') as stream:
                stream.write('\n' + KEY + ': "' + token + '"\n')
    command(['node', str(REPO / 'new-hass-configs/config-generator/dist/cli/home-assistant.js'),
             'call', 'automation.reload'])
    for entity in ('automation.usenet_recovery_receive', 'automation.usenet_recovery_watchdog'):
        state = json.loads(command(['node', str(REPO / 'new-hass-configs/config-generator/dist/cli/home-assistant.js'), 'state', entity]))
        if state['state'] != 'on':
            raise RuntimeError('Recovery notification automation is not enabled')
    print(json.dumps({'ha_package': 'validated_and_loaded', 'notification': 'persistent_notification', 'secret': 'private'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='192.168.1.163')
    args = parser.parse_args()
    try:
        install(args.host)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else 'Recovery notification setup failed')
