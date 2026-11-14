"""Dedicated QNAP SSH connection for controller tools."""
from pathlib import Path
import re
import stat


class QnapConnectionError(RuntimeError):
    pass


def connection_command(environment: dict) -> list[str]:
    values = {name: environment.get(name, '') for name in ('QNAP_SSH_TARGET', 'QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS')}
    if not all(values.values()) or not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9][A-Za-z0-9.-]*', values['QNAP_SSH_TARGET']):
        raise QnapConnectionError('dedicated_qnap_connection_settings_missing_or_invalid')
    for name in ('QNAP_SSH_KEY', 'QNAP_SSH_KNOWN_HOSTS'):
        path = Path(values[name]).expanduser().resolve()
        if not path.is_file():
            raise QnapConnectionError('dedicated_key_or_pinned_known_hosts_file_missing')
        if name == 'QNAP_SSH_KEY' and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise QnapConnectionError('dedicated_private_key_permissions_must_be_0600')
        values[name] = str(path)
    return ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'IdentityAgent=none', '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-i', values['QNAP_SSH_KEY'],
            '-o', 'UserKnownHostsFile=' + values['QNAP_SSH_KNOWN_HOSTS'], '--', values['QNAP_SSH_TARGET'], 'sh -s']
