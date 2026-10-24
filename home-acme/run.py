#!/usr/bin/env python3
"""Renew LAN HTTPS certificates without exposing services or installing roots."""
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

DOMAIN = 'home.rytim.com'
DATA = Path('/data')
KEY = Path('/config/dreamhost-api-key')
PUBLISHED = Path('/ssl/smarthome/acme')
STOP = threading.Event()
child = None


def stop(signum, frame):
    STOP.set()
    if child is not None and child.poll() is None:
        child.terminate()


def sanitized(text, secret):
    text = text.replace(secret, '[redacted]')
    return re.sub(r'([?&]key=)[^&\s"<>]+', r'\1[redacted]', text)


def checked(args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT)


def verify_certificate(certificate, key, ca_file='/etc/ssl/cert.pem'):
    checked(['openssl', 'verify', '-CAfile', str(ca_file), '-untrusted', str(certificate),
             '-purpose', 'sslserver', '-verify_hostname', 'auth.'+DOMAIN, str(certificate)])
    checked(['openssl', 'x509', '-in', str(certificate), '-checkend', '86400', '-noout'])
    cert_public = checked(['openssl', 'x509', '-in', str(certificate), '-pubkey', '-noout'])
    key_public = checked(['openssl', 'pkey', '-in', str(key), '-pubout'])
    if cert_public != key_public:
        raise ValueError('Certificate and private key do not match')


def publish(certificate, key, destination=PUBLISHED, ca_file='/etc/ssl/cert.pem'):
    # Validate first: a failed issuance must never replace the working pair.
    verify_certificate(certificate, key, ca_file)
    fingerprint = hashlib.sha256(certificate.read_bytes()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination/fingerprint
    if target.exists():
        if ((target/'fullchain.pem').read_bytes() != certificate.read_bytes()
                or (target/'key.pem').read_bytes() != key.read_bytes()):
            raise ValueError('Existing certificate publication differs')
    else:
        with tempfile.TemporaryDirectory(prefix='.incoming-', dir=destination) as incoming:
            incoming = Path(incoming)
            for source, name in ((certificate, 'fullchain.pem'), (key, 'key.pem')):
                shutil.copyfile(source, incoming/name)
                (incoming/name).chmod(0o600)
            incoming.rename(target)
    link = destination/'.current.new'
    if link.is_symlink():
        link.unlink()
    link.symlink_to(fingerprint, target_is_directory=True)
    link.replace(destination/'current')
    return fingerprint


def issue(server, secret):
    global child
    folder = DATA/server
    folder.mkdir(exist_ok=True, mode=0o700)
    env = dict(os.environ, DREAMHOST_API_KEY_FILE=str(KEY),
               DREAMHOST_PROPAGATION_TIMEOUT='7200', DREAMHOST_HTTP_TIMEOUT='60')
    command = ['lego', 'run', '--server', server, '--path', str(folder),
               '--account-id', 'smarthome-'+DOMAIN, '--cert.name', DOMAIN,
               '--domains', '*.'+DOMAIN, '--dns', 'dreamhost', '--accept-tos',
               # UniFi intercepts outbound port 53. Its cached answer is not an
               # authoritative propagation check. Quad9's alternate port keeps
               # both recursive checks independent of the split DNS namespace.
               '--reuse-key', '--dns.resolvers', '9.9.9.9:9953',
               '--dns.resolvers', '149.112.112.112:9953',
               '--dns.propagation.disable-ans', '--log.format', 'text']
    print('Checking certificate with '+server+' through independent public DNS.', flush=True)
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    try:
        output, _ = child.communicate(timeout=7800)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:
            output, _ = child.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            output, _ = child.communicate()
        raise RuntimeError('ACME request exceeded its time limit')
    finally:
        # Credential-bearing request URLs must not reach Supervisor logs.
        if 'output' in locals():
            (DATA/'last-run.log').write_text(sanitized(output.decode(errors='replace'), secret))
    if child.returncode:
        raise RuntimeError('ACME request failed; inspect the redacted private log')
    return folder/'certificates'/f'{DOMAIN}.crt', folder/'certificates'/f'{DOMAIN}.key'


def seed():
    source = Path('/ssl/smarthome/acme-seed/dreamhost-api-key')
    if source.is_file():
        if KEY.exists() and KEY.read_bytes() != source.read_bytes():
            raise RuntimeError('Existing DNS credential differs; refusing replacement')
        KEY.parent.mkdir(exist_ok=True, mode=0o700)
        if not KEY.exists():
            shutil.copyfile(source, KEY)
        KEY.chmod(0o600)
    value = KEY.read_text().strip()
    if len(value) < 16 or any(c.isspace() for c in value):
        raise RuntimeError('Missing or invalid DNS credential')
    return value


def main():
    os.umask(0o077)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    DATA.mkdir(exist_ok=True, mode=0o700)
    secret = seed()
    status = DATA/'status.json'
    if status.exists() and json.loads(status.read_text()).get('status') == 'error':
        previous_log = DATA/'last-run.log'
        if previous_log.exists():
            print(sanitized(previous_log.read_text()[-5000:], secret), flush=True)
    while not STOP.is_set():
        try:
            marker = DATA/'staging-passed.json'
            if not marker.exists():
                certificate, _ = issue('letsencrypt-staging', secret)
                checked(['openssl', 'x509', '-in', str(certificate),
                         '-checkhost', 'auth.'+DOMAIN, '-noout'])
                marker.write_text(json.dumps({'domain': '*.'+DOMAIN, 'checked_at': time.time()})+'\n')
                print('ACME staging issuance passed; production issuance is next.', flush=True)
            if STOP.is_set():
                break
            certificate, key = issue('letsencrypt', secret)
            fingerprint = publish(certificate, key)
            (DATA/'status.json').write_text(json.dumps({
                'status': 'ok', 'checked_at': time.time(), 'certificate_sha256': fingerprint})+'\n')
            print('Public certificate verified and published; automatic renewal is active.', flush=True)
            STOP.wait(12*3600+random.randrange(1800))
        except Exception as error:
            if STOP.is_set():
                break
            (DATA/'status.json').write_text(json.dumps({
                'status': 'error', 'checked_at': time.time(), 'error_type': type(error).__name__})+'\n')
            print('Certificate check failed; the prior published certificate remains in place.', flush=True)
            print('Failure:', sanitized(str(error), secret), flush=True)
            if isinstance(error, subprocess.CalledProcessError):
                print(sanitized(error.output.decode(errors='replace'), secret), flush=True)
            elif (DATA/'last-run.log').exists():
                print(sanitized((DATA/'last-run.log').read_text()[-5000:], secret), flush=True)
            STOP.wait(900+random.randrange(300))


if __name__ == '__main__':
    main()
