#!/usr/bin/env python3
"""Inspect, prepare, enable, or test a saved NZBGeek or NZBFinder indexer safely.

Reviewed against Prowlarr v2.5.2.5491 ProviderControllerBase, IndexerFactory,
IndexerResource and SchemaBuilder. No limits are guessed or set. Enabling
requires a successful credentialed test; no applications or clients are created.
Run on the cloud host, including through ``python3 - inspect < this-file``.
Pass an optional second argument ``nzbfinder``; the default remains ``nzbgeek``.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import fcntl
import json
import os
import re
from pathlib import Path
import sys
import urllib.parse
import urllib.request


VERSION = '2.5.2.5491'
API_ROOT = 'http://127.0.0.1:9696/api/v1/'
ENV_PATH = Path('/srv/usenet/config/catalog.env')
LOCK_PATH = Path('/srv/usenet/state/prowlarr-indexer.lock')
BASE_URL = 'https://api.nzbgeek.info'
INDEXERS = {
    'nzbgeek': ('NZBgeek', BASE_URL),
    'nzbfinder': ('NZBFinder', 'https://nzbfinder.ws'),
}
FIELD_NAMES = {'baseUrl', 'apiPath', 'apiKey', 'additionalParameters', 'vipExpiration',
               'baseSettings.queryLimit', 'baseSettings.grabLimit', 'baseSettings.limitsUnit'}


class IndexerError(Exception):
    """Fixed, nonsecret diagnostic categories only."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_key(path: Path = ENV_PATH) -> str:
    try:
        if path.stat().st_mode & 0o027:
            raise IndexerError('protected_environment_permissions_invalid')
        values = [value.strip().strip('\"\'') for line in path.read_text().splitlines()
                  for key, separator, value in [line.partition('=')]
                  if separator and key.strip() == 'PROWLARR_API_KEY']
        if len(values) != 1 or not values[0]:
            raise IndexerError('prowlarr_api_key_unavailable')
        return values[0]
    except OSError:
        raise IndexerError('prowlarr_api_key_unavailable') from None


class ProwlarrAPI:
    def __init__(self, key: str):
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, path: str, *, method: str = 'GET', payload=None):
        if path not in {'system/status', 'config/host', 'indexer', 'indexer/schema', 'indexer/test', 'appprofile'} and not (method == 'PUT' and re.fullmatch(r'indexer/[1-9][0-9]*', path)):
            raise IndexerError('unsupported_api_path')
        request = urllib.request.Request(
            API_ROOT + path, method=method,
            headers={'X-Api-Key': self.key, 'Content-Type': 'application/json'},
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                data = response.read()
            return json.loads(data) if data else None
        except Exception:
            # Errors can contain a Newznab URL with its key or entire configs.
            raise IndexerError('prowlarr_request_failed_or_rejected') from None


def fields(indexer: dict) -> dict:
    entries = indexer.get('fields')
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise IndexerError('unexpected_indexer_schema')
    result = {}
    for entry in entries:
        name = entry.get('name')
        if not isinstance(name, str) or name in result:
            raise IndexerError('unexpected_indexer_schema')
        result[name] = entry.get('value')
    return result


def provider_settings(provider: str) -> tuple[str, str]:
    if provider not in INDEXERS:
        raise IndexerError('unsupported_indexer')
    return INDEXERS[provider]


def matches_provider(indexer: dict, provider: str = 'nzbgeek') -> bool:
    name, expected_url = provider_settings(provider)
    values = fields(indexer)
    base = values.get('baseUrl')
    hostname = urllib.parse.urlsplit(base).hostname if isinstance(base, str) else None
    return str(indexer.get('name', '')).casefold() == name.casefold() or hostname == urllib.parse.urlsplit(expected_url).hostname


def existing(api: ProwlarrAPI, provider: str = 'nzbgeek') -> dict | None:
    provider_settings(provider)
    entries = api.call('indexer')
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise IndexerError('unexpected_indexer_list')
    found = [entry for entry in entries if matches_provider(entry, provider)]
    if len(found) > 1:
        raise IndexerError(f'duplicate_{provider}_indexers')
    return found[0] if found else None


def global_checks(api: ProwlarrAPI) -> dict:
    if api.call('system/status').get('version') != VERSION:
        raise IndexerError('unsupported_prowlarr_version')
    enabled = api.call('config/host').get('certificateValidation') == 'enabled'
    return {'version': VERSION, 'certificate_validation_enabled': enabled}


def require_secure(report: dict) -> None:
    if not report['certificate_validation_enabled']:
        raise IndexerError('strict_certificate_validation_required')


def validate_endpoint(indexer: dict, provider: str = 'nzbgeek') -> dict:
    _, expected_url = provider_settings(provider)
    values = fields(indexer)
    if (indexer.get('implementation') != 'Newznab' or indexer.get('configContract') != 'NewznabSettings'
            or indexer.get('protocol') != 'usenet' or values.get('baseUrl', '').rstrip('/') != expected_url
            or values.get('apiPath') != '/api' or values.get('additionalParameters') not in (None, '')
            or indexer.get('redirect') is not True):
        raise IndexerError(f'{provider}_endpoint_or_definition_requires_review')
    return values


def integer(value, *, optional=False):
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise IndexerError('unexpected_numeric_setting')
    try:
        parsed = int(value)
        if parsed < 0 or str(parsed) != str(value):
            raise ValueError()
        return parsed
    except (TypeError, ValueError):
        raise IndexerError('unexpected_numeric_setting') from None


def public_indexer(indexer: dict | None, provider: str = 'nzbgeek') -> dict:
    name, _ = provider_settings(provider)
    if indexer is None:
        return {'indexer': name, 'exists': False, 'api_key_saved': False}
    values = validate_endpoint(indexer, provider)
    unit = integer(values.get('baseSettings.limitsUnit'))
    if unit not in (0, 1) or not isinstance(indexer.get('enable'), bool):
        raise IndexerError('unexpected_indexer_settings')
    return {
        'indexer': name, 'exists': True, 'id': integer(indexer.get('id')), 'enabled': indexer['enable'],
        'api_key_saved': bool(values.get('apiKey')), 'endpoint_https': True,
        'priority': integer(indexer.get('priority')),
        'query_limit': integer(values.get('baseSettings.queryLimit'), optional=True),
        'grab_limit': integer(values.get('baseSettings.grabLimit'), optional=True),
        'limits_period': 'day' if unit == 0 else 'hour',
    }


@contextmanager
def operation_lock(path: Path = LOCK_PATH):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise IndexerError('another_indexer_operation_is_running') from None
        yield


def prepare_disabled(api: ProwlarrAPI, lock_path: Path = LOCK_PATH, provider: str = 'nzbgeek') -> dict:
    name, _ = provider_settings(provider)
    with operation_lock(lock_path):
        safety = global_checks(api)
        require_secure(safety)
        saved = existing(api, provider)
        if saved is not None:
            return dict(safety, **public_indexer(saved, provider), changed=False)
        templates = api.call('indexer/schema')
        options = [entry for template in templates for entry in [template, *template.get('presets', [])]
                   if str(entry.get('name', '')).casefold() == name.casefold()]
        if len(options) != 1:
            raise IndexerError(f'{provider}_preset_missing_or_ambiguous')
        request = copy.deepcopy(options[0])
        values = validate_endpoint(request, provider)
        if set(values) != FIELD_NAMES or values['baseSettings.queryLimit'] is not None or values['baseSettings.grabLimit'] is not None:
            raise IndexerError(f'{provider}_preset_changed_requires_review')
        profiles = api.call('appprofile')
        standard = [profile for profile in profiles if profile.get('name') == 'Standard']
        if len(standard) != 1 or integer(standard[0].get('id')) == 0:
            raise IndexerError('existing_standard_application_profile_required')
        # The schema's appProfileId=0 cannot pass the controller's shared
        # validator. Select the existing profile; never create/alter profiles.
        request.update(name=name, enable=False, appProfileId=standard[0]['id'])
        request.pop('id', None)
        request.pop('presets', None)
        for field in request['fields']:
            if field['name'] == 'apiKey':
                field['value'] = ''
        # No forceSave and no enable. Upstream skips network testing and caps
        # discovery for a disabled Newznab definition with an empty saved key.
        api.call('indexer', method='POST', payload=request)
        saved = existing(api, provider)
        report = public_indexer(saved, provider)
        if not report['exists'] or report['enabled'] or report['api_key_saved'] or saved.get('appProfileId') != standard[0]['id']:
            raise IndexerError('disabled_indexer_readback_failed')
        if fields(saved) != fields(request) or saved.get('priority') != request.get('priority'):
            raise IndexerError('disabled_indexer_settings_readback_failed')
        return dict(safety, **report, changed=True)


def test_saved(api: ProwlarrAPI, provider: str = 'nzbgeek') -> dict:
    safety = global_checks(api)
    require_secure(safety)
    saved = existing(api, provider)
    report = public_indexer(saved, provider)
    if not report['exists'] or not report['api_key_saved'] or report['id'] == 0:
        raise IndexerError(f'saved_{provider}_api_key_required')
    # GET masks API keys as ********. SchemaBuilder restores that saved value
    # when this exact existing ID is posted to /test; it is never printed.
    candidate = copy.deepcopy(saved)
    candidate['enable'] = True  # Require network validation even if currently disabled.
    result = api.call('indexer/test', method='POST', payload=candidate)
    if result not in ({}, '{}'):
        raise IndexerError('unexpected_indexer_test_response')
    after = existing(api, provider)
    if after is None or after.get('id') != saved.get('id') or fields(after) != fields(saved) or after.get('enable') != saved.get('enable'):
        raise IndexerError('indexer_changed_during_test')
    return dict(safety, **public_indexer(after, provider), connection_test_passed=True)


def enable_saved(api: ProwlarrAPI, lock_path: Path = LOCK_PATH, provider: str = 'nzbgeek') -> dict:
    with operation_lock(lock_path):
        before = existing(api, provider)
        report = test_saved(api, provider)
        if report['enabled']:
            return dict(report, changed=False)
        saved = existing(api, provider)
        if saved != before:
            raise IndexerError('indexer_changed_during_enable')
        candidate = copy.deepcopy(saved)
        candidate['enable'] = True
        api.call(f"indexer/{report['id']}", method='PUT', payload=candidate)
        after = existing(api, provider)
        if after is None or after.get('id') != saved.get('id') or after.get('enable') is not True or fields(after) != fields(saved):
            raise IndexerError('enabled_indexer_readback_failed')
        return dict(test_saved(api, provider), changed=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'prepare-disabled', 'test', 'enable'))
    parser.add_argument('indexer', nargs='?', default='nzbgeek', choices=tuple(INDEXERS))
    args = parser.parse_args(argv)
    try:
        api = ProwlarrAPI(api_key())
        if args.command == 'prepare-disabled':
            report = prepare_disabled(api, provider=args.indexer)
        elif args.command == 'test':
            report = test_saved(api, provider=args.indexer)
        elif args.command == 'enable':
            report = enable_saved(api, provider=args.indexer)
        else:
            report = dict(global_checks(api), **public_indexer(existing(api, args.indexer), args.indexer))
        print(json.dumps(report, sort_keys=True))
        return 0
    except IndexerError as exc:
        print(json.dumps({'error': str(exc)}, sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'error': 'unexpected_prowlarr_response'}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
