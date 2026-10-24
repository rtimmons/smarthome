"""Start only preserved identities; preparation cannot launch an AD listener."""
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

os.umask(0o077)
state = Path('/data')
configuration = Path('/config')
seed = Path('/ssl/smarthome/directory-seed')
configuration.mkdir(mode=0o700, exist_ok=True)


def preserve(source, destination, mode=0o600):
    if destination.is_symlink():
        raise RuntimeError('Refusing a linked private input')
    if destination.exists():
        if source.exists() and source.read_bytes() != destination.read_bytes():
            raise RuntimeError('Existing directory identity differs; refusing replacement')
    elif source.is_file():
        destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    else:
        raise RuntimeError('Restore the original directory bootstrap before starting')
    destination.chmod(mode)


for name in ('ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub', 'operator.pub'):
    preserve(seed/name, state/'ssh'/name)
preserve(seed/'preparation.json', configuration/'preparation.json')
settings = json.loads((configuration/'preparation.json').read_text())
address = str(ipaddress.IPv4Address(settings['address']))
if address != '192.168.1.11':
    raise RuntimeError('Unexpected preparation address')
activation = state/'migration-ready.json'
if activation.exists():
    approved = json.loads(activation.read_text())
    if approved.get('domain_sid') != 'S-1-5-21-2612071719-3246555018-4093554428':
        raise RuntimeError('Existing AD identity differs; refusing startup')
    identity = json.loads((state/'identity.json').read_text())
    if identity != {'realm': 'AD.HOME.ARPA', 'domain': 'SMARTHOME',
                    'hostname': 'dc1', 'hostip': '192.168.1.10'}:
        raise RuntimeError('Directory identity marker differs')
    for required in ('private/sam.ldb', 'etc/smb.conf', 'tls/dc.key', 'tls/dc-chain.crt', 'tls/ca.crt'):
        if not (state/required).is_file():
            raise RuntimeError('Existing domain is incomplete; restore instead of reprovisioning')
    address = '192.168.1.10'

# This capability applies only inside this container's network namespace.
# The companion app owns the separate, narrowly scoped host route.
subprocess.run(['ip', 'address', 'replace', address+'/32', 'dev', 'lo'], check=True)
account = subprocess.check_output(['id', '-u', 'identity-admin']).decode().strip()
home = Path('/home/identity-admin/.ssh')
home.mkdir(mode=0o700, exist_ok=True)
public = (state/'ssh/operator.pub').read_text().strip()+'\n'
(home/'authorized_keys').write_text(public)
(home/'authorized_keys').chmod(0o600)
os.chown(home, int(account), int(account))
os.chown(home/'authorized_keys', int(account), int(account))
Path('/run/sshd').mkdir(exist_ok=True)
Path('/run/sshd-directory.conf').write_text('''Port 22
HostKey /data/ssh/ssh_host_ed25519_key
AuthorizedKeysFile .ssh/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers identity-admin
UsePAM yes
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
PrintMotd no
PidFile /run/sshd-directory.pid
''')
children = [subprocess.Popen(['/usr/sbin/sshd', '-D', '-e', '-f', '/run/sshd-directory.conf'])]
if activation.exists():
    from directory_state import recover_checkpoint
    recover_checkpoint()
    shutil.copyfile('/data/private/krb5.conf', '/etc/krb5.conf')
    # Docker recreates this container-local file. AD must resolve its own zone
    # through Samba after every rebuild, independent of Supervisor DNS policy.
    # This changes only the isolated directory namespace, never the HA host.
    Path('/etc/resolv.conf').write_text(
        'nameserver 127.0.0.1\nsearch ad.home.arpa\noptions timeout:2 attempts:2\n')
    children.append(subprocess.Popen(['/usr/sbin/samba', '--foreground', '--no-process-group',
                                     '--configfile=/data/etc/smb.conf']))
    print('Preserved household directory started.', flush=True)
else:
    children.append(subprocess.Popen([
        'dnsmasq', '--no-daemon', '--user=root', '--group=root', '--port=53',
        '--listen-address=192.168.1.11', '--bind-interfaces', '--no-resolv', '--no-hosts',
        '--address=/probe.directory-preparation.invalid/192.0.2.1', '--local-ttl=0']))
    print('Directory preparation ready; AD remains stopped.', flush=True)


def terminate(*_, exit_code=0):
    clean = True
    for process in children:
        if process.poll() is None:
            process.terminate()
    for process in children:
        try:
            process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            clean = False
            process.kill()
            process.wait()
    if activation.exists() and clean:
        from directory_state import checkpoint
        checkpoint()
        print('Portable SYSVOL permissions saved for cold recovery.', flush=True)
    raise SystemExit(exit_code)


signal.signal(signal.SIGTERM, terminate)
signal.signal(signal.SIGINT, terminate)
while all(process.poll() is None for process in children):
    time.sleep(1)
terminate(exit_code=1)
