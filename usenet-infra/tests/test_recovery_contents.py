"""Synthetic offline recovery-content validation tests."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('recovery_contents', Path(__file__).parents[1] / 'scripts/recovery-contents.py')
contents = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contents)


def state(resources=None):
    names = contents.CLOUD_RESOURCES if resources is None else resources
    return {'version': 4, 'serial': 3, 'lineage': '5f8aa700-1dd2-41c9-a4bf-0495b86bb999',
            'resources': [{'mode': 'managed', 'type': name.split('.')[0], 'name': name.split('.')[1],
                           'instances': [{'attributes': {'id': str(index + 10)}}]}
                          for index, name in enumerate(sorted(names))]}


def usg(kind='usg-pre', corrupt=False, extra=False):
    values = {'gateway-dump-cfg.json': b'{"synthetic":true}', 'unifi-usenet-cloud-ui.json': b'[]'}
    if kind == 'usg-post':
        values['config.gateway.json'] = b'{}'
    manifest = {'scope': ('post' if kind == 'usg-post' else 'pre') + '-fix-usg-and-unifi-vpn',
                'created_at': '2026-09-11T00:00:00Z',
                'files': [{'path': name, 'source_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                          for name, value in values.items()]}
    if corrupt:
        manifest['files'][0]['sha256'] = '0' * 64
    if extra:
        values['../unexpected'] = b'bad'
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for name, value in {'MANIFEST.json': json.dumps(manifest).encode(), **values}.items():
            member = tarfile.TarInfo(name)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return output.getvalue()


class RecoveryContentsTests(unittest.TestCase):
    def validate_state(self, value, identifier='cloud-tfstate'):
        return contents.validate_entry({'id': identifier, 'category': 'state'}, json.dumps(value).encode(), Path('/unused'), Path('/unused'))

    def test_both_terraform_roots_report_only_sanitized_identity_hashes(self):
        for identifier, names in (('cloud-tfstate', contents.CLOUD_RESOURCES), ('storage-tfstate', contents.STORAGE_RESOURCES)):
            result = self.validate_state(state(names), identifier)
            self.assertEqual(result['resources'], len(names))
            self.assertEqual(result['serial'], 3)
            self.assertNotIn('5f8aa700', json.dumps(result))

    def test_wrong_root_missing_resource_and_duplicate_resource_rejected(self):
        values = [state(contents.STORAGE_RESOURCES), state({'hcloud_server.acquisition'})]
        duplicate = state()
        duplicate['resources'].append(duplicate['resources'][0])
        values.append(duplicate)
        for value in values:
            with self.subTest(value=value), self.assertRaises(contents.ContentsError):
                self.validate_state(value)

    def test_cloud_image_data_source_is_explicitly_allowlisted(self):
        value = state()
        data = {'mode': 'data', 'type': 'hcloud_image', 'name': 'ubuntu', 'instances': [{'attributes': {'id': '123'}}]}
        value['resources'].append(data)
        result = self.validate_state(value)
        self.assertEqual(result['resources'], 5)
        self.assertEqual(result['data_sources'], 1)
        data['name'] = 'unexpected'
        with self.assertRaises(contents.ContentsError):
            self.validate_state(value)

    def test_invalid_lineage_serial_and_deposed_instance_rejected(self):
        values = []
        for field, value in (('lineage', 'secret-invalid-value'), ('serial', True), ('version', True)):
            altered = state()
            altered[field] = value
            values.append(altered)
        altered = state()
        altered['resources'][0]['instances'][0]['deposed'] = 'old'
        values.append(altered)
        for value in values:
            with self.assertRaises(contents.ContentsError) as caught:
                self.validate_state(value)
            self.assertNotIn('secret-invalid-value', str(caught.exception))

    def test_duplicate_state_json_fields_are_rejected(self):
        with self.assertRaises(contents.ContentsError):
            contents.validate_entry({'id': 'cloud-tfstate', 'category': 'state'},
                                    b'{"version":4,"version":4}', Path('/unused'), Path('/unused'))

    def test_historical_state_is_explicitly_not_current(self):
        result = contents.validate_entry({'id': 'zwave-historical-nvm', 'category': 'state'},
                                         b'synthetic binary', Path('/unused'), Path('/unused'))
        self.assertIn('not a current restore baseline', result['validation'])

    def test_usg_pre_and_post_exact_schema_and_checksums(self):
        self.assertEqual(contents._usg(usg(), 'usg-pre')['files'], 2)
        self.assertEqual(contents._usg(usg('usg-post'), 'usg-post')['files'], 3)
        for value in (usg(corrupt=True), usg(extra=True), usg('usg-post')):
            with self.assertRaises(contents.ContentsError):
                contents._usg(value, 'usg-pre')

    def test_archive_authentication_failure_precedes_parser(self):
        with mock.patch.object(contents, '_decrypt', side_effect=contents.ContentsError('Retained archive authentication failed.')), \
                mock.patch.object(contents, '_usg') as parser, self.assertRaises(contents.ContentsError):
            contents.validate_entry({'id': 'archive-usg-unifi-vpn-pre-fix-20260911t171125', 'category': 'archive'},
                                    b'ciphertext', Path('/unused'), Path('/unused'))
        parser.assert_not_called()

    def test_native_unifi_export_requires_recorded_bytes_and_discloses_limitation(self):
        value = b'synthetic native export'
        evidence = (len(value), hashlib.sha256(value).hexdigest())
        entry = {'id': 'archive-unifi-network-20260911t004042z', 'category': 'archive'}
        with mock.patch.object(contents, '_decrypt', return_value=value), \
                mock.patch.dict(contents.NATIVE_EXPORTS, {'unifi-network': evidence}):
            result = contents.validate_entry(entry, b'ciphertext', Path('/unused'), Path('/unused'))
            self.assertIn('native application restore unproven', result['validation'])
        with mock.patch.object(contents, '_decrypt', return_value=b'wrong bytes'), self.assertRaises(contents.ContentsError):
            contents.validate_entry(entry, b'ciphertext', Path('/unused'), Path('/unused'))

    def test_subprocess_environment_has_no_ambient_master_or_agent(self):
        self.assertEqual(set(contents.ENV), {'PATH', 'LANG', 'LC_ALL'})

    def test_six_real_synthetic_ssh_keypairs_and_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {'files': []}
            for identifier in contents.KEY_IDS:
                path = root / identifier
                subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(path)],
                               env=contents.ENV, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for suffix, mode in (('', '0600'), ('-public', '0644')):
                    filename = identifier + ('.pub' if suffix else '')
                    (root / filename).chmod(int(mode, 8))
                    manifest['files'].append({'id': identifier + suffix, 'restore_path': filename, 'mode': mode})
            self.assertEqual(contents.verify_keypairs(root, manifest), 6)
            (root / 'cloud-admin.pub').write_bytes((root / 'cloud-ui.pub').read_bytes())
            with self.assertRaisesRegex(contents.ContentsError, 'mismatch'):
                contents.verify_keypairs(root, manifest)

    def test_keypair_validation_refuses_symlinked_private_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'cloud-admin').symlink_to('/does-not-exist')
            manifest = {'files': [{'id': 'cloud-admin', 'restore_path': 'cloud-admin', 'mode': '0600'},
                                  {'id': 'cloud-admin-public', 'restore_path': 'cloud-admin.pub', 'mode': '0644'}]}
            with self.assertRaises(contents.ContentsError):
                contents.verify_keypairs(root, manifest)

    def test_real_age_roundtrip_wrong_key_and_truncation(self):
        target = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-amd64'}.get((platform.system(), platform.machine()))
        age = Path(__file__).parents[2] / 'build/tools/age-1.3.2' / str(target) / 'age'
        if not age.is_file():
            self.skipTest('Pinned native age cache not installed.')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'usenet-infra/secrets/ssh'
            directory.mkdir(parents=True, mode=0o700)
            private = directory / 'cloud-admin'
            subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(private)],
                           env=contents.ENV, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            encrypted = subprocess.run([str(age), '--encrypt', '--recipients-file', str(private) + '.pub'],
                                       input=usg(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       env=contents.ENV, check=True).stdout
            entry = {'id': 'archive-usg-unifi-vpn-pre-fix-20260911t171125', 'category': 'archive'}
            self.assertEqual(contents.validate_entry(entry, encrypted, root, age)['files'], 2)
            for damaged in (encrypted[:-1], encrypted[:-40], b'invalid-ciphertext'):
                with self.assertRaises(contents.ContentsError):
                    contents.validate_entry(entry, damaged, root, age)
            private.unlink()
            Path(str(private) + '.pub').unlink()
            subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(private)],
                           env=contents.ENV, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.assertRaisesRegex(contents.ContentsError, 'authentication failed'):
                contents.validate_entry(entry, encrypted, root, age)


if __name__ == '__main__':
    unittest.main()
