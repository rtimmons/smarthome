#!/usr/bin/env python3
"""Install only leaf TLS material on HA; preserve CA keys on the controller."""
import base64
import subprocess

from manage import PRIVATE, ROOT


def main():
    script = 'set -eu\numask 077\ntest ! -L /ssl/smarthome\nmkdir -p /ssl/smarthome\n'
    for name in ('web.key', 'web-chain.crt', 'ca.crt'):
        data = (PRIVATE/'tls'/name).read_bytes()
        encoded = base64.b64encode(data).decode()
        script += f"printf '%s' '{encoded}' | base64 -d > /ssl/smarthome/{name}.new\n"
        if name in ('web.key', 'ca.crt'):
            script += f'''if test -e /ssl/smarthome/{name}; then
 cmp /ssl/smarthome/{name} /ssl/smarthome/{name}.new
fi
'''
        script += f'chmod 600 /ssl/smarthome/{name}.new\nmv /ssl/smarthome/{name}.new /ssl/smarthome/{name}\n'
    args = ['ssh','-T','-i',str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
            '-o','IdentitiesOnly=yes','-o','IdentityAgent=none','-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
            'root@homeassistant.local','sh -s']
    result = subprocess.run(args, input=script.encode(), capture_output=True, timeout=60)
    if result.returncode:
        (PRIVATE/'stage-web.log').write_bytes(result.stderr)
        raise RuntimeError('HA TLS staging failed; inspect the private log. No fallback credentials attempted.')
    print('HA leaf certificate staged. CA signing keys remain on the controller.')


if __name__ == '__main__': main()
