"""Manual aliases retain runtime discovery ownership and local containment."""
import unittest
from discovery import reconcile, rules, GRACE
from manual import with_record


class ManualTests(unittest.TestCase):
    def setUp(self):
        records = {'wiki.home.arpa': '192.168.1.66'}
        self.policy, _ = reconcile({'records': records, 'user_rules': rules(records)},
                                   {'fixture.local': ['192.168.1.90']}, now=100)

    def test_manual_edit_preserves_learned_state_and_survives_discovery(self):
        result = with_record(self.policy, 'service.home.arpa', '192.168.1.163')
        self.assertEqual(result['mdns_records'], self.policy['mdns_records'])
        self.assertEqual(result['records']['fixture.home.arpa'], '192.168.1.90')
        self.assertNotIn('service.home.arpa', self.policy['records'])
        later, _ = reconcile(result, {'service.local': ['192.168.1.99']}, now=101 + GRACE)
        self.assertEqual(later['records']['service.home.arpa'], '192.168.1.163')
        self.assertNotIn('fixture.home.arpa', later['records'])

    def test_refuses_discovery_collision_invalid_names_and_addresses(self):
        for name, address in [('fixture.home.arpa', '192.168.1.163'),
                              ('nested.service.home.arpa', '192.168.1.163'),
                              ('*.home.arpa', '192.168.1.163'),
                              ('service.home.arpa', '8.8.8.8'),
                              ('service.home.arpa', '192.168.1.255')]:
            with self.subTest(name=name, address=address), self.assertRaises(ValueError):
                with_record(self.policy, name, address)

    def test_refuses_unreviewed_custom_rules(self):
        self.policy['user_rules'].append('||fixture.example^')
        with self.assertRaises(ValueError):
            with_record(self.policy, 'service.home.arpa', '192.168.1.163')

    def test_pending_generation_is_verified_before_manual_alias(self):
        import copy
        import json
        from pathlib import Path
        import sys
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from manual import main
        from reconciler import atomic_json
        from test_reconciler import Client
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            pending = with_record(self.policy, 'prior-service.home.arpa', '192.168.1.91')
            apis = [Client(pending['user_rules']), Client(self.policy['user_rules'])]
            atomic_json(state / 'policy.json', self.policy)
            atomic_json(state / 'pending.json', {'previous': self.policy, 'candidate': pending})
            verified = []
            fake = SimpleNamespace(STATE=state, clients=lambda: apis,
                                   verify=lambda candidate, previous: verified.append(copy.deepcopy(candidate)))
            with patch.dict(sys.modules, {'automatic': fake}), patch.object(sys, 'argv',
                    ['manual.py', 'service.home.arpa', '192.168.1.163']):
                main()
            accepted = json.loads((state / 'policy.json').read_text())
            self.assertEqual(len(verified), 2)
            self.assertNotIn('service.home.arpa', verified[0]['records'])
            self.assertEqual(accepted['records']['prior-service.home.arpa'], '192.168.1.91')
            self.assertEqual(accepted['records']['service.home.arpa'], '192.168.1.163')
            self.assertEqual(accepted['mdns_records'], self.policy['mdns_records'])
            self.assertFalse((state / 'pending.json').exists())
