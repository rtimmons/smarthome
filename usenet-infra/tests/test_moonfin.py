import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('moonfin', Path(__file__).resolve().parents[1] / 'scripts/moonfin-login.py')
moonfin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(moonfin)


class SessionBindingTests(unittest.TestCase):
    def test_reconciles_only_metadata_and_preserves_session_cookie(self):
        uid = '11111111-1111-1111-1111-111111111111'
        session = {'jellyfinUserId': uid, 'seerrUserId': 2, 'permissions': 0,
                   'sessionCookie': 'synthetic-cookie'}
        user = {'id': 2, 'permissions': 160, 'displayName': 'Fixture User'}
        result = moonfin.reconcile_session(session, uid, user, 2)
        self.assertEqual(result['permissions'], 160)
        self.assertEqual(result['sessionCookie'], session['sessionCookie'])
        self.assertEqual(session['permissions'], 0)
        for changed in ({**user, 'id': 3}, {**user, 'permissions': 2}):
            with self.assertRaises(ValueError):
                moonfin.reconcile_session(session, uid, changed, 2)
        with self.assertRaises(ValueError):
            moonfin.reconcile_session(session, '22222222-2222-2222-2222-222222222222', user, 2)
