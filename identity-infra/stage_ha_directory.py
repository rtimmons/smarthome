#!/usr/bin/env python3
"""Stage only the preserved maintenance identity; never provision a domain."""
import io
import json
import os
import subprocess
import tarfile

from manage import PRIVATE, ROOT
from vm_prepare import keypair


def main():
    os.umask(0o077)
    root = PRIVATE/'vm'
    names = ('id_ed25519_dc_vm', 'id_ed25519_dc_vm.pub',
             'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub')
    if not all((root/name).is_file() for name in names):
        raise RuntimeError('Restore the preserved directory keys; do not generate replacements')
    keypair(root/'id_ed25519_dc_vm', 'smarthome-directory-vm-operator')
    keypair(root/'ssh_host_ed25519_key', 'smarthome-directory-vm-host')
    files = {name: (root/name).read_bytes() for name in
             ('ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub')}
    files['operator.pub'] = (root/'id_ed25519_dc_vm.pub').read_bytes()
    files['preparation.json'] = (json.dumps({'address': '192.168.1.11'})+'\n').encode()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        for name, data in files.items():
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(data), 0o600
            archive.addfile(item, io.BytesIO(data))
    script = '''set -eu
umask 077
test ! -L /ssl/smarthome
mkdir -p /ssl/smarthome
test ! -e /ssl/smarthome/directory-seed
mkdir -m 700 /ssl/smarthome/directory-seed
tar -xf - -C /ssl/smarthome/directory-seed
'''
    command = ['ssh', '-T', '-i', str(ROOT/'.ssh/id_ed25519_codex_smarthome'),
               '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'BatchMode=yes',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
               'root@homeassistant.local', script]
    result = subprocess.run(command, input=payload.getvalue(), capture_output=True, timeout=60)
    if result.returncode:
        (PRIVATE/'stage-ha-directory.log').write_bytes(result.stdout+result.stderr)
        raise RuntimeError('HA directory seed staging failed; no alternate credentials attempted')
    print('Preserved directory SSH identity staged on HA. No AD databases or administrator passwords copied.')


if __name__ == '__main__':
    main()
