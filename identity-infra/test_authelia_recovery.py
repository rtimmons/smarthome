"""SMTP migration must preserve identity keys and never silently lose delivery."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import render_authelia
from pki import require_existing_secrets


class AutheliaRecovery(unittest.TestCase):
    def test_certificate_renewal_cannot_regenerate_lost_identity_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            (private/'ha-cutover.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'restore it before certificate renewal'):
                require_existing_secrets(private)
            self.assertFalse((private/'secrets').exists())

    def test_smtp_transition_preserves_identity_and_refuses_missing_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            (private/'tls').mkdir()
            (private/'tls/ca.crt').write_text('synthetic CA fixture')
            secrets = private/'secrets'
            secrets.mkdir()
            for name in ('oidc-hmac', 'forgejo-client-id', 'oidc-rsa.pem',
                         'forgejo-client-digest', 'ldap-bind', 'session', 'storage'):
                (secrets/name).write_text('synthetic fixture '+name)
            with patch.object(render_authelia, 'PRIVATE', private), contextlib.redirect_stdout(io.StringIO()):
                render_authelia.main()
                target = private/'authelia-seed/configuration.json'
                initial = json.loads(target.read_text())
                smtp_path = secrets/'gmail-smtp.json'
                smtp_path.write_text(json.dumps({'username': 'fixture@gmail.com', 'password': 'synthetic fixture'}))
                render_authelia.main()
                configured = json.loads(target.read_text())
                expected = dict(initial)
                expected['notifier'] = configured['notifier']
                self.assertEqual(configured, expected)
                notifier = configured['notifier']
                self.assertNotIn('filesystem', notifier)
                self.assertFalse(notifier['disable_startup_check'])
                self.assertFalse(notifier['smtp']['tls']['skip_verify'])
                before = target.read_bytes()
                render_authelia.main()
                self.assertEqual(target.read_bytes(), before)
                smtp_path.unlink()
                with self.assertRaisesRegex(RuntimeError, 'Restore the existing SMTP credential'):
                    render_authelia.main()
                self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
