"""Synthetic scanner tests; credential-shaped values are assembled at runtime."""
import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('secret_scan', Path(__file__).parents[1] / 'scripts/secret-scan.py')
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


def encrypted():
    data, iv, tag = [base64.b64encode(value).decode() for value in (b'ciphertext', b'i' * 32, b't' * 16)]
    return 'ENC[AES256_GCM,data:' + data + ',iv:' + iv + ',tag:' + tag + ',type:str]'


def envelope():
    wrapped = base64.b64encode(b'age-encryption.org/v1\n-> X25519 synthetic\nopaque ciphertext').decode()
    return {'entries': [{'id': encrypted(), 'sha256': encrypted(), 'content': encrypted()}],
            'schema_version': encrypted(), 'inventory_sha256': encrypted(), 'source_checkout': encrypted(),
            'sops': {'age': [{'recipient': 'age1' + 'q' * 58,
                              'enc': '-----BEGIN AGE ENCRYPTED FILE-----\n' + wrapped + '\n-----END AGE ENCRYPTED FILE-----\n'}],
                     'lastmodified': '2026-09-11T00:00:00Z', 'mac': encrypted(),
                     'unencrypted_suffix': '_unencrypted', 'version': '3.13.3'}}


def age_secret():
    return ('AGE-' + 'SECRET-KEY-1' + 'Q' * 58).encode()


class SecretScanTests(unittest.TestCase):
    def test_complete_native_age_identity_detected_but_template_literals_are_not(self):
        self.assertIn('native age private identity', scanner.inspect_content('anywhere.txt', age_secret()))
        for content in (b'AGE-SECRET-KEY-1synthetic', b'$SOPS_AGE_KEY', b'AGE-SECRET-KEY-1...'):
            self.assertFalse(scanner.inspect_content('example.py', content))

    def test_existing_service_token_detectors_include_quoted_values(self):
        for name in ('HCLOUD_TOKEN', 'SABNZBD_API_KEY', 'PROWLARR_API_KEY'):
            content = (name + '="' + 'a' * 32 + '"').encode()
            self.assertIn('named service token', scanner.inspect_content('example.env', content))
        self.assertFalse(scanner.inspect_content('example.env', b'HCLOUD_TOKEN=replace-me\n'))

    def test_private_key_armors_require_real_multiline_body(self):
        for kind in ('OPENSSH ', 'RSA ', 'EC ', 'DSA ', '', 'ENCRYPTED '):
            key = ('-----BEGIN ' + kind + 'PRIVATE KEY-----\n' + 'A' * 64 + '\n').encode()
            self.assertIn('armored private key', scanner.inspect_content('unknown.file', key))
        self.assertFalse(scanner.inspect_content('code.py', b'BEGIN (OPENSSH|RSA|EC|DSA) PRIVATE KEY'))

    def test_sops_exact_envelope_accepts_only_encrypted_payload_leaves(self):
        good = envelope()
        self.assertTrue(scanner.valid_sops(json.dumps(good).encode()))
        for field in ('id', 'sha256', 'content'):
            value = copy.deepcopy(good)
            value['entries'][0][field] = 'plaintext'
            self.assertFalse(scanner.valid_sops(json.dumps(value).encode()))
        value = copy.deepcopy(good)
        value['extra_unencrypted'] = 'plaintext'
        self.assertFalse(scanner.valid_sops(json.dumps(value).encode()))

    def test_sops_recipient_metadata_and_mac_are_bounded_and_required(self):
        for field in ('mac', 'age', 'unencrypted_suffix'):
            value = envelope()
            value['sops'].pop(field)
            self.assertFalse(scanner.valid_sops(json.dumps(value).encode()))
        value = envelope()
        value['sops']['age'][0]['enc'] = 'not age ciphertext'
        self.assertFalse(scanner.valid_sops(json.dumps(value).encode()))

    def test_only_exact_vault_path_gets_ciphertext_acceptance(self):
        value = json.dumps(envelope()).encode()
        self.assertFalse(scanner.inspect_content(scanner.VAULT_PATH, value))
        self.assertIn('SOPS ciphertext outside the exact reviewed vault path', scanner.inspect_content('other.json', value))
        self.assertTrue(scanner.forbidden_path('usenet-infra/vault/decrypted.json'))
        self.assertTrue(scanner.forbidden_path('usenet-infra/terraform/cloud/terraform.tfstate'))
        self.assertFalse(scanner.forbidden_path('usenet-infra/.env.example'))

    def test_renamed_base64_plaintext_bundle_is_detected(self):
        value = {'entries': [{'content': 'aGVsbG8='}], 'schema_version': 1,
                 'inventory_sha256': 'a' * 64, 'source_checkout': '/synthetic'}
        self.assertIn('plaintext or malformed recovery bundle', scanner.inspect_content('unexpected.data', json.dumps(value).encode()))

    def test_chunk_boundaries_cannot_hide_complete_identity(self):
        content = b'x' * (scanner.CHUNK - 20) + b'\n' + age_secret() + b'\n' + b'x' * 100
        with mock.patch.object(scanner, 'MAX_JSON', 128):
            self.assertIn('native age private identity', scanner.inspect_stream('large.bin', io.BytesIO(content), len(content)))

    def test_source_open_does_not_follow_parent_or_leaf_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'real').mkdir()
            (root / 'real/file').write_text('synthetic')
            (root / 'linked').symlink_to(root / 'real', target_is_directory=True)
            (root / 'leaf').symlink_to(root / 'real/file')
            for path in ('linked/file', 'leaf'):
                with self.assertRaises(OSError):
                    scanner._source_fd(root, path)

    def test_worktree_index_and_deleted_history_all_checked_without_submodules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args], check=True,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            git('init', '-q')
            (root / '.gitignore').write_text('private/\n')
            (root / 'old.txt').write_bytes(age_secret())
            git('add', '.gitignore', 'old.txt')
            git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-qm', 'synthetic fixture')
            git('rm', 'old.txt')
            git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-qm', 'remove fixture')
            (root / 'new.txt').write_bytes(age_secret())
            git('add', 'new.txt')
            (root / 'new.txt').write_bytes(b'clean worktree')
            (root / 'untracked.txt').write_bytes(age_secret())
            (root / 'private').mkdir()
            (root / 'private/ignored.txt').write_bytes(age_secret())
            findings, files, blobs = scanner.scan(root)
            self.assertIn(('history', 'old.txt', 'native age private identity'), findings)
            self.assertIn(('index', 'new.txt', 'native age private identity'), findings)
            self.assertIn(('source', 'untracked.txt', 'native age private identity'), findings)
            self.assertFalse(any('ignored.txt' in path for _, path, _ in findings))

    def test_cli_diagnostics_never_echo_matched_content(self):
        finding = [('source', 'synthetic.txt', 'native age private identity')]
        with mock.patch.object(scanner, 'scan', return_value=(finding, 1, 0)), \
                mock.patch('sys.stderr', new_callable=io.StringIO) as output:
            self.assertEqual(scanner.main([]), 1)
            self.assertIn('synthetic.txt', output.getvalue())
            self.assertNotIn(age_secret().decode(), output.getvalue())


if __name__ == '__main__':
    unittest.main()
