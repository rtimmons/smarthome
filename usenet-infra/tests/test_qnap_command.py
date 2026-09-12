from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

COMMAND = Path(__file__).parents[1] / 'scripts/qnap-command'


class QnapCommandTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        binary = root / 'bin'
        binary.mkdir()
        (binary / 'ssh').write_text('#!/bin/sh\nfor argument; do remote=$argument; done\nexec /bin/sh -c "$remote"\n')
        (binary / 'docker').write_text('''#!/usr/bin/env python3
import json, os, sys
print(json.dumps({'argv': sys.argv[1:], 'config': os.environ.get('DOCKER_CONFIG'),
                  'buildx': os.environ.get('BUILDX_CONFIG'),
                  'ansi': os.environ.get('COMPOSE_ANSI'),
                  'progress': os.environ.get('BUILDKIT_PROGRESS')}))
''')
        for path in binary.iterdir():
            path.chmod(0o700)
        project = root / "custom project 'quoted'"
        project.mkdir()
        client = project / 'private-client'
        client.mkdir(mode=0o700)
        environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                           QNAP_SSH_TARGET='fixture@nas.invalid', QNAP_SSH_KEY='unused-fixture-key',
                           QNAP_SSH_KNOWN_HOSTS='unused-fixture-pin', QNAP_PROJECT_DIR=str(project),
                           QNAP_DOCKER_CONFIG_DIR=str(client))
        return environment, client

    def test_cli_passes_scoped_state_and_plain_output_to_remote_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            environment, client = self.fixture(directory)
            result = subprocess.run(['/bin/bash', str(COMMAND), 'status'], env=environment,
                                    text=True, capture_output=True, check=True)
            report = json.loads(result.stdout)
            self.assertEqual(report['config'], str(client))
            self.assertEqual(report['buildx'], str(client / 'buildx'))
            self.assertEqual(report['ansi'], 'never')
            self.assertEqual(report['progress'], 'plain')
            self.assertEqual(report['argv'], ['--config', str(client), 'compose', '--ansi', 'never',
                                             '--progress', 'plain', 'run', '--rm', 'catalog', 'catalog-status'])

    def test_native_commands_preserve_exact_item_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            environment, _ = self.fixture(directory)
            for command in ('native-list', 'native-status', 'native-pull', 'native-evict'):
                with self.subTest(command=command):
                    result = subprocess.run(['/bin/bash', str(COMMAND), command, "native-title;$(false)'quoted"],
                                            env=environment, text=True, capture_output=True, check=True)
                    report = json.loads(result.stdout)
                    self.assertEqual(report['argv'][-2:], [command, "native-title;$(false)'quoted"])

    def test_missing_application_client_directory_refuses_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            environment, client = self.fixture(directory)
            client.rmdir()
            result = subprocess.run(['/bin/bash', str(COMMAND), 'status'], env=environment,
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(client.exists())
            self.assertEqual(result.stdout, '')
            self.assertIn('missing or unwritable', result.stderr)


if __name__ == '__main__':
    unittest.main()
