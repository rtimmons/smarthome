#!/usr/bin/env python3
"""Prepare an unstarted NAS guest; never modify the live directory or its IP."""
import base64
import json
import os
from pathlib import Path
import subprocess

from manage import PRIVATE, connection

IMAGE_URL = 'https://cloud-images.ubuntu.com/releases/resolute/release-20261016/ubuntu-26.04-server-cloudimg-amd64.img'
IMAGE_SHA256 = '5645d0318ad21f643ebb1ac4567514620e9893380b07b0201fda163baa5b7eb5'
REMOTE = '/share/Container/home-identity/vm'


def keypair(path, comment):
    public_path = path.with_suffix('.pub')
    if public_path.exists() and not path.exists():
        raise RuntimeError('Existing dedicated private key is missing; restore it instead of replacing it')
    if not path.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', comment, '-f', str(path)], check=True)
    if not public_path.is_file():
        raise RuntimeError('Existing dedicated key has no public half; refusing replacement')
    path.chmod(0o600)
    public = public_path.read_text().strip()
    derived = subprocess.check_output(['ssh-keygen', '-y', '-f', str(path)], stderr=subprocess.DEVNULL).decode()
    if derived.split()[:2] != public.split()[:2]:
        raise RuntimeError('Dedicated private/public keys differ; refusing to use or replace them')
    return public


def write_seed(seed, contents, iso):
    # An existing image contains credentials. Never silently describe a new
    # seed while uploading stale bytes from an older ISO.
    if iso.exists():
        if any(not (seed/name).is_file() or (seed/name).read_text() != value
               for name, value in contents.items()):
            raise RuntimeError('Existing bootstrap ISO differs from the requested seed; preserve it and prepare an explicit new image')
        return
    for name, value in contents.items():
        (seed/name).write_text(value)


def main():
    os.umask(0o077)
    root = PRIVATE/'vm'
    root.mkdir(mode=0o700, exist_ok=True)
    if (root/'image.json').exists() and not all((root/name).is_file() for name in
            ('id_ed25519_dc_vm', 'id_ed25519_dc_vm.pub', 'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub')):
        raise RuntimeError('Previously prepared VM is missing key material; restore its recovery archive')
    public = keypair(root/'id_ed25519_dc_vm', 'smarthome-directory-vm-operator')
    host_public = keypair(root/'ssh_host_ed25519_key', 'smarthome-directory-vm-host')
    seed = root/'seed'
    seed.mkdir(mode=0o700, exist_ok=True)
    # JSON is valid YAML. SSH host identity is pinned before its first boot.
    config = {
        'hostname': 'dc1', 'fqdn': 'dc1.ad.home.arpa', 'manage_etc_hosts': True,
        'users': [{'name': 'identity-admin', 'groups': ['sudo'], 'shell': '/bin/bash',
                   'sudo': 'ALL=(ALL) NOPASSWD:ALL', 'lock_passwd': True,
                   'ssh_authorized_keys': [public]}],
        'disable_root': True, 'ssh_pwauth': False,
        'ssh_keys': {'ed25519_private': (root/'ssh_host_ed25519_key').read_text(),
                     'ed25519_public': host_public},
        'ssh_publish_hostkeys': {'enabled': False},
        'package_update': True,
        'packages': ['qemu-guest-agent', 'samba-ad-dc', 'samba-ad-provision', 'krb5-user',
                     'bind9-dnsutils', 'ldap-utils', 'smbclient', 'python3-samba',
                     'ca-certificates', 'openssl', 'iputils-arping', 'tdb-tools'],
        'bootcmd': [['cloud-init-per', 'once', 'block-unconfigured-samba', 'systemctl',
                     'mask', 'samba-ad-dc.service', 'smbd.service', 'nmbd.service', 'winbind.service']],
        'runcmd': [['systemctl', 'enable', '--now', 'qemu-guest-agent.service'],
                  ['sh', '-c', 'install -d -m 0700 /data /tls; touch /var/lib/smarthome-guest-prepared']],
        'final_message': 'Smarthome guest prepared; directory remains stopped pending controlled migration.'
    }
    # DHCP only during preparation. The live DC retains .10 until the cutover.
    iso = root/'cidata.iso'
    write_seed(seed, {
        'user-data': '#cloud-config\n'+json.dumps(config, indent=2)+'\n',
        'meta-data': 'instance-id: smarthome-directory-vm-20261024\nlocal-hostname: dc1\n',
        'network-config': 'version: 2\nethernets:\n  primary:\n    match:\n      name: "e*"\n    dhcp4: true\n    dhcp6: false\n    optional: true\n',
    }, iso)
    if not iso.exists():
        subprocess.run(['hdiutil', 'makehybrid', '-iso', '-joliet', '-default-volume-name',
                        'cidata', '-o', str(iso), str(seed)], check=True, stdout=subprocess.DEVNULL)
    iso.chmod(0o600)
    # Authenticate transport with the already pinned NAS identity. No guest or
    # directory credentials are passed in argv or written into checkout files.
    payload = f'''set -eu
umask 077
mkdir -p {REMOTE}
chmod 700 {REMOTE}
test ! -L {REMOTE}/ubuntu-base.img
if ! test -f {REMOTE}/ubuntu-base.img; then
 curl --fail --location --silent --show-error --retry 3 '{IMAGE_URL}' -o {REMOTE}/ubuntu-base.img.part
 echo '{IMAGE_SHA256}  {REMOTE}/ubuntu-base.img.part' | sha256sum -c -
 mv {REMOTE}/ubuntu-base.img.part {REMOTE}/ubuntu-base.img
fi
echo '{IMAGE_SHA256}  {REMOTE}/ubuntu-base.img' | sha256sum -c -
chmod 600 {REMOTE}/ubuntu-base.img
printf '%s' '{base64.b64encode(iso.read_bytes()).decode()}' | base64 -d > {REMOTE}/cidata.iso.new
chmod 600 {REMOTE}/cidata.iso.new
mv {REMOTE}/cidata.iso.new {REMOTE}/cidata.iso
df -h {REMOTE}
'''
    log = PRIVATE/'vm-prepare.log'
    with log.open('wb') as stream:
        result = subprocess.run(connection(), input=payload.encode(), stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
    if result.returncode:
        raise RuntimeError(f'Guest preparation failed; see {log}')
    (root/'image.json').write_text(json.dumps({'url': IMAGE_URL, 'sha256': IMAGE_SHA256}, indent=2)+'\n')
    print('Verified Ubuntu image and private cloud-init seed staged on NAS. No VM started; live AD unchanged.')


if __name__ == '__main__':
    main()
