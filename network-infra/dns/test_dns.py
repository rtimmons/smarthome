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

    def test_scanner_identity_requires_positive_pair_and_preserves_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime').mkdir()
            cases = [('', 0, 'false'), ('DNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_GID=100\n', 0, 'true'),
                     ('DNS_DISCOVERY_UID=1008\n', 1, ''), ('DNS_DISCOVERY_GID=100\n', 1, ''),
                     ('DNS_DISCOVERY_UID=0\nDNS_DISCOVERY_GID=100\n', 1, ''),
                     ('DNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_GID=0\n', 1, ''),
                     ('DNS_DISCOVERY_UID=\nDNS_DISCOVERY_GID=\n', 1, ''),
                     ('DNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_UID=1009\nDNS_DISCOVERY_GID=100\n', 1, ''),
                     ('  DNS_DISCOVERY_UID=1008\n', 1, ''),
                     ('export DNS_DISCOVERY_GID=100\n', 1, ''),
                     ('DNS_DISCOVERY_UID=$(false)\nDNS_DISCOVERY_GID=100\n', 1, '')]
            for values, expected, selected in cases:
                with self.subTest(values=values):
                    (root / 'runtime/.env').write_text('DNS_UID=1004\nDNS_GID=100\n' + values)
                    result = subprocess.run(['sh', '-c', 'set -eu; root="$1"; ' + m.DISCOVERY_IDENTITY +
                                             '\ndiscovery_identity; printf "%s" "$discovery_selected"', 'sh', str(root)],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected)
                    if expected == 0: self.assertEqual(result.stdout, selected)

    def test_selected_identity_deploy_preserves_credentials_and_learned_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, private, root = base / 'source', base / 'private', base / 'nas'
            source.mkdir(); private.mkdir()
            for name in ('automatic.py', 'discovery.py', 'reconciler.py', 'Dockerfile.automatic', 'automatic-compose.yaml'):
                (source / name).write_bytes((m.HERE / name).read_bytes())
            (source / 'policy.json').write_text(json.dumps(m.POLICY))
            (private / 'dns-automatic-credentials.json').write_text('{"synthetic": "incoming"}')
            for name in ('runtime/automatic', 'config/automatic', 'backups/automatic-state'):
                (root / name).mkdir(parents=True)
            (root / 'runtime/.env').write_text('DNS_UID=1004\nDNS_GID=100\nDNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_GID=100\n')
            credentials = root / 'config/automatic/credentials.json'
            policy = root / 'backups/automatic-state/policy.json'
            credentials.write_text('existing synthetic credential bytes')
            policy.write_text('existing learned policy')
            original = [(p.read_bytes(), p.stat().st_ino, p.stat().st_mode) for p in (credentials, policy)]
            docker = base / 'docker'
            docker.write_text('#!/bin/sh\nexit 0\n'); docker.chmod(0o700)
            def remote(script, payload=None, transcript=None):
                result = subprocess.run(['sh', '-c', 'set -eu; root="$1"; docker="$2"; ' + m.DISCOVERY_IDENTITY + script,
                                         'sh', str(root), str(docker)], input=payload, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
            with mock.patch.object(m, 'HERE', source), mock.patch.object(m, 'ROOT', base), mock.patch.object(m, 'PRIVATE', private), \
                 mock.patch.object(m, 'Primary'), mock.patch.object(m, 'remote', side_effect=remote), \
                 mock.patch.object(m, 'auto_status'), mock.patch('builtins.print'):
                m.auto_deploy()
            self.assertEqual(original, [(p.read_bytes(), p.stat().st_ino, p.stat().st_mode) for p in (credentials, policy)])
            self.assertEqual((root / 'runtime/.env').read_text(),
                             'DNS_UID=1004\nDNS_GID=100\nDNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_GID=100\n')

    def test_static_deploy_refuses_scanner_identity_without_rolling_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime').mkdir()
            (root / 'runtime/.env').write_text('DNS_DISCOVERY_UID=1008\nDNS_DISCOVERY_GID=100\n')
            private = root / 'private'
            private.mkdir()
            (private / 'dns-secondary-credentials.json').write_text('{"hash": "synthetic"}')
            static_policy = {key: value for key, value in m.POLICY.items() if key != 'automatic_discovery'}

            def remote(script, payload=None):
                return subprocess.run(['sh', '-c', 'set -eu; root="$1"; ' + m.DISCOVERY_IDENTITY + script,
                                       'sh', str(root)], input=payload, capture_output=True, check=True).stdout

            with mock.patch.object(m, 'POLICY', static_policy), mock.patch.object(m, 'PRIVATE', private), \
                 mock.patch.object(m, 'Primary') as primary, mock.patch.object(m, 'validate_primary'), \
                 mock.patch.object(m, 'remote', side_effect=remote) as run:
                primary.return_value.snapshot.return_value = {}
                with self.assertRaisesRegex(ValueError, 'static resolver deployment refused'):
                    m.deploy()
            run.assert_called_once()
            primary.return_value.api.assert_not_called()

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
        local_negatives = sum((name == 'home.arpa' or name.endswith('.home.arpa')) and not any(
            name == zone or name.endswith('.' + zone) for zone in m.POLICY.get('delegated_zones', {}))
            for name in m.POLICY['records'])
        self.assertEqual(run.call_count, 2 * (2 * len(m.POLICY['records']) + local_negatives + 3))
        queried = {(call.args[0][2], call.args[0][3]) for call in run.call_args_list}
        self.assertIn(('wiki.home.rytim.com', 'A'), queried)
        self.assertIn(('wiki.home.rytim.com', 'AAAA'), queried)
        self.assertNotIn(('unknown.wiki.home.rytim.com', 'A'), queried)
        self.assertIn(('unknown.wiki.home.arpa', 'A'), queried)
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
