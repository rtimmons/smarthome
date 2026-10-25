"""SMTP migration must preserve identity keys and never silently lose delivery."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import render_authelia
from pki import require_existing_secrets, require_existing_pki


class AutheliaRecovery(unittest.TestCase):
    def test_missing_external_ca_directory_cannot_replace_the_existing_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, pki = root/'private', root/'pki'
            private.mkdir()
            (private/'ha-cutover.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'restore the identity seal'):
                require_existing_pki(private, pki)
            self.assertFalse(pki.exists())
            paths = [pki/name for name in ('root.key', 'root.crt', 'issuing.key', 'issuing.crt')]
            paths += [private/'tls'/name for name in ('dc.key', 'web.key')]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic existing material')
            require_existing_pki(private, pki)
            for path in paths:
                path.unlink()
                with self.assertRaisesRegex(RuntimeError, 'restore the identity seal'):
                    require_existing_pki(private, pki)
                path.write_text('synthetic existing material')

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
