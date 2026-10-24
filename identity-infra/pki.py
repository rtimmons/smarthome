#!/usr/bin/env python3
"""Create an offline root and issuing CA once; issue narrowly named leaf certs."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

STATE=Path(os.environ.get('SMARTHOME_STATE_DIR',Path.home()/'.local/share/smarthome'))/'tree/build/identity-private'
PKI=Path.home()/'.config/smarthome/pki'
SECRET_NAMES = ('domain-admin','ldap-bind','session','storage','jwt','forgejo-client')

def require_existing_secrets(state):
    initialized = any((state/name).exists() for name in
                      ('authelia-seed/configuration.json', 'human-logins.json', 'ha-cutover.json'))
    if initialized and any(not (state/'secrets'/name).is_file() for name in SECRET_NAMES):
        raise RuntimeError('Existing identity is missing secret material; restore it before certificate renewal')

def run(*args):
    subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

def key(path):
    if not path.exists():
        if path.with_suffix('.crt').exists():
            raise RuntimeError('Certificate exists without its key; restore the key instead of replacing its identity.')
        run('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:P-256','-out',path)
    path.chmod(0o600)

def issue(name, subject, sans, days=180):
    directory=STATE/'tls';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    private=directory/(name+'.key');cert=directory/(name+'.crt')
    key(private)
    if cert.exists():
        details = subprocess.check_output(['openssl','x509','-in',str(cert),'-noout','-text']).decode()
        valid = subprocess.run(['openssl','x509','-in',str(cert),'-checkend',str(30*86400),'-noout'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE).returncode == 0
        if valid and 'X509v3 Authority Key Identifier' in details and 'X509v3 Subject Key Identifier' in details and all((item if item.startswith('DNS:') else item.replace('IP:', 'IP Address:')) in details for item in sans.split(',')):
            return
    with tempfile.TemporaryDirectory(dir=PKI) as tmp:
        csr=Path(tmp)/'request';extension=Path(tmp)/'extensions'
        run('req','-new','-key',private,'-subj','/CN='+subject,'-out',csr)
        extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName='+sans+'\n')
        run('x509','-req','-in',csr,'-CA',PKI/'issuing.crt','-CAkey',PKI/'issuing.key','-set_serial','0x'+secrets.token_hex(20),'-days',str(days),'-sha256','-extfile',extension,'-out',cert)
    (directory/(name+'-chain.crt')).write_bytes(cert.read_bytes()+(PKI/'issuing.crt').read_bytes())

def main():
    require_existing_secrets(STATE)
    os.umask(0o077);PKI.mkdir(parents=True,exist_ok=True,mode=0o700)
    key(PKI/'root.key')
    if not (PKI/'root.crt').exists():
        run('req','-x509','-new','-key',PKI/'root.key','-days','3650','-sha256','-subj','/CN=Smarthome Root CA','-addext','basicConstraints=critical,CA:TRUE,pathlen:1','-addext','keyUsage=critical,keyCertSign,cRLSign','-out',PKI/'root.crt')
    key(PKI/'issuing.key')
    if not (PKI/'issuing.crt').exists():
        with tempfile.TemporaryDirectory(dir=PKI) as tmp:
            csr=Path(tmp)/'request';ext=Path(tmp)/'extensions'
            run('req','-new','-key',PKI/'issuing.key','-subj','/CN=Smarthome Issuing CA','-out',csr)
            ext.write_text('basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
            run('x509','-req','-in',csr,'-CA',PKI/'root.crt','-CAkey',PKI/'root.key','-set_serial','0x'+secrets.token_hex(20),'-days','1095','-sha256','-extfile',ext,'-out',PKI/'issuing.crt')
    issue('dc','dc1.ad.home.arpa','DNS:dc1.ad.home.arpa,IP:192.168.1.10')
    web_names = [s+'.home.arpa' for s in ('auth','git','radarr','sonarr','prowlarr','sabnzbd','catalog','wiki')]
    web_names += [s+'.apps.home.arpa' for s in ('auth','radarr','sonarr','prowlarr','sabnzbd','catalog')]
    issue('web','auth.apps.home.arpa',','.join('DNS:'+s for s in web_names))
    (STATE/'tls/ca.crt').write_bytes((PKI/'root.crt').read_bytes())
    for name in ('dc','web'):
        run('verify','-CAfile',PKI/'root.crt','-untrusted',PKI/'issuing.crt',STATE/'tls'/(name+'.crt'))
    secret_dir=STATE/'secrets';secret_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name in SECRET_NAMES:
        path=secret_dir/name
        if not path.exists():path.write_text(secrets.token_urlsafe(48)+'\n');path.chmod(0o600)
    print('Private CA and leaf chains verified. Public trust certificate:',PKI/'root.crt')
    print('CA private keys remain only on the controller:',PKI)

if __name__=='__main__':main()
