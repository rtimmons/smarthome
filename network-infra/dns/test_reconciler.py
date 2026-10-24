"""Synthetic failure/crash cases for unattended paired updates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from reconciler import atomic_json, converge


class Client:
    def __init__(self, rules):
        self.rules = rules[:]
        self.fail = False
        self.writes = 0
    def api(self, path, data=None):
        if path == 'filtering/status': return {'enabled': True, 'user_rules': self.rules}
        if path == 'dns_info': return {'protection_enabled': True}
        if path == 'rewrite/list': return []
        if path == 'cache_clear': return None
        if path == 'filtering/set_rules':
            self.writes += 1
            if self.fail: raise RuntimeError('synthetic outage')
            self.rules = data['rules'][:]
            return None
        raise AssertionError(path)


class ReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = {'records': {'fixture.home.arpa': '192.168.1.80'}, 'user_rules': ['old']}
        self.new = {'records': {'fixture.home.arpa': '192.168.1.81'}, 'user_rules': ['new']}
        self.clients = [Client(['old']), Client(['old'])]
        atomic_json(self.root / 'policy.json', self.old)

    def test_updates_both_without_restarts_and_accepts_only_after_verification(self):
        def verify(*args):
            self.assertEqual([c.rules for c in self.clients], [['new'], ['new']])
            self.assertEqual(json.loads((self.root / 'policy.json').read_text()), self.old)
        _, changed = converge(self.clients, self.old, self.new, self.root, verify)
        self.assertTrue(changed)
        self.assertEqual(json.loads((self.root / 'policy.json').read_text()), self.new)
        self.assertFalse((self.root / 'pending.json').exists())

    def test_second_backend_outage_rolls_back_first(self):
        self.clients[1].fail = True
        with self.assertRaises(RuntimeError):
            converge(self.clients, self.old, self.new, self.root, Mock())
        self.assertEqual([c.rules for c in self.clients], [['old'], ['old']])
        self.assertEqual(json.loads((self.root / 'policy.json').read_text()), self.old)

    def test_bad_dns_answers_roll_back_both(self):
        with self.assertRaises(ValueError):
            converge(self.clients, self.old, self.new, self.root, Mock(side_effect=ValueError()))
        self.assertEqual([c.rules for c in self.clients], [['old'], ['old']])

    def test_crash_between_backends_recovers_known_pending_generation(self):
        self.clients[0].rules = ['new']
        atomic_json(self.root / 'pending.json', {'previous': self.old, 'candidate': self.new})
        accepted, changed = converge(self.clients, self.old, self.old, self.root, Mock())
        self.assertEqual(accepted, self.new)
        self.assertEqual([c.rules for c in self.clients], [['new'], ['new']])

    def test_foreign_rules_pause_without_writes(self):
        self.clients[1].rules = ['manual']
        with self.assertRaises(ValueError):
            converge(self.clients, self.old, self.new, self.root, Mock())
        self.assertEqual([c.writes for c in self.clients], [0, 0])

    def test_unchanged_discovery_does_not_touch_resolvers(self):
        _, changed = converge(self.clients, self.old, self.old, self.root, Mock())
        self.assertFalse(changed)
        self.assertEqual([c.writes for c in self.clients], [0, 0])

    def test_manual_edit_during_failure_is_preserved_with_pending_recovery(self):
        def verify(*args):
            self.clients[0].rules = ['manual']
            raise ValueError('synthetic validation failure')
        with self.assertRaises(ValueError):
            converge(self.clients, self.old, self.new, self.root, verify)
        self.assertEqual(self.clients[0].rules, ['manual'])
        self.assertTrue((self.root / 'pending.json').exists())
