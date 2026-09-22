#!/usr/bin/env python3
"""Configure private Seerr without requesting, acquiring or deleting media.

Only fixed summaries leave this helper. Plex credentials stay in private files
and loopback request bodies. Existing Arr settings and historical jobs are read
only; Seerr requests retain native Arr ownership.
"""
import argparse
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path('/srv/usenet')
URL = 'http://10.77.0.1:15055'
LIBRARIES = {'2', '3', '4', '5'}
MAIN = {'applicationTitle': 'Seerr', 'applicationUrl': URL, 'newPlexLogin': False,
        'localLogin': False, 'mediaServerLogin': True, 'defaultPermissions': 32,
        'discoverRegion': 'US', 'streamingRegion': 'US', 'locale': 'en'}


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def validate(settings):
    require(settings.get('public', {}).get('initialized') is True, 'seerr_setup_incomplete')
    require(all(settings['main'].get(k) == v for k, v in MAIN.items()), 'seerr_login_policy_changed')
    plex = settings['plex']
    require(plex.get('ip') == '192.168.1.66' and plex.get('port') == 32400
            and plex.get('useSsl') is False, 'seerr_plex_endpoint_changed')
    require({str(x['id']) for x in plex['libraries'] if x.get('enabled')} == LIBRARIES,
            'seerr_private_library_boundary_changed')
    for app, port in (('radarr', 7878), ('sonarr', 8989)):
        servers = settings[app]
        require(len(servers) == 1, 'seerr_unique_native_server_required')
        server = servers[0]
        expected = {'hostname': '127.0.0.1', 'port': port, 'baseUrl': '/' + app,
                    'activeDirectory': '/library', 'activeProfileId': 5, 'is4k': False,
                    'isDefault': True, 'syncEnabled': True, 'preventSearch': False}
        require(all(server.get(k) == v for k, v in expected.items()), 'seerr_native_routing_changed')
        if app == 'sonarr':
            require(server.get('monitorNewItems') == 'none', 'seerr_future_seasons_policy_changed')
    return {'status': 'verified', 'private_url': URL, 'plex_library_ids': sorted(LIBRARIES),
            'quality_profile': 'Ultra-HD', 'native_requests': True, 'direct_carts': 'disabled'}


def validate_quality_profile(profile):
    require(profile.get('name') == 'Ultra-HD' and profile.get('upgradeAllowed') is False,
            'seerr_quality_profile_policy_changed')
    allowed = [item.get('quality', {}).get('name') or item.get('name', '')
               for item in profile['items'] if item.get('allowed')]
    require(allowed and all('1080p' in name or '2160p' in name for name in allowed),
            'seerr_quality_resolution_changed')
    require(any('1080p' in name for name in allowed) and any('2160p' in name for name in allowed),
            'seerr_quality_fallback_missing')
    first_4k = next(i for i, name in enumerate(allowed) if '2160p' in name)
    require(all('2160p' in name for name in allowed[first_4k:]), 'seerr_quality_order_changed')


def native_quality(root, app, *, configure=False):
    port = {'radarr': 7878, 'sonarr': 8989}[app]
    key = ET.parse(root / f'config/{app}/config.xml').getroot().findtext('ApiKey')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
    url = f'http://127.0.0.1:{port}/{app}/api/v3/qualityprofile/5'

    def call(payload=None):
        request = urllib.request.Request(url, headers={'X-Api-Key': key, 'Content-Type': 'application/json'},
            data=json.dumps(payload).encode() if payload is not None else None,
            method='PUT' if payload is not None else 'GET')
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    profile = call()
    if configure:
        before = json.dumps(profile, sort_keys=True)
        for item in profile['items']:
            name = item.get('quality', {}).get('name') or item.get('name', '')
            if '1080p' in name:
                item['allowed'] = True
                for child in item.get('items', []):
                    child['allowed'] = True
        validate_quality_profile(profile)
        if json.dumps(profile, sort_keys=True) != before:
            call(profile)
            profile = call()
    validate_quality_profile(profile)


class API:
    def __init__(self, root=ROOT):
        self.root = root
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    def call(self, endpoint, payload=None, *, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            settings = json.loads((self.root / 'config/seerr/settings.json').read_text())
            headers['X-API-Key'] = settings['main']['apiKey']
        request = urllib.request.Request('http://127.0.0.1:5055/api/v1/' + endpoint,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        with self.opener.open(request, timeout=60) as response:
            raw = response.read(8 * 1024**2 + 1)
            require(len(raw) <= 8 * 1024**2, 'seerr_response_too_large')
            return json.loads(raw) if raw else None


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('seerr_redirect_refused')


def configure(root, token_path):
    for app in ('radarr', 'sonarr'):
        native_quality(root, app, configure=True)
    api = API(root)
    settings_path = root / 'config/seerr/settings.json'
    settings = json.loads(settings_path.read_text())
    if settings.get('public', {}).get('initialized'):
        return inspect(root)
    require(token_path.is_file() and not token_path.is_symlink()
            and not token_path.stat().st_mode & 0o077, 'private_plex_bootstrap_required')
    credentials = json.loads(token_path.read_text())
    require(set(credentials) == {'authToken'} and credentials['authToken'], 'plex_bootstrap_invalid')
    user = api.call('auth/plex', credentials, authenticated=False)
    require(user.get('id') == 1, 'seerr_original_owner_required')
    api.call('settings/main', MAIN)
    # No Plex library is enabled until the exact selected IDs are read back.
    api.call('settings/plex', {'ip': '192.168.1.66', 'port': 32400, 'useSsl': False})
    libraries = api.call('settings/plex/library?sync=true&enable=2,3,4,5')
    require({str(x['id']) for x in libraries if x.get('enabled')} == LIBRARIES,
            'seerr_selected_libraries_missing')
    profile = api.call('user/1/settings/main')
    profile.update(watchlistSyncMovies=False, watchlistSyncTv=False)
    api.call('user/1/settings/main', profile)
    for app, port in (('radarr', 7878), ('sonarr', 8989)):
        key = ET.parse(root / f'config/{app}/config.xml').getroot().findtext('ApiKey')
        require(bool(key), 'native_application_key_missing')
        server = {'name': app.capitalize(), 'hostname': '127.0.0.1', 'port': port,
                  'apiKey': key, 'useSsl': False, 'baseUrl': '/' + app,
                  'activeProfileId': 5, 'activeProfileName': 'Ultra-HD', 'activeDirectory': '/library',
                  'tags': [], 'is4k': False, 'isDefault': True, 'syncEnabled': True,
                  'preventSearch': False, 'tagRequests': False, 'overrideRule': [],
                  'externalUrl': f'http://10.77.0.1:19696/{app}/'}
        if app == 'radarr':
            server['minimumAvailability'] = 'released'
        else:
            server.update(seriesType='standard', animeSeriesType='anime', enableSeasonFolders=True,
                          monitorNewItems='none')
        result = api.call(f'settings/{app}/test', server)
        require(any(p['id'] == 5 and p['name'] == 'Ultra-HD' for p in result['profiles'])
                and any(f['path'] == '/library' for f in result['rootFolders']),
                'native_profile_or_library_unavailable')
        existing = api.call('settings/' + app)
        if existing:
            require(len(existing) == 1 and all(existing[0].get(k) == v for k, v in server.items()),
                    'partial_seerr_setup_requires_review')
        else:
            api.call('settings/' + app, server)
    api.call('settings/initialize', {})
    return inspect(root)


def inspect(root):
    settings = json.loads((root / 'config/seerr/settings.json').read_text())
    report = validate(settings)
    api = API(root)
    require(api.call('settings/public', authenticated=False)['initialized'], 'seerr_not_ready')
    profile = api.call('user/1/settings/main')
    require(not profile.get('watchlistSyncMovies') and not profile.get('watchlistSyncTv'),
            'unrequested_watchlist_acquisition_enabled')
    counts = {}
    for endpoint in ('discover/trending', 'discover/movies', 'discover/tv'):
        response = api.call(endpoint)
        counts[endpoint] = len(response.get('results', []))
        require(counts[endpoint] > 0, 'seerr_discovery_unavailable')
    report['discovery_result_counts'] = counts
    for app in ('radarr', 'sonarr'):
        native_quality(root, app)
        api.call('settings/' + app + '/test', settings[app][0])
    report['native_connections'] = 'verified'
    report['quality_preference'] = '2160p_then_1080p'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'inspect', 'ready'))
    parser.add_argument('--plex-token-file', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'ready':
            result = validate(json.loads((ROOT / 'config/seerr/settings.json').read_text()))
        elif args.action == 'configure':
            result = configure(ROOT, args.plex_token_file)
        else:
            result = inspect(ROOT)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error) if type(error) is RuntimeError
                          else 'private_seerr_setup_requires_review', 'error_type': type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
