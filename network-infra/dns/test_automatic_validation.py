"""Validate the owned DNS boundary without requiring public negative lookups."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from automatic import verification_cases
from discovery import owns_negative_name, rules
from reconciler import converge


class AutomaticValidationTests(unittest.TestCase):
    def policy(self):
        value = {'records': {'fixture.home.arpa': '192.168.1.90',
                             'fixture.home.rytim.com': '192.168.1.163'},
                 'delegated_zones': {'ad.home.arpa': '192.168.1.10'}}
        value['user_rules'] = rules(value['records'], value['delegated_zones'])
        return value

    def test_public_alias_keeps_exact_ipv4_and_empty_ipv6_without_claiming_subdomains(self):
        policy = self.policy()
        cases = verification_cases(policy, policy)
        self.assertIn(('fixture.home.rytim.com', 'A', 'NOERROR', ['192.168.1.163']), cases)
        self.assertIn(('fixture.home.rytim.com', 'AAAA', 'NOERROR', []), cases)
        self.assertNotIn('unknown.fixture.home.rytim.com', {case[0] for case in cases})
        self.assertIn(('unknown.fixture.home.arpa', 'A', 'NXDOMAIN', []), cases)
        self.assertIn(('home.arpa', 'SOA', 'NXDOMAIN', []), cases)
        self.assertIn(('unknown-autodns-check.home.arpa', 'A', 'NXDOMAIN', []), cases)
        self.assertIn(('example.com', 'A', 'NOERROR', None), cases)

    def test_delegation_keeps_explicit_dc_srv_and_negative_acceptance(self):
        policy = self.policy()
        cases = verification_cases(policy, policy)
        self.assertFalse(owns_negative_name(policy, 'ad.home.arpa'))
        self.assertFalse(owns_negative_name(policy, 'dc1.ad.home.arpa'))
        self.assertFalse(owns_negative_name(policy, 'not-home.arpa'))
        self.assertIn(('dc1.ad.home.arpa', 'A', 'NOERROR', ['192.168.1.10']), cases)
        self.assertIn(('_ldap._tcp.ad.home.arpa', 'SRV', 'NOERROR', ['0 100 389 dc1.ad.home.arpa.']), cases)
        self.assertIn(('_kerberos._tcp.ad.home.arpa', 'SRV', 'NOERROR', ['0 100 88 dc1.ad.home.arpa.']), cases)
        self.assertIn(('unknown-autodns-check.ad.home.arpa', 'A', 'NXDOMAIN', []), cases)

    def test_removed_local_names_remain_negative_but_public_namespace_is_not_owned(self):
        previous = self.policy()
        current = copy.deepcopy(previous)
        current['records'] = {}
        cases = verification_cases(current, previous)
        self.assertIn(('fixture.home.arpa', 'A', 'NXDOMAIN', []), cases)
        self.assertNotIn('fixture.home.rytim.com', {case[0] for case in cases})

    def test_pending_generation_recovers_without_public_descendant_lookup_or_journal_reset(self):
        previous = self.policy()
        candidate = copy.deepcopy(previous)
        candidate['records']['new-fixture.home.arpa'] = '192.168.1.91'
        candidate['user_rules'] = rules(candidate['records'], candidate['delegated_zones'])
        class Client:
            def __init__(self): self.rules = previous['user_rules'][:]
            def api(self, path, data=None):
                if path == 'filtering/status': return {'enabled': True, 'user_rules': self.rules[:]}
                if path == 'dns_info': return {'protection_enabled': True}
                if path == 'rewrite/list': return []
                if path == 'filtering/set_rules': self.rules = data['rules'][:]; return
                if path == 'cache_clear': return
                raise AssertionError(path)
        verified = []
        def verify(actual, old):
            cases = verification_cases(actual, old)
            # Simulates unavailable upstream for a name the local policy never owns.
            if any(name == 'unknown.fixture.home.rytim.com' for name, *_ in cases):
                raise TimeoutError('upstream-owned negative lookup')
            self.assertIn(('unknown.new-fixture.home.arpa', 'A', 'NXDOMAIN', []), cases)
            verified.append(actual)
        clients = [Client(), Client()]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pending.json').write_text(json.dumps({'previous': previous, 'candidate': candidate}))
            accepted, changed = converge(clients, previous, previous, root, verify)
            self.assertTrue(changed)
            self.assertEqual(verified, [candidate])
            self.assertEqual(accepted, candidate)
            self.assertEqual(json.loads((root / 'policy.json').read_text()), candidate)
            self.assertFalse((root / 'pending.json').exists())
            self.assertEqual([client.rules for client in clients], [candidate['user_rules']] * 2)


if __name__ == '__main__': unittest.main()
