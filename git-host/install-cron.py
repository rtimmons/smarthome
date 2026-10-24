"""Install one preserved QNAP cron entry and notify its existing BusyBox daemon."""
import fcntl
import os
from pathlib import Path
import sys

PERSISTENT = Path('/persistent')
SPOOL = Path('/crontabs/admin')
ROOT = Path('/source')
MARKER = '# home-git-backup'
LINE = '23 * * * * /bin/sh /share/Container/home-git/backup.sh >> /share/Container/home-git/backup.log 2>&1 ' + MARKER
PROBE = '* * * * * /bin/date > /share/Container/home-git/cron-probe.txt # home-git-cron-probe'


def reconcile(existing, probe=False):
    lines = [line for line in existing.splitlines() if not line.endswith((MARKER, '# home-git-cron-probe'))]
    return '\n'.join([*lines, LINE, *([PROBE] if probe else [])]) + '\n'


def main():
    os.umask(0o077)
    with PERSISTENT.open('r+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        before = stream.read()
        if SPOOL.is_symlink() or SPOOL.read_text() != before:
            raise RuntimeError('Persistent and active cron differ; preserve both and inspect')
        backup = ROOT / 'crontab.before-forgejo'
        if not backup.exists():
            backup.write_text(before); backup.chmod(0o600)
        after = reconcile(before, '--probe' in sys.argv)
        stream.seek(0); stream.write(after); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
        temp = SPOOL.with_suffix('.forgejo-new')
        temp.write_text(after); temp.chmod(0o600)
        os.replace(temp, SPOOL)
        with (SPOOL.parent / 'cron.update').open('a') as update:
            update.write('admin\n')
    print('Forgejo cron installed; unrelated entries preserved.')


if __name__ == '__main__':
    main()
