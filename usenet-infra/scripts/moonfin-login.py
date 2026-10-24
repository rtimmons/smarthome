#!/usr/bin/env python3
"""Reconnect the dedicated Moonfin request account without exposing credentials."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://192.168.1.66:8096'


def reconcile_session(session, jellyfin_id, seerr_user, expected_seerr_id):
    """Repair 2.4.0's missing login-response metadata from authenticated auth/me."""
    if (uuid.UUID(session['jellyfinUserId']) != uuid.UUID(jellyfin_id)
            or session['seerrUserId'] != expected_seerr_id
            or seerr_user['id'] != expected_seerr_id
            or seerr_user['permissions'] != 160):
        raise ValueError('Account binding or request-only permissions changed')
    return {**session, 'permissions': seerr_user['permissions'],
            'displayName': seerr_user['displayName']}


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused')


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
    token = None

    def api(path, data=None):
        auth = 'MediaBrowser Client="Moonfin Setup", Device="Operator", DeviceId="moonfin-setup", Version="1"'
        if token:
            auth += ', Token="' + token + '"'
        request = urllib.request.Request(URL + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization': auth, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=90) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    def private(path):
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError('Credentials must be private regular files')
        return json.loads(path.read_text())

    jellyfin = private(ROOT / 'secrets/jellyfin/operator.json')
    seerr = private(ROOT / 'secrets/moonfin/seerr.json')
    auth = api('/Users/AuthenticateByName', {'Username': jellyfin['username'], 'Pw': jellyfin['password']})
    token, user_id = auth['AccessToken'], auth['User']['Id']
    plugin = next(p for p in api('/Plugins') if p['Name'] == 'Moonbase')
    if plugin['Version'] != '2.4.0.0' or plugin['Status'] != 'Active':
        raise ValueError('Review changed Moonbase version before applying compatibility repair')
    api('/Moonfin/Seerr/Login', {'Username': seerr['email'], 'Password': seerr['password'], 'AuthType': 'local'})
    me = api('/Moonfin/Seerr/Api/auth/me')
    spec = importlib.util.spec_from_file_location('qnap_recon', ROOT / 'scripts/qnap-recon.py')
    recon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recon)
    prelude = '''set -eu
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"
if test ! -x "$docker"; then docker="$pkg/usr/bin/docker"; fi
'''

    def remote(command):
        result = subprocess.run(recon.connection_command(os.environ),
            input=(prelude + command + '\n').encode(), capture_output=True, timeout=45)
        if result.returncode:
            raise ValueError('Dedicated NAS command failed; no fallback attempted')
        return result.stdout

    path = '/config/plugins/configurations/Moonfin/seerr-sessions/' + str(uuid.UUID(user_id)) + '.json'
    raw = remote('"$docker" exec usenet-jellyfin-trial-jellyfin-1 cat ' + shlex.quote(path))
    updated = reconcile_session(json.loads(raw), user_id, me, seerr['userId'])
    encoded = base64.b64encode(json.dumps(updated).encode()).decode()
    # Refuse a concurrent session rotation. Preserve the previous cookie privately.
    command = ('test "$(sha256sum ' + shlex.quote(path) + " | cut -d ' ' -f1)"
        + '" = ' + shlex.quote(hashlib.sha256(raw).hexdigest())
        + '\numask 077\ncp ' + shlex.quote(path) + ' ' + shlex.quote(path + '.previous')
        + '\nprintf %s ' + shlex.quote(encoded) + ' | base64 -d > ' + shlex.quote(path + '.new')
        + '\nmv ' + shlex.quote(path + '.new') + ' ' + shlex.quote(path))
    remote('"$docker" exec usenet-jellyfin-trial-jellyfin-1 sh -c ' + shlex.quote(command))
    status = api('/Moonfin/Seerr/Status')
    if not status['authenticated'] or status['permissions'] != 160:
        raise ValueError('Moonfin session verification failed')
    print('Moonfin Seerr session verified: explicit requests and auto-approval; no admin rights.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never emit remote bodies, URLs containing credentials, or exception arguments.
        print('Moonfin reconnect failed (' + type(error).__name__ + '); credentials were not printed.')
        raise SystemExit(1)
