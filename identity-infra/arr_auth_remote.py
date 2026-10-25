#!/usr/bin/env python3
"""Change only Prowlarr's UI gate; preserve API keys and its saved settings."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET


def external_config(data):
    root = ET.fromstring(data)
    if len(root.findall('AuthenticationMethod')) != 1:
        raise RuntimeError('Expected exactly one authentication setting')
    if root.findtext('AuthenticationMethod') not in ('Forms', 'External'):
        raise RuntimeError('Unexpected existing authentication mode')
    if not root.findtext('ApiKey'):
        raise RuntimeError('Existing API key required')
    result, count = re.subn(rb'<AuthenticationMethod>Forms</AuthenticationMethod>',
                           b'<AuthenticationMethod>External</AuthenticationMethod>', data)
    if root.findtext('AuthenticationMethod') == 'Forms' and count != 1:
        raise RuntimeError('Expected exactly one authentication setting')
    return result


def main():
    os.umask(0o077)
    path = Path('/srv/usenet/config/prowlarr/config.xml')
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Expected a regular Prowlarr configuration')
    original = path.read_bytes()
    key = ET.fromstring(original).findtext('ApiKey')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def api(endpoint):
        request = urllib.request.Request('http://127.0.0.1:9696/api/v1/'+endpoint,
                                         headers={'X-Api-Key':key})
        with opener.open(request, timeout=15) as response:
            return json.load(response)
    if api('system/status')['version'] != '2.6.5.5623':
        raise RuntimeError('Prowlarr version needs review')
    if any(item.get('status') in ('queued','started') for item in api('command')):
        raise RuntimeError('Prowlarr is busy; defer the scoped restart')
    identifiers = subprocess.check_output(['docker','ps','--filter',
        'label=com.docker.compose.service=prowlarr','--format','{{.ID}}'],text=True).splitlines()
    if len(identifiers) != 1:
        raise RuntimeError('Expected exactly one running Prowlarr container')
    container = identifiers[0]
    info = json.loads(subprocess.check_output(['docker','inspect',container]))[0]
    bindings = info['NetworkSettings']['Ports']
    if bindings.get('9696/tcp') != [{'HostIp':'127.0.0.1','HostPort':'9696'}]:
        raise RuntimeError('Prowlarr must retain its loopback-only port')
    if external_config(original) == original:
        print('Prowlarr already uses External; existing authenticated API and loopback binding verified.')
        return
    backup = path.parent/'identity-recovery'
    backup.mkdir(exist_ok=True, mode=0o700)
    saved = backup/'config.before-sso.xml'
    if saved.exists():
        raise RuntimeError('Prior migration backup exists; inspect before changing the app again')
    subprocess.run(['docker','stop','--time','30',container],check=True,stdout=subprocess.DEVNULL)
    try:
        stopped = path.read_bytes()
        before = ET.fromstring(stopped)
        if before.findtext('ApiKey') != key:
            raise RuntimeError('API key changed during shutdown')
        external_config(stopped)
        with saved.open('xb') as stream:
            stream.write(stopped)
    except Exception:
        subprocess.run(['docker','start',container],check=True,stdout=subprocess.DEVNULL)
        raise RuntimeError('Prowlarr preservation check failed; original service restarted') from None
    info = path.stat()
    def replace(data):
        stage = path.with_suffix('.identity-new')
        with stage.open('xb') as stream:
            stream.write(data)
        os.chown(stage,info.st_uid,info.st_gid)
        stage.chmod(info.st_mode & 0o777)
        stage.replace(path)
    try:
        replace(external_config(stopped))
        subprocess.run(['docker','start',container],check=True,stdout=subprocess.DEVNULL)
        for attempt in range(30):
            try:
                if api('system/status')['version'] == '2.6.5.5623': break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError('Prowlarr API did not recover')
        after = ET.fromstring(path.read_bytes())
        if after.findtext('AuthenticationMethod') != 'External':
            raise RuntimeError('External authentication was not retained')
        settings = lambda root: {item.tag:item.text for item in root if item.tag!='AuthenticationMethod'}
        if settings(before) != settings(after):
            raise RuntimeError('Unrelated Prowlarr settings changed')
        (backup/'receipt.json').write_text(json.dumps({'original_sha256':hashlib.sha256(stopped).hexdigest(),
            'settings_except_authentication':'identical','api_key':'preserved','loopback_binding':'verified'})+'\n')
        print('Prowlarr External auth enabled; original API key and every other setting preserved.')
    except Exception:
        subprocess.run(['docker','stop','--time','30',container],check=True,stdout=subprocess.DEVNULL)
        replace(stopped)
        subprocess.run(['docker','start',container],check=True,stdout=subprocess.DEVNULL)
        raise RuntimeError('Prowlarr migration failed; original configuration restored') from None


if __name__=='__main__': main()
