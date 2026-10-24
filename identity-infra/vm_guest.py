#!/usr/bin/env python3
"""Inspect the prepared guest using its pre-generated, pinned SSH identity."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess

from manage import PRIVATE


def connection(host):
    address = ipaddress.IPv4Address(host)
    if address not in ipaddress.IPv4Network('192.168.1.0/24') or address.packed[-1] in (0, 1, 255):
        raise ValueError('Guest must use an explicit household LAN address')
    root = PRIVATE/'vm'
    identity = root/'id_ed25519_dc_vm'
    if not identity.is_file() or identity.stat().st_mode & 0o077:
        raise RuntimeError('Restore the dedicated guest key with private permissions')
    public = (root/'ssh_host_ed25519_key.pub').read_text().split()
    if len(public) < 2 or public[0] != 'ssh-ed25519':
        raise RuntimeError('Missing prepared guest host identity; do not accept a discovered replacement')
    expected = 'smarthome-directory-vm '+ ' '.join(public[:2])+'\n'
    hosts = root/'known_hosts'
    if hosts.exists() and hosts.read_text() != expected:
        raise RuntimeError('Pinned guest host key differs; refusing replacement')
    if not hosts.exists():
        fd = os.open(hosts, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(expected)
    return ['ssh', '-T', '-i', str(identity), '-o', 'BatchMode=yes',
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
            '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=smarthome-directory-vm',
            '-o', 'UserKnownHostsFile='+str(hosts), '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            'identity-admin@'+str(address), 'sudo -n sh -s']


STATUS = '''set -eu
date -u
cloud-init status --long || true
test ! -f /var/lib/smarthome-guest-prepared || echo 'Guest package preparation marker present'
hostname
ip -brief address
free -m
df -h /
for service in samba-ad-dc smbd nmbd winbind smarthome-directory qemu-guest-agent; do
 printf '%s: ' "$service"; systemctl is-active "$service" || true
done
command -v samba >/dev/null 2>&1 && samba --version || true
systemctl --failed --no-pager
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    args = parser.parse_args()
    log = PRIVATE/'vm-guest-status.log'
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as output:
        result = subprocess.run(connection(args.host), input=STATUS.encode(),
                                stdout=output, stderr=subprocess.STDOUT, timeout=120)
    print(f'Guest status: exit {result.returncode}; private log: {log}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
