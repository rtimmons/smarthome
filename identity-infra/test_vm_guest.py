"""The first guest connection must trust only the prepared host identity."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import vm_guest
from vm_prepare import keypair


class GuestTrust(unittest.TestCase):
    def test_pinned_host_identity_is_preserved_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            root = private/'vm'
            root.mkdir()
            keypair(root/'id_ed25519_dc_vm', 'synthetic-operator')
            host = keypair(root/'ssh_host_ed25519_key', 'synthetic-host')
            with patch.object(vm_guest, 'PRIVATE', private):
                command = vm_guest.connection('192.168.1.250')
                hosts = root/'known_hosts'
                self.assertIn(' '.join(host.split()[:2]), hosts.read_text())
                self.assertIn('StrictHostKeyChecking=yes', command)
                self.assertIn('IdentityAgent=none', command)
                original = hosts.read_bytes()
                vm_guest.connection('192.168.1.10')
                self.assertEqual(hosts.read_bytes(), original)
                hosts.write_text('unexpected-host-key\n')
                with self.assertRaisesRegex(RuntimeError, 'refusing replacement'):
                    vm_guest.connection('192.168.1.250')
                self.assertEqual(hosts.read_text(), 'unexpected-host-key\n')

    def test_non_lan_or_shell_host_inputs_are_refused_before_key_access(self):
        for host in ('203.0.113.5', '192.168.1.1', '192.168.1.255', '192.168.1.250;id'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                vm_guest.connection(host)


if __name__ == '__main__':
    unittest.main()
