#!/usr/bin/env python3
"""Configure native Arr import notifications with verified general-library mappings."""
import argparse
import copy
import importlib.util
import json
import ipaddress
from pathlib import Path
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path('/srv/usenet')
NAME = 'Plex native imports'
TARGETS = {
    'sonarr': ('5', 'show', '/share/CACHEDEV2_DATA/FromDrobo/Remote/files/library/TV'),
    'radarr': ('4', 'movie', '/share/CACHEDEV2_DATA/FromDrobo/Remote/files/library/Movies'),
}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def fields(resource):
    values = {f['name']: f.get('value') for f in resource['fields']}
    require(len(values) == len(resource['fields']), 'duplicate_connector_fields')
    return values


def verify_mapping(app, roots, sections):
    section_id, kind, target = TARGETS[app]
    require([r['path'] for r in roots] == ['/library'], 'unexpected_native_roots')
    matches = [(s['id'], s['type']) for s in sections for p in s['locations'] if p == target]
    require(matches == [(section_id, kind)], 'plex_mapping_not_unique_expected_library')
    return target


def desired(schema, app, token, host='172.18.0.1'):
    require(schema['implementation'] == 'PlexServer', 'unexpected_connector_schema')
    value = copy.deepcopy(schema)
    value.pop('id', None)
    value['name'] = NAME
    value['tags'] = []
    for key in value:
        if key.startswith('on'):
            value[key] = False
    # One Sonarr notification after the batch completes; Radarr's import event.
    trigger = 'onImportComplete' if app == 'sonarr' else 'onDownload'
    require(value.get('supports' + trigger[0].upper() + trigger[1:]) is True, 'import_trigger_unsupported')
    value[trigger] = True
    value['onRename'] = True
    expected = {'host': host, 'port': 32401, 'useSsl': False, 'urlBase': '',
                'authToken': token, 'updateLibrary': True, 'mapFrom': '/library',
                'mapTo': TARGETS[app][2]}
    require(set(expected) <= fields(value).keys(), 'required_connector_fields_missing')
    for field in value['fields']:
        if field['name'] in expected:
            field['value'] = expected[field['name']]
    return value


def verify_resource(actual, expected):
    require(actual['implementation'] == 'PlexServer' and actual['name'] == NAME
            and actual.get('tags', []) == [], 'connector_identity_changed')
    for key in expected:
        if key.startswith('on'):
            require(actual.get(key) == expected[key], 'connector_trigger_changed')
    observed, wanted = fields(actual), fields(expected)
    for key in ('host', 'port', 'useSsl', 'urlBase', 'updateLibrary', 'mapFrom', 'mapTo'):
        require((observed.get(key) or '' if key == 'urlBase' else observed.get(key)) == wanted[key],
                'connector_field_changed')
    # Secret readback may be masked. The native test validates the stored token.


def run(action, root=ROOT):
    spec = importlib.util.spec_from_file_location('discovery', root/'libexec/discovery-config.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    api = module.API(root/'config'); module.ensure_versions(api)
    with sqlite3.connect(f'file:{root}/config/seerr/db/db.sqlite3?mode=ro', uri=True) as db:
        row = db.execute('select plexToken from user where id=1').fetchone()
    require(row and row[0], 'existing_plex_owner_token_required')
    token = row[0]
    req = urllib.request.Request('http://192.168.1.66:32400/library/sections', headers={'X-Plex-Token': token})
    with api.opener.open(req, timeout=30) as response:
        tree = ET.fromstring(response.read(1024**2))
    sections = [{'id': e.get('key'), 'type': e.get('type'),
                 'locations': [p.get('path') for p in e.findall('Location')]} for e in tree]
    network = json.loads((root/'config/catalog/arr-plex-network.json').read_text())
    subnet = ipaddress.IPv4Network(network['subnet'])
    gateway = ipaddress.IPv4Address(network['gateway'])
    require(subnet.is_private and gateway in subnet and not subnet.overlaps(ipaddress.ip_network('192.168.1.0/24')), 'proxy_network_invalid')
    plans = {}
    for app in TARGETS:
        verify_mapping(app, api.call(app, 'rootfolder'), sections)
        existing = api.call(app, 'notification')
        require(all(c.get('implementation') != 'PlexServer' or c.get('name') == NAME for c in existing),
                'existing_plex_connector_requires_review')
        owned = [c for c in existing if c.get('name') == NAME]
        require(len(owned) <= 1, 'duplicate_owned_connector')
        schema = next(c for c in api.call(app, 'notification/schema') if c['implementation'] == 'PlexServer')
        candidate = desired(schema, app, token, str(gateway))
        if owned:
            verify_resource(owned[0], candidate)
            candidate['id'] = owned[0]['id']
        require(action == 'configure' or owned, 'connector_missing')
        api.call(app, 'notification/test', 'POST', candidate)
        plans[app] = (owned, candidate)
    changed = False
    for app, (owned, candidate) in plans.items():
        if not owned:
            api.call(app, 'notification', 'POST', candidate)
            changed = True
        actual = next(c for c in api.call(app, 'notification') if c.get('name') == NAME)
        verify_resource(actual, candidate)
        api.call(app, 'notification/test', 'POST', actual)
    return {'status': 'verified', 'changed': changed, 'library_ids': ['4', '5'],
            'native_import_notifications': True, 'rename_notifications': True,
            'new_import_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'inspect'))
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.action), sort_keys=True))
    except Exception as error:
        # Never print native payloads, URLs with tokens, or upstream responses.
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
