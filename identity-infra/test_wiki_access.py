import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import check_wiki_access as checks
from check_wiki_access import classify_smb, ssh_denied


class WikiAccessClassification(unittest.TestCase):
    def test_failed_transport_does_not_prompt_or_read_nas_credential(self):
        with patch.object(checks.sys.stdin, 'isatty', return_value=True), \
                patch.object(checks, 'directory_connection', side_effect=RuntimeError('failed')), \
                patch.object(checks.getpass, 'getpass') as password, \
                patch.object(checks, 'password_from_vault', return_value='synthetic'):
            with self.assertRaises(checks.CheckError):
                checks.main()
            password.assert_not_called()

    def test_distinguishes_authenticated_share_denial_from_session_refusal(self):
        self.assertEqual(classify_smb(1, 'tree connect failed: NT_STATUS_ACCESS_DENIED')['phase'],
                         'authenticated-tree-connect')
        self.assertEqual(classify_smb(1, 'session setup failed: NT_STATUS_ACCOUNT_DISABLED')['phase'],
                         'session-setup')

    def test_wrong_password_network_failure_and_success_never_pass(self):
        for code, output in [(1, 'session setup failed: NT_STATUS_LOGON_FAILURE'),
                             (1, 'connection failed: NT_STATUS_IO_TIMEOUT'),
                             (0, 'NT_STATUS_ACCESS_DENIED'), (1, 'access denied'),
                             (1, 'tree connect failed: NT_STATUS_ACCESS_DENIED NT_STATUS_IO_TIMEOUT')]:
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                classify_smb(code, output)

    def test_ssh_requires_login_denial_not_a_failed_connection_or_session(self):
        for code, stdout, stderr, expected in [
            (255, b'', b'Permission denied (publickey,password).', True),
            (255, b'', b'Host key verification failed.', False),
            (255, b'', b'Connection timed out', False),
            (0, b'1005\n', b'', False),
            (255, b'1005\n', b'Permission denied (password).', False),
        ]:
            self.assertEqual(ssh_denied(subprocess.CompletedProcess([], code, stdout, stderr)), expected)

    def test_ssh_secret_is_never_in_argv_and_temporary_files_are_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            hosts = Path(directory)/'hosts'; hosts.write_text('synthetic host pin')
            seen = []
            def run(args, **kwargs):
                self.assertNotIn('synthetic-password', ' '.join(args))
                secret = Path(kwargs['env']['WIKI_CHECK_PASSWORD_FILE'])
                self.assertEqual(secret.read_text(), 'synthetic-password\n')
                self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
                seen.append(secret)
                Path(kwargs['env']['WIKI_CHECK_PROMPT_MARKER']).touch()
                return subprocess.CompletedProcess(args, 255, b'', b'Permission denied (password).')
            with patch.dict(checks.os.environ, {'QNAP_SSH_TARGET':'operator@nas.invalid',
                                               'QNAP_SSH_KNOWN_HOSTS':str(hosts)}), \
                    patch.object(checks.subprocess, 'run', side_effect=run):
                self.assertTrue(checks.ssh_check('synthetic-password')['password_prompted'])
            self.assertFalse(seen[0].exists())


class WikiAccessLatency(unittest.TestCase):
    def test_human_delay_does_not_consume_network_budget(self):
        budget = checks.Budget()
        with patch.object(checks.time, 'monotonic', side_effect=[0, 5, 125, 130]):
            budget.call('before prompt', lambda timeout: None, 10)
            # Two minutes spent entering a password occur outside timed calls.
            observed = budget.call('after prompt', lambda timeout: timeout, 55)
        self.assertEqual(observed, 50)
        self.assertEqual(budget.elapsed, 10)

    def test_total_budget_is_shared_and_expiry_is_inconclusive(self):
        budget = checks.Budget()
        with patch.object(checks.time, 'monotonic', side_effect=[0, 20, 20, 50, 50, 55]):
            limits = []
            for stage in ('first', 'second', 'third'):
                budget.call(stage, lambda limit: limits.append(limit), 40)
        self.assertEqual(limits, [40, 35, 5])
        with self.assertRaisesRegex(checks.CheckError, 'inconclusive'):
            budget.call('too late', lambda _: self.fail('must not run'), 10)
        with patch.object(checks.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE', 1)):
            with self.assertRaisesRegex(checks.CheckError, '^synthetic stage timed out; access result inconclusive$'):
                checks.Budget().run('synthetic stage', ['fixture'], limit=1)
