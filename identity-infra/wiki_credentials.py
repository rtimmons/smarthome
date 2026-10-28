"""Read or add only the existing wiki password in the current SOPS escrow."""
import base64
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile

import credentials
from manage import PRIVATE


class CredentialError(ValueError):
    pass


ENTRY = 'tree/build/identity-private/secrets/wiki-runtime.json'


def decode(data):
    value = json.loads(data)
    password = value.get('password')
    if (value.get('account') != 'svc-wiki' or not isinstance(password, str)
            or not password or any(c in password for c in '\r\n\x00')):
        raise CredentialError('Wiki credential entry is invalid; no credential changed')
    return password


def password_from_vault(budget):
    key = Path(os.environ.get('SMARTHOME_RECOVERY_KEY', Path.home()/'.config/smarthome/recovery.agekey'))
    original = credentials.VAULT.read_bytes()
    document = budget.call('SOPS credential read', lambda timeout:
        credentials.decrypt(original, key, timeout=timeout), 10)
    entries = credentials.unpack(document)
    if ENTRY in entries:
        return decode(entries[ENTRY])

    local = PRIVATE/'secrets/wiki-runtime.json'
    if local.exists():
        if local.is_symlink():
            raise CredentialError('Linked wiki credential refused')
        data = local.read_bytes()
        password = decode(data)
    else:
        if not sys.stdin.isatty():
            raise CredentialError('Wiki password is absent from SOPS; run interactively to add the existing password')
        password = getpass.getpass('Existing svc-wiki password to save in SOPS (hidden): ')
        confirm = getpass.getpass('Confirm existing password (hidden): ')
        if password != confirm:
            raise CredentialError('Passwords differ; nothing saved')
        data = (json.dumps({'account': 'svc-wiki', 'password': password})+'\n').encode()
        decode(data)

    # Merge this entry only, preserving every existing recovery input. Keep its
    # local source in the already-covered secrets directory for future capture.
    document['entries'][ENTRY] = {'content': base64.b64encode(data).decode(),
                                  'sha256': credentials.digest(data)}
    payload = json.dumps({'payload': json.dumps(document, sort_keys=True)}).encode()
    cipher = budget.call('SOPS credential save', lambda timeout:
        credentials.crypt(payload, key, encrypt=True, timeout=timeout), 10)
    checked = budget.call('SOPS credential readback', lambda timeout:
        credentials.decrypt(cipher, key, timeout=timeout), 10)
    if checked != document:
        raise CredentialError('Wiki credential readback failed; nothing saved')
    lock = credentials.VAULT.with_suffix('.wiki-lock')
    with lock.open('x'):
        try:
            if credentials.VAULT.read_bytes() != original:
                raise CredentialError('SOPS changed concurrently; retry after reviewing it')
            local.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if local.exists():
                if local.is_symlink() or local.read_bytes() != data:
                    raise CredentialError('Local wiki credential changed; no overwrite attempted')
            else:
                with local.open('xb') as stream:
                    stream.write(data)
                local.chmod(0o600)
            with tempfile.NamedTemporaryFile(dir=credentials.VAULT.parent, prefix='.wiki-sops-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(cipher)
            try:
                temporary.chmod(0o644)
                temporary.replace(credentials.VAULT)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            lock.unlink()
    print('Existing wiki password added to SOPS and verified; no NAS credential changed.', flush=True)
    return password
