"""Synthetic Bonjour parsing and reconciliation boundaries."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('discovery', Path(__file__).with_name('discovery.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DiscoveryTests(unittest.TestCase):
    def policy(self):
        records = {'wiki.home.arpa': '192.168.1.66', 'hass.home.arpa': '192.168.1.163'}
        return {'records': records, 'user_rules': d.rules(records)}

    def test_use_host_not_display_name_and_deduplicate(self):
        output = 'Synthetic\\032Device._http._tcp SRV 0 0 80 Fixture-Host.local. ; comment\n'
        self.assertEqual(d.targets(output * 2), {'fixture-host.local'})
        self.assertEqual(d.targets('display SRV 0 0 80 external.example.\n'), set())
        self.assertEqual(d.service_types('12:00 Add 3 14 . _tcp.local. _http\n'), [('_tcp', '_http')])

    def test_address_removal_and_interface_duplicates(self):
        output = ('12:00 Add 3 14 fixture.local. 192.168.1.90 120\n'
                  '12:00 Add 3 27 fixture.local. 192.168.1.90 120\n'
                  '12:00 Rmv 3 14 fixture.local. 192.168.1.90 0\n'
                  '12:00 Add 3 14 fixture.local. 10.1.1.3 120\n')
        self.assertEqual(d.addresses(output, 'fixture.local'), ['192.168.1.90'])
        self.assertEqual(d.addresses(output + '12:00 Rmv 3 27 fixture.local. 192.168.1.90 0\n', 'fixture.local'), [])

    def test_protect_manual_names_update_learned_and_expire_only_learned(self):
        original = self.policy()
        result, skipped = d.reconcile(original, {'wiki.local': ['192.168.1.90'],
                                               'fixture.local': ['192.168.1.91']}, now=100)
        self.assertEqual(result['records']['wiki.home.arpa'], '192.168.1.66')
        self.assertIn('wiki.local', skipped)
        self.assertNotIn('fixture.home.arpa', original['records'])
        result, _ = d.reconcile(result, {'fixture.local': ['192.168.1.92']}, now=200)
        self.assertEqual(result['records']['fixture.home.arpa'], '192.168.1.92')
        result, _ = d.reconcile(result, {}, now=201)
        self.assertIn('fixture.home.arpa', result['records'])
        result, _ = d.reconcile(result, {}, now=201 + d.GRACE)
        self.assertEqual(result['records'], original['records'])

    def test_ambiguity_withdraws_learned_answer_and_bad_addresses_fail(self):
        learned, _ = d.reconcile(self.policy(), {'fixture.local': ['192.168.1.90']}, now=100)
        result, skipped = d.reconcile(learned, {'fixture.local': ['192.168.1.90', '192.168.1.91']}, now=101)
        self.assertNotIn('fixture.home.arpa', result['records'])
        self.assertIn('fixture.local', skipped)
        for address in ('8.8.8.8', '192.168.1.255', '192.168.1.0', '::1'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                d.reconcile(self.policy(), {'fixture.local': [address]})

    def test_empty_discovery_fails_closed(self):
        with patch.object(d, 'browse', return_value=''), self.assertRaises(RuntimeError):
            d.discover()

    def test_custom_policy_rules_are_not_discarded(self):
        policy = self.policy()
        policy['user_rules'].append('||synthetic.example^')
        with self.assertRaises(ValueError):
            d.reconcile(policy, {'fixture.local': ['192.168.1.90']})


if __name__ == '__main__':
    unittest.main()
