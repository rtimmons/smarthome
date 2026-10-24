"""NAS-resident Bonjour scanner and paired AdGuard reconciler.

No service names/TXT data are logged or persisted. Secrets are read from a
read-only private mount. The only writer is this process, guarded by flock.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler

from discovery import HOST, LAN, reconcile
from reconciler import atomic_json, converge

STATE = Path(os.environ.get('DNS_AUTO_STATE', '/state'))
CONFIG = Path(os.environ.get('DNS_AUTO_CONFIG', '/config'))


class AdGuard:
    def __init__(self, base, headers):
        self.base, self.headers = base, headers
        self.opener = build_opener(ProxyHandler({}))

    def api(self, path, data=None):
        request = Request(self.base + '/control/' + path,
                          headers={**self.headers, 'Content-Type': 'application/json'},
                          data=None if data is None else json.dumps(data).encode())
        with self.opener.open(request, timeout=15) as response:
            body = response.read()
            return json.loads(body) if body and response.headers.get_content_type() == 'application/json' else None


def clients():
    import websocket
    secrets = json.loads((CONFIG / 'credentials.json').read_text())
    server = secrets['ha_server']
    connection = websocket.create_connection(server.replace('http://', 'ws://') + '/api/websocket',
                                             timeout=15, http_no_proxy=['*'])
    try:
        if json.loads(connection.recv())['type'] != 'auth_required':
            raise RuntimeError('Unexpected Home Assistant handshake')
        connection.send(json.dumps({'type': 'auth', 'access_token': secrets['ha_token']}))
        if json.loads(connection.recv())['type'] != 'auth_ok':
            raise RuntimeError('Home Assistant authentication failed')
        def call(index, endpoint, method):
            connection.send(json.dumps({'id': index, 'type': 'supervisor/api',
                                        'endpoint': endpoint, 'method': method}))
            result = json.loads(connection.recv())
            if result.get('id') != index or not result.get('success'):
                raise RuntimeError('Supervisor ingress request failed')
            return result['result']
        session = call(1, '/ingress/session', 'post')
        info = call(2, '/addons/a0d7b954_adguard/info', 'get')
    finally:
        connection.close()
    primary = AdGuard(server + info['ingress_url'].rstrip('/'),
                      {'Cookie': 'ingress_session=' + session['session']})
    basic = base64.b64encode((secrets['username'] + ':' + secrets['password']).encode()).decode()
    secondary = AdGuard('http://127.0.0.1:3001', {'Authorization': 'Basic ' + basic})
    return [secondary, primary]


def discover_lan():
    from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes
    class Listener(ServiceListener):
        def __init__(self):
            self.services = set()
            self.lock = threading.Lock()
        def add_service(self, zc, kind, name):
            with self.lock: self.services.add((kind, name))
        update_service = add_service
        def remove_service(self, zc, kind, name):
            with self.lock: self.services.discard((kind, name))
    zc = Zeroconf(interfaces=['192.168.1.66'], ip_version=IPVersion.V4Only)
    browser = None
    try:
        types = ZeroconfServiceTypes.find(zc=zc, timeout=5)
        if not types:
            raise RuntimeError('No Bonjour types visible; retaining existing records')
        listener = Listener()
        browser = ServiceBrowser(zc, list(types), listener=listener)
        time.sleep(8)
        with listener.lock: services = list(listener.services)
        found = {}
        def resolve(item):
            return zc.get_service_info(*item, timeout=2500)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for info in pool.map(resolve, services):
                if not info or not info.server or not HOST.fullmatch(info.server):
                    continue
                host = info.server.lower().rstrip('.')
                addresses = found.setdefault(host, set())
                for value in info.parsed_addresses(IPVersion.V4Only):
                    ip = ipaddress.IPv4Address(value)
                    if ip in LAN and ip not in (LAN.network_address, LAN.broadcast_address):
                        addresses.add(str(ip))
        if not any(found.values()):
            raise RuntimeError('No Bonjour LAN addresses visible; retaining existing records')
        return {host: sorted(values) for host, values in found.items()}
    finally:
        if browser: browser.cancel()
        zc.close()


def verify_once(policy, previous):
    import dns.message
    import dns.query
    import dns.rcode
    import dns.rdatatype
    cases = []
    for name, address in policy['records'].items():
        cases.extend([(name, 'A', 'NOERROR', [address]), (name, 'AAAA', 'NOERROR', []),
                      ('unknown.' + name, 'A', 'NXDOMAIN', [])])
    for removed in previous['records'].keys() - policy['records'].keys():
        cases.append((removed, 'A', 'NXDOMAIN', []))
    cases.extend([('home.arpa', 'SOA', 'NXDOMAIN', []),
                  ('unknown-autodns-check.home.arpa', 'A', 'NXDOMAIN', []),
                  ('example.com', 'A', 'NOERROR', None)])
    for address in [*policy['resolvers'], policy['client_resolver']]:
        for send in (dns.query.udp, dns.query.tcp):
            for name, kind, status, expected in cases:
                answer = send(dns.message.make_query(name, kind), address, timeout=3)
                if dns.rcode.to_text(answer.rcode()) != status:
                    raise ValueError('DNS validation status mismatch')
                records = [(rr.name.to_text().rstrip('.').lower(), dns.rdatatype.to_text(rr.rdtype), item.to_text())
                           for rr in answer.answer for item in rr]
                if expected is None:
                    if not any(record[1] == kind for record in records):
                        raise ValueError('Public DNS answer missing')
                elif records != [(name, kind, value) for value in expected]:
                    raise ValueError('DNS validation answer mismatch')
                time.sleep(0.12)


def verify(policy, previous):
    for attempt in range(4):
        try:
            verify_once(policy, previous)
            return
        except Exception:
            if attempt == 3: raise
            # Gateway can cache the prior answer/negative result briefly.
            time.sleep(10)


def cycle():
    current = json.loads((STATE / 'policy.json').read_text())
    apis = clients()
    if (STATE / 'pending.json').exists():
        # Recover a known generation before discovering anything new.
        converge(apis, current, current, STATE, verify)
        current = json.loads((STATE / 'policy.json').read_text())
    found = discover_lan()
    candidate, skipped = reconcile(current, found)
    accepted, changed = converge(apis, current, candidate, STATE, verify)
    prior_health = json.loads((STATE / 'health.json').read_text()) if (STATE / 'health.json').exists() else {}
    verified_at = prior_health.get('verified_at', 0)
    if changed or time.time() - verified_at > 900:
        if not changed:
            verify(accepted, current)
        verified_at = time.time()
    atomic_json(STATE / 'health.json', {'ok': True, 'last_success': time.time(),
                                      'verified_at': verified_at,
                                      'records': len(accepted['records']), 'visible_hosts': len(found),
                                      'skipped_hosts': len(skipped), 'changed': changed})
    print(json.dumps({'ok': True, 'records': len(accepted['records']), 'changed': changed}), flush=True)


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'health':
        health = json.loads((STATE / 'health.json').read_text())
        raise SystemExit(0 if health['ok'] and time.time() - health['last_success'] < 600 else 1)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'worker.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            started = time.monotonic()
            try:
                cycle()
            except Exception as error:
                # Avoid response bodies, tokens, service metadata and hostnames in logs.
                atomic_json(STATE / 'health.json', {'ok': False, 'failed_at': time.time(),
                                                  'error_type': type(error).__name__})
                print(json.dumps({'ok': False, 'error_type': type(error).__name__}), flush=True)
            time.sleep(max(5, 60 - (time.monotonic() - started)))


if __name__ == '__main__': main()
