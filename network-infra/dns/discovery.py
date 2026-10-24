"""Bounded macOS Bonjour host discovery; never persist service TXT/display names."""
from concurrent.futures import ThreadPoolExecutor
import copy
import ipaddress
import re
import subprocess
import time

LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
HOST = re.compile(rf'^{LABEL}\.local\.?$', re.I)
LAN = ipaddress.ip_network('192.168.1.0/24')
GRACE = 7 * 86400


def browse(*args, seconds=6):
    process = subprocess.Popen(['dns-sd', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        process.terminate()
        out, err = process.communicate(timeout=5)
    else:
        if process.returncode:
            raise RuntimeError('Bonjour discovery unavailable; no records changed')
    return out.decode('utf-8', errors='replace')


def service_types(output):
    return sorted(set(re.findall(r'\b(_(?:tcp|udp))\.local\.\s+(_[A-Za-z0-9-]+)\s*$', output, re.M)))


def targets(output):
    return {host.lower().rstrip('.') for host in re.findall(r'\sSRV\s+\d+\s+\d+\s+\d+\s+(\S+)', output)
            if HOST.fullmatch(host)}


def addresses(output, host):
    # Track interface-specific removals, not just every address ever observed.
    live = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 7 or fields[1] not in ('Add', 'Rmv') or fields[4].lower().rstrip('.') != host:
            continue
        try:
            address = ipaddress.IPv4Address(fields[5])
        except ValueError:
            continue
        if address not in LAN or address in (LAN.network_address, LAN.broadcast_address):
            continue
        item = (fields[3], str(address))
        if fields[1] == 'Add': live.add(item)
        else: live.discard(item)
    return sorted({address for _, address in live})


def discover():
    types = service_types(browse('-B', '_services._dns-sd._udp', 'local.'))
    if not types:
        raise RuntimeError('No Bonjour service types found; refusing an empty reconciliation')
    with ThreadPoolExecutor(max_workers=8) as pool:
        zones = pool.map(lambda item: browse('-Z', item[1] + '.' + item[0], 'local.'), types)
        hosts = sorted(set().union(*(targets(zone) for zone in zones)))
        results = list(pool.map(lambda host: addresses(browse('-G', 'v4', host + '.'), host), hosts))
    found = dict(zip(hosts, results))
    if not any(found.values()):
        raise RuntimeError('No LAN host addresses found; refusing an empty reconciliation')
    return found


def rules(records, delegated_zones=None):
    result = ['! Repository-owned home.arpa zone. Keep unknown names local.',
              '||home.arpa^$dnsrewrite=NXDOMAIN;;']
    for zone, address in (delegated_zones or {}).items():
        if zone != 'ad.home.arpa' or address != '192.168.1.10':
            raise ValueError('Unreviewed delegated DNS zone or destination')
        result.append(f'@@||{zone}^$dnsrewrite=NXDOMAIN;;')
    for name, address in records.items():
        result.extend([f'@@|{name}|$dnsrewrite=NXDOMAIN;;', f'|{name}|$dnsrewrite=NOERROR;A;{address}'])
    return result


def reconcile(policy, found, now=None):
    if policy['user_rules'] != rules(policy['records'], policy.get('delegated_zones')):
        raise ValueError('Policy has custom rules beyond exact records; review before importing Bonjour names')
    now = time.time() if now is None else now
    result = copy.deepcopy(policy)
    owned = result.setdefault('mdns_records', {})
    records = result['records']
    skipped = {}
    for host, ips in found.items():
        if not HOST.fullmatch(host):
            skipped[host] = 'invalid hostname'
            continue
        name = host.lower().removesuffix('.').removesuffix('.local') + '.home.arpa'
        if name in records and name not in owned:
            skipped[host] = 'protected manual record'
            continue
        if len(ips) > 1:
            skipped[host] = 'multiple LAN addresses'
            # Do not leave a previously learned answer pointing at an ambiguous host.
            if name in owned:
                records.pop(name, None)
                owned.pop(name)
            continue
        if not ips:
            continue
        address = ipaddress.IPv4Address(ips[0])
        if address not in LAN or address in (LAN.network_address, LAN.broadcast_address):
            raise ValueError('Discovered address is outside the allowed LAN')
        records[name] = str(address)
        owned[name] = {'source': host, 'last_seen': now}
    for name, metadata in list(owned.items()):
        if now - metadata['last_seen'] > GRACE:
            records.pop(name, None)
            del owned[name]
    result['user_rules'] = rules(records, result.get('delegated_zones'))
    return result, skipped
