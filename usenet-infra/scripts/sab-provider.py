#!/usr/bin/env python3
"""Inspect and tune the existing Eweka server without exposing saved credentials.

Run on the cloud host (also supports ``python3 - inspect < sab-provider.py``).
SABnzbd's API key is read internally from its protected catalog environment.
Requests use a fixed loopback endpoint, POST bodies, and never print raw responses.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request


ENV_PATH = Path('/srv/usenet/config/catalog.env')
API_URL = 'http://127.0.0.1:8080/api'
HOST = 'news.eweka.nl'
DESIRED = {
    'required': 1, 'optional': 0, 'priority': 0, 'connections': 20,
    'ssl_verify': 3, 'ssl': 1, 'port': 563, 'enable': 1, 'retention': 0,
}


class ProviderError(Exception):
    """Only a fixed error category may cross the output boundary."""


def api_key(path: Path = ENV_PATH) -> str:
    try:
        matches = []
        for line in path.read_text(encoding='utf-8').splitlines():
            key, separator, value = line.partition('=')
            if separator and key.strip() == 'SABNZBD_API_KEY':
                matches.append(value.strip().strip('\"\''))
        if len(matches) != 1 or not matches[0]:
            raise ProviderError('api_key_unavailable')
        return matches[0]
    except OSError:
        raise ProviderError('api_key_unavailable') from None


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The API key must never follow a redirect away from the fixed endpoint.
        return None


class SabClient:
    def __init__(self, key: str):
        self._key = key
        # Ignore proxy environment variables for these local credentialed calls.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, **parameters) -> dict:
        payload = dict(parameters, apikey=self._key, output='json')
        body = urllib.parse.urlencode(payload).encode('utf-8')
        request = urllib.request.Request(
            API_URL, data=body, method='POST',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        try:
            with self._opener.open(request, timeout=45) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise ProviderError('unexpected_api_response')
            return result
        except ProviderError:
            raise
        except Exception:
            # HTTPError/URLError and malformed API data can contain credentials
            # or complete URLs. Do not interpolate exceptions into diagnostics.
            raise ProviderError('api_request_failed') from None


def existing_server(client: SabClient) -> tuple[dict, int]:
    payload = client.call(mode='get_config', section='servers')
    config = payload.get('config')
    servers = config.get('servers') if isinstance(config, dict) else None
    if not isinstance(servers, list) or any(not isinstance(server, dict) for server in servers):
        raise ProviderError('unexpected_api_response')
    matches = [server for server in servers if str(server.get('host', '')).lower().rstrip('.') == HOST]
    if not matches:
        raise ProviderError('existing_eweka_server_missing')
    if len(matches) != 1:
        raise ProviderError('duplicate_eweka_servers')
    server = matches[0]
    name = server.get('name')
    if server.get('host') != HOST or not isinstance(name, str) or not name:
        raise ProviderError('existing_server_identity_invalid')
    if sum(other.get('name') == name for other in servers) != 1:
        raise ProviderError('duplicate_server_names')
    return server, len(servers)


def numeric_settings(server: dict) -> dict:
    settings = {}
    for key in DESIRED:
        value = server.get(key)
        try:
            settings[key] = int(value) if value is not None else None
        except (ValueError, TypeError, OverflowError):
            raise ProviderError('unexpected_server_settings') from None
    return settings


def public_server(server: dict) -> dict:
    return {
        'host': HOST,
        'settings': numeric_settings(server),
        'username_present': bool(server.get('username')),
        'password_present': bool(server.get('password')),
    }


def require_credentials(server: dict) -> None:
    if not server.get('username') or not server.get('password'):
        raise ProviderError('saved_credentials_missing')


def configure(client: SabClient) -> dict:
    before, count = existing_server(client)
    require_credentials(before)
    changed = numeric_settings(before) != DESIRED
    if changed:
        fields = dict(DESIRED)
        # SAB 5.1.3 resets usage_at_start when a nonempty quota is omitted.
        if before.get('quota') not in (None, ''):
            fields['quota'] = before['quota']
        # A wrong keyword creates a new server in SAB. Use only the exact name
        # just resolved from the existing unique host; never accept it as input.
        client.call(mode='set_config', section='servers', keyword=before['name'], **fields)
        after, new_count = existing_server(client)
        if new_count != count or after['name'] != before['name']:
            raise ProviderError('server_identity_changed')
        if numeric_settings(after) != DESIRED:
            raise ProviderError('configuration_readback_failed')
        if (after.get('username'), after.get('password')) != (before.get('username'), before.get('password')):
            raise ProviderError('credential_readback_changed')
        if before.get('quota') not in (None, '') and after.get('quota') != before.get('quota'):
            raise ProviderError('quota_readback_changed')
    else:
        after = before
    return dict(public_server(after), changed=changed)


def test_provider(client: SabClient) -> dict:
    server, _ = existing_server(client)
    require_credentials(server)
    if numeric_settings(server) != DESIRED:
        raise ProviderError('configure_required_before_test')
    response = client.call(
        mode='config', name='test_server', server=server['name'], host=HOST,
        port=DESIRED['port'], username=server['username'], password='********',
        connections=DESIRED['connections'], ssl=DESIRED['ssl'], ssl_verify=DESIRED['ssl_verify'],
    )
    value = response.get('value')
    if not isinstance(value, dict) or not isinstance(value.get('result'), bool):
        raise ProviderError('unexpected_test_response')
    if not value['result']:
        # Deliberately discard upstream message; it may include saved identity.
        raise ProviderError('provider_connection_test_failed')
    return dict(public_server(server), connection_test='passed')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'configure', 'test'))
    args = parser.parse_args(argv)
    try:
        client = SabClient(api_key())
        if args.command == 'inspect':
            result = public_server(existing_server(client)[0])
        elif args.command == 'configure':
            result = configure(client)
        else:
            result = test_provider(client)
        print(json.dumps(dict(command=args.command, status='ok', **result), sort_keys=True))
        return 0
    except ProviderError as exc:
        print(json.dumps({'command': args.command, 'status': 'error', 'error': str(exc)}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'command': args.command, 'status': 'error', 'error': 'internal_error'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
