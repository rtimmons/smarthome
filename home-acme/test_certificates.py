"""Protect the last working certificate when a renewal is invalid."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from run import publish, sanitized


def openssl(*args):
    subprocess.run(['openssl', *map(str, args)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


class CertificatePublicationTest(unittest.TestCase):
    def test_invalid_renewals_preserve_working_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('ca', 'leaf', 'wrong'):
                openssl('genpkey', '-algorithm', 'EC', '-pkeyopt',
                        'ec_paramgen_curve:P-256', '-out', root/(name+'.key'))
            openssl('req', '-x509', '-new', '-key', root/'ca.key', '-days', '3',
                    '-subj', '/CN=Synthetic test CA', '-out', root/'ca.crt',
                    '-addext', 'basicConstraints=critical,CA:TRUE',
                    '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
            openssl('req', '-new', '-key', root/'leaf.key', '-subj',
                    '/CN=Synthetic service', '-out', root/'leaf.csr')
            extension = root/'extensions'
            extension.write_text('basicConstraints=critical,CA:FALSE\n'
                                 'extendedKeyUsage=serverAuth\n'
                                 'subjectAltName=DNS:*.home.rytim.com\n')
            openssl('x509', '-req', '-in', root/'leaf.csr', '-CA', root/'ca.crt',
                    '-CAkey', root/'ca.key', '-set_serial', '2', '-days', '3',
                    '-extfile', extension, '-out', root/'leaf.crt')
            destination = root/'published'
            expected = publish(root/'leaf.crt', root/'leaf.key', destination, root/'ca.crt')
            with self.assertRaises(ValueError):
                publish(root/'leaf.crt', root/'wrong.key', destination, root/'ca.crt')
            self.assertEqual((destination/'current').readlink().name, expected)
            self.assertEqual((destination/'current/key.pem').read_bytes(), (root/'leaf.key').read_bytes())
            # A certificate valid for an unrelated name cannot replace this one.
            extension.write_text('subjectAltName=DNS:unrelated.example\n')
            openssl('x509', '-req', '-in', root/'leaf.csr', '-CA', root/'ca.crt',
                    '-CAkey', root/'ca.key', '-set_serial', '3', '-days', '3',
                    '-extfile', extension, '-out', root/'unrelated.crt')
            with self.assertRaises(subprocess.CalledProcessError):
                publish(root/'unrelated.crt', root/'leaf.key', destination, root/'ca.crt')
            self.assertEqual((destination/'current').readlink().name, expected)
            # Idempotent publication does not rotate an existing key or version.
            self.assertEqual(publish(root/'leaf.crt', root/'leaf.key', destination, root/'ca.crt'), expected)

    def test_provider_error_log_redacts_credentials(self):
        secret = 'synthetic-test-token'
        result = sanitized('GET https://api.dreamhost.com/?key='+secret+'&cmd=dns-list_records '+secret, secret)
        self.assertNotIn(secret, result)
        self.assertIn('cmd=dns-list_records', result)


if __name__ == '__main__':
    unittest.main()
