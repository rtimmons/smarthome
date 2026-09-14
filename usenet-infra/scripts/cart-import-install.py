#!/usr/bin/env python3
"""Install reviewed importer helpers only while the shared operation lock is held.

Deployment stages complete files first. This helper serializes their atomic
replacement against native cart imports and scheduled cloud backup capture.
It never starts/stops applications or changes SAB state.
"""
from __future__ import annotations

import argparse
import fcntl
import grp
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile

FILES = ('cart-import.py', 'cart_import_sab.py', 'cart_import_arr.py',
         'discovery-config.py', 'catalogctl.py', 'config-backup.py', 'healthcheck.py')


class InstallError(RuntimeError):
    pass


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode) or any(p.is_symlink() for p in path.parents):
        raise InstallError('installer_path_invalid')


def require_quiet(stage, root):
    spec = importlib.util.spec_from_file_location('cart_install_backup', stage / 'config-backup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.require_idle(module.read_environment(root)['SABNZBD_API_KEY'])


def install(stage, root, *, quiet=require_quiet, gid=None):
    stage, root = Path(stage), Path(root)
    lock = root / 'state/catalog/locks/cache.lock'
    regular(lock)
    # Do not create or replace the shared lock inode used by running operations.
    with os.fdopen(os.open(lock, os.O_RDWR | os.O_NOFOLLOW), 'r+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise InstallError('backup_or_import_active_no_files_changed') from None
        status = root / 'state/catalog/cart-import/status.json'
        if status.exists() or status.is_symlink():
            regular(status)
            if json.loads(status.read_text()).get('status') == 'processing':
                raise InstallError('prior_import_processing_requires_recovery')
        # Validate every staged/target path before any deployed file changes.
        sources = {}
        for name in FILES:
            path = stage / name
            regular(path)
            data = path.read_bytes()
            if len(data) > 2 * 1024 * 1024:
                raise InstallError('helper_exceeds_bound')
            compile(data, name, 'exec')
            target = root / 'libexec' / name
            if target.exists() or target.is_symlink():
                regular(target)
            elif any(p.is_symlink() for p in target.parents):
                raise InstallError('installer_path_invalid')
            sources[name] = data
        quiet(stage, root)
        changed = []
        for name, data in sources.items():
            target = root / 'libexec' / name
            ownership_ok = target.is_file() and (gid is None or (target.stat().st_uid == 0 and target.stat().st_gid == gid))
            if ownership_ok and target.read_bytes() == data and stat.S_IMODE(target.stat().st_mode) == 0o550:
                continue
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                    temporary = Path(output.name)
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                    os.fchmod(output.fileno(), 0o550)
                    if gid is not None:
                        os.fchown(output.fileno(), 0, gid)
                os.replace(temporary, target)
                temporary = None
                changed.append(name)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return {'status': 'installed', 'changed': len(changed), 'shared_lock_held': True, 'quiet_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path('/srv/usenet'))
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.stage, args.root, gid=grp.getgrnam('usenet').gr_gid), sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__,
                          'detail': 'Cart installation refused or incomplete; timer remains stopped. No application or job was interrupted.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
