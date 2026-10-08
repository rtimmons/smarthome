#!/usr/bin/env python3
"""Validate and bootstrap the isolated portal with writable staging and read-only media."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import urllib.error
import urllib.parse
import urllib.request

IMAGE_DIGEST = 'sha256:e6b89d15606318a88675070e5fc5d6e1bfc133af43ae5a77a6b16ea9655b9a2e'


class Refused(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def validate(value):
    require(isinstance(value, dict), 'configuration must be an object')
    require(set(value) == {'schema_version', 'image_digest', 'public_url', 'admin',
                           'operator', 'nas', 'storagebox'}, 'unexpected configuration fields')
    require(value['schema_version'] == 2, 'unsupported schema')
    require(value['image_digest'] == IMAGE_DIGEST, 'the reviewed filex image digest is required')
    url = urllib.parse.urlsplit(value['public_url'])
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password
            and url.path in ('', '/') and not url.query and not url.fragment,
            'public_url must be a private HTTPS origin')
    require(url.hostname == '10.77.0.1' and url.port == 5213,
            'the reviewed private VPN HTTPS endpoint is required')
    for name in ('admin', 'operator'):
        account = value[name]
        require(set(account) == {'email', 'password'}, 'invalid account fields')
        require(isinstance(account['email'], str) and '@' in account['email'], 'account email required')
        require(isinstance(account['password'], str) and 24 <= len(account['password']) <= 72
                and len(account['password'].encode()) <= 72, 'use a 24–72 byte random password')
    require(value['admin']['email'] != value['operator']['email'], 'use separate administrator and operator accounts')
    require(value['admin']['password'] != value['operator']['password'], 'use distinct account passwords')
    require(value['storagebox'] == {'mode': 'read_only_bind'}, 'Storage Box requires the fixed kernel read-only bind')
    for name in ('nas',):
        remote = value[name]
        require(set(remote) == {'host', 'port', 'user', 'root', 'host_key', 'private_key',
                                'restricted_staging_account'}, 'invalid remote fields')
        require(remote['restricted_staging_account'] is True,
                'dedicated server-restricted staging SFTP account required')
        require((remote['host'], remote['port'], remote['user'], remote['root']) ==
                ('192.168.1.66', 2226, 'filex-staging', '/staging'),
                'the dedicated NAS staging endpoint is required')
        require(re.fullmatch(r'[A-Za-z0-9.-]+', remote['host']) is not None, 'invalid SFTP host')
        require(type(remote['port']) is int and 1 <= remote['port'] <= 65535, 'invalid SFTP port')
        require(re.fullmatch(r'[A-Za-z0-9_-]+', remote['user']) is not None
                and remote['user'] not in ('root', 'admin', 'usenet'), 'dedicated SFTP user required')
        root = PurePosixPath(remote['root'])
        require(root.is_absolute() and root != PurePosixPath('/') and not str(root).startswith('//')
                and '..' not in root.parts
                and str(root) == remote['root'] and '\x00' not in str(root),
                'SFTP root must be an explicit normalized subdirectory')
        require(re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', remote['host_key']) is not None,
                'independently verified Ed25519 host key required; TOFU is forbidden')
        require(remote['private_key'].startswith('-----BEGIN OPENSSH PRIVATE KEY-----\n')
                and remote['private_key'].strip().endswith('-----END OPENSSH PRIVATE KEY-----'),
                'dedicated OpenSSH private key required')
    return value


def load(path):
    p = Path(path)
    require(not p.is_symlink() and stat.S_ISREG(p.stat().st_mode)
            and p.stat().st_mode & 0o077 == 0, 'configuration must be a private regular file (0600)')
    return validate(json.loads(p.read_text()))


def storages(config):
    result = [{'name': 'Download staging', 'driver': 'local', 'mount_path': '/downloads',
               'config': {'path': '/srv/files'}}]
    remote = config['nas']
    result.append({'name': 'NAS staging', 'driver': 'sftp', 'mount_path': '/nas',
                   'config': {k: remote[k] for k in
                              ('host', 'port', 'user', 'root', 'host_key', 'private_key')}})
    result.append({'name': 'Storage Box', 'driver': 'local', 'mount_path': '/storagebox',
                   'config': {'path': '/srv/storagebox'}})
    for row in result:
        row.update(read_only=row['name'] == 'Storage Box', enabled=True, sync_mode='poll',
                   sync_interval_s=900, rbac_enabled=False)
    return result


def server_config(config):
    # JSON is a YAML subset, avoiding YAML interpolation of passwords.
    return {'listen': '127.0.0.1:5212', 'data_dir': '/data', 'public_url': config['public_url'],
            'auth': {'drivers': ['local']}, 'plugins_disabled': True,
            'cors': {'allowed_origins': [config['public_url'].rstrip('/'), 'http://127.0.0.1:15213']},
            'thumbs': {'enabled': False}, 'search': {'enabled': True},
            'queue': {'enabled': True, 'workers': 1},
            'seed': {'admin_email': config['admin']['email'],
                     'admin_password': config['admin']['password'],
                     'site_name': 'Private files'}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refused('API redirects are forbidden')


class API:
    def __init__(self):
        # Never send credentials to a configurable URL or an environment proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.token = None

    def call(self, method, path, body=None):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request('http://127.0.0.1:5212' + path,
                                         data=None if body is None else json.dumps(body).encode(),
                                         headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise Refused('filex API rejected request (HTTP %s)' % exc.code) from None
        except urllib.error.URLError:
            raise Refused('filex loopback API unavailable') from None


def bootstrap(config, api):
    api.token = api.call('POST', '/api/auth/login', config['admin'])['token']
    try:
        expected = storages(config)
        current = api.call('GET', '/api/admin/storages') or []
        users = api.call('GET', '/api/admin/users') or []
        # Check ALL existing records before making any mutation. Never overwrite
        # changed roots, permissions, credentials, or an existing operator's role.
        names = [row['name'] for row in current]
        require(len(set(names)) == len(names), 'duplicate storage names require review')
        allowed = {row['name']: row for row in expected}
        for row in current:
            require(row['name'] in allowed, 'unexpected storage requires review')
            require(all(row.get(k) == v for k, v in allowed[row['name']].items()),
                    'existing storage differs from reviewed configuration')
        operators = [u for u in users if u['email'] == config['operator']['email']]
        require(len(operators) <= 1 and all(u['role'] == 'user' for u in operators),
                'existing operator has unexpected privileges')
        created = 0
        for row in expected:
            if row['name'] not in names:
                api.call('POST', '/api/admin/storages', row)
                created += 1
        if not operators:
            api.call('POST', '/api/admin/users', {**config['operator'], 'role': 'user'})
            created += 1
        # Read back actual persisted permission/root fields, not only HTTP status.
        actual = api.call('GET', '/api/admin/storages') or []
        require(len(actual) == 3 and {r['name'] for r in actual} == set(allowed),
                'storage readback failed')
        for row in actual:
            require(all(row.get(k) == v for k, v in allowed[row['name']].items()),
                    'storage readback differs')
        return {'status': 'configured', 'read_only_storages': 1, 'writable_staging_roots': 2, 'created': created}
    finally:
        api.token = None


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'render', 'bootstrap'])
    parser.add_argument('config')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        config = load(args.config)
        if args.command == 'render':
            require(args.output is not None, 'render requires a new output file')
            with open(args.output, 'x') as output:
                json.dump(server_config(config), output, indent=2)
                output.write('\n')
            result = {'status': 'rendered'}
        elif args.command == 'bootstrap':
            result = bootstrap(config, API())
        else:
            result = {'status': 'valid', 'read_only_storages': 1, 'writable_staging_roots': 2}
        print(json.dumps(result))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Configuration, backend errors and filenames can contain credentials.
        print(json.dumps({'status': 'refused', 'reason': str(exc) if isinstance(exc, Refused)
                          else 'invalid or inaccessible private configuration'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
