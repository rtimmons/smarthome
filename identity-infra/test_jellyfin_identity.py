"""A failed external-login verification must leave the existing account usable."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import migrate_jellyfin as migration


class JellyfinMigration(unittest.TestCase):
    def test_wrong_external_account_rolls_back_without_overwriting_operator_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root/'private'
            (private/'secrets').mkdir(parents=True)
            operator = root/'usenet-infra/secrets/jellyfin/operator.json'
            operator.parent.mkdir(parents=True)
            operator.write_text(json.dumps({'username':'ryan','password':'synthetic-local-password'}))
            original_bytes = operator.read_bytes()
            user_id = '11111111111111111111111111111111'
            recovery_id = '22222222222222222222222222222222'
            original_policy = {'IsAdministrator': True, 'IsDisabled': False,
                'EnableAllFolders': False, 'EnabledFolders': ['synthetic-library'],
                'AuthenticationProviderId': 'Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider',
                'PasswordResetProviderId': 'synthetic-original-reset-provider'}
            (private/'jellyfin-pre-ad-receipt.json').write_text(json.dumps({'user_id':user_id}))
            (private/'secrets/jellyfin-ldap.json').write_text(json.dumps({'password':'synthetic-bind'}))
            (private/'secrets/jellyfin-recovery.json').write_text(json.dumps({
                'username':'smarthome-recovery','password':'synthetic-recovery','user_id':recovery_id}))
            (private/'human-logins.json').write_text(json.dumps({'users':[{
                'username':'ryantimmons','initial_password':'synthetic-ad'}]}))
            policy = copy.deepcopy(original_policy)
            writes = []

            class FakeClient:
                def __init__(self, credential):
                    self.name = credential['username']
                    self.user = {'User': {'Policy': {'IsAdministrator': True}}}
                def logout(self): pass
                def call(self, path, data=None, method=None):
                    if path == '/Users/Me':
                        return {'Id': ('33333333333333333333333333333333'
                                       if self.name == 'ryantimmons' else user_id),
                                'Name':'ryan','Policy':copy.deepcopy(policy)}
                    if path == '/Sessions': return []
                    if path == '/Plugins':
                        return [{'Id':migration.PLUGIN.replace('-',''),'Version':'24.0.0.0','Status':'Active'}]
                    if path.endswith('/Configuration'): return {} if data is None else None
                    if path == '/Ldap/TestServerBind':
                        return {'Connect':'Success','Bind':'Success','BaseSearch':'Found 3 Entities'}
                    if path == '/Users':
                        return [{'Id':recovery_id,'Name':'smarthome-recovery','Policy':copy.deepcopy(original_policy)}]
                    if path == '/Users/'+recovery_id+'/Policy': return None
                    if path == '/Users/'+user_id+'/Policy':
                        writes.append(copy.deepcopy(data)); policy.clear(); policy.update(data); return None
                    raise AssertionError('Unexpected operation: '+path)

            with patch.object(migration,'ROOT',root), patch.object(migration,'PRIVATE',private), \
                    patch.object(migration,'Client',FakeClient), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(AssertionError): migration.main()
            self.assertEqual(len(writes),2)
            self.assertEqual(writes[0]['AuthenticationProviderId'],migration.PROVIDER)
            self.assertEqual(writes[1],original_policy)
            self.assertEqual(policy,original_policy)
            self.assertEqual(operator.read_bytes(),original_bytes)
            self.assertFalse((private/'jellyfin-ad-receipt.json').exists())

    def test_logout_only_accepts_already_invalidated_session(self):
        client = object.__new__(migration.Client)
        with patch.object(client,'call',side_effect=urllib.error.HTTPError('https://fixture.invalid',401,'expired',{},None)):
            client.logout()
        with patch.object(client,'call',side_effect=urllib.error.HTTPError('https://fixture.invalid',500,'failed',{},None)):
            with self.assertRaises(urllib.error.HTTPError): client.logout()
