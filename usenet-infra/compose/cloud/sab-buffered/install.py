"""Build-time, exact-version adapter installation; never modifies live files."""
import hashlib
import json
from pathlib import Path
import shutil

UPSTREAM_SHA256 = '6d953b28cd99ca9b6839bfb5dc0a58f69c94a15450b7b457ef25533a6f165a33'
APP = Path('/app/sabnzbd/sabnzbd')
WORK = Path('/opt/sab-buffered')
BINDING = '''
# Repository-owned, version-pinned Storage Box copy adapter. Global shutil stays unchanged.
from sabnzbd.buffered_copy import BufferedCopy as _StorageBoxCopy
shutil = _StorageBoxCopy('/data/incomplete', '/data/complete/remote/complete')
'''


def patched(source):
    if hashlib.sha256(source).hexdigest() != UPSTREAM_SHA256:
        raise RuntimeError('unreviewed_sab_filesystem_source')
    return source + BINDING.encode()


def main():
    source = APP / 'filesystem.py'
    changed = patched(source.read_bytes())
    compile(changed, str(source), 'exec')
    source.write_bytes(changed)
    shutil.copyfile(WORK / 'buffered_copy.py', APP / 'buffered_copy.py')
    files = [source, APP / 'buffered_copy.py']
    (WORK / 'manifest.json').write_text(json.dumps({
        'version': 1, 'upstream_sha256': UPSTREAM_SHA256,
        'files': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2) + '\n')


if __name__ == '__main__':
    main()
