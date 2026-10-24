"""Pinned maintenance transport through the repository-owned HA SSH identity."""
import ipaddress
import json
import shlex
import subprocess

from manage import ROOT
from vm_guest import connection as guest_connection


def ha_connection():
    return ['ssh', '-T', '-i', str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
            'root@homeassistant.local']


def connection():
    result = subprocess.run(ha_connection()+['ha apps info local_directory --raw-json'],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('HA SSH inspection failed; no alternate credentials attempted')
    info = json.loads(result.stdout)['data']
    if info.get('state') != 'started':
        raise RuntimeError('Directory app is not started')
    address = str(ipaddress.IPv4Address(info['ip_address']))
    if ipaddress.IPv4Address(address) not in ipaddress.IPv4Network('172.30.32.0/23'):
        raise RuntimeError('Unexpected directory bridge address')
    command = guest_connection('192.168.1.11')
    command[-2] = 'identity-admin@'+address
    proxy = shlex.join(ha_connection()+['nc', address, '22'])
    return command[:-2]+['-o', 'ProxyCommand='+proxy]+command[-2:]


def execute(script, timeout=120):
    return subprocess.run(connection(), input=script, capture_output=True, timeout=timeout)


def main():
    result = execute(b'''set -eu
hostname
samba --version
ip -brief address
ps -eo comm | sort -u
test ! -e /data/migration-ready.json
test ! -e /data/private/sam.ldb
dig @192.168.1.11 +short probe.directory-preparation.invalid
dig @192.168.1.11 +tcp +short probe.directory-preparation.invalid
''')
    if result.returncode:
        from manage import PRIVATE
        (PRIVATE/'ha-directory-preparation.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('Pinned directory preparation check failed; see private log')
    print(result.stdout.decode(), end='')
    print('Preserved SSH host/operator identity passed; no AD database or production listener exists.')


if __name__ == '__main__':
    main()
