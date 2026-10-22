"""Policy and rollback boundaries; no household network required."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import subprocess

spec = importlib.util.spec_from_file_location('dns_manager', Path(__file__).with_name('manage.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class DNSTests(unittest.TestCase):
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
            status = 'NXDOMAIN' if name not in ('wiki.home.arpa', 'example.com') else 'NOERROR'
            record = ''
            if name == 'wiki.home.arpa' and kind == 'A': record = 'wiki.home.arpa. 60 IN A 192.168.1.66\n'
            if name == 'example.com': record = 'example.com. 60 IN A 93.184.215.14\n'
            return subprocess.CompletedProcess(argv, 0, self.answer(status, record), '')
        with mock.patch.object(m.subprocess, 'run', side_effect=dig) as run, mock.patch('builtins.print'):
            m.check(['192.168.1.1'])
        self.assertEqual(run.call_count, 12)
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

    def test_only_exact_wiki_name_exempts_local_negative_rule(self):
        self.assertIn('||home.arpa^$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertIn('@@|wiki.home.arpa|$dnsrewrite=NXDOMAIN;;', m.POLICY['user_rules'])
        self.assertNotIn('denyallow', '\n'.join(m.POLICY['user_rules']))

if __name__ == '__main__':unittest.main()
