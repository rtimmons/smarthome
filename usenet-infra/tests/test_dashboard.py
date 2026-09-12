from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('dashboard', SCRIPTS / 'catalog-dashboard.py')
assert spec and spec.loader
dash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dash)


def item(item_id='sample-id', state='remote_only', action='download', **extra):
    return dict(id=item_id, title='Sample book', category='books', size_bytes=10,
                state=state, valid_action=action, error=None, **extra)


class DashboardTests(unittest.TestCase):
    def test_only_current_state_action_is_generated(self):
        data = {'items': [item(), item('local-id', 'local', 'evict'),
                          item('failed-id', 'failed', 'retry'), item('active-id', 'downloading', None)]}
        actions = dash.dashboard_config(data)['actions']
        self.assertCountEqual([a['id'] for a in actions], ['catalog-refresh', 'catalog-download-sample-id',
                         'catalog-evict-local-id', 'catalog-retry-failed-id'])
        self.assertTrue(all('shell' not in a for a in actions))

    def test_bad_local_copy_offers_removal_before_new_download(self):
        actions = dash.dashboard_config({'items': [item(state='failed', action='evict')]})['actions']
        self.assertEqual(actions[1]['id'], 'catalog-evict-sample-id')
        self.assertIn('canonical remote copy will remain', actions[1]['arguments'][0]['title'])

    def test_metadata_cannot_inject_html_yaml_or_go_templates(self):
        record = item()
        record['title'] = '<script>alert(1)</script> ${{ CATALOG_DASHBOARD_PASSWORD_HASH }}'
        record['error'] = '{{ .Env.HOME }} & <img src=x>'
        encoded = json.dumps(dash.dashboard_config({'items': [record]}))
        self.assertNotIn('<script>', encoded)
        self.assertNotIn('{{', encoded)
        self.assertNotIn('<img', encoded)
        self.assertIn('&#123;', encoded)

    def test_actions_keep_stable_identity_when_rows_reorder(self):
        first = dash.dashboard_config({'items': [item('aaa-id'), item('bbb-id')]})
        second = dash.dashboard_config({'items': [item('bbb-id')]})
        prior = next(a for a in first['actions'] if a['id'] == 'catalog-download-bbb-id')
        later = next(a for a in second['actions'] if a['id'] == 'catalog-download-bbb-id')
        self.assertEqual(prior, later)
        self.assertEqual(prior['exec'][-1], 'bbb-id')

    def test_invalid_manifest_id_never_becomes_an_action(self):
        with self.assertRaises(dash.catalogctl.CatalogError):
            dash.dashboard_config({'items': [item('../../unsafe;rm')]})

    def test_failed_refresh_keeps_summary_but_disables_mutation(self):
        data = {'items': [item()], 'remote_items': 1, 'local_reserve_bytes': 20}
        config = dash.dashboard_config(data, 'Remote unavailable')
        self.assertEqual([a['id'] for a in config['actions']], ['catalog-refresh'])
        self.assertIn('Values may be stale', json.dumps(config))

    def test_eviction_requires_server_validated_confirmation(self):
        for confirmation in (None, '0'):
            with mock.patch.object(dash, 'snapshot') as snapshot:
                with self.assertRaises(ValueError):
                    dash.perform_action('evict', 'sample-id', confirmation)
                snapshot.assert_not_called()

    def test_stale_action_does_not_launch_backend(self):
        with mock.patch.object(dash, 'snapshot', return_value={'items': [item(state='local', action='evict')]}), \
                mock.patch.object(dash.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError):
                dash.perform_action('download', 'sample-id', None)
            start.assert_not_called()

    def test_actions_invoke_same_catalog_backend(self):
        with mock.patch.object(dash, 'snapshot', return_value={'items': [item()]}), \
                mock.patch.object(dash, 'refresh'), mock.patch.object(dash.subprocess, 'Popen') as start:
            start.return_value.wait.return_value = 0
            self.assertEqual(dash.perform_action('download', 'sample-id', None), 0)
            self.assertEqual(start.call_args.args[0][-3:], [str(dash.BACKEND), 'pull', 'sample-id'])

    def test_native_and_legacy_actions_keep_source_and_backend_separate(self):
        rows = [item('same-id'), item('same-id', source='native')]
        config = dash.dashboard_config({'items': rows})
        native = next(a for a in config['actions'] if a['id'] == 'native-download-same-id')
        self.assertEqual(native['exec'][-2:], ['--source', 'native'])
        with mock.patch.object(dash, 'snapshot', return_value={'items': rows}), \
                mock.patch.object(dash, 'refresh'), mock.patch.object(dash.subprocess, 'Popen') as start:
            start.return_value.wait.return_value = 0
            self.assertEqual(dash.perform_action('download', 'same-id', None, 'native'), 0)
            self.assertEqual(start.call_args.args[0][-3:], [str(dash.NATIVE_BACKEND), 'pull', 'same-id'])

    def test_stale_native_action_cannot_match_legacy_id(self):
        with mock.patch.object(dash, 'snapshot', return_value={'items': [item('same-id')]}), \
                mock.patch.object(dash.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError):
                dash.perform_action('download', 'same-id', None, 'native')
            start.assert_not_called()

    def test_native_refresh_failure_disables_both_sources(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'CATALOG_DASHBOARD_ROOT': directory}):
            dash.publish({'items': [item(), item('native-id', source='native')]})
            with mock.patch.object(dash, 'backend_snapshot', side_effect=[{'items': [item()]},
                                   dash.catalogctl.CatalogError('Native unavailable')]):
                self.assertFalse(dash.refresh())
            config = json.loads((Path(directory) / 'generated/catalog.yaml').read_text())
            self.assertEqual([a['id'] for a in config['actions']], ['catalog-refresh'])

    def test_combined_snapshot_sums_items_but_not_shared_capacity(self):
        snapshots = [dict(items=[item()], remote_items=1, remote_bytes=10, local_free_bytes=100,
                          local_reserve_bytes=20, recorded_failures=3),
                     dict(items=[item('native-id')], remote_items=1, remote_bytes=30,
                          local_free_bytes=90, local_reserve_bytes=20, recorded_failures=2)]
        with mock.patch.object(dash, 'backend_snapshot', side_effect=snapshots):
            result = dash.snapshot()
        self.assertEqual(result['recorded_failures'], 3)
        self.assertEqual(result['remote_items'], 2)
        self.assertEqual(result['remote_bytes'], 40)
        self.assertEqual(result['local_free_bytes'], 90)
        self.assertEqual(result['local_reserve_bytes'], 20)
        self.assertEqual([i['source'] for i in result['items']], ['legacy', 'native'])

    def test_auth_file_refuses_plaintext_and_group_readable_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'auth.json'
            path.write_text(json.dumps({'username': 'operator', 'password_hash': 'plaintext'}))
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                dash.load_auth(path)
            path.chmod(0o640)
            with self.assertRaises(ValueError):
                dash.load_auth(path)

    def test_startup_log_hashes_are_never_forwarded(self):
        self.assertIsNone(dash.sanitized_log(json.dumps({'level': 'debug', 'msg': 'hash'}), 'hash'))
        self.assertNotIn('private-hash', dash.sanitized_log('{"level":"info","msg":"private-hash"}', 'private-hash'))

    def test_invalid_snapshot_timeout_never_launches_process(self):
        with mock.patch.dict(os.environ, {'CATALOG_DASHBOARD_SNAPSHOT_TIMEOUT': 'bad'}), \
                mock.patch.object(dash.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError):
                dash.snapshot()
            start.assert_not_called()

    def test_timeout_kills_descendants_even_if_parent_has_exited(self):
        with mock.patch.object(dash.subprocess, 'Popen') as start, \
                mock.patch.object(dash.os, 'killpg') as kill:
            start.return_value.pid = 123
            start.return_value.poll.return_value = 0
            start.return_value.communicate.side_effect = [dash.subprocess.TimeoutExpired('status', 1), ('', '')]
            with self.assertRaises(dash.catalogctl.CatalogError):
                dash.snapshot()
            kill.assert_called_once_with(123, dash.signal.SIGKILL)

    def test_runtime_config_keeps_authentication_and_stable_actions(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {
            'CATALOG_DASHBOARD_ROOT': directory,
            'CATALOG_DASHBOARD_CONFIG_TEMPLATE': str(SCRIPTS.parent / 'compose/qnap/olivetin/config.yaml'),
        }):
            dash.publish({'items': [item()]})
            config = json.loads((Path(directory) / 'runtime/config.yaml').read_text())
            self.assertTrue(config['authRequireGuestsToLogin'])
            self.assertFalse(config['defaultPermissions']['exec'])
            self.assertIn('CATALOG_DASHBOARD_PASSWORD_HASH', config['authLocalUsers']['users'][0]['password'])
            self.assertEqual(config['actions'][1]['id'], 'catalog-download-sample-id')

    def test_atomic_publish_writes_valid_yaml_subset_and_status(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'CATALOG_DASHBOARD_ROOT': directory}):
            dash.publish({'items': [item()]})
            config = json.loads((Path(directory) / 'generated/catalog.yaml').read_text())
            self.assertEqual(config['dashboards'][0]['title'], 'Catalog')
            status = json.loads((Path(directory) / 'status.json').read_text())
            self.assertIsNone(status['error'])
            self.assertEqual(status['snapshot']['items'][0]['id'], 'sample-id')


if __name__ == '__main__':
    unittest.main()
