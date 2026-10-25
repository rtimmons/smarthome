"""Explicit manual aliases without replacing the scanner's learned inventory.

Executed on the NAS with the existing scanner image, while its worker is stopped.
Only the exact requested records are changed; credentials stay in its private mount.
"""
import copy
import fcntl
import ipaddress
import json
import re
import sys
import time


def with_record(policy, name, address):
    from discovery import rules
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:(?:apps\.)?home\.arpa|home\.rytim\.com)', name):
        raise ValueError('Expected one explicit hostname beneath home.arpa, apps.home.arpa or home.rytim.com')
    ip = ipaddress.IPv4Address(address)
    lan = ipaddress.IPv4Network('192.168.1.0/24')
    if ip not in lan or ip in (lan.network_address, lan.broadcast_address):
        raise ValueError('Manual destination must be a Newark LAN address')
    if policy['user_rules'] != rules(policy['records'], policy.get('delegated_zones')):
        raise ValueError('Unexpected custom rules; reconcile before editing')
    if name in policy.get('mdns_records', {}):
        raise ValueError('Name is discovery-owned; choose an unused service alias')
    result = copy.deepcopy(policy)
    result['records'][name] = str(ip)
    result['user_rules'] = rules(result['records'], result.get('delegated_zones'))
    return result


def with_records(policy, names, address):
    if not names or len(set(names)) != len(names):
        raise ValueError('Expected distinct explicit aliases')
    candidate = policy
    for name in names:
        candidate = with_record(candidate, name, address)
    return candidate


def main():
    from automatic import STATE, clients, verify
    from reconciler import atomic_json, converge
    names, address = sys.argv[1:-1], sys.argv[-1]
    with (STATE / 'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = json.loads((STATE / 'policy.json').read_text())
        apis = clients()
        if (STATE / 'pending.json').exists():
            # Finish the scanner's known generation using its own drift guards
            # and DNS verification. Never discard a journal to permit a write.
            converge(apis, previous, previous, STATE, verify)
            previous = json.loads((STATE / 'policy.json').read_text())
        candidate = with_records(previous, names, address)
        atomic_json(STATE / ('manual-before-' + str(time.time_ns()) + '.json'), previous)
        accepted, changed = converge(apis, previous, candidate, STATE, verify)
        print(json.dumps({'ok': True, 'changed': changed, 'records': len(accepted['records'])}))


if __name__ == '__main__':
    main()
