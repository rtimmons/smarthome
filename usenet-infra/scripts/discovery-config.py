#!/usr/bin/env python3
"""Configure/inspect pinned Radarr and Sonarr acquisition settings on the cloud host.

No search, grab, import, download deletion, or arbitrary URL entry point exists.
Only sanitized summaries leave this helper; application keys remain in memory.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import stat
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

APPS = {'radarr': (7878, '6.3.0.10514'), 'sonarr': (8989, '4.0.19.2979'),
        'prowlarr': (9696, '2.5.2.5491')}
# Keep the existing resource name so upgrades preserve its ID and bindings.
PROFILE = 'Manual discovery only'
CLIENT = 'SABnzbd manual discovery'
DOWNLOAD_POLICY = {'enableCompletedDownloadHandling': True,
                   'autoRedownloadFailed': False,
                   'autoRedownloadFailedFromInteractiveSearch': False}
RSS_INTERVAL = 15
PROFILE_POLICY = {'enableRss': True, 'enableAutomaticSearch': True,
                  'enableInteractiveSearch': True}
EXPECTED_HEALTH = set()


class DiscoveryError(RuntimeError):
    """Messages must be fixed categories without remote content."""


def private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027 or info.st_size > 131072:
        raise DiscoveryError('private_configuration_permissions_invalid')
    return path.read_bytes()


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DiscoveryError('api_redirect_refused')


class API:
    def __init__(self, root=Path('/srv/usenet/config')):
        self.keys = {}
        for app in ('radarr', 'sonarr'):
            config = ET.fromstring(private_file(root / app / 'config.xml'))
            key = config.findtext('ApiKey', '')
            if not re.fullmatch('[a-fA-F0-9]{32}', key):
                raise DiscoveryError('application_key_invalid')
            if app != 'prowlarr' and (config.findtext('UrlBase') != '/' + app
                    or config.findtext('AuthenticationMethod') != 'External'):
                raise DiscoveryError('discovery_bootstrap_settings_changed')
            self.keys[app] = key
        values = {}
        for line in private_file(root / 'catalog.env').decode().splitlines():
            name, sep, value = line.partition('=')
            if sep and name in ('SABNZBD_API_KEY', 'PROWLARR_API_KEY'):
                values[name] = value.strip()
        self.keys['prowlarr'] = values.get('PROWLARR_API_KEY', '')
        self.sab_key = values.get('SABNZBD_API_KEY', '')
        if not self.sab_key or not self.keys['prowlarr']:
            raise DiscoveryError('existing_application_key_missing')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, app, endpoint, method='GET', body=None):
        port = APPS[app][0]
        base = '/api/v1/' if app == 'prowlarr' else '/' + app + '/api/v3/'
        request = urllib.request.Request(f'http://127.0.0.1:{port}{base}{endpoint}',
            headers={'X-Api-Key': self.keys[app], 'Content-Type': 'application/json'},
            method=method, data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(8 * 1024 * 1024)
            return json.loads(raw) if raw else None
        except DiscoveryError:
            raise
        except Exception:
            raise DiscoveryError('private_application_request_failed') from None


def require_policy(resource, desired):
    return all(key in resource and type(resource[key]) is type(value)
               and resource[key] == value for key, value in desired.items())


def field_values(resource):
    fields = resource.get('fields', [])
    if len({field['name'] for field in fields}) != len(fields):
        raise DiscoveryError('duplicate_provider_fields')
    return {field['name']: field.get('value') for field in fields}


def set_fields(resource, desired):
    if not set(desired) <= set(field_values(resource)):
        raise DiscoveryError('provider_schema_changed')
    for field in resource['fields']:
        if field['name'] in desired:
            field['value'] = desired[field['name']]


def fields_match(resource, desired):
    values = field_values(resource)
    return all(values.get(key) == value or value == '' and values.get(key) is None
               or key == 'apiKey' and values.get(key) == '********' and bool(value)
               for key, value in desired.items())


def upsert(api, app, endpoint, name, desired, fields=None, implementation=None):
    resources = api.call(app, endpoint)
    matches = [item for item in resources if item.get('name') == name]
    if len(matches) > 1:
        raise DiscoveryError('ambiguous_managed_resource')
    before = matches[0] if matches else None
    if before and implementation and before.get('implementation') != implementation:
        raise DiscoveryError('managed_resource_implementation_changed')
    if before is None:
        if implementation:
            schemas = api.call(app, endpoint + '/schema')
            schema = [item for item in schemas if item.get('implementation') == implementation]
            if len(schema) != 1:
                raise DiscoveryError('managed_provider_schema_unavailable')
            value = copy.deepcopy(schema[0])
            value.pop('id', None)
        else:
            value = {}
    else:
        value = copy.deepcopy(before)
    value.update(desired, name=name)
    if fields:
        set_fields(value, fields)
    if before and require_policy(before, desired) and (
            not fields or fields_match(before, fields)):
        if implementation:
            # All three pinned applications redact provider keys as eight stars.
            # Test the stored connection using its ID/masked resource before
            # declaring it unchanged. On failure, retry with the intended key
            # below so an existing credential rotation can be reconciled.
            try:
                api.call(app, endpoint + '/test', 'POST', before)
            except DiscoveryError:
                pass
            else:
                return before, False
        else:
            return before, False
    if implementation:
        api.call(app, endpoint + '/test', 'POST', value)
    result = api.call(app, endpoint + ('/' + str(before['id']) if before else ''),
                      'PUT' if before else 'POST', value)
    if not isinstance(result, dict):
        raise DiscoveryError('managed_resource_write_unverified')
    return result, True


def config_policy(api, app, endpoint, desired):
    resource = api.call(app, endpoint)
    if not set(desired) <= resource.keys():
        raise DiscoveryError('policy_schema_changed')
    if require_policy(resource, desired):
        return False
    resource.update(desired)
    api.call(app, endpoint, 'PUT', resource)
    if not require_policy(api.call(app, endpoint), desired):
        raise DiscoveryError('manual_policy_readback_failed')
    return True


def ensure_versions(api):
    for app, (_, version) in APPS.items():
        if api.call(app, 'system/status').get('version') != version:
            raise DiscoveryError('application_version_not_reviewed')


def check_lists(api, app):
    # No lists are created implicitly. Existing lists must remain metadata-only.
    for item in api.call(app, 'importlist'):
        flags = ('enableAuto', 'searchOnAdd') if app == 'radarr' else (
            'enableAutomaticAdd', 'searchForMissingEpisodes')
        if not require_policy(item, dict.fromkeys(flags, False)):
            raise DiscoveryError('automatic_import_list_requires_review')


def run_configuration_command(api, app, name):
    # Deliberately restricted to definition sync and health checks, never grabs.
    if (app, name) not in {('prowlarr', 'ApplicationIndexerSync'),
                          ('radarr', 'CheckHealth'), ('sonarr', 'CheckHealth')}:
        raise DiscoveryError('configuration_command_not_allowed')
    command = api.call(app, 'command', 'POST', {'name': name})
    for attempt in range(30):
        state = api.call(app, 'command/' + str(command['id']))
        if state.get('status') == 'completed':
            return
        if state.get('status') in ('failed', 'aborted', 'cancelled'):
            raise DiscoveryError('configuration_command_failed')
        time.sleep(2)
    raise DiscoveryError('configuration_command_timeout')


def configure(api):
    ensure_versions(api)
    # Refuse unrelated application wiring before changing shared indexer profiles.
    apps = api.call('prowlarr', 'applications')
    if any(item.get('name') not in ('Radarr manual discovery', 'Sonarr manual discovery') for item in apps):
        raise DiscoveryError('unreviewed_prowlarr_application')
    changed = False
    for app in ('radarr', 'sonarr'):
        check_lists(api, app)
        changed |= config_policy(api, app, 'config/indexer', {'rssSyncInterval': RSS_INTERVAL})
        changed |= config_policy(api, app, 'config/downloadclient', DOWNLOAD_POLICY)
        roots = api.call(app, 'rootfolder')
        if any(item.get('path') != '/library' for item in roots):
            raise DiscoveryError('unreviewed_library_root')
        if not roots:
            api.call(app, 'rootfolder', 'POST', {'path': '/library'})
            changed = True
        clients = api.call(app, 'downloadclient')
        if any(item.get('name') != CLIENT for item in clients):
            raise DiscoveryError('unreviewed_download_client')
        fields = {'host': 'sabnzbd', 'port': 8080, 'useSsl': False, 'urlBase': '',
                  'apiKey': api.sab_key, 'username': '', 'password': ''}
        prefix = 'Movie' if app == 'radarr' else 'Tv'
        fields.update({prefix[0].lower() + prefix[1:] + 'Category': 'prowlarr',
                       'recent' + prefix + 'Priority': -100, 'older' + prefix + 'Priority': -100})
        _, update = upsert(api, app, 'downloadclient', CLIENT,
            {'enable': True, 'priority': 1, 'removeCompletedDownloads': True,
             'removeFailedDownloads': False}, fields, 'Sabnzbd')
        changed |= update

    profile, update = upsert(api, 'prowlarr', 'appprofile', PROFILE,
                            dict(PROFILE_POLICY, minimumSeeders=1))
    changed |= update
    indexers = api.call('prowlarr', 'indexer')
    if len(indexers) != 2 or {item.get('implementation') for item in indexers} != {'Newznab'}:
        raise DiscoveryError('expected_two_reviewed_usenet_indexers')
    for indexer in indexers:
        if not indexer.get('enable'):
            raise DiscoveryError('required_indexer_disabled')
        if indexer.get('appProfileId') != profile['id']:
            indexer['appProfileId'] = profile['id']
            api.call('prowlarr', 'indexer/' + str(indexer['id']), 'PUT', indexer)
            changed = True
    for app in ('radarr', 'sonarr'):
        port = APPS[app][0]
        _, update = upsert(api, 'prowlarr', 'applications', app.title() + ' manual discovery',
            {'syncLevel': 'fullSync', 'tags': []},
            {'prowlarrUrl': 'http://prowlarr:9696', 'baseUrl': f'http://{app}:{port}/{app}',
             'apiKey': api.keys[app], 'syncCategories': [2000] if app == 'radarr' else [5000]},
            app.title())
        changed |= update
    # This command synchronizes definitions only, never searches for content.
    run_configuration_command(api, 'prowlarr', 'ApplicationIndexerSync')
    for app in ('radarr', 'sonarr'):
        run_configuration_command(api, app, 'CheckHealth')
    for attempt in range(20):
        try:
            result = inspect(api)
            result['changed'] = changed
            return result
        except DiscoveryError:
            if attempt == 19:
                raise
            time.sleep(2)


def inspect(api):
    ensure_versions(api)
    profiles = api.call('prowlarr', 'appprofile')
    owned = [item for item in profiles if item.get('name') == PROFILE]
    if len(owned) != 1 or not require_policy(owned[0], PROFILE_POLICY):
        raise DiscoveryError('manual_sync_profile_not_verified')
    source_indexers = api.call('prowlarr', 'indexer')
    if len(source_indexers) != 2 or any(item.get('appProfileId') != owned[0]['id'] for item in source_indexers):
        raise DiscoveryError('source_indexer_policy_not_verified')
    result = {'status': 'verified', 'automatic_acquisition': True, 'automatic_import': True, 'apps': {}}
    for app in ('radarr', 'sonarr'):
        check_lists(api, app)
        if not require_policy(api.call(app, 'config/indexer'), {'rssSyncInterval': RSS_INTERVAL}):
            raise DiscoveryError('rss_policy_not_verified')
        if not require_policy(api.call(app, 'config/downloadclient'), DOWNLOAD_POLICY):
            raise DiscoveryError('download_policy_not_verified')
        indexers = api.call(app, 'indexer')
        if len(indexers) != 2 or any(not require_policy(item, PROFILE_POLICY) for item in indexers):
            raise DiscoveryError('synced_indexer_policy_not_verified')
        clients = api.call(app, 'downloadclient')
        if len(clients) != 1 or clients[0].get('name') != CLIENT or not require_policy(clients[0],
                {'enable': True, 'removeCompletedDownloads': True, 'removeFailedDownloads': False}):
            raise DiscoveryError('client_policy_not_verified')
        health = api.call(app, 'health')
        if any(item.get('type') in ('warning', 'error') and item.get('source') not in EXPECTED_HEALTH
               for item in health):
            raise DiscoveryError('unexpected_application_health_issue')
        result['apps'][app] = {'version': APPS[app][1], 'interactive_indexers': len(indexers),
                               'download_clients': len(clients), 'rss_interval': RSS_INTERVAL,
                               'automatic_search': True, 'rss_enabled': True,
                               'expected_policy_notices': len(health)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'inspect'))
    args = parser.parse_args()
    try:
        api = API()
        result = configure(api) if args.action == 'configure' else inspect(api)
        print(json.dumps(result, sort_keys=True))
    except DiscoveryError as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}))
        return 1
    except Exception:
        print(json.dumps({'status': 'failed', 'reason': 'unexpected_private_configuration_failure'}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
