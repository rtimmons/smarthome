#!/usr/bin/env python3
"""Summarize access principals from the encrypted pre-AD QTS rollback archive."""
import configparser
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from manage import PRIVATE


def main():
    os.umask(0o077)
    state = Path(os.environ.get('SMARTHOME_STATE_DIR', Path.home()/'.local/share/smarthome'))
    archive = sorted((state/'recovery').glob('qnap-pre-ad-*.tar.gz.age'))[-1]
    age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age'
    plain = subprocess.check_output([str(age),'-d','-i',str(Path.home()/'.config/smarthome/recovery.agekey'),str(archive)])
    with tarfile.open(fileobj=io.BytesIO(plain),mode='r:gz') as source:
        config = configparser.RawConfigParser(strict=False)
        config.read_string(source.extractfile('smb.conf').read().decode())
        users = [line.split(':') for line in source.extractfile('passwd').read().decode().splitlines()]
    result = {'source': archive.name,
              'users': [{'name': row[0], 'uid': int(row[2]), 'gid': int(row[3])}
                        for row in users if row[2].isdigit() and 1000 <= int(row[2]) < 2000],
              'shares': {name: {key: config.get(name,key,fallback='') for key in
                               ('valid users','write list','read list','invalid users','guest ok','read only')}
                         for name in config.sections() if name.lower() != 'global'}}
    (PRIVATE/'nas-access-before.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
