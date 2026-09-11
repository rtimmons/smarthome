from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.parse


SPEC = importlib.util.spec_from_file_location('sab_provider', Path(__file__).parents[1] / 'scripts/sab-provider.py')
assert SPEC and SPEC.loader
sab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sab)


def server(**changes):
    return dict(name='saved-eweka-name', host=sab.HOST, username='PRIVATE_USERNAME',
                password='**********', quota='500G', **dict(sab.DESIRED, **changes))


class FakeClient:
    def __init__(self, servers):
        self.servers = copy.deepcopy(servers)
        self.calls = []
        self.test_response = {'value': {'result': True, 'message': 'PRIVATE RESPONSE'}}

    def call(self, **fields):
        self.calls.append(fields)
        if fields['mode'] == 'get_config':
            return {'config': {'servers': copy.deepcopy(self.servers)}}
        if fields['mode'] == 'set_config':
            matches = [item for item in self.servers if item['name'] == fields['keyword']]
            assert len(matches) == 1, 'test client refuses server creation'
            matches[0].update({key: value for key, value in fields.items() if key not in {'mode', 'section', 'keyword'}})
            return {'config': {'servers': copy.deepcopy(matches)}}
        if fields['mode'] == 'config':
            return self.test_response
        raise AssertionError('unexpected test request')


class SabProviderTests(unittest.TestCase):
    def test_configure_changes_existing_server_without_sending_credentials(self):
        client = FakeClient([server(connections=50, ssl_verify=1, optional=1)])
        result = sab.configure(client)
        update = next(call for call in client.calls if call['mode'] == 'set_config')
        self.assertEqual(update['keyword'], 'saved-eweka-name')
        self.assertNotIn('username', update)
        self.assertNotIn('password', update)
        self.assertEqual(update['quota'], '500G')
        self.assertEqual(result['settings'], sab.DESIRED)
        self.assertTrue(result['changed'])
        self.assertTrue(result['username_present'])
        self.assertNotIn('PRIVATE_USERNAME', json.dumps(result))
        self.assertEqual(len(client.servers), 1)

    def test_configure_is_idempotent(self):
        client = FakeClient([server()])
        self.assertFalse(sab.configure(client)['changed'])
        self.assertFalse(any(call['mode'] == 'set_config' for call in client.calls))

    def test_missing_duplicate_and_ambiguous_names_never_mutate(self):
        duplicate_name = server()
        duplicate_name['host'] = 'unrelated.example'
        for entries in ([], [server(), server()], [server(), duplicate_name]):
            client = FakeClient(entries)
            with self.assertRaises(sab.ProviderError):
                sab.configure(client)
            self.assertFalse(any(call['mode'] == 'set_config' for call in client.calls))

    def test_host_alias_duplicate_is_refused(self):
        duplicate = server()
        duplicate['host'] = 'NEWS.EWEKA.NL.'
        client = FakeClient([server(), duplicate])
        with self.assertRaisesRegex(sab.ProviderError, 'duplicate_eweka_servers'):
            sab.configure(client)

    def test_missing_credentials_refuse_mutation_and_test(self):
        saved = server(connections=50)
        saved['password'] = ''
        client = FakeClient([saved])
        for action in (sab.configure, sab.test_provider):
            with self.assertRaisesRegex(sab.ProviderError, 'saved_credentials_missing'):
                action(client)
        self.assertTrue(all(call['mode'] == 'get_config' for call in client.calls))

    def test_test_uses_saved_secret_sentinel_and_checks_result(self):
        client = FakeClient([server()])
        result = sab.test_provider(client)
        request = client.calls[-1]
        self.assertEqual(request['password'], '********')
        self.assertEqual(request['server'], 'saved-eweka-name')
        self.assertEqual(request['username'], 'PRIVATE_USERNAME')
        self.assertEqual(result['connection_test'], 'passed')
        self.assertNotIn('PRIVATE', json.dumps(result))
        client.test_response = {'value': {'result': False, 'message': 'PRIVATE_USERNAME PRIVATE_PASSWORD'}}
        with self.assertRaisesRegex(sab.ProviderError, '^provider_connection_test_failed$'):
            sab.test_provider(client)

    def test_test_refuses_weaker_tls_without_sending_credentials(self):
        client = FakeClient([server(ssl_verify=1)])
        with self.assertRaisesRegex(sab.ProviderError, 'configure_required_before_test'):
            sab.test_provider(client)
        self.assertEqual(len(client.calls), 1)

    def test_readback_must_confirm_settings(self):
        client = FakeClient([server(connections=50)])
        original = client.call
        def ignore_write(**fields):
            if fields['mode'] == 'set_config':
                return {'status': True}
            return original(**fields)
        client.call = ignore_write
        with self.assertRaisesRegex(sab.ProviderError, 'configuration_readback_failed'):
            sab.configure(client)

    def test_post_has_no_secrets_in_url_and_disables_proxy_redirects(self):
        client = sab.SabClient('PRIVATE_API_KEY')
        response = mock.MagicMock()
        response.__enter__.return_value = io.StringIO('{"config":{"servers":[]}}')
        with mock.patch.object(client._opener, 'open', return_value=response) as open_request:
            client.call(mode='get_config', section='servers')
        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:8080/api')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())['apikey'], ['PRIVATE_API_KEY'])
        self.assertIsNone(sab.NoRedirects().redirect_request(None, None, 302, '', {}, 'https://example.invalid'))

    def test_cli_sanitizes_network_and_api_failure_output(self):
        client = sab.SabClient('PRIVATE_API_KEY')
        with mock.patch.object(client._opener, 'open', side_effect=OSError('PRIVATE_PASSWORD https://unsafe/?apikey=PRIVATE_API_KEY')):
            with mock.patch.object(sab, 'api_key', return_value='PRIVATE_API_KEY'), mock.patch.object(sab, 'SabClient', return_value=client):
                with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                    self.assertEqual(sab.main(['inspect']), 1)
        text = output.getvalue()
        self.assertEqual(json.loads(text)['error'], 'api_request_failed')
        self.assertNotIn('PRIVATE', text)
        self.assertNotIn('https:', text)

    def test_cli_inspection_emits_only_allowlisted_fields(self):
        with mock.patch.object(sab, 'api_key', return_value='PRIVATE_API_KEY'), mock.patch.object(sab, 'SabClient', return_value=FakeClient([server()])):
            with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(sab.main(['inspect']), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(set(result), {'command', 'status', 'host', 'settings', 'username_present', 'password_present'})
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertNotIn('saved-eweka-name', output.getvalue())

    def test_env_key_missing_or_duplicate_is_generic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.env'
            path.write_text('SABNZBD_API_KEY=PRIVATE_KEY\n')
            self.assertEqual(sab.api_key(path), 'PRIVATE_KEY')
            path.write_text('SABNZBD_API_KEY=ONE\nSABNZBD_API_KEY=TWO\n')
            with self.assertRaisesRegex(sab.ProviderError, '^api_key_unavailable$'):
                sab.api_key(path)


if __name__ == '__main__':
    unittest.main()
