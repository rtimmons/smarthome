#!/usr/bin/env python3
"""Root-only capture of Filex state; publish only encrypted recovery material."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import tempfile
import time

LIBEXEC = Path('/srv/usenet/libexec')
OUTPUT = Path('/srv/usenet/config/filex-recovery')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location('backup', LIBEXEC / 'config-backup.py')
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    try:
        if os.geteuid() != 0 or OUTPUT.is_symlink():
            raise RuntimeError('root_owned_recovery_directory_required')
        account = pwd.getpwnam('usenet')
        OUTPUT.mkdir(mode=0o750, exist_ok=True)
        os.chown(OUTPUT, 0, account.pw_gid)
        OUTPUT.chmod(0o750)
        receipt_path = OUTPUT / 'latest.json'
        archive_path = OUTPUT / 'latest.tar.age'
        if receipt_path.exists() and not args.force:
            receipt = json.loads(receipt_path.read_text())
            if time.time() - receipt['created_at'] < 23 * 3600 and archive_path.is_file() and backup.digest(archive_path) == receipt['sha256']:
                print(json.dumps({'status': 'fresh', 'scope': 'filex-config'}))
                return
        backup.check_age(str(LIBEXEC / 'age'))
        with tempfile.TemporaryDirectory(prefix='filex-backup-') as directory:
            private = Path(directory)
            stage = private / 'stage'
            stage.mkdir(mode=0o700)
            manifest = backup.stage_snapshot(Path('/'), stage, scope='filex-config')
            encrypted = private / 'filex.tar.age'
            backup.encrypt(stage, Path('/srv/usenet/config/backup-recipient.pub'), encrypted, str(LIBEXEC / 'age'))
            receipt = {'schema_version': 1, 'scope': 'filex-config', 'created_at': int(time.time()),
                       'sha256': backup.digest(encrypted), 'files': len(manifest['entries']),
                       'sqlite_databases': sum(e['sqlite'] for e in manifest['entries'])}
            # The destination is root-owned and the service is serialized by systemd.
            target = OUTPUT / 'next.tar.age'
            with target.open('xb') as stream:
                stream.write(encrypted.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            target.chmod(0o600)
            os.chown(target, account.pw_uid, account.pw_gid)
            os.replace(target, archive_path)
            temp_receipt = OUTPUT / 'latest.json.new'
            temp_receipt.write_text(json.dumps(receipt) + '\n')
            temp_receipt.chmod(0o640)
            os.chown(temp_receipt, 0, account.pw_gid)
            os.replace(temp_receipt, receipt_path)
        print(json.dumps({'status': 'captured', 'files': receipt['files'], 'sqlite_databases': receipt['sqlite_databases']}))
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
