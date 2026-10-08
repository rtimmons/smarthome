import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('filex_portal', ROOT / 'scripts/filex-portal.py')
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)


def fixture():
    remote = {'host': '192.168.1.66', 'port': 2226, 'user': 'filex-staging',
              'root': '/staging', 'host_key': 'ssh-ed25519 AAAA',
              'private_key': '-----BEGIN OPENSSH PRIVATE KEY-----\nfixture-only\n-----END OPENSSH PRIVATE KEY-----',
              'restricted_staging_account': True}
    return {'schema_version': 2, 'image_digest': portal.IMAGE_DIGEST,
            'public_url': 'https://10.77.0.1:5213',
            'admin': {'email': 'admin@example.invalid', 'password': 'synthetic-admin-password-12345'},
            'operator': {'email': 'operator@example.invalid', 'password': 'synthetic-operator-password-12345'},
            'nas': copy.deepcopy(remote), 'storagebox': {'mode':'read_only_bind'}}


class FakeAPI:
    def __init__(self):
        self.token = None
        self.rows = []
        self.users = []
        self.writes = []
        self.fail_at = None

    def call(self, method, path, body=None):
        if path == '/api/auth/login':
            return {'token': 'synthetic-session'}
        if method == 'GET':
            return copy.deepcopy(self.rows if path.endswith('storages') else self.users)
        self.writes.append((path, copy.deepcopy(body)))
        if len(self.writes) == self.fail_at:
            raise portal.Refused('simulated disconnect')
        (self.rows if path.endswith('storages') else self.users).append(copy.deepcopy(body))
        return body


class FilexPolicyTests(unittest.TestCase):
    def test_browser_tunnel_has_only_fixed_loopback_origin(self):
        self.assertEqual(portal.server_config(fixture())['cors']['allowed_origins'],
                         ['https://10.77.0.1:5213', 'http://127.0.0.1:15213'])

    def test_only_reviewed_image_and_https_origin(self):
        self.assertIsNotNone(portal.validate(fixture()))
        for field, value in [('image_digest', 'sha256:' + 'a' * 64),
                             ('public_url', 'http://files.example.invalid'),
                             ('public_url', 'https://user:pass@files.example.invalid'),
                             ('public_url', 'https://files.example.invalid/path'),
                             ('public_url', 'https://files.example.invalid'),
                             ('schema_version', 1)]:
            with self.subTest(field=field, value=value):
                config = fixture()
                config[field] = value
                with self.assertRaises(portal.Refused):
                    portal.validate(config)

    def test_rejects_remote_root_escape_and_unrestricted_credentials(self):
        for field, value in [('root', '/'), ('root', '//'), ('root', '//scratch'),
                             ('root', '/scratch/../library'),
                             ('root', '/scratch//nested'), ('root', 'relative'),
                             ('root', '/scratch\x00'), ('user', 'root'),
                             ('port', 0), ('port', True), ('host_key', ''),
                             ('restricted_staging_account', False)]:
            with self.subTest(field=field, value=value):
                config = fixture()
                config['nas'][field] = value
                with self.assertRaises(portal.Refused):
                    portal.validate(config)
        for extra in ('insecure_skip_host_key', 'known_hosts', 'password'):
            config = fixture()
            config['nas'][extra] = True
            with self.assertRaises(portal.Refused):
                portal.validate(config)

    def test_account_separation_and_password_limits(self):
        for key, value in [('password', 'short'), ('email', fixture()['admin']['email']),
                           ('password', fixture()['admin']['password']),
                           ('password', 'é' * 40)]:
            config = fixture()
            config['operator'][key] = value
            with self.assertRaises(portal.Refused):
                portal.validate(config)

    def test_storagebox_cannot_be_rebound_or_made_writable(self):
        for value in ({'mode': 'read_write_bind'}, {'mode': 'read_only_bind', 'path': '/'}, {}):
            config = fixture()
            config['storagebox'] = value
            with self.assertRaises(portal.Refused):
                portal.validate(config)

    def test_refuses_public_secret_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps(fixture()))
            path.chmod(0o644)
            with self.assertRaises(portal.Refused):
                portal.load(path)
            path.chmod(0o600)
            portal.load(path)
            alias = Path(tmp) / 'alias.json'
            alias.symlink_to(path)
            with self.assertRaises(portal.Refused):
                portal.load(alias)

    def test_bootstrap_and_repeat_preserve_existing_configuration(self):
        api = FakeAPI()
        self.assertEqual(portal.bootstrap(fixture(), api)['created'], 4)
        self.assertIsNone(api.token)
        self.assertEqual([row['read_only'] for row in api.rows], [False,False,True])
        self.assertEqual(api.rows[0]['config'], {'path': '/srv/files'})
        self.assertEqual(api.users[0]['role'], 'user')
        self.assertEqual(portal.bootstrap(fixture(), api)['created'], 0)
        self.assertEqual(len(api.writes), 4)

    def test_partial_bootstrap_resumes_without_duplicates(self):
        api = FakeAPI()
        api.fail_at = 2
        with self.assertRaises(portal.Refused):
            portal.bootstrap(fixture(), api)
        self.assertIsNone(api.token)
        api.fail_at = None
        self.assertEqual(portal.bootstrap(fixture(), api)['created'], 3)
        self.assertEqual(len(api.rows), 3)

    def test_drift_and_unexpected_roots_refuse_before_any_write(self):
        for drift in ('read_only', 'root', 'unexpected', 'duplicate', 'operator_role'):
            with self.subTest(drift=drift):
                api = FakeAPI()
                api.rows = portal.storages(fixture())[:1]
                if drift == 'read_only':
                    api.rows[0]['read_only'] = True
                elif drift == 'root':
                    api.rows[0]['config']['path'] = '/data'
                elif drift == 'unexpected':
                    api.rows[0]['name'] = 'Unreviewed storage'
                elif drift == 'duplicate':
                    api.rows *= 2
                else:
                    api.users = [{**fixture()['operator'], 'role': 'admin'}]
                with self.assertRaises(portal.Refused):
                    portal.bootstrap(fixture(), api)
                self.assertEqual(api.writes, [])

    def test_bad_persisted_permissions_fail_readback(self):
        class BadAPI(FakeAPI):
            def call(self, method, path, body=None):
                result = super().call(method, path, body)
                if method == 'POST' and path.endswith('storages'):
                    self.rows[-1]['read_only'] = not self.rows[-1]['read_only']
                return result
        with self.assertRaises(portal.Refused):
            portal.bootstrap(fixture(), BadAPI())

    def test_redirect_never_forwards_bootstrap_credentials(self):
        with self.assertRaises(portal.Refused):
            portal.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.invalid')

    def test_server_config_has_no_seeded_writable_storage(self):
        config = portal.server_config(fixture())
        self.assertNotIn('storage', config['seed'])
        self.assertTrue(config['plugins_disabled'])
        self.assertEqual(config['auth']['drivers'], ['local'])
        self.assertEqual(config['queue']['workers'], 1)


if __name__ == '__main__':
    unittest.main()
