import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import credentials
import wiki_credentials as wiki
from check_wiki_access import Budget


class WikiCredentialTests(unittest.TestCase):
    def test_existing_vault_entry_needs_no_prompt_or_nas(self):
        raw = b'{"account":"svc-wiki","password":"synthetic-existing"}'
        doc = {'schema':1, 'entries':{wiki.ENTRY:{'content':base64.b64encode(raw).decode(),
                                               'sha256':credentials.digest(raw)}}}
        with tempfile.TemporaryDirectory() as directory:
            vault=Path(directory)/'vault'; vault.write_bytes(b'original')
            with patch.object(credentials, 'VAULT', vault), \
                    patch.object(credentials, 'decrypt', return_value=doc), \
                    patch.object(wiki.getpass, 'getpass') as prompt:
                self.assertEqual(wiki.password_from_vault(Budget()), 'synthetic-existing')
                prompt.assert_not_called()
                self.assertEqual(vault.read_bytes(), b'original')

    def test_add_preserves_other_entries_and_confirms_readback(self):
        doc={'schema':1,'entries':{'tree/other':{'content':'eA==','sha256':credentials.digest(b'x')}}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); vault=root/'vault'; original=json.dumps(doc).encode();vault.write_bytes(original)
            def decrypt(data, key, **kwargs):
                value=json.loads(data)
                return json.loads(value['payload']) if 'payload' in value else value
            with patch.object(credentials,'VAULT',vault), patch.object(wiki,'PRIVATE',root/'private'), \
                    patch.object(credentials,'decrypt',side_effect=decrypt), \
                    patch.object(credentials,'crypt',side_effect=lambda data,key,**kwargs:data), \
                    patch.object(wiki.sys.stdin,'isatty',return_value=True), \
                    patch.object(wiki.getpass,'getpass',side_effect=['synthetic-new','synthetic-new']):
                self.assertEqual(wiki.password_from_vault(Budget()),'synthetic-new')
                entries=credentials.unpack(decrypt(vault.read_bytes(),None))
                self.assertEqual(entries['tree/other'],b'x')
                local=root/'private/secrets/wiki-runtime.json'
                self.assertEqual(entries[wiki.ENTRY],local.read_bytes())
                self.assertEqual(local.stat().st_mode & 0o777,0o600)
                self.assertFalse(vault.with_suffix('.wiki-lock').exists())

    def test_mismatched_confirmation_does_not_write(self):
        doc={'schema':1,'entries':{'tree/other':{'content':'eA==','sha256':credentials.digest(b'x')}}}
        with tempfile.TemporaryDirectory() as directory:
            vault=Path(directory)/'vault';vault.write_bytes(b'original')
            with patch.object(credentials,'VAULT',vault),patch.object(wiki,'PRIVATE',Path(directory)/'private'), \
                    patch.object(credentials,'decrypt',return_value=doc), \
                    patch.object(wiki.sys.stdin,'isatty',return_value=True), \
                    patch.object(wiki.getpass,'getpass',side_effect=['synthetic-one','synthetic-two']):
                with self.assertRaises(wiki.CredentialError): wiki.password_from_vault(Budget())
                self.assertEqual(vault.read_bytes(),b'original')
