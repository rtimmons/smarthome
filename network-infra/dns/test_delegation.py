import unittest

from delegation import candidate_policy
from discovery import reconcile, rules
from manual import with_record


class DelegationTests(unittest.TestCase):
    def policy(self):
        records = {'wiki.home.arpa': '192.168.1.66'}
        return {'records': records, 'user_rules': rules(records),
                'upstream_dns': ['https://dns10.quad9.net/dns-query'], 'fallback_dns': []}

    def test_only_ad_subtree_is_exempted(self):
        result = candidate_policy(self.policy())
        self.assertIn('||home.arpa^$dnsrewrite=NXDOMAIN;;', result['user_rules'])
        self.assertIn('@@||ad.home.arpa^$dnsrewrite=NXDOMAIN;;', result['user_rules'])
        self.assertNotIn('@@||home.arpa^$dnsrewrite=NXDOMAIN;;', result['user_rules'])
        self.assertEqual(result['upstream_dns'][-1], '[/ad.home.arpa/]192.168.1.10')
        self.assertEqual(candidate_policy(result), result)

    def test_discovery_and_manual_alias_preserve_ad(self):
        before = candidate_policy(self.policy())
        learned, _ = reconcile(before, {'fixture-host.local': ['192.168.1.100']}, now=1)
        after = with_record(learned, 'auth.home.arpa', '192.168.1.163')
        self.assertEqual(after['delegated_zones'], before['delegated_zones'])
        self.assertEqual(after['upstream_dns'], before['upstream_dns'])
        self.assertIn('@@||ad.home.arpa^$dnsrewrite=NXDOMAIN;;', after['user_rules'])

    def test_unknown_rules_and_public_fallback_refused(self):
        policy = self.policy()
        policy['user_rules'].append('@@||fixture.invalid^')
        with self.assertRaises(ValueError): candidate_policy(policy)
        policy = self.policy()
        policy['fallback_dns'] = ['1.1.1.1']
        with self.assertRaises(ValueError): candidate_policy(policy)
        with self.assertRaises(ValueError): rules({}, {'home.arpa': '192.168.1.10'})

    def test_public_certificate_name_stays_a_private_exact_record(self):
        before = candidate_policy(self.policy())
        after = with_record(before, 'auth.home.rytim.com', '192.168.1.163')
        self.assertIn('|auth.home.rytim.com|$dnsrewrite=NOERROR;A;192.168.1.163', after['user_rules'])
        learned, _ = reconcile(after, {'fixture-host.local': ['192.168.1.100']}, now=1)
        self.assertEqual(learned['records']['auth.home.rytim.com'], '192.168.1.163')
        self.assertEqual(learned['upstream_dns'], before['upstream_dns'])
        # ACME TXT/SOA queries continue to public authoritative DNS. Only the
        # approved web host's A/AAAA responses are overridden locally.
        self.assertFalse(any('||home.rytim.com^' in rule for rule in after['user_rules']))
        with self.assertRaises(ValueError): with_record(before, 'auth.rytim.com', '192.168.1.163')


if __name__ == '__main__': unittest.main()
