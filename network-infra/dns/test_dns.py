"""Policy and rollback boundaries; no household network required."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import subprocess
import tempfile
import json
import types

spec = importlib.util.spec_from_file_location('dns_manager', Path(__file__).with_name('manage.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class DNSTests(unittest.TestCase):
    def test_failed_discovery_deployment_does_not_publish_candidate_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = {key: value for key, value in m.POLICY.items() if key != 'automatic_discovery'}
            original = json.dumps(seed)
            (root / 'policy.json').write_text(original)
            candidate = {**m.POLICY, 'records': {**m.POLICY['records'], 'fixture.home.arpa': '192.168.1.90'},
                         'user_rules': m.POLICY['user_rules'] + ['synthetic-rule']}
            discovery = types.SimpleNamespace(discover=lambda: {}, reconcile=lambda *args: (candidate, {}))
            with mock.patch.dict('sys.modules', {'discovery': discovery}), \
                 mock.patch.object(m, 'HERE', root), mock.patch.object(m, 'PRIVATE', root / 'private'), \
                 mock.patch.object(m, 'POLICY', seed), \
                 mock.patch.object(m, 'deploy', side_effect=RuntimeError('synthetic failure')), \
                 mock.patch('builtins.print'), self.assertRaises(RuntimeError):
                m.sync_mdns(True)
            self.assertEqual((root / 'policy.json').read_text(), original)

    def test_manual_apply_cannot_compete_with_automatic_owner(self):
        with mock.patch.object(m, 'POLICY', {**m.POLICY, 'automatic_discovery': {'host': 'NAS'}}):
            with self.assertRaises(ValueError): m.sync_mdns(True)
            with self.assertRaises(ValueError): m.deploy()

    def answer(self, status, records=''):
        return ';; ->>HEADER<<- opcode: QUERY, status: ' + status + ', id: 1\n' + records

    def test_wiki_address_must_be_the_exact_answer_not_a_comment_or_other_owner(self):
        expected = {'status': 'NOERROR', 'address': '192.168.1.66'}
        m.validate_answer(self.answer('NOERROR', 'wiki.home.arpa. 60 IN A 192.168.1.66\n'),
                          'wiki.home.arpa', 'A', expected)
        for records in (';; SERVER: 192.168.1.66\n', 'other.home.arpa. 60 IN A 192.168.1.66\n',
                        'wiki.home.arpa. 60 IN A 192.168.1.67\n',
                        'wiki.home.arpa. 60 IN A 192.168.1.66\nwiki.home.arpa. 60 IN A 192.168.1.67\n'):
            with self.subTest(records=records), self.assertRaises(ValueError):
                m.validate_answer(self.answer('NOERROR', records), 'wiki.home.arpa', 'A', expected)

    def test_status_and_empty_answers_are_both_required(self):
        expected = {'status': 'NXDOMAIN', 'empty': True}
        m.validate_answer(self.answer('NXDOMAIN'), 'unknown.home.arpa', 'A', expected)
        for output in (self.answer('SERVFAIL') + ';; status: NXDOMAIN\n',
                       self.answer('NOERROR'),
                       self.answer('NXDOMAIN', 'unknown.home.arpa. 60 IN A 192.168.1.66\n')):
            with self.subTest(output=output), self.assertRaises(ValueError):
                m.validate_answer(output, 'unknown.home.arpa', 'A', expected)
        with self.assertRaises(ValueError):
            m.validate_answer(self.answer('NOERROR', 'wiki.home.arpa. 60 IN AAAA ::1\n'),
                              'wiki.home.arpa', 'AAAA', {'status': 'NOERROR', 'empty': True})

    def test_explicit_gateway_checks_both_transports_without_accessing_adguard(self):
        def dig(argv, **kwargs):
            name, kind = argv[2:4]
            status = 'NOERROR' if name in m.POLICY['records'] or name == 'example.com' else 'NXDOMAIN'
            record = ''
            if name in m.POLICY['records'] and kind == 'A': record = f'{name}. 60 IN A {m.POLICY["records"][name]}\n'
            if name == 'example.com': record = 'example.com. 60 IN A 93.184.215.14\n'
            return subprocess.CompletedProcess(argv, 0, self.answer(status, record), '')
        with mock.patch.object(m.subprocess, 'run', side_effect=dig) as run, mock.patch('builtins.print'), \
             mock.patch.object(m.time, 'sleep'):
            m.check(['192.168.1.1'])
        self.assertEqual(run.call_count, 2 * (3 * len(m.POLICY['records']) + 3))
        self.assertEqual({call.args[0][1] for call in run.call_args_list}, {'@192.168.1.1'})
        self.assertEqual({call.args[0][4] for call in run.call_args_list}, {'+tcp', '+notcp'})

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

    def test_rule_migration_requires_exact_reviewed_previous_rules(self):
        old_rules = m.POLICY['user_rules'][:-2]
        snapshot = {
            'dns_info': {**{k: m.POLICY[k] for k in ('upstream_dns', 'bootstrap_dns', 'fallback_dns')},
                         'protection_enabled': True},
            'filtering/status': {'filters': m.POLICY['filters'], 'enabled': True, 'user_rules': old_rules},
            'rewrite/list': [], 'blocked_services/get': {'ids': []},
            **{p: {'enabled': False} for p in ('safebrowsing/status', 'parental/status', 'safesearch/status')},
        }
        with self.assertRaises(ValueError):
            m.validate_primary(snapshot)
        m.validate_primary(snapshot, {'user_rules': old_rules})
        snapshot['filtering/status']['user_rules'] = old_rules + ['||unexpected.example^']
        with self.assertRaises(ValueError):
            m.validate_primary(snapshot, {'user_rules': old_rules})

    def test_only_exact_wiki_name_exempts_local_negative_rule(self):
        self.assertIn('||home.arpa^$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertIn('@@|wiki.home.arpa|$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertNotIn('denyallow', '\n'.join(m.POLICY['user_rules']))

if __name__ == '__main__':unittest.main()
