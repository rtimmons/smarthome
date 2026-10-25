import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import credentials


class CredentialRecovery(unittest.TestCase):
    def bundle(self, name='tree/example/key'):
        data = b'synthetic-existing-key\n'
        return {'schema': 1, 'entries': {name: {'content': base64.b64encode(data).decode(),
                'sha256': hashlib.sha256(data).hexdigest()}}}

    def test_restore_exact_bytes_private_modes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp).resolve()/'restore'
            self.assertEqual(credentials.restore(self.bundle(), destination), 1)
            path = destination/'tree/example/key'
            self.assertEqual(path.read_bytes(), b'synthetic-existing-key\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(ValueError):
                credentials.restore(self.bundle(), destination)

    def test_bad_paths_and_checksums_install_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp).resolve()/'restore'
            for name in ('/tmp/key', 'tree/../key', 'tree//key', 'pki/../../key', 'other/key'):
                with self.assertRaises(ValueError):
                    credentials.restore(self.bundle(name), destination)
                self.assertFalse(destination.exists())
            document = self.bundle()
            document['entries']['tree/example/key']['sha256'] = '0'*64
            with self.assertRaises(ValueError):
                credentials.restore(document, destination)
            self.assertFalse(destination.exists())

    def test_real_sops_round_trip_tamper_and_wrong_key(self):
        # Actual pinned executable; no live credentials are consumed by this test.
        with tempfile.TemporaryDirectory() as temp:
            import subprocess
            age = Path.home()/'.cache/smarthome/crypto/age-1.3.2/darwin-arm64/age-keygen'
            if not age.is_file():
                self.skipTest('Pinned age-keygen cache unavailable')
            key = Path(temp)/'key'
            subprocess.run([str(age), '-o', str(key)], check=True, capture_output=True)
            recipient = subprocess.check_output([str(age), '-y', str(key)]).decode().strip()
            config = Path(temp)/'.sops.yaml'
            config.write_text('creation_rules:\n  - age: '+recipient+'\n')
            from unittest.mock import patch
            with patch.object(credentials, 'CONFIG', config):
                cipher = credentials.crypt(json.dumps({'payload': json.dumps(self.bundle())}).encode(), key, True)
            self.assertEqual(credentials.decrypt(cipher, key), self.bundle())
            wrong = Path(temp)/'wrong'
            subprocess.run([str(age), '-o', str(wrong)], check=True, capture_output=True)
            with self.assertRaises(ValueError):
                credentials.decrypt(cipher, wrong)
            document = json.loads(cipher)
            document['payload'] = document['payload'].replace('data:', 'data:A', 1)
            with self.assertRaises(ValueError):
                credentials.decrypt(json.dumps(document).encode(), key)
