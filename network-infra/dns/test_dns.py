"""Policy and rollback boundaries; no household network required."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('dns_manager', Path(__file__).with_name('manage.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class DNSTests(unittest.TestCase):
    def test_independent_upstreams_and_unprivileged_dns(self):
        config = m.secondary_config('synthetic-hash')
        self.assertEqual(config['dns']['port'], 1053)
        self.assertFalse(config['dhcp']['enabled'])
        self.assertFalse(config['querylog']['enabled'])
        self.assertTrue(all(ip not in ' '.join(config['dns']['upstream_dns']) for ip in m.POLICY['resolvers']))
        compose = (m.HERE / 'compose.yaml').read_text()
        for binding in ['192.168.1.66:53:1053/udp','192.168.1.66:53:1053/tcp','127.0.0.1:3001:3000/tcp']:
            self.assertIn(binding, compose)
        self.assertNotIn('network_mode: host', compose)

    def test_policy_drift_is_not_silently_overwritten(self):
        with self.assertRaises(ValueError):
            m.validate_primary({'dns_info': {'upstream_dns':['192.168.1.66']}})

    def test_only_exact_wiki_name_exempts_local_negative_rule(self):
        self.assertIn('||home.arpa^$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertIn('@@|wiki.home.arpa|$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertNotIn('denyallow', '\n'.join(m.POLICY['user_rules']))

if __name__ == '__main__':unittest.main()
