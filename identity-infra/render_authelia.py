#!/usr/bin/env python3
"""Render secret configuration only to external controller state."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess

from manage import PRIVATE


def main():
    os.umask(0o077)
    directory = PRIVATE/'authelia-seed'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory/'certificates').mkdir(exist_ok=True, mode=0o700)
    (directory/'certificates/ca.crt').write_bytes((PRIVATE/'tls/ca.crt').read_bytes())
    secret_dir = PRIVATE/'secrets'
    for name in ('oidc-hmac', 'forgejo-client-id'):
        path = secret_dir/name
        if not path.exists():
            if (directory/'configuration.json').exists():
                raise RuntimeError('Existing configuration is missing a secret; restore it instead of generating a new identity')
            path.write_text(secrets.token_urlsafe(48)+'\n')
    rsa = secret_dir/'oidc-rsa.pem'
    if not rsa.exists():
        if (directory/'configuration.json').exists():
            raise RuntimeError('Existing OIDC signing key is missing; restore it')
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',str(rsa)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    def secret(name):
        return (secret_dir/name).read_text().strip()
    # Authelia's documented PBKDF2 format; keep the original client secret for
    # Forgejo and reuse the same digest across repeat renders.
    digest = secret_dir/'forgejo-client-digest'
    if not digest.exists():
        salt = secrets.token_bytes(16)
        encoded = lambda value: base64.b64encode(value).decode().rstrip('=').replace('+', '.')
        key = hashlib.pbkdf2_hmac('sha512', secret('forgejo-client').encode(), salt, 310000)
        digest.write_text('$pbkdf2-sha512$310000$'+encoded(salt)+'$'+encoded(key)+'\n')
    smtp_path = secret_dir/'gmail-smtp.json'
    notifier = {'filesystem': {'filename': '/data/notifications.txt'}}
    if smtp_path.exists():
        smtp = json.loads(smtp_path.read_text())
        notifier = {'disable_startup_check': False, 'smtp': {
            'address': 'submissions://smtp.gmail.com:465',
            'timeout': '15 seconds', 'username': smtp['username'], 'password': smtp['password'],
            'sender': 'Smarthome <'+smtp['username']+'>',
            'identifier': 'auth.home.rytim.com', 'subject': '[Smarthome] {title}',
            'startup_check_address': smtp['username'],
            'disable_require_tls': False,
            'tls': {'server_name': 'smtp.gmail.com', 'skip_verify': False, 'minimum_version': 'TLS1.2'},
        }}
    elif (directory/'configuration.json').exists():
        old = json.loads((directory/'configuration.json').read_text())
        if 'smtp' in old.get('notifier', {}):
            raise RuntimeError('Restore the existing SMTP credential; refusing to fall back to file notifications')
    config = {
        'theme': 'auto',
        'server': {'address': 'tcp://127.0.0.1:9091/'},
        'log': {'level': 'info'},
        'certificates_directory': '/config/certificates',
        'totp': {'issuer': 'Smarthome'},
        'authentication_backend': {
            'password_reset': {'disable': True},
            'password_change': {'disable': True},
            'refresh_interval': '1 minute',
            'ldap': {
                'address': 'ldaps://192.168.1.10:636',
                'implementation': 'activedirectory',
                'tls': {'server_name': 'dc1.ad.home.arpa', 'minimum_version': 'TLS1.2'},
                'base_dn': 'DC=ad,DC=home,DC=arpa',
                'additional_users_dn': 'OU=People',
                'additional_groups_dn': 'OU=Groups',
                'users_filter': '(&({username_attribute}={input})(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))',
                'groups_filter': '(&(member={dn})(objectClass=group))',
                'user': 'CN=svc-authelia,OU=Services,DC=ad,DC=home,DC=arpa',
                'password': secret('ldap-bind'),
            },
        },
        'access_control': {'default_policy': 'deny', 'rules': [
            {'domain': ['grid-dashboard.home.rytim.com', 'printer.home.rytim.com',
                        'tinyurl.home.rytim.com', 'wiki.home.rytim.com'],
             'subject': 'user:ryantimmons', 'policy': 'two_factor'},
            {'domain': ['radarr.home.rytim.com','sonarr.home.rytim.com','prowlarr.home.rytim.com','sabnzbd.home.rytim.com'],
             'subject': 'group:arr-users', 'policy': 'two_factor'},
        ]},
        'session': {'secret': secret('session'), 'inactivity': '15 minutes', 'expiration': '8 hours',
                    'remember_me': '-1s', 'cookies': [{'domain': 'home.rytim.com','authelia_url': 'https://auth.home.rytim.com'}]},
        'regulation': {'max_retries': 5, 'find_time': '2 minutes', 'ban_time': '5 minutes'},
        'storage': {'encryption_key': secret('storage'), 'local': {'path': '/data/authelia.sqlite3'}},
        # File notifications are for initial bootstrap only. Once SMTP is
        # configured, missing recovery credentials must fail closed.
        'notifier': notifier,
        'identity_providers': {'oidc': {
            'hmac_secret': secret('oidc-hmac'),
            'jwks': [{'algorithm': 'RS256','use': 'sig','key': rsa.read_text()}],
            'authorization_policies': {'forgejo': {'default_policy': 'deny', 'rules': [
                {'subject': 'group:git-users','policy': 'two_factor'}]}},
            'clients': [{'client_id': secret('forgejo-client-id'), 'client_name': 'Household Git',
                         'client_secret': secret('forgejo-client-digest'), 'public': False,
                         'authorization_policy': 'forgejo', 'require_pkce': True, 'pkce_challenge_method': 'S256',
                         'redirect_uris': ['https://git.home.rytim.com/user/oauth2/authelia/callback'],
                         'scopes': ['openid','email','profile','groups'], 'response_types': ['code'],
                         'grant_types': ['authorization_code'], 'token_endpoint_auth_method': 'client_secret_basic'}],
        }},
    }
    catalog_path = secret_dir/'catalog-client.json'
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else None
    existing_path = directory/'configuration.json'
    if catalog is None and existing_path.exists():
        old_clients = json.loads(existing_path.read_text()).get('identity_providers', {}).get('oidc', {}).get('clients', [])
        if any(client.get('authorization_policy') == 'catalog' for client in old_clients):
            raise RuntimeError('Restore the existing Catalog credential; refusing to remove its login')
    if catalog is not None:
        oidc = config['identity_providers']['oidc']
        oidc['authorization_policies']['catalog'] = {'default_policy': 'deny', 'rules': [
            {'subject': 'user:ryantimmons', 'policy': 'two_factor'}]}
        config['access_control']['rules'].append({
            'domain': 'catalog.home.rytim.com', 'subject': 'user:ryantimmons', 'policy': 'two_factor'})
        oidc['clients'].append({
            'client_id': catalog['client_id'], 'client_name': 'Household Catalog',
            'client_secret': secret('catalog-client-digest'), 'public': False,
            'authorization_policy': 'catalog',
            # OliveTin 3000.19.0 does not implement PKCE. This exception is
            # confined to its confidential client; Forgejo still requires S256.
            'require_pkce': False,
            'redirect_uris': ['https://catalog.home.rytim.com/oauth/callback'],
            'scopes': ['openid', 'profile'], 'response_types': ['code'],
            'grant_types': ['authorization_code'], 'token_endpoint_auth_method': 'client_secret_basic',
        })
    path = directory/'configuration.json'
    rendered = json.dumps(config, indent=2)+'\n'
    if path.exists() and path.read_text() != rendered:
        (directory/'previous.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'\n')
    path.write_text(rendered)
    path.chmod(0o600)
    print('Rendered private Authelia configuration:', path)


if __name__ == '__main__': main()
