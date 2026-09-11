#!/usr/bin/env python3
"""Initialize only new discovery config files; private keys stay on the host."""
import os
from pathlib import Path
import secrets
import xml.etree.ElementTree as ET


def initialize(root=Path('/srv/usenet/config')):
    for app, port in (('radarr', 7878), ('sonarr', 8989)):
        path = root / app / 'config.xml'
        if path.exists():
            # Existing settings are inspected by discovery-config.py; never
            # rotate credentials or silently replace an existing application.
            continue
        config = ET.Element('Config')
        for key, value in {
            'BindAddress': '*', 'Port': str(port), 'UrlBase': '/' + app,
            'ApiKey': secrets.token_hex(16), 'AuthenticationMethod': 'External',
            'AuthenticationRequired': 'Enabled', 'LaunchBrowser': 'False',
            'Branch': 'master' if app == 'radarr' else 'main',
            'UpdateMechanism': 'Docker', 'UpdateAutomatically': 'False',
            'AnalyticsEnabled': 'False', 'LogLevel': 'warn',
        }.items():
            ET.SubElement(config, key).text = value
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(ET.tostring(config, encoding='utf-8'))


if __name__ == '__main__':
    initialize()
