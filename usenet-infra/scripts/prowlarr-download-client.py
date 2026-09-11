#!/usr/bin/env python3
"""Inspect, configure, or test Prowlarr's private connection to existing SABnzbd.

Reviewed against Prowlarr v2.5.2.5491 ProviderControllerBase and SabnzbdSettings,
and SABnzbd 5.1.3 category APIs. Configuration tests read connection/category
metadata only. This helper never searches, grabs content, or changes app/RSS
profiles. Run on the cloud host; API keys remain inside that host.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import stat
import sys
import urllib.parse
import urllib.request

ENV_PATH = Path('/srv/usenet/config/catalog.env')
PROWLARR_VERSION = '2.5.2.5491'
SAB_VERSION = '5.1.3'
NAME = 'SABnzbd'
IMPLEMENTATION = 'Sabnzbd'
CATEGORY = 'prowlarr'
DESIRED_CATEGORY = {'pp': '3', 'script': 'None', 'dir': '', 'priority': 0}
DESIRED_FIELDS = {'host': 'sabnzbd', 'port': 8080, 'useSsl': False, 'urlBase': '',
                  'username': '', 'password': '', 'category': CATEGORY, 'priority': -100}


class ClientError(RuntimeError):
    """Fixed safe categories only; never interpolate upstream response values."""


def read_keys(path: Path = ENV_PATH) -> dict[str, str]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027:
        raise ClientError('protected_environment_permissions_invalid')
    values = {}
    for line in path.read_text().splitlines():
        name, separator, value = line.partition('=')
        if separator and name in ('SABNZBD_API_KEY', 'PROWLARR_API_KEY'):
            if name in values or not value.strip():
                raise ClientError('protected_environment_keys_invalid')
            values[name] = value.strip()
    if len(values) != 2:
        raise ClientError('protected_environment_keys_missing')
    return values


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ClientError('private_api_redirect_refused')


class APIs:
    def __init__(self, keys: dict[str, str]):
        self.keys = keys
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def request(self, request):
        try:
            with self.opener.open(request, timeout=45) as response:
                content = response.read()
            return json.loads(content) if content else None
        except ClientError:
            raise
        except Exception:
            raise ClientError('private_api_request_failed') from None

    def prowlarr(self, method: str, path: str, body=None):
        # All callers use literal endpoints or an integer ID just read from
        # that endpoint. No hostname, URL, or credential is accepted as input.
        request = urllib.request.Request('http://127.0.0.1:9696/api/v1/' + path,
                    data=json.dumps(body).encode() if body is not None else None, method=method,
                    headers={'X-Api-Key': self.keys['PROWLARR_API_KEY'], 'Content-Type': 'application/json'})
        return self.request(request)

    def sab(self, mode: str, **parameters):
        body = urllib.parse.urlencode(dict(parameters, mode=mode, output='json', apikey=self.keys['SABNZBD_API_KEY'])).encode()
        request = urllib.request.Request('http://127.0.0.1:8080/api', data=body, method='POST',
                                         headers={'Content-Type': 'application/x-www-form-urlencoded'})
        result = self.request(request)
        if not isinstance(result, dict) or result.get('status') is False or 'error' in result:
            raise ClientError('sab_api_rejected_operation')
        return result


def fields(resource: dict) -> dict:
    entries = resource['fields']
    names = [entry['name'] for entry in entries]
    if len(names) != len(set(names)) or set(names) != set(DESIRED_FIELDS) | {'apiKey'}:
        raise ClientError('download_client_field_schema_changed')
    return {entry['name']: entry.get('value') for entry in entries}


def selected(clients: list[dict]) -> dict | None:
    matches = [client for client in clients if client.get('implementation') == IMPLEMENTATION
               or str(client.get('name', '')).casefold() == NAME.casefold()]
    if not matches:
        return None
    if len(matches) != 1 or matches[0].get('name') != NAME or matches[0].get('implementation') != IMPLEMENTATION:
        raise ClientError('existing_download_client_identity_ambiguous')
    client = matches[0]
    if type(client.get('id')) is not int or client['id'] <= 0:
        raise ClientError('existing_download_client_id_invalid')
    if client.get('configContract') != 'SabnzbdSettings' or client.get('protocol') != 'usenet':
        raise ClientError('existing_download_client_contract_changed')
    if client.get('categories') not in (None, []) or client.get('tags') not in (None, []):
        raise ClientError('existing_download_client_has_unreviewed_routing')
    fields(client)
    return client


def category_state(api: APIs) -> tuple[dict | None, list[dict]]:
    config = api.sab('get_config', section='categories')['config']
    categories = config.get('categories', [])
    matches = [item for item in categories if str(item['name']).casefold() == CATEGORY]
    if len(matches) > 1 or matches and matches[0]['name'] != CATEGORY:
        raise ClientError('sab_category_identity_ambiguous')
    return (matches[0] if matches else None), categories


def category_matches(category: dict | None) -> bool:
    if category is None:
        return False
    return (str(category.get('pp')) == '3' and category.get('script') == 'None'
            and category.get('dir') == '' and str(category.get('priority')) == '0'
            and category.get('newzbin') in (None, '', []))


def job_counts(api: APIs) -> tuple[int, int]:
    values = (api.sab('queue', start=0, limit=1)['queue']['noofslots_total'],
              api.sab('history', start=0, limit=1, archive=0, last_history_update=-1)['history']['ppslots'])
    if any(isinstance(value, bool) or not str(value).isdigit() for value in values):
        raise ClientError('sab_job_counts_unavailable')
    return tuple(map(int, values))


def host_allowlist(api: APIs) -> list[str]:
    values = api.sab('get_config', section='misc', keyword='host_whitelist')['config']['misc']['host_whitelist']
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ClientError('sab_hostname_allowlist_unavailable')
    return values


def ensure_docker_hostname(api: APIs) -> bool:
    before = host_allowlist(api)
    if 'sabnzbd' in before:
        return False
    # SAB's OptionList API accepts comma-separated values. Refuse unusual
    # existing entries that cannot round-trip exactly through that format.
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]*', name) for name in before):
        raise ClientError('sab_hostname_allowlist_requires_manual_review')
    if any(job_counts(api)):
        raise ClientError('sab_must_be_idle_before_hostname_configuration')
    if host_allowlist(api) != before:
        raise ClientError('sab_hostname_allowlist_changed_during_configuration')
    desired = before + ['sabnzbd']
    # Only this exact Docker DNS name is added; hostname verification remains
    # active. API keys still authenticate the internal HTTP connection.
    api.sab('set_config', section='misc', keyword='host_whitelist', value=','.join(desired))
    if host_allowlist(api) != desired:
        raise ClientError('sab_hostname_allowlist_readback_failed')
    return True


def same_setting(value, desired) -> bool:
    if desired == '' and value is None:
        return True
    if isinstance(desired, bool):
        return type(value) is bool and value == desired
    if isinstance(desired, int):
        return type(value) is int and value == desired
    return value == desired


def client_matches(client: dict | None, key: str) -> bool:
    if client is None:
        return False
    values = fields(client)
    return (all(same_setting(values[name], desired) for name, desired in DESIRED_FIELDS.items())
            and values['apiKey'] in (key, '********') and type(client.get('priority')) is int and client['priority'] == 1
            and client.get('categories') in (None, []) and client.get('tags') in (None, []))


def state(api: APIs) -> dict:
    if api.prowlarr('GET', 'system/status')['version'] != PROWLARR_VERSION or api.sab('version')['version'] != SAB_VERSION:
        raise ClientError('application_version_not_reviewed')
    templates = [item for item in api.prowlarr('GET', 'downloadclient/schema') if item.get('implementation') == IMPLEMENTATION]
    if len(templates) != 1 or templates[0].get('configContract') != 'SabnzbdSettings' or templates[0].get('protocol') != 'usenet':
        raise ClientError('download_client_template_changed')
    fields(templates[0])
    clients = api.prowlarr('GET', 'downloadclient')
    if not isinstance(clients, list):
        raise ClientError('download_client_inventory_unavailable')
    client = selected(clients)
    category, categories = category_state(api)
    return {'client': client, 'client_count': len(clients), 'category': category,
            'categories': categories, 'jobs': job_counts(api), 'allowed_hosts': host_allowlist(api)}


def public_state(api: APIs, current: dict) -> dict:
    client, category = current['client'], current['category']
    matches = client_matches(client, api.keys['SABNZBD_API_KEY'])
    category_ok = category_matches(category)
    host_allowed = 'sabnzbd' in current['allowed_hosts']
    return {'prowlarr_version': PROWLARR_VERSION, 'sab_version': SAB_VERSION,
            'name': NAME, 'host': 'sabnzbd', 'port': 8080, 'use_ssl': False,
            'category': CATEGORY, 'client_exists': client is not None,
            'client_enabled': client is not None and client.get('enable') is True,
            'client_settings_match': matches, 'category_exists': category is not None,
            'category_settings_match': category_ok,
            'api_key_present': client is not None and bool(fields(client)['apiKey']),
            'sab_service_name_allowlisted': host_allowed,
            'other_download_clients': current['client_count'] - int(client is not None),
            'queued_jobs': current['jobs'][0], 'postprocessing_jobs': current['jobs'][1],
            'safe_to_configure': (category_ok or category is None and not any(current['jobs']))
                and (host_allowed or not any(current['jobs']))}


def candidate(api: APIs, existing: dict | None) -> dict:
    body = {'name': NAME, 'implementationName': NAME, 'implementation': IMPLEMENTATION, 'configContract': 'SabnzbdSettings',
            'enable': True, 'protocol': 'usenet', 'priority': 1, 'categories': [], 'tags': [],
            'fields': [{'name': name, 'value': value} for name, value in
                       dict(DESIRED_FIELDS, apiKey=api.keys['SABNZBD_API_KEY']).items()]}
    if existing:
        body['id'] = existing['id']
    return body


def saved_candidate(api: APIs, existing: dict) -> dict:
    body = candidate(api, existing)
    # SchemaBuilder resolves this sentinel against the given saved client ID.
    # Testing with catalog.env's key here would hide a stale persisted secret.
    for field in body['fields']:
        if field['name'] == 'apiKey':
            field['value'] = fields(existing)['apiKey']
    return body


def connection_test(api: APIs, body: dict) -> None:
    # ProviderControllerBase.Test returns "{}"; JSON media handling may yield
    # an object or that JSON string. HTTP validation failures remain failures.
    if api.prowlarr('POST', 'downloadclient/test', body) not in ({}, '{}'):
        raise ClientError('download_client_connection_test_failed')


def configure(api: APIs) -> dict:
    before = state(api)
    category_changed = False
    if before['category'] is not None and not category_matches(before['category']):
        raise ClientError('existing_sab_category_conflicts_with_approved_settings')
    hostname_changed = ensure_docker_hostname(api)
    if before['category'] is None:
        if any(job_counts(api)):
            raise ClientError('sab_must_be_idle_before_category_creation')
        current, categories = category_state(api)
        if current is not None:
            if not category_matches(current):
                raise ClientError('sab_category_changed_during_configuration')
        else:
            untouched = copy.deepcopy(categories)
            if any(job_counts(api)):
                raise ClientError('sab_must_be_idle_before_category_creation')
            api.sab('set_config', section='categories', keyword=CATEGORY, **DESIRED_CATEGORY, order=0)
            current, after_categories = category_state(api)
            if not category_matches(current) or [item for item in after_categories if item['name'] != CATEGORY] != untouched:
                raise ClientError('sab_category_readback_failed')
            category_changed = True
    # Resolve identity again after category creation; never retry a failed POST
    # blindly. Prowlarr also enforces unique case-insensitive client names.
    inventory = api.prowlarr('GET', 'downloadclient')
    existing = selected(inventory)
    body = candidate(api, existing)
    connection_test(api, body)
    changed = not client_matches(existing, api.keys['SABNZBD_API_KEY']) or existing.get('enable') is not True
    if not changed:
        try:
            connection_test(api, saved_candidate(api, existing))
        except ClientError:
            # The explicit current key passed, but the retained credential did
            # not. Replacing it is within configure's approved scope.
            changed = True
    if not category_matches(category_state(api)[0]):
        raise ClientError('sab_category_changed_during_connection_test')
    latest = api.prowlarr('GET', 'downloadclient')
    if latest != inventory:
        raise ClientError('download_client_inventory_changed_during_test')
    if changed:
        api.prowlarr('PUT' if existing else 'POST',
                     'downloadclient/' + str(existing['id']) if existing else 'downloadclient', body)
    after = state(api)
    expected_count = len(inventory) + int(existing is None)
    saved = after['client']
    if (after['client_count'] != expected_count or saved is None
            or existing is not None and saved['id'] != existing['id']
            or not client_matches(saved, api.keys['SABNZBD_API_KEY']) or saved.get('enable') is not True
            or not category_matches(after['category']) or 'sabnzbd' not in after['allowed_hosts']):
        raise ClientError('download_client_readback_failed')
    connection_test(api, saved_candidate(api, saved))
    return dict(public_state(api, after), changed=changed, category_created=category_changed,
                hostname_added=hostname_changed, connection_test='passed', saved_connection_test='passed')


def test_existing(api: APIs) -> dict:
    before = state(api)
    if (not client_matches(before['client'], api.keys['SABNZBD_API_KEY']) or not category_matches(before['category'])
            or 'sabnzbd' not in before['allowed_hosts']):
        raise ClientError('configure_required_before_connection_test')
    connection_test(api, saved_candidate(api, before['client']))
    after = state(api)
    if after != before:
        raise ClientError('configuration_changed_during_connection_test')
    return dict(public_state(api, after), connection_test='passed', saved_connection_test='passed')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'configure', 'test'))
    args = parser.parse_args(argv)
    try:
        api = APIs(read_keys())
        result = (public_state(api, state(api)) if args.command == 'inspect'
                  else configure(api) if args.command == 'configure' else test_existing(api))
        print(json.dumps(dict(status='ok', command=args.command, **result), sort_keys=True))
        return 0
    except ClientError as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'status': 'error', 'error': 'private_client_operation_failed'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
