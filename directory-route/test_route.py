import importlib.util
from pathlib import Path
import sys
import types
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Plan and refusal tests need no live network or crypto dependency.
sys.modules.setdefault('paramiko', types.ModuleType('paramiko'))
spec = importlib.util.spec_from_file_location('directory_route', Path(__file__).with_name('route.py'))
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class RouteTests(unittest.TestCase):
    def test_production_readiness_requires_routed_ldaps(self):
        with tempfile.TemporaryDirectory() as directory:
            options = Path(directory)/'options.json'
            state = Path(directory)/'route-owner.json'
            options.write_text(json.dumps({'address': '192.168.1.10'}))
            state.write_text(json.dumps({'address': '192.168.1.10', 'backend': '172.30.33.14'}))
            with patch.object(route, 'STATE', state), patch.object(route.socket, 'create_connection', return_value=MagicMock()) as connect:
                route.check_health(options)
                connect.assert_called_once_with(('192.168.1.10', 636), timeout=2)
            with patch.object(route, 'STATE', state), patch.object(route.socket, 'create_connection', side_effect=OSError):
                with self.assertRaises(OSError):
                    route.check_health(options)
            state.write_text(json.dumps({'address': '192.168.1.11', 'backend': '172.30.33.14'}))
            with patch.object(route, 'STATE', state), patch.object(route.socket, 'create_connection') as connect:
                with self.assertRaises(RuntimeError):
                    route.check_health(options)
                connect.assert_not_called()

    def test_address_scope_cannot_expand(self):
        for value in ('0.0.0.0/0', '192.168.1.163', '192.168.1.66', '192.168.1.1', '127.0.0.1'):
            with self.assertRaises(ValueError):
                route.approved_address(value)
        self.assertEqual(route.approved_address('192.168.1.10'), '192.168.1.10')

    def test_backend_must_be_supervisor_app(self):
        for value in ('192.168.1.10', '127.0.0.1', '172.30.32.1', '172.30.32.2', '172.30.32.3'):
            with self.assertRaises(ValueError):
                route.approved_backend(value)
        self.assertEqual(route.approved_backend('172.30.33.100'), '172.30.33.100')

    def test_only_ad_ports_and_responses_are_allowed(self):
        rules = route.rules('192.168.1.10')
        self.assertEqual(rules[-1], ['-j', 'DROP'])
        for rule in rules[:-1]:
            self.assertIn('192.168.1.10/32', rule)
            if '--dport' in rule:
                ports = [rule[rule.index('--dport')+1]]
                self.assertNotIn('22', ports)
                self.assertNotIn('8123', ports)
                self.assertIn('-s', rule)
            else:
                self.assertIn('ESTABLISHED,RELATED', rule)
        for jump in route.jumps('192.168.1.10'):
            self.assertIn('192.168.1.10/32', jump)
            self.assertIn(route.COMMENT, jump)

    def test_ambiguous_firewall_is_refused(self):
        with patch.object(route, 'command', return_value=types.SimpleNamespace(returncode=0, stdout='-N DOCKER')):
            with self.assertRaisesRegex(RuntimeError, 'single active'):
                route.firewall_tool()


if __name__ == '__main__':
    unittest.main()
