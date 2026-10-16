"""Verify installed code without importing SAB or opening its configuration."""
import hashlib
import json
from pathlib import Path


def verify(root=Path('/')):
    manifest = json.loads((root / 'opt/sab-buffered/manifest.json').read_text())
    expected = {'/app/sabnzbd/sabnzbd/filesystem.py', '/app/sabnzbd/sabnzbd/buffered_copy.py'}
    if manifest['version'] != 1 or set(manifest['files']) != expected:
        raise RuntimeError('buffered_copy_manifest_invalid')
    for name, digest in manifest['files'].items():
        if hashlib.sha256((root / name.lstrip('/')).read_bytes()).hexdigest() != digest:
            raise RuntimeError('buffered_copy_integrity_failed')
    return manifest


if __name__ == '__main__':
    verify()
    print('storagebox-buffered-v1 integrity verified')
