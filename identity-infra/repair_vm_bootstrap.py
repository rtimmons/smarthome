#!/usr/bin/env python3
"""Resume interrupted preparation without replacing guest or directory keys."""
import base64
import json
import os
import subprocess
import uuid

from manage import PRIVATE, connection
from vm_prepare import keypair, write_seed


def main():
    os.umask(0o077)
    root = PRIVATE/'vm'
    instance = json.loads((root/'instance.json').read_text())
    if instance.get('directory_migrated') is not False:
        raise RuntimeError('Bootstrap repair is only permitted before directory migration')
    identifier = str(uuid.UUID(instance['uuid']))
    original = root/'seed'
    config = json.loads((original/'user-data').read_text().split('\n', 1)[1])
    if not all((root/name).is_file() for name in
               ('id_ed25519_dc_vm', 'id_ed25519_dc_vm.pub',
                'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub')):
        raise RuntimeError('Restore missing original guest keys before repairing bootstrap')
    public = keypair(root/'id_ed25519_dc_vm', 'smarthome-directory-vm-operator')
    host_public = keypair(root/'ssh_host_ed25519_key', 'smarthome-directory-vm-host')
    if (config['users'][0]['ssh_authorized_keys'] != [public]
            or config['ssh_keys']['ed25519_public'] != host_public
            or config['ssh_keys']['ed25519_private'] != (root/'ssh_host_ed25519_key').read_text()):
        raise RuntimeError('Original seed keys differ; refusing repair or key replacement')
    # A new instance ID reruns interrupted once-per-instance modules. The
    # original seed and ISO remain available as diagnostic/recovery evidence.
    seed = root/'seed-repair-1'
    seed.mkdir(mode=0o700, exist_ok=True)
    iso = root/'cidata-repair-1.iso'
    write_seed(seed, {
        'user-data': (original/'user-data').read_text(),
        'meta-data': 'instance-id: smarthome-directory-vm-20261024-repair-1\nlocal-hostname: dc1\n',
        'network-config': (original/'network-config').read_text(),
    }, iso)
    if not iso.exists():
        subprocess.run(['hdiutil', 'makehybrid', '-iso', '-joliet', '-default-volume-name',
                        'cidata', '-o', str(iso), str(seed)], check=True, stdout=subprocess.DEVNULL)
    iso.chmod(0o600)
    payload = f'''set -eu
umask 077
root=/share/Container/home-identity
test ! -e "$root/vm-cutover.json"
qkvm=$(/sbin/getcfg QKVM Install_Path -f /etc/config/qpkg.conf)
test "$("$qkvm/usr/bin/virsh" -c qemu:///system domstate {identifier})" = 'shut off'
export LD_LIBRARY_PATH="$qkvm/usr/lib"
ulimit -v 524288
"$qkvm/usr/bin/qemu-img" check -f qcow2 "$root/vm/dc1.img"
if ! test -e "$root/vm/cidata-initial.iso"; then
 cp -p "$root/vm/cidata.iso" "$root/vm/cidata-initial.iso"
fi
printf '%s' '{base64.b64encode(iso.read_bytes()).decode()}' | base64 -d > "$root/vm/cidata.iso.new"
chmod 640 "$root/vm/cidata.iso.new"
chgrp administrators "$root/vm/cidata.iso.new"
mv "$root/vm/cidata.iso.new" "$root/vm/cidata.iso"
'''
    with (PRIVATE/'vm-repair-bootstrap.log').open('wb') as output:
        result = subprocess.run(connection(), input=payload.encode(), stdout=output,
                                stderr=subprocess.STDOUT, timeout=180)
    if result.returncode:
        raise RuntimeError('Bootstrap repair staging failed; inspect the private log')
    print('Repaired preparation seed staged with original keys; VM remains stopped and AD unchanged.')


if __name__ == '__main__':
    main()
