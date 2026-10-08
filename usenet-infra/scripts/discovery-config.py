#!/usr/bin/env python3
"""Inspect pinned Radarr and Sonarr acquisition settings on the cloud host.

No search, grab, import, download deletion, or arbitrary URL entry point exists.
Only sanitized summaries leave this helper; application keys remain in memory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import sys
import urllib.request
import xml.etree.ElementTree as ET

APPS = {'radarr': (7878, '6.4.4.10685'), 'sonarr': (8989, '4.0.20.3014'),
        'prowlarr': (9696, '2.6.5.5623')}
# Keep the existing resource name so upgrades preserve its ID and bindings.
PROFILE = 'Manual discovery only'
CLIENT = 'SABnzbd manual discovery'
DOWNLOAD_POLICY = {'enableCompletedDownloadHandling': True,
                   'autoRedownloadFailed': False,
                   'autoRedownloadFailedFromInteractiveSearch': False}
RSS_INTERVAL = 0
PROFILE_POLICY = {'enableRss': True, 'enableAutomaticSearch': True,
                  'enableInteractiveSearch': True}
EXPECTED_HEALTH = set()
NATIVE_MARKER = Path('/srv/usenet/config/catalog/native-ownership.json')


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

    def call(self, app, endpoint, method='GET', body=None, *, timeout=60):
        port = APPS[app][0]
        base = '/api/v1/' if app == 'prowlarr' else '/' + app + '/api/v3/'
        request = urllib.request.Request(f'http://127.0.0.1:{port}{base}{endpoint}',
            headers={'X-Api-Key': self.keys[app], 'Content-Type': 'application/json'},
            method=method, data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(8 * 1024 * 1024)
            return json.loads(raw) if raw else None
        except DiscoveryError:
            raise
        except Exception:
            raise DiscoveryError('private_application_request_failed') from None


def require_policy(resource, desired):
    return all(key in resource and type(resource[key]) is type(value)
               and resource[key] == value for key, value in desired.items())


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


def inspect(api):
    ensure_versions(api)
    marker = json.loads(NATIVE_MARKER.read_text())
    if marker.get('phase') != 'active' or marker.get('integrity_policy') != 'native_arr_import_and_cleanup':
        raise DiscoveryError('native_ownership_marker_invalid')
    rss_interval = RSS_INTERVAL
    profiles = api.call('prowlarr', 'appprofile')
    owned = [item for item in profiles if item.get('name') == PROFILE]
    if len(owned) != 1 or not require_policy(owned[0], PROFILE_POLICY):
        raise DiscoveryError('manual_sync_profile_not_verified')
    source_indexers = api.call('prowlarr', 'indexer')
    if len(source_indexers) != 2 or any(item.get('appProfileId') != owned[0]['id'] for item in source_indexers):
        raise DiscoveryError('source_indexer_policy_not_verified')
    result = {'status': 'verified', 'automatic_acquisition': False, 'automatic_import': True,
              'explicit_native_requests': True, 'apps': {}}
    for app in ('radarr', 'sonarr'):
        check_lists(api, app)
        if not require_policy(api.call(app, 'config/indexer'), {'rssSyncInterval': rss_interval}):
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
                               'download_clients': len(clients), 'rss_interval': rss_interval,
                               'automatic_search': True, 'rss_enabled': False,
                               'expected_policy_notices': len(health)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect',))
    args = parser.parse_args()
    try:
        api = API()
        result = inspect(api)
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
