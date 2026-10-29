"""Execute the role's rendered shell branches with synthetic local paths."""
import base64
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = yaml.safe_load((ROOT / 'ansible/roles/qnap_filex/tasks/main.yml').read_text())


class NASIdentityTests(unittest.TestCase):
    def render(self, name, **variables):
        source = next(t['ansible.builtin.raw'] for t in TASKS if t['name'].startswith(name))
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters['quote'] = lambda value: shlex.quote(str(value))
        env.filters['b64encode'] = lambda value: base64.b64encode(value.encode()).decode()
        env.globals['lookup'] = lambda kind, path, **kwargs: Path(path).read_text()
        return env.from_string(source).render(**variables)

    def test_named_identity_is_resolved_and_missing_account_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / 'id'
            fake.write_text('#!/bin/sh\ncase "$2" in svc-fixture) echo 1234;; "") echo 1004;; *) exit 1;; esac\n')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'])
            for account, expected in [('', '1004:1004'), ('svc-fixture', '1234:1234')]:
                script = self.render('Resolve the selected', qnap_filex_runtime_account=account)
                result = subprocess.run(['sh', '-c', script], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
            result = subprocess.run(['sh', '-c', self.render('Resolve the selected',
                                    qnap_filex_runtime_account='svc-absent')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_named_prepare_preserves_staging_and_key_modes_without_privileged_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / 'share/FromDrobo/FilexStaging'
            config = root / 'share/Container/usenet/filex-sftp'
            staging.mkdir(parents=True)
            (config / 'keys').mkdir(parents=True)
            (config / 'managed').touch()
            staging.chmod(0o750)
            (config / 'keys').chmod(0o710)
            script = self.render('Prepare only', qnap_filex_runtime_account='svc-fixture',
                                 qnap_filex_runtime_identity={'stdout': '1234:100'},
                                 qnap_docker_command='exit 97 #')
            result = subprocess.run(['sh', '-c', script.replace('/share/', str(root / 'share') + '/')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(staging.stat().st_mode & 0o777, 0o750)
            self.assertEqual((config / 'keys').stat().st_mode & 0o777, 0o710)
            self.assertEqual((config / '.env').read_text(), 'FILEX_NAS_UID=1234\nFILEX_NAS_GID=100\n')

    def test_named_install_preserves_keys_while_default_install_reconciles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'keys').mkdir()
            key = root / 'keys/host_key'
            key.write_text('existing fixture key')
            source = root / 'source'
            source.write_text('replacement fixture key')
            for account, expected in [('svc-fixture', 'existing fixture key'), ('', 'replacement fixture key')]:
                script = self.render('Install dedicated', qnap_filex_runtime_account=account,
                                     item={'source': str(source), 'destination': str(key)})
                result = subprocess.run(['sh', '-c', script], capture_output=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(key.read_text(), expected)


if __name__ == '__main__':
    unittest.main()
