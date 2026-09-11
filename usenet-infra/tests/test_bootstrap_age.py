from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location('bootstrap_age', Path(__file__).parents[1] / 'scripts/bootstrap-age.py')
assert SPEC and SPEC.loader
age = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(age)


def archive(binary=b'fixture binary', *, name='age/age', kind=tarfile.REGTYPE, duplicate=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        member = tarfile.TarInfo(name)
        member.type = kind
        if kind == tarfile.REGTYPE:
            member.size = len(binary)
            tar.addfile(member, io.BytesIO(binary))
        else:
            member.linkname = '../../outside'
            tar.addfile(member)
        if duplicate:
            tar.addfile(member, io.BytesIO(binary))
    return buffer.getvalue()


class BootstrapAgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'build/tools/age-1.3.2'
        self.payloads = {name: archive(name.encode()) for name in ('darwin-arm64', 'linux-amd64')}
        self.releases = {name: {'url': name, 'sha256': age.sha256(payload)} for name, payload in self.payloads.items()}

    def tearDown(self):
        self.temp.cleanup()

    def run_bootstrap(self, **kwargs):
        return age.bootstrap(self.root, releases=self.releases, fetch=lambda url: self.payloads[url], **kwargs)

    def test_installs_both_verified_platforms_atomically(self):
        results = self.run_bootstrap()
        self.assertEqual({item['platform'] for item in results}, {'darwin-arm64', 'linux-amd64'})
        for item in results:
            binary = Path(item['path'])
            self.assertEqual(binary.read_bytes(), item['platform'].encode())
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
            self.assertEqual(age.sha256(binary.read_bytes()), item['binary_sha256'])
            self.assertTrue(item['changed'])

    def test_offline_repeat_is_idempotent_without_downloading(self):
        self.run_bootstrap()
        inodes = {name: (self.root / name / 'age').stat().st_ino for name in self.releases}
        fetch = mock.Mock(side_effect=AssertionError('offline run contacted network'))
        results = age.bootstrap(self.root, releases=self.releases, fetch=fetch, offline=True)
        self.assertTrue(all(not result['changed'] for result in results))
        self.assertEqual(inodes, {name: (self.root / name / 'age').stat().st_ino for name in self.releases})
        fetch.assert_not_called()

    def test_existing_binary_is_rehashed_and_repaired_from_verified_cache(self):
        self.run_bootstrap()
        binary = self.root / 'linux-amd64/age'
        binary.write_bytes(b'corrupted or replaced binary')
        results = self.run_bootstrap(offline=True)
        self.assertTrue(next(item for item in results if item['platform'] == 'linux-amd64')['changed'])
        self.assertEqual(binary.read_bytes(), b'linux-amd64')

    def test_correct_binary_permissions_are_repaired(self):
        self.run_bootstrap()
        binary = self.root / 'darwin-arm64/age'
        inode = binary.stat().st_ino
        binary.chmod(0o600)
        self.run_bootstrap(offline=True)
        self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
        self.assertEqual(binary.stat().st_ino, inode)

    def test_hash_failure_never_replaces_existing_binary_or_cache(self):
        self.run_bootstrap()
        cache = self.root / 'darwin-arm64/archive.tar.gz'
        binary = self.root / 'darwin-arm64/age'
        cache.write_bytes(b'corrupt cache')
        with self.assertRaisesRegex(age.BootstrapError, 'SHA-256'):
            age.bootstrap(self.root, releases=self.releases, fetch=lambda url: b'bad download')
        self.assertEqual(binary.read_bytes(), b'darwin-arm64')
        self.assertEqual(cache.read_bytes(), b'corrupt cache')

    def test_corrupted_cache_cannot_authorize_offline_binary(self):
        self.run_bootstrap()
        (self.root / 'darwin-arm64/archive.tar.gz').write_bytes(b'bad cache')
        with self.assertRaisesRegex(age.BootstrapError, 'Offline bootstrap'):
            self.run_bootstrap(offline=True)
        self.assertEqual((self.root / 'darwin-arm64/age').read_bytes(), b'darwin-arm64')

    def test_malformed_archive_never_replaces_executable(self):
        self.run_bootstrap()
        (self.root / 'darwin-arm64/archive.tar.gz').unlink()
        payload = b'not a gzip tar archive'
        release = {'url': 'fixture', 'sha256': age.sha256(payload)}
        with self.assertRaisesRegex(age.BootstrapError, 'Malformed'):
            age.install('darwin-arm64', release, self.root, fetch=lambda url: payload)
        self.assertEqual((self.root / 'darwin-arm64/age').read_bytes(), b'darwin-arm64')

    def test_archive_traversal_symlink_hardlink_and_duplicate_binary_are_rejected(self):
        for payload in (archive(name='../outside'), archive(kind=tarfile.SYMTYPE),
                        archive(kind=tarfile.LNKTYPE), archive(duplicate=True)):
            with self.assertRaises(age.BootstrapError):
                age.binary_from_archive(payload, age.sha256(payload))

    def test_symlinked_install_target_is_not_followed(self):
        self.run_bootstrap()
        binary = self.root / 'linux-amd64/age'
        binary.unlink()
        outside = Path(self.temp.name) / 'outside'
        outside.write_bytes(b'must remain')
        binary.symlink_to(outside)
        with self.assertRaisesRegex(age.BootstrapError, 'symlinked'):
            self.run_bootstrap(offline=True)
        self.assertEqual(outside.read_bytes(), b'must remain')

    def test_redirects_only_allow_official_https_release_hosts(self):
        self.assertTrue(age.allowed_url('https://release-assets.githubusercontent.com/github-production-release-asset/id'))
        for url in ('http://github.com/a', 'https://attacker.invalid/a', 'https://github.com.attacker.invalid/a',
                    'https://user:password@github.com/a', 'https://github.com:444/a'):
            self.assertFalse(age.allowed_url(url))
            with self.assertRaises(age.BootstrapError):
                age.OfficialRedirects().redirect_request(None, None, 302, '', {}, url)


if __name__ == '__main__':
    unittest.main()
