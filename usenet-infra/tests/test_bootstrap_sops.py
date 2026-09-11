from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('bootstrap_sops', Path(__file__).parents[1] / 'scripts/bootstrap-sops.py')
assert SPEC and SPEC.loader
sops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sops)


class BootstrapSopsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'build/tools/sops-3.13.3'
        self.payloads = {name: ('fixture-' + name).encode() for name in ('darwin-arm64', 'linux-amd64')}
        self.releases = {name: {'url': name, 'sha256': sops.sha256(payload)}
                         for name, payload in self.payloads.items()}
        self.verify = mock.Mock()

    def tearDown(self):
        self.temp.cleanup()

    def run_bootstrap(self, **kwargs):
        return sops.bootstrap(self.root, releases=self.releases,
                              fetch=lambda url: self.payloads[url], verify=self.verify, **kwargs)

    def test_installs_both_verified_platforms_atomically(self):
        results = self.run_bootstrap()
        self.assertEqual({item['platform'] for item in results}, {'darwin-arm64', 'linux-amd64'})
        for item in results:
            binary = Path(item['path'])
            self.assertEqual(binary.read_bytes(), self.payloads[item['platform']])
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
            self.assertEqual(sops.sha256(binary.read_bytes()), item['release_sha256'])
            self.assertTrue(item['changed'])
        self.assertEqual(self.verify.call_count, 1)
        self.assertTrue(next(item for item in results if item['platform'] == sops.local_platform())['version_checked'])

    def test_offline_repeat_is_idempotent_without_downloading(self):
        self.run_bootstrap()
        inodes = {name: (self.root / name / 'sops').stat().st_ino for name in self.releases}
        fetch = mock.Mock(side_effect=AssertionError('offline run contacted network'))
        results = sops.bootstrap(self.root, releases=self.releases, fetch=fetch, verify=self.verify, offline=True)
        self.assertTrue(all(not result['changed'] for result in results))
        self.assertEqual(inodes, {name: (self.root / name / 'sops').stat().st_ino for name in self.releases})
        fetch.assert_not_called()

    def test_existing_binary_is_rehashed_and_repaired_from_verified_cache(self):
        self.run_bootstrap()
        binary = self.root / 'linux-amd64/sops'
        binary.write_bytes(b'corrupted or replaced binary')
        results = self.run_bootstrap(offline=True)
        self.assertTrue(next(item for item in results if item['platform'] == 'linux-amd64')['changed'])
        self.assertEqual(binary.read_bytes(), self.payloads['linux-amd64'])

    def test_hash_failure_never_replaces_existing_binary_or_cache(self):
        self.run_bootstrap()
        cache = self.root / 'darwin-arm64/release.bin'
        binary = self.root / 'darwin-arm64/sops'
        cache.write_bytes(b'corrupt cache')
        with self.assertRaisesRegex(sops.BootstrapError, 'SHA-256'):
            sops.bootstrap(self.root, releases=self.releases, fetch=lambda url: b'bad download', verify=self.verify)
        self.assertEqual(binary.read_bytes(), self.payloads['darwin-arm64'])
        self.assertEqual(cache.read_bytes(), b'corrupt cache')

    def test_corrupted_cache_cannot_authorize_offline_binary(self):
        self.run_bootstrap()
        (self.root / 'darwin-arm64/release.bin').write_bytes(b'bad cache')
        with self.assertRaisesRegex(sops.BootstrapError, 'Offline bootstrap'):
            self.run_bootstrap(offline=True)

    def test_symlinked_install_target_is_not_followed(self):
        self.run_bootstrap()
        binary = self.root / 'linux-amd64/sops'
        binary.unlink()
        outside = Path(self.temp.name) / 'outside'
        outside.write_bytes(b'must remain')
        binary.symlink_to(outside)
        with self.assertRaisesRegex(sops.BootstrapError, 'symlinked'):
            self.run_bootstrap(offline=True)
        self.assertEqual(outside.read_bytes(), b'must remain')

    def test_unexpected_version_fails_after_verified_install(self):
        with self.assertRaisesRegex(sops.BootstrapError, 'unexpected version'):
            sops.bootstrap(self.root, releases=self.releases,
                           fetch=lambda url: self.payloads[url],
                           verify=lambda binary: (_ for _ in ()).throw(sops.BootstrapError('unexpected version')))

    def test_redirects_only_allow_official_https_release_hosts(self):
        self.assertTrue(sops.allowed_url('https://release-assets.githubusercontent.com/github-production-release-asset/id'))
        for url in ('http://github.com/a', 'https://attacker.invalid/a', 'https://github.com.attacker.invalid/a',
                    'https://user:password@github.com/a', 'https://github.com:444/a'):
            self.assertFalse(sops.allowed_url(url))
            with self.assertRaises(sops.BootstrapError):
                sops.OfficialRedirects().redirect_request(None, None, 302, '', {}, url)


if __name__ == '__main__':
    unittest.main()
