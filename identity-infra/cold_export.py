"""Export a stopped directory. Caller must first disable/stop its only runtime."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile

from directory_state import identity, sysvol

os.umask(0o077)
root = Path('/data')
# Runtime locks/caches and prior backups are deliberately not restoration inputs.
# The authoritative private databases, idmaps, configuration and ACLs are.
selected = ['etc', 'private', 'state', 'bind-dns', 'identity.json',
            'authelia-bind.json', 'household-users.json', 'sysvol-acl.json']
with contextlib.redirect_stdout(sys.stderr):
    evidence = {'identity': identity(), 'sysvol': sysvol(), 'files': {}}
output = io.BytesIO()
with tarfile.open(fileobj=output, mode='w:gz') as archive:
    for name in selected:
        source = root/name
        if not source.exists():
            raise RuntimeError('Missing directory preservation input: '+name)
        for path in [source, *sorted(source.rglob('*'))] if source.is_dir() else [source]:
            relative = str(path.relative_to(root))
            if path.is_socket():
                continue
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise RuntimeError('Unexpected directory preservation file type')
            archive.add(path, arcname=relative, recursive=False)
            if path.is_file():
                evidence['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('dc.key', 'dc-chain.crt', 'ca.crt'):
        path = Path('/tls')/name
        relative = 'tls/'+name
        archive.add(path, arcname=relative, recursive=False)
        evidence['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    data=(json.dumps(evidence, sort_keys=True)+'\n').encode()
    item=tarfile.TarInfo('migration-evidence.json'); item.size=len(data); item.mode=0o600
    archive.addfile(item, io.BytesIO(data))
sys.stdout.buffer.write(output.getvalue())
