from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.parse

SPEC = importlib.util.spec_from_file_location('prowlarr_download_client', Path(__file__).parents[1] / 'scripts/prowlarr-download-client.py')
assert SPEC and SPEC.loader
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class FakeAPIs:
    def __init__(self):
        self.keys = {'SABNZBD_API_KEY': 'SYNTHETIC-SAB-KEY', 'PROWLARR_API_KEY': 'SYNTHETIC-PROWLARR-KEY'}
        self.clients = []
        self.categories = [{'name': '*', **client.DESIRED_CATEGORY, 'newzbin': []}]
        self.calls = []
        self.queued = 0
        self.processing = 0
        self.fail_test = False
        self.ignore_write = False
        self.keep_wrong_secret = False
        self.change_during_test = False
        self.allowed_hosts = ['sabnzbd']
        self.ignore_hostname_write = False

    def prowlarr(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path == 'system/status':
            return {'version': client.PROWLARR_VERSION}
        if path == 'downloadclient/schema':
            return [client.candidate(self, None)]
        if method == 'GET' and path == 'downloadclient':
            resources = copy.deepcopy(self.clients)
            for resource in resources:
                for field in resource['fields']:
                    if field['name'] in ('apiKey', 'password') and field['value']:
                        field['value'] = '********'
            return resources
        if path == 'downloadclient/test':
            if 'sabnzbd' not in self.allowed_hosts:
                raise client.ClientError('private_api_request_failed')
            values = client.fields(body)
            key = values['apiKey']
            if key == '********':
                existing = next(item for item in self.clients if item['id'] == body['id'])
                key = client.fields(existing)['apiKey']
            if self.fail_test or key != self.keys['SABNZBD_API_KEY']:
                raise client.ClientError('private_api_request_failed')
            if not any(item['name'] == 'prowlarr' for item in self.categories):
                raise client.ClientError('private_api_request_failed')
            if self.change_during_test and self.clients:
                self.clients[0]['priority'] = 2
            return {}
        if method in ('POST', 'PUT') and path.startswith('downloadclient'):
            if not self.ignore_write:
                saved = copy.deepcopy(body)
                saved['id'] = saved.get('id', 7)
                if self.keep_wrong_secret:
                    next(field for field in saved['fields'] if field['name'] == 'apiKey')['value'] = 'STALE-SECRET'
                self.clients = [saved]
            return {}
        raise AssertionError((method, path))

    def sab(self, mode, **parameters):
        self.calls.append(('SAB', mode, copy.deepcopy(parameters)))
        if mode == 'version':
            return {'version': client.SAB_VERSION}
        if mode == 'get_config':
            if parameters['section'] == 'misc':
                return {'config': {'misc': {'host_whitelist': list(self.allowed_hosts)}}}
            return {'config': {'categories': copy.deepcopy(self.categories)}}
        if mode == 'queue':
            return {'queue': {'noofslots_total': self.queued, 'slots': [{'filename': 'PRIVATE-JOB'}]}}
        if mode == 'history':
            return {'history': {'ppslots': self.processing, 'slots': [{'name': 'PRIVATE-HISTORY'}]}}
        if mode == 'set_config':
            if parameters['section'] == 'misc':
                if not self.ignore_hostname_write:
                    self.allowed_hosts = parameters['value'].split(',')
                return {'config': {}}
            self.categories.append({'name': parameters['keyword'], 'newzbin': [],
                                    **{key: value for key, value in parameters.items() if key in (*client.DESIRED_CATEGORY, 'order')}})
            return {'config': {}}
        raise AssertionError(mode)

    def existing(self, **changes):
        resource = client.candidate(self, None)
        resource.update(id=7, **changes)
        self.clients = [resource]
        self.categories.append({'name': 'prowlarr', **client.DESIRED_CATEGORY, 'newzbin': []})


class ProwlarrDownloadClientTests(unittest.TestCase):
    def test_inspect_is_read_only_and_only_returns_fixed_values_and_counts(self):
        api = FakeAPIs()
        report = client.public_state(api, client.state(api))
        self.assertFalse(report['client_exists'])
        self.assertFalse(report['category_exists'])
        self.assertTrue(report['safe_to_configure'])
        self.assertNotIn('PRIVATE-', json.dumps(report))
        self.assertNotIn('SYNTHETIC-', json.dumps(report))
        self.assertFalse(any(method in ('POST', 'PUT') or path == 'set_config' for method, path, _ in api.calls))

    def test_create_category_test_then_enable_and_read_back_saved_secret(self):
        api = FakeAPIs()
        default = copy.deepcopy(api.categories)
        report = client.configure(api)
        self.assertTrue(report['changed'])
        self.assertTrue(report['category_created'])
        self.assertTrue(report['client_enabled'])
        self.assertEqual(report['saved_connection_test'], 'passed')
        self.assertEqual(api.categories[:1], default)
        writes = [call for call in api.calls if call[0] in ('POST', 'PUT') and call[1] != 'downloadclient/test']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][:2], ('POST', 'downloadclient'))
        self.assertTrue(writes[0][2]['enable'])
        self.assertEqual(client.fields(writes[0][2])['host'], 'sabnzbd')
        tests = [call[2] for call in api.calls if call[1] == 'downloadclient/test']
        self.assertEqual(client.fields(tests[0])['apiKey'], api.keys['SABNZBD_API_KEY'])
        self.assertEqual(client.fields(tests[-1])['apiKey'], '********')
        self.assertEqual(tests[-1]['id'], 7)
        allowed = {'system/status', 'downloadclient/schema', 'downloadclient', 'downloadclient/test',
                   'version', 'get_config', 'queue', 'history', 'set_config'}
        self.assertTrue(all(path in allowed for _, path, _ in api.calls))

    def test_repeated_configure_does_not_duplicate_or_rewrite(self):
        api = FakeAPIs()
        api.existing()
        report = client.configure(api)
        self.assertFalse(report['changed'])
        self.assertFalse(report['category_created'])
        self.assertFalse(any(method in ('POST', 'PUT') and path != 'downloadclient/test'
                             or path == 'set_config' for method, path, _ in api.calls))

    def test_existing_identity_is_updated_in_place_after_test(self):
        api = FakeAPIs()
        api.existing(enable=False)
        next(field for field in api.clients[0]['fields'] if field['name'] == 'host')['value'] = 'old-host'
        report = client.configure(api)
        self.assertTrue(report['changed'])
        writes = [call for call in api.calls if call[0] == 'PUT']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1], 'downloadclient/7')
        self.assertEqual(api.clients[0]['id'], 7)

    def test_masked_stale_saved_secret_is_repaired_not_mistaken_for_correct(self):
        api = FakeAPIs()
        api.existing()
        next(field for field in api.clients[0]['fields'] if field['name'] == 'apiKey')['value'] = 'STALE-SECRET'
        report = client.configure(api)
        self.assertTrue(report['changed'])
        self.assertEqual(client.fields(api.clients[0])['apiKey'], api.keys['SABNZBD_API_KEY'])

    def test_test_command_uses_persisted_secret_and_does_not_fix_it(self):
        api = FakeAPIs()
        api.existing()
        next(field for field in api.clients[0]['fields'] if field['name'] == 'apiKey')['value'] = 'STALE-SECRET'
        with self.assertRaises(client.ClientError):
            client.test_existing(api)
        self.assertFalse(any(method == 'PUT' for method, _, _ in api.calls))

    def test_changed_secret_that_does_not_persist_fails_final_test(self):
        api = FakeAPIs()
        api.keep_wrong_secret = True
        with self.assertRaises(client.ClientError):
            client.configure(api)

    def test_duplicate_partial_identity_and_custom_routing_refuse_mutations(self):
        for case in ('duplicate', 'name', 'implementation', 'routing'):
            with self.subTest(case=case):
                api = FakeAPIs()
                api.existing()
                if case == 'duplicate':
                    api.clients.append(copy.deepcopy(api.clients[0]))
                elif case == 'routing':
                    api.clients[0]['categories'] = [{'clientCategory': 'unreviewed'}]
                else:
                    api.clients[0][case] = 'Unexpected'
                with self.assertRaises(client.ClientError):
                    client.configure(api)
                self.assertFalse(any(method in ('POST', 'PUT') or path == 'set_config' for method, path, _ in api.calls))

    def test_conflicting_existing_category_is_preserved_and_refused(self):
        api = FakeAPIs()
        api.categories.append({'name': 'prowlarr', **client.DESIRED_CATEGORY, 'dir': 'custom'})
        with self.assertRaisesRegex(client.ClientError, 'conflicts'):
            client.configure(api)
        self.assertEqual(api.categories[-1]['dir'], 'custom')
        self.assertFalse(any(path == 'set_config' for _, path, _ in api.calls))

    def test_category_creation_refuses_queued_or_processing_jobs(self):
        for name in ('queued', 'processing'):
            with self.subTest(counter=name):
                api = FakeAPIs()
                setattr(api, name, 1)
                with self.assertRaisesRegex(client.ClientError, 'idle'):
                    client.configure(api)
                self.assertFalse(any(method in ('POST', 'PUT') or path == 'set_config' for method, path, _ in api.calls))

    def test_adds_only_docker_hostname_preserves_existing_entries_and_is_idempotent(self):
        api = FakeAPIs()
        api.allowed_hosts = ['existing-container', 'private-service.local']
        report = client.configure(api)
        self.assertTrue(report['hostname_added'])
        self.assertEqual(api.allowed_hosts, ['existing-container', 'private-service.local', 'sabnzbd'])
        self.assertTrue(report['sab_service_name_allowlisted'])
        self.assertNotIn('private-service.local', json.dumps(report))
        api.calls.clear()
        self.assertFalse(client.configure(api)['hostname_added'])
        self.assertFalse(any(path == 'set_config' for _, path, _ in api.calls))

    def test_hostname_addition_refuses_busy_jobs_unsafe_entries_and_failed_readback(self):
        for case in ('busy', 'unsafe', 'ignored'):
            with self.subTest(case=case):
                api = FakeAPIs()
                api.allowed_hosts = ['existing-container']
                if case == 'busy':
                    api.queued = 1
                elif case == 'unsafe':
                    api.allowed_hosts = ['cannot,roundtrip']
                else:
                    api.ignore_hostname_write = True
                with self.assertRaises(client.ClientError):
                    client.configure(api)
                self.assertEqual(api.clients, [])
                if case != 'ignored':
                    self.assertFalse(any(path == 'set_config' for _, path, _ in api.calls))

    def test_failed_candidate_test_never_enables_a_client(self):
        api = FakeAPIs()
        api.fail_test = True
        with self.assertRaises(client.ClientError):
            client.configure(api)
        self.assertEqual(api.clients, [])

    def test_concurrent_client_change_or_ignored_write_is_detected(self):
        api = FakeAPIs()
        api.existing(enable=False)
        api.change_during_test = True
        with self.assertRaisesRegex(client.ClientError, 'inventory_changed'):
            client.configure(api)
        self.assertFalse(any(method == 'PUT' for method, _, _ in api.calls))
        api = FakeAPIs()
        api.ignore_write = True
        with self.assertRaisesRegex(client.ClientError, 'readback'):
            client.configure(api)

    def test_private_api_uses_loopback_header_or_post_and_redacts_errors(self):
        api = client.APIs(FakeAPIs().keys)
        api.opener = mock.Mock()
        api.opener.open.side_effect = urllib.error.URLError('PRIVATE-ERROR secret=VALUE')
        with self.assertRaisesRegex(client.ClientError, '^private_api_request_failed$'):
            api.prowlarr('GET', 'downloadclient')
        request = api.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:9696/api/v1/downloadclient')
        self.assertEqual(request.get_header('X-api-key'), api.keys['PROWLARR_API_KEY'])
        with self.assertRaises(client.ClientError):
            api.sab('version')
        request = api.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:8080/api')
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())['apikey'], [api.keys['SABNZBD_API_KEY']])
        with self.assertRaises(client.ClientError):
            client.NoRedirects().redirect_request()

    def test_protected_keys_reject_duplicate_world_readable_or_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.env'
            path.write_text('SABNZBD_API_KEY=one\nPROWLARR_API_KEY=two\n')
            path.chmod(0o640)
            self.assertEqual(len(client.read_keys(path)), 2)
            path.chmod(0o644)
            with self.assertRaises(client.ClientError):
                client.read_keys(path)
            path.chmod(0o600)
            path.write_text('SABNZBD_API_KEY=one\nSABNZBD_API_KEY=duplicate\n')
            with self.assertRaises(client.ClientError):
                client.read_keys(path)

    def test_main_never_returns_unexpected_exception_or_credentials(self):
        with mock.patch.object(client, 'read_keys', side_effect=RuntimeError('PRIVATE-ERROR')), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as stdout:
            self.assertEqual(client.main(['inspect']), 1)
            self.assertNotIn('PRIVATE-ERROR', stdout.getvalue())
            self.assertNotIn('Traceback', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
