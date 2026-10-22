"""Manage the two household resolvers separately from wiki publication.

Private snapshots stay in ignored build/wiki-private and NAS dns/backups.
DHCP remains a supported UniFi UI operation, never a database mutation.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tarfile
import time
from urllib.request import Request, urlopen
import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIVATE = ROOT / 'build/wiki-private'
NAS_ROOT = '/share/Container/usenet/dns'
POLICY = json.loads((HERE / 'policy.json').read_text())
ENDPOINTS = ['status', 'dns_info', 'filtering/status', 'rewrite/list',
             'safebrowsing/status', 'parental/status', 'safesearch/status', 'blocked_services/get']
PREAMBLE = r'''
set -eu
export DOCKER_CONFIG=/share/Container/usenet/state/docker-client
pkg=$(/sbin/getcfg container-station Install_Path -f /etc/config/qpkg.conf)
docker="$pkg/bin/docker"
if test ! -x "$docker"; then docker="$pkg/usr/bin/docker"; fi
test -x "$docker"
test "$(id -u)" -gt 0
root=/share/Container/usenet/dns
compose() { "$docker" compose --ansi never --file "$root/runtime/compose.yaml" --env-file "$root/runtime/.env" "$@"; }
'''


def remote(script, payload=None):
    args = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'ConnectTimeout=8',
            '-i', os.environ['QNAP_SSH_KEY'], '-o', 'UserKnownHostsFile=' + os.environ['QNAP_SSH_KNOWN_HOSTS'],
            os.environ['QNAP_SSH_TARGET'], 'sh -c ' + shlex.quote(PREAMBLE + script)]
    return subprocess.run(args, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


class Primary:
    def __init__(self):
        result = subprocess.run(['bash', '-c',
            'source talos/scripts/nvm_use.sh; node network-infra/dns/ha-session.cjs'],
            cwd=ROOT, capture_output=True, text=True, check=True)
        self.auth = json.loads(result.stdout)

    def api(self, path, data=None):
        request = Request('http://homeassistant.local:8123' + self.auth['prefix'].rstrip('/') + '/control/' + path,
                          headers={'Cookie': 'ingress_session=' + self.auth['session'], 'Content-Type': 'application/json'},
                          data=json.dumps(data).encode() if data is not None else None)
        with urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body and response.headers.get_content_type() == "application/json" else None

    def snapshot(self):
        return {endpoint: self.api(endpoint) for endpoint in ENDPOINTS}


def save_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def validate_primary(snapshot):
    # Refuse silent divergence or loss of existing custom policy. Adjust the
    # reviewed policy explicitly before changing an installation that has drifted.
    for key in ('upstream_dns', 'bootstrap_dns', 'fallback_dns'):
        if snapshot['dns_info'][key] != POLICY[key]:
            raise ValueError(f'Primary {key} differs from reviewed policy; reconcile before deployment')
    actual = [{k: f[k] for k in ('enabled', 'url', 'name', 'id')} for f in snapshot['filtering/status']['filters']]
    if actual != POLICY['filters'] or not snapshot['filtering/status']['enabled']:
        raise ValueError('Primary filter policy differs; review before deployment')
    if snapshot['filtering/status'].get('user_rules', []) not in ([], POLICY['user_rules']):
        raise ValueError('Primary has additional custom rules; preserve and review them first')
    if snapshot['rewrite/list']:
        raise ValueError('Primary has additional rewrites; review secondary parity first')
    if not snapshot['dns_info']['protection_enabled']:
        raise ValueError('Primary protection is disabled; local-zone rules would be bypassed')
    if any(snapshot[p]['enabled'] for p in ('safebrowsing/status', 'parental/status', 'safesearch/status')):
        raise ValueError('Primary safe-browsing/parental policy changed; reconcile secondary first')
    if snapshot['blocked_services/get']['ids']:
        raise ValueError('Primary blocked-services policy changed; reconcile secondary first')


def secondary_config(password_hash):
    return {
        'schema_version': 34,
        'http': {'address': '0.0.0.0:3000', 'session_ttl': '24h'},
        'users': [{'name': 'operator', 'password': password_hash}],
        'auth_attempts': 5, 'block_auth_min': 15,
        'dns': {'bind_hosts': ['0.0.0.0'], 'port': 1053,
                'upstream_dns': POLICY['upstream_dns'], 'bootstrap_dns': POLICY['bootstrap_dns'],
                'fallback_dns': POLICY['fallback_dns'], 'upstream_mode': 'load_balance',
                'protection_enabled': True, 'ratelimit': 20, 'cache_size': 4194304,
                'use_private_ptr_resolvers': False, 'resolve_clients': False},
        'filtering': {'protection_enabled': True, 'filtering_enabled': True, 'filters_update_interval': 24,
                      'rewrites_enabled': True, 'blocking_mode': 'default'},
        'filters': POLICY['filters'], 'user_rules': POLICY['user_rules'],
        'querylog': {'enabled': False, 'file_enabled': False},
        'statistics': {'enabled': False}, 'dhcp': {'enabled': False},
        'tls': {'enabled': False},
    }


def validate_answer(output, name, kind, expected):
    """Check the response header and answer records, never comments/additionals."""
    status = re.search(r'^;; ->>HEADER<<-.*\bstatus: ([A-Z]+),', output, re.MULTILINE)
    if status is None or status[1] != expected['status']:
        raise ValueError(f'DNS response status differs: {name} {kind}')
    records = []
    for line in output.splitlines():
        if not line or line.startswith(';'):
            continue
        fields = line.split()
        if len(fields) < 5 or fields[2] != 'IN':
            raise ValueError(f'Malformed DNS answer: {name} {kind}')
        records.append((fields[0].rstrip('.').lower(), fields[3], ' '.join(fields[4:])))
    if 'address' in expected:
        if records != [(name.lower(), kind, expected['address'])]:
            raise ValueError(f'DNS answer differs: {name} {kind}')
    elif expected.get('empty'):
        if records:
            raise ValueError(f'Expected an empty DNS answer: {name} {kind}')
    elif not any(record[1] == kind for record in records):
        raise ValueError(f'DNS answer is missing: {name} {kind}')


def check(addresses=None):
    for address in addresses or POLICY['resolvers']:
        for transport in ('+notcp', '+tcp'):
            for name, kind, expected in [('wiki.home.arpa', 'A', {'status': 'NOERROR', 'address': '192.168.1.66'}),
                                          ('wiki.home.arpa', 'AAAA', {'status': 'NOERROR', 'empty': True}),
                                          ('unknown-wiki-check.home.arpa', 'A', {'status': 'NXDOMAIN', 'empty': True}),
                                          ('unknown.wiki.home.arpa', 'A', {'status': 'NXDOMAIN', 'empty': True}),
                                          ('home.arpa', 'SOA', {'status': 'NXDOMAIN', 'empty': True}),
                                          ('example.com', 'A', {'status': 'NOERROR'})]:
                result = subprocess.run(['dig', '@' + address, name, kind, transport, '+time=3', '+tries=1',
                                         '+noall', '+comments', '+answer'],
                                        capture_output=True, text=True, check=True, timeout=6)
                validate_answer(result.stdout, name, kind, expected)
        print(f'{address}: exact wiki and negative answers plus public resolution pass over UDP/TCP; verify local handling/upstream independence separately')


def deploy():
    primary = Primary()
    snapshot = primary.snapshot()
    validate_primary(snapshot)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = PRIVATE / ('dns-before-' + stamp + '.json')
    save_private(backup, snapshot)
    # Credentials are generated once, kept private, and never printed.
    credential_path = PRIVATE / 'dns-secondary-credentials.json'
    if credential_path.exists():
        credentials = json.loads(credential_path.read_text())
    else:
        password = secrets.token_urlsafe(36)
        hashed = subprocess.run(['/usr/sbin/htpasswd', '-niB', 'operator'], input=password + '\n',
                                capture_output=True, text=True, check=True).stdout.strip().split(':', 1)[1]
        credentials = {'username': 'operator', 'password': password, 'hash': hashed}
        save_private(credential_path, credentials)
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as bundle:
        for name, content in {'compose.yaml': (HERE / 'compose.yaml').read_bytes(),
                              'Dockerfile': (HERE / 'Dockerfile').read_bytes(),
                              '.dockerignore': (HERE / '.dockerignore').read_bytes(),
                              'AdGuardHome.yaml': yaml.safe_dump(secondary_config(credentials['hash'])).encode(),
                              'primary-before.json': backup.read_bytes(),
                              'credentials.json': json.dumps(credentials).encode()}.items():
            info = tarfile.TarInfo(name); info.size = len(content); info.mode = 0o600; info.mtime = int(time.time())
            bundle.addfile(info, io.BytesIO(content))
    # Only the secondary is replaced. Capture its previous config/runtime before
    # stopping it. Never alter other NAS DNS listeners or any DHCP settings here.
    script = '''
mkdir -p "$root/config" "$root/data" "$root/runtime" "$root/backups"
chmod 700 "$root" "$root/config" "$root/data" "$root/runtime" "$root/backups"
mkdir "$root/.deploy-lock" || exit 1
stage=$(mktemp -d "$root/.incoming-XXXXXXXX")
trap 'rm -rf "$stage"; rmdir "$root/.deploy-lock"' EXIT HUP INT TERM
tar -xf - -C "$stage"
if test -f "$root/runtime/.env" && test -n "$("$docker" ps -aq --filter label=com.docker.compose.project=home-dns)"; then
  tar -czf "$root/backups/secondary-STAMP.tgz" -C "$root" config runtime
  compose stop resolver >/dev/null
fi
cp "$stage/primary-before.json" "$root/backups/primary-STAMP.json"
cp "$stage/credentials.json" "$root/backups/secondary-credentials.json"
cp "$stage/compose.yaml" "$root/runtime/compose.yaml"
cp "$stage/Dockerfile" "$stage/.dockerignore" "$root/runtime/"
cp "$stage/AdGuardHome.yaml" "$root/config/AdGuardHome.yaml"
printf 'DNS_ROOT=%s\\nDNS_UID=%s\\nDNS_GID=%s\\n' "$root" "$(id -u)" "$(id -g)" > "$root/runtime/.env"
compose config --quiet
compose build resolver >/dev/null
if ! compose up -d --force-recreate --wait --wait-timeout 120 resolver; then
 "$docker" logs --tail 30 "$(compose ps -aq resolver)" >&2
 "$docker" inspect --format '{{json .State.Health}}' "$(compose ps -aq resolver)" >&2
 exit 1
fi
'''.replace('STAMP', stamp)
    try:
        remote(script, payload.getvalue())
        check(['192.168.1.66'])
        primary.api('filtering/set_rules', {'rules': POLICY['user_rules']})
        primary.api('cache_clear', {})
        for attempt in range(5):
            try:
                check()
                break
            except ValueError:
                if attempt == 4:
                    raise
                time.sleep(2)
        # The filter API supplies evidence that unknown local queries are
        # synthesized by the rule engine rather than sent upstream.
        evidence = primary.api('querylog?search=unknown-wiki-check.home.arpa&limit=20')
        matching = [r for r in evidence.get('data', []) if r.get('question', {}).get('name') == 'unknown-wiki-check.home.arpa' and r.get('reason') == 'RewriteRule' and not r.get('upstream')]
        save_private(PRIVATE / 'dns-local-rule-evidence.json', {'matching_local_rewrites': len(matching)})
        if not matching:
            raise ValueError('Primary query log did not confirm local handling of the synthetic check name')
    except Exception as original_error:
        save_private(PRIVATE / 'dns-failure.json', {'stage': 'deployment_or_validation', 'error_type': type(original_error).__name__})
        # Restore only the changed primary rule list. Retain snapshots even if
        # restoration fails; never hide that outcome behind a success message.
        primary.api('filtering/set_rules', {'rules': snapshot['filtering/status'].get('user_rules', [])})
        primary.api('cache_clear', {})
        remote('''
if test -f "$root/backups/secondary-STAMP.tgz"; then
 compose stop resolver >/dev/null
 tar -xzf "$root/backups/secondary-STAMP.tgz" -C "$root"
 compose up -d --force-recreate --wait --wait-timeout 120 resolver
elif test -f "$root/runtime/.env"; then
 compose down >/dev/null
fi
'''.replace('STAMP', stamp))
        raise
    remote('umask 077; cat > "$root/backups/primary-current.json"', json.dumps(primary.snapshot()).encode())
    save_private(PRIVATE / 'dns-accepted.json', {'timestamp': stamp, 'primary_backup': str(backup),
                                              'policy': POLICY, 'dhcp_changed': False})
    print('Both resolvers validated. DHCP unchanged. Private rollback snapshot: ' + str(backup.relative_to(ROOT)))


def rollback(snapshot_path):
    snapshot = json.loads(snapshot_path.read_text())
    primary = Primary()
    primary.api('filtering/set_rules', {'rules': snapshot['filtering/status'].get('user_rules', [])})
    primary.api('cache_clear', {})
    print('Primary custom rules restored. Keep secondary available until DHCP leases no longer advertise it.')


def main():
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['deploy', 'check', 'rollback-primary'])
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--resolver', action='append', help='Check this resolver instead of the configured pair; repeatable')
    args = p.parse_args()
    if args.resolver and args.action != 'check': p.error('--resolver is only supported for check')
    if args.action == 'deploy': deploy()
    elif args.action == 'check': check(args.resolver)
    elif args.snapshot: rollback(args.snapshot)
    else: p.error('--snapshot is required for rollback-primary')


if __name__ == '__main__':
    try: main()
    except subprocess.TimeoutExpired:
        raise SystemExit('DNS check timed out; no DNS settings changed.') from None
    except subprocess.CalledProcessError as error:
        # Captured stderr may contain configuration or credentials; keep it private.
        PRIVATE.mkdir(parents=True, exist_ok=True)
        log = PRIVATE / 'dns-command-error.txt'
        value = error.stderr or b''
        log.write_bytes(value.encode() if isinstance(value, str) else value); log.chmod(0o600)
        raise SystemExit('DNS command failed; private diagnostic: build/wiki-private/dns-command-error.txt')
