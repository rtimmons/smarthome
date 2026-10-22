from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('peer_check', Path(__file__).parents[1] / 'scripts/vpn-peer-check.py')
peer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(peer)
WAN = '8.8.4.4'


class VpnPeerCheckTests(unittest.TestCase):
    def test_rejects_non_public_and_non_canonical_peer_inputs(self):
        self.assertEqual(peer.peer_address(WAN), WAN)
        for address in ('192.168.1.1', '127.0.0.1', '100.64.0.1', '203.0.113.1',
                        '8.8.4.4/32', '8.8.4.04', '::1', '8.8.4.4; false'):
            with self.subTest(address=address), self.assertRaises(peer.CheckError):
                peer.peer_address(address)

    def test_private_input_check_reports_drift_without_replacing_other_admin_sources(self):
        inventory = {'all': {'children': {'cloud': {'hosts': {'cloud': {
            'cloud_vpn_peer_ip': WAN, 'cloud_ssh_allowed_cidrs': [WAN + '/32', '1.1.1.1/32']}}}}}}
        variables = 'vpn_peer_ipv4 = "8.8.4.4"\nadmin_ssh_cidrs = ["8.8.4.4/32", "1.1.1.1/32"]\n'
        original = json.dumps(inventory)
        self.assertTrue(all(peer.local_checks(WAN, inventory, variables).values()))
        checks = peer.local_checks('8.8.8.8', inventory, variables)
        self.assertFalse(any(checks.values()))
        self.assertEqual(json.dumps(inventory), original)

    def test_ambiguous_or_executable_terraform_literals_are_rejected(self):
        for text in ('vpn_peer_ipv4 = var.address', 'vpn_peer_ipv4 = "8.8.4.4"\nvpn_peer_ipv4 = "1.1.1.1"',
                     'vpn_peer_ipv4 = "8.8.4.4"; execute()'):
            with self.subTest(text=text), self.assertRaises(peer.CheckError):
                peer.hcl_literal(text, 'vpn_peer_ipv4')

    def firewall(self):
        return {'rules': [{'direction': 'in', 'protocol': protocol, 'port': port,
                           'source_ips': [WAN + '/32']} for port, protocol in
                          [('22', 'tcp'), ('500', 'udp'), ('4500', 'udp')]]}

    def test_exact_ike_rules_cannot_hide_an_old_or_unrestricted_source(self):
        firewall = self.firewall()
        self.assertTrue(all(peer.provider_checks(WAN, firewall).values()))
        for source in ('1.1.1.1/32', '0.0.0.0/0'):
            firewall = self.firewall()
            firewall['rules'][1]['source_ips'].append(source)
            self.assertFalse(peer.provider_checks(WAN, firewall)['hetzner_udp_500_source_exact'])

    def test_competing_all_port_or_range_rule_is_detected(self):
        for ports in ('1-65535', '499-501', 'any', None):
            firewall = self.firewall()
            firewall['rules'].append({'direction': 'in', 'protocol': 'udp', 'port': ports,
                                      'source_ips': ['0.0.0.0/0']})
            self.assertFalse(peer.provider_checks(WAN, firewall)['hetzner_no_competing_500_rule'])

    def test_narrow_ssh_rule_cannot_hide_a_world_open_source(self):
        firewall = self.firewall()
        firewall['rules'][0]['source_ips'].append('0.0.0.0/0')
        self.assertFalse(peer.provider_checks(WAN, firewall)['hetzner_ssh_not_unrestricted'])

    def test_remote_failure_does_not_disclose_ssh_output(self):
        failed = subprocess.CompletedProcess([], 255, 'PRIVATE REPLY', 'PRIVATE STDERR')
        with mock.patch.object(peer.subprocess, 'run', return_value=failed) as run:
            with self.assertRaises(peer.CheckError) as error:
                peer.cloud(WAN)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(run.call_args.args[0], [str(peer.INFRA / 'scripts/cloud-command'), 'python3', '-', WAN])
        self.assertEqual(run.call_args.kwargs['input'], peer.REMOTE)


if __name__ == '__main__':
    unittest.main()
