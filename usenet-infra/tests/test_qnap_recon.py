from __future__ import annotations

import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('qnap_recon', Path(__file__).parents[1] / 'scripts/qnap-recon.py')
assert SPEC and SPEC.loader
recon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recon)


def framed(*rows):
    return b''.join(key.encode() + b'\t' + base64.b64encode(value.encode()) + b'\n'
                    for key, value in (*rows, ('complete', 'yes')))


class QnapReconTests(unittest.TestCase):
    def test_deployment_report_excludes_environment_commands_and_mount_sources(self):
        report = recon.parse_output(framed(
            ('deployed_containers', json.dumps({'name': 'dashboard', 'user': '1004:100',
                                                'Env': ['PRIVATE-KEY'], 'Cmd': ['PRIVATE-COMMAND'],
                                                'mounts': [{'source': '/PRIVATE-HOST-PATH', 'target': '/config',
                                                            'writable': False}]})),
            ('dashboard_runtime', '{"uid":1004,"gid":100,"groups":[100],"page_size":4096,"secret":"PRIVATE-KEY"}'),
            ('hybridmount_versions', 'CacheMount\t1.17.5691')))
        self.assertNotIn('PRIVATE-', json.dumps(report))
        self.assertFalse(report['deployed_containers'][0]['docker_socket_mounted'])
        self.assertEqual(report['dashboard_runtime']['groups'], [100])
        self.assertEqual(report['hybridmount_versions'], [{'package': 'CacheMount', 'version': '1.17.5691'}])

    def test_only_selected_docker_metadata_reaches_output(self):
        report = recon.parse_output(framed(
            ('docker_info', json.dumps({'server_version': '27.1.2', 'Env': ['PRIVATE-SECRET']})),
            ('containers', json.dumps({'name': 'service', 'status': 'Up', 'Command': 'PRIVATE-SECRET'})),
            ('container_stats', json.dumps({'name': 'service', 'cpu_percent': '1.25%',
                                           'memory': '2MiB / 4GiB', 'pids': '2',
                                           'Secret': 'PRIVATE-SECRET'})),
            ('container_stats_available', 'yes')))
        self.assertNotIn('PRIVATE-SECRET', json.dumps(report))
        self.assertEqual(report['container_totals'], {'cpu_percent': 1.25, 'memory_used_bytes': 2097152,
                                                    'pids': 2, 'sampled_containers': 1})

    def test_failed_stats_do_not_report_false_zero_usage(self):
        report = recon.parse_output(framed(('docker_info', '{"running_containers":1}'),
                                          ('container_stats_available', 'no')))
        self.assertFalse(report['container_stats_available'])
        self.assertIsNone(report['container_totals'])

    def test_share_names_cannot_inject_an_extra_record(self):
        name = 'share\nuid\tMA=='
        report = recon.parse_output(framed(('uid', '1004'), ('share_name', name),
                                          ('share_path', '/share/data'), ('share_capacity', '100 25 75'),
                                          ('share_ownership', '1004 100 750')))
        self.assertEqual(report['uid'], 1004)
        self.assertEqual(report['shares'][0]['name'], name)
        self.assertEqual(report['shares'][0]['free_bytes'], 76800)

    def test_unframed_banners_unknown_records_and_truncation_are_rejected(self):
        for output in (b'PRIVATE-SECRET\n', framed(('password', 'PRIVATE-SECRET')),
                       framed(('uid', '1004'), ('uid', '0')), b'uid\tMTAwNA==\n'):
            with self.subTest(output=output), self.assertRaises(recon.ReconError):
                recon.parse_output(output)

    def test_dedicated_connection_requires_private_key_and_host_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / 'key'
            pin = Path(directory) / 'known_hosts'
            key.write_text('SYNTHETIC-KEY')
            pin.write_text('SYNTHETIC-HOST-PIN')
            key.chmod(0o600)
            environment = {'QNAP_SSH_TARGET': 'service@nas.local', 'QNAP_SSH_KEY': str(key),
                           'QNAP_SSH_KNOWN_HOSTS': str(pin)}
            command = recon.connection_command(environment)
            for required in ('StrictHostKeyChecking=yes', 'IdentityAgent=none', 'IdentitiesOnly=yes',
                             'PasswordAuthentication=no', 'UserKnownHostsFile=' + str(pin.resolve())):
                self.assertIn(required, command)
            self.assertNotIn('SYNTHETIC-KEY', ' '.join(command))
            key.chmod(0o644)
            with self.assertRaises(recon.ReconError):
                recon.connection_command(environment)
            key.chmod(0o600)
            pin.unlink()
            with self.assertRaises(recon.ReconError):
                recon.connection_command(environment)

    def test_failed_connection_never_prints_raw_diagnostics(self):
        output = io.StringIO()
        result = subprocess.CompletedProcess([], 255, b'PRIVATE-CONFIG', b'Permission denied PRIVATE-SECRET')
        with mock.patch.object(recon, 'connection_command', return_value=['ssh']), \
                mock.patch.object(recon.subprocess, 'run', return_value=result), redirect_stdout(output):
            self.assertEqual(recon.main(), 1)
        self.assertNotIn('PRIVATE-', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error'],
                         'dedicated_qnap_key_authentication_failed_no_fallback_attempted')


if __name__ == '__main__':
    unittest.main()
