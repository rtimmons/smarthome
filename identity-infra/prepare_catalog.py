#!/usr/bin/env python3
"""Prepare Catalog's confidential OAuth client without rotating recovery credentials."""
import base64
import hashlib
import json
import os
import secrets
from manage import PRIVATE, ROOT


def main():
    os.umask(0o077)
    path = ROOT/'usenet-infra/secrets/dashboard-auth.json'
    original = path.read_bytes()
    config = json.loads(original)
    digest_path = PRIVATE/'secrets/catalog-client-digest'
    client_path = PRIVATE/'secrets/catalog-client.json'
    if 'oauth' in config:
        if not digest_path.exists():
            raise RuntimeError('Restore the existing Catalog client digest; refusing rotation')
        if client_path.exists() and json.loads(client_path.read_text()) != config['oauth']:
            raise RuntimeError('Catalog client copies differ; refusing rotation')
        if not client_path.exists():
            with client_path.open('x') as stream:
                stream.write(json.dumps(config['oauth'])+'\n')
        print('Existing Catalog client retained.')
        return
    if digest_path.exists() or client_path.exists():
        raise RuntimeError('Partial client preparation; restore the matching configuration before continuing')
    backup = PRIVATE/'secrets/catalog-auth-before-oauth.json'
    with backup.open('xb') as stream:
        stream.write(original)
    client = {'client_id': secrets.token_urlsafe(48), 'client_secret': secrets.token_urlsafe(48)}
    salt = secrets.token_bytes(16)
    encode = lambda value: base64.b64encode(value).decode().rstrip('=').replace('+', '.')
    key = hashlib.pbkdf2_hmac('sha512', client['client_secret'].encode(), salt, 310000)
    with digest_path.open('x') as stream:
        stream.write('$pbkdf2-sha512$310000$'+encode(salt)+'$'+encode(key)+'\n')
    config['oauth'] = client
    with client_path.open('x') as stream:
        stream.write(json.dumps(client)+'\n')
    temporary = path.with_suffix('.oauth-new')
    with temporary.open('x') as stream:
        stream.write(json.dumps(config, indent=2)+'\n')
    temporary.replace(path)
    print('Catalog client prepared; original local username and password hash retained. Capture SOPS before deployment.')


if __name__ == '__main__': main()
