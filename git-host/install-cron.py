"""Install one preserved QNAP cron entry and notify its existing BusyBox daemon."""
import fcntl
import os
from pathlib import Path
import sys
import tempfile

PERSISTENT = Path('/persistent')
SPOOL = Path('/crontabs/admin')
ROOT = Path('/source')
MARKER = '# home-git-backup'
LINE = '23 * * * * /bin/sh /share/Container/home-git/backup.sh >> /share/Container/home-git/backup.log 2>&1 ' + MARKER
PROBE = '* * * * * /bin/date > /share/Container/home-git/cron-probe.txt # home-git-cron-probe'


def reconcile(existing, probe=False, remove=False):
    lines = [line for line in existing.splitlines() if not line.endswith((MARKER, '# home-git-cron-probe'))]
    return '\n'.join([*lines, *([] if remove else [LINE]), *([PROBE] if probe and not remove else [])]) + '\n'


def main():
    os.umask(0o077)
    with PERSISTENT.open('r+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        before = stream.read()
        if SPOOL.is_symlink() or not SPOOL.is_file():
            raise RuntimeError('Active cron must be an ordinary file')
        active_before = SPOOL.read_text()
        backup = ROOT / 'crontab.before-forgejo'
        if not backup.exists():
            backup.write_text(before); backup.chmod(0o600)
        # QTS can maintain different entries in these files. Preserve each
        # independently; never reconstruct one from the other or an old backup.
        checkpoint = Path(tempfile.mkdtemp(prefix='cron-checkpoint-', dir=ROOT))
        for name, content in (('persistent', before), ('active', active_before)):
            path = checkpoint / name
            path.write_text(content); path.chmod(0o600)
        stream.seek(0)
        if stream.read() != before or SPOOL.is_symlink() or SPOOL.read_text() != active_before:
            raise RuntimeError('Cron changed during preparation; inspect and retry')
        after = reconcile(before, '--probe' in sys.argv, '--remove' in sys.argv)
        active_after = reconcile(active_before, '--probe' in sys.argv, '--remove' in sys.argv)
        with tempfile.NamedTemporaryFile(mode='w', prefix='.forgejo-', dir=SPOOL.parent, delete=False) as temporary:
            temporary.write(active_after); temporary.flush(); os.fsync(temporary.fileno())
            temp = Path(temporary.name)
        stream.seek(0); stream.write(after); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, SPOOL)
        with (SPOOL.parent / 'cron.update').open('a') as update:
            update.write('admin\n')
    print('Forgejo cron reconciled; each file preserved separately in ' + checkpoint.name)


if __name__ == '__main__':
    main()
