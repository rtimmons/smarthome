"""Delegate only the AD zone without restarting either household resolver."""
import copy
import fcntl
import json
import time

from discovery import rules
from reconciler import atomic_json, converge


def candidate_policy(previous):
    if previous['user_rules'] != rules(previous['records'], previous.get('delegated_zones')):
        raise ValueError('Unreviewed custom rules; refusing delegation')
    candidate = copy.deepcopy(previous)
    candidate['delegated_zones'] = {'ad.home.arpa': '192.168.1.10'}
    upstream = '[/ad.home.arpa/]192.168.1.10'
    if upstream not in candidate['upstream_dns']:
        candidate['upstream_dns'].append(upstream)
    for name in ('auth.apps.home.arpa', 'auth.home.arpa'):
        if name in candidate.get('mdns_records', {}) or candidate['records'].get(name, '192.168.1.163') != '192.168.1.163':
            raise ValueError('Sign-in alias conflicts with an existing DNS owner')
        candidate['records'][name] = '192.168.1.163'
    candidate['user_rules'] = rules(candidate['records'], candidate['delegated_zones'])
    if candidate['fallback_dns']:
        raise ValueError('Public DNS fallback is incompatible with the private AD zone')
    return candidate


def main():
    from automatic import STATE, clients, verify
    with (STATE/'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = STATE/'delegation-pending.json'
        if journal.exists():
            raise RuntimeError('Recover the pending DNS transaction before retrying delegation')
        previous = json.loads((STATE/'policy.json').read_text())
        apis = clients()
        if (STATE/'pending.json').exists():
            # Stopping discovery can interrupt its known paired update. Finish
            # that journal with its existing drift guards before adding AD.
            converge(apis, previous, previous, STATE, verify)
            previous = json.loads((STATE/'policy.json').read_text())
        candidate = candidate_policy(previous)
        before = [api.api('dns_info') for api in apis]
        for info in before:
            if info['upstream_dns'] != previous['upstream_dns'] or info['fallback_dns']:
                raise ValueError('Unreviewed upstream DNS drift')
        atomic_json(STATE/('delegation-before-'+str(time.time_ns())+'.json'),
                    {'policy': previous, 'dns_info': before})
        atomic_json(journal, {'previous': previous, 'candidate': candidate, 'dns_info': before})
        try:
            for api in apis:
                api.api('dns_config', {'upstream_dns': candidate['upstream_dns']})
                if api.api('dns_info')['upstream_dns'] != candidate['upstream_dns']:
                    raise RuntimeError('Upstream readback differs')
            # Forwarding is in place before the NXDOMAIN exception is introduced.
            converge(apis, previous, candidate, STATE, verify)
        except Exception:
            restored = not (STATE/'pending.json').exists()
            for api, old in zip(apis, before):
                try:
                    # Never remove private forwarding while its exception is
                    # still active: that could send AD queries to public DNS.
                    if api.api('filtering/status').get('user_rules', []) != previous['user_rules']:
                        restored = False
                        continue
                    current = api.api('dns_info')['upstream_dns']
                    if current not in (old['upstream_dns'], candidate['upstream_dns']):
                        restored = False
                        continue
                    api.api('dns_config', {'upstream_dns': old['upstream_dns']})
                    api.api('cache_clear', {})
                    if api.api('dns_info')['upstream_dns'] != old['upstream_dns']:
                        restored = False
                except Exception:
                    restored = False
            if restored:
                journal.unlink()
            raise
        journal.unlink()
        print('AD delegation verified through both resolvers and gateway; public upstreams retained.')


if __name__ == '__main__': main()
