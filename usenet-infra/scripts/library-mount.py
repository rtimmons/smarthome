#!/usr/bin/env python3
"""Run a synchronous SSHFS library using the existing Storage Box identity."""
import configparser
import os
from pathlib import Path
import re

config = configparser.ConfigParser(interpolation=None)
config.read('/srv/usenet/config/rclone/rclone.conf')
remote = config['storagebox']
if remote['type'] != 'sftp' or not re.fullmatch(r'[a-zA-Z0-9.-]+', remote['host']) or not re.fullmatch(r'[a-zA-Z0-9_-]+', remote['user']):
    raise SystemExit('Unexpected existing storage configuration')
if remote['key_file'] != '/srv/usenet/secrets/storagebox/id_ed25519' or remote['known_hosts_file'] != '/srv/usenet/secrets/storagebox/known_hosts':
    raise SystemExit('Unexpected storage identity paths')
args = ['/usr/bin/sshfs', remote['user'] + '@' + remote['host'] + ':catalog/library',
        '/srv/usenet/library', '-f', '-p', remote.get('port', '23'), '-o',
        ','.join(['IdentityFile=' + remote['key_file'], 'UserKnownHostsFile=' + remote['known_hosts_file'],
                  'IdentitiesOnly=yes', 'IdentityAgent=none', 'StrictHostKeyChecking=yes',
                  'BatchMode=yes', 'ConnectTimeout=15', 'ServerAliveInterval=15', 'ServerAliveCountMax=3',
                  'reconnect', 'sshfs_sync', 'allow_other', 'default_permissions', 'uid=1991', 'gid=1991',
                  'umask=0022'])]
os.execv(args[0], args)
