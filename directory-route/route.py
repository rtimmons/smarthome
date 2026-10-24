"""Own one proxy-ARP route; never alter HA's addresses, default route or DNS."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import paramiko

CHAIN = 'SMARTHOME_AD'
COMMENT = 'smarthome-directory-route-v1'
LAN = 'enp4s0'
BRIDGE = 'hassio'
STATE = Path('/data/route-owner.json')
TCP = '53,88,135,389,445,464,636,3268,3269,50000:50050'
UDP = '53,88,389,464'


def command(*args, check=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=15)
    if check and result.returncode:
        raise RuntimeError(f'Network command failed: {args!r}: {result.stderr.strip()}')
    return result


def approved_address(value):
    if value not in ('192.168.1.11', '192.168.1.10'):
        raise ValueError('Only the reviewed preparation and directory addresses are supported')
    return value


def approved_backend(value):
    address = ipaddress.IPv4Address(value)
    if address not in ipaddress.IPv4Network('172.30.32.0/23') or value in ('172.30.32.0', '172.30.32.1', '172.30.32.2', '172.30.32.3', '172.30.33.255'):
        raise ValueError('Directory backend must be an app on the Supervisor bridge')
    return str(address)


def backend(public):
    address = approved_backend(socket.gethostbyname('local-directory'))
    with socket.create_connection((address, 22), timeout=5) as connection:
        transport = paramiko.Transport(connection)
        try:
            transport.start_client(timeout=5)
            key = transport.get_remote_server_key()
            if key.get_name() != public[0] or key.asbytes() != base64.b64decode(public[1], validate=True):
                raise RuntimeError('Directory SSH identity mismatch; route withheld')
        finally:
            transport.close()
    return address


def firewall_tool():
    candidates = []
    for name in ('iptables-nft', 'iptables-legacy'):
        result = command(name, '-S', check=False)
        if result.returncode == 0 and '-N DOCKER' in result.stdout:
            candidates.append(name)
    if len(candidates) != 1:
        raise RuntimeError('Cannot identify the single active Docker firewall')
    return candidates[0]


def rules(address):
    # Return traffic is scoped to the directory's address. No unrelated packet
    # reaches this chain, and no broad Docker or host policy is replaced.
    return [
        ['-s', address+'/32', '-i', BRIDGE, '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
        *[['-d', address+'/32', '-s', source, '-i', interface, '-p', protocol,
           '--dport', port, '-j', 'ACCEPT']
          for source, interface in [('192.168.1.0/24', LAN), ('172.30.32.0/23', BRIDGE)]
          for protocol, ports in [('tcp', TCP), ('udp', UDP)]
          for port in ports.split(',')],
        ['-j', 'DROP'],
    ]


def jumps(address):
    return [['-d', address+'/32', '-m', 'comment', '--comment', COMMENT, '-j', CHAIN],
            ['-s', address+'/32', '-m', 'comment', '--comment', COMMENT, '-j', CHAIN]]


def cleanup():
    if not STATE.exists():
        return
    owned = json.loads(STATE.read_text())
    address, target, firewall = owned['address'], owned['backend'], owned['firewall']
    approved_address(address)
    approved_backend(target)
    if firewall not in ('iptables-nft', 'iptables-legacy'):
        raise RuntimeError('Invalid owned firewall marker')
    # Exact-match deletion cannot remove another route or another app's rules.
    command('ip', 'neigh', 'del', 'proxy', address, 'dev', LAN, check=False)
    command('ip', 'route', 'del', address+'/32', 'via', target, 'dev', BRIDGE, 'proto', '186', check=False)
    for rule in jumps(address):
        while command(firewall, '-C', 'FORWARD', *rule, check=False).returncode == 0:
            command(firewall, '-D', 'FORWARD', *rule)
    if command(firewall, '-S', CHAIN, check=False).returncode == 0:
        contents = command(firewall, '-S', CHAIN).stdout.splitlines()
        if any(line.startswith('-A ') and COMMENT not in line for line in contents):
            raise RuntimeError('Foreign rule in owned chain; refusing deletion')
        command(firewall, '-F', CHAIN)
        command(firewall, '-X', CHAIN)
    STATE.unlink()


def install(address, target, firewall):
    if Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() != '1':
        raise RuntimeError('Host forwarding is disabled; refusing to change host sysctls')
    routes = json.loads(command('ip', '-j', 'route', 'show', 'exact', address+'/32').stdout)
    if routes or command('ip', 'neigh', 'show', 'proxy', 'dev', LAN).stdout.find(address+' ') >= 0:
        raise RuntimeError('Address already has a route or proxy owner')
    if command(firewall, '-S', CHAIN, check=False).returncode == 0:
        raise RuntimeError('Firewall chain already exists without ownership')
    if command('arping', '-D', '-I', LAN, '-c', '3', '-w', '5', address, check=False).returncode != 0:
        raise RuntimeError('LAN address conflict or failed duplicate-address check')
    owned = {'address': address, 'backend': target, 'firewall': firewall}
    with STATE.open('x') as output:
        json.dump(owned, output)
        output.flush()
        os.fsync(output.fileno())
    command(firewall, '-N', CHAIN)
    for rule in rules(address):
        command(firewall, '-A', CHAIN, '-m', 'comment', '--comment', COMMENT, *rule)
    for rule in jumps(address):
        command(firewall, '-I', 'FORWARD', '1', *rule)
    command('ip', 'route', 'add', address+'/32', 'via', target, 'dev', BRIDGE, 'proto', '186')
    command('ip', 'neigh', 'add', 'proxy', address, 'dev', LAN)
    # Announce the new next-hop MAC after the route and firewall are ready.
    command('arping', '-U', '-I', LAN, '-c', '2', address, check=False)
    print('Directory route installed after pinned backend and address checks.', flush=True)
    return owned


def main():
    os.umask(0o077)
    public_path = Path('/data/ssh-host-key.pub')
    source = Path('/ssl/smarthome/directory-seed/ssh_host_ed25519_key.pub')
    if not public_path.exists():
        public_path.write_bytes(source.read_bytes())
    elif source.exists() and source.read_bytes() != public_path.read_bytes():
        raise RuntimeError('Pinned directory public key differs')
    public = public_path.read_text().split()
    if len(public) < 2 or public[0] != 'ssh-ed25519':
        raise RuntimeError('Missing preserved directory public identity')
    address = approved_address(json.loads(Path('/data/options.json').read_text())['address'])
    firewall = firewall_tool()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    cleanup()
    active = None
    try:
        while True:
            try:
                target = backend(public)
            except (OSError, paramiko.SSHException, RuntimeError, ValueError):
                if active:
                    cleanup()
                    active = None
                    print('Directory backend unavailable; route withdrawn.', flush=True)
                time.sleep(10)
                continue
            if active and active['backend'] != target:
                cleanup()
                active = None
            if not active:
                active = install(address, target, firewall)
            time.sleep(30)
    finally:
        cleanup()


if __name__ == '__main__':
    main()
