#!/usr/bin/env python3
"""Escrow existing application API keys without changing live configuration."""
import json, os, subprocess
from pathlib import Path
from manage import ROOT, PRIVATE
os.umask(0o077)
script = r'''
import json,re,xml.etree.ElementTree as ET
from pathlib import Path
root=Path('/srv/usenet/config')
keys={name:ET.parse(root/name/'config.xml').getroot().findtext('ApiKey') for name in ('radarr','sonarr','prowlarr')}
text=(root/'sabnzbd/sabnzbd.ini').read_text()
values=re.findall(r'^api_key\s*=\s*([^\r\n]+)',text,re.M)
if len(values)!=1 or not all(keys.values()):raise RuntimeError('Missing API credential')
keys['sabnzbd']=values[0].strip().strip('"')
print(json.dumps(keys))
'''
result=subprocess.run([str(ROOT/'usenet-infra/scripts/cloud-command'),'sudo','-n','python3','-'],input=script.encode(),capture_output=True,timeout=45)
if result.returncode:raise SystemExit('API key escrow read failed; no credential output displayed')
value=json.loads(result.stdout)
if set(value)!={'radarr','sonarr','prowlarr','sabnzbd'} or not all(isinstance(v,str) and len(v)>=16 for v in value.values()):raise SystemExit('Unexpected API credential format')
p=PRIVATE/'secrets/app-api-keys.json'
if p.exists() and json.loads(p.read_text())!=value:raise SystemExit('Existing escrow differs; review before replacing')
p.write_text(json.dumps(value,sort_keys=True)+'\n');p.chmod(0o600)
print('Four existing application API keys escrowed privately; none changed.')
