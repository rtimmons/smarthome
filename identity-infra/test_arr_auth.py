import unittest
from arr_auth_remote import external_config


class ArrSettings(unittest.TestCase):
    def test_only_authentication_element_changes_and_repeat_is_identical(self):
        source=b'<Config>\n<ApiKey>synthetic-existing-key</ApiKey>\n<AuthenticationMethod>Forms</AuthenticationMethod>\n<Password>synthetic-saved-password</Password><UrlBase></UrlBase>\n</Config>'
        result=external_config(source)
        self.assertEqual(result,source.replace(b'>Forms<',b'>External<'))
        self.assertEqual(external_config(result),result)

    def test_missing_key_or_unexpected_mode_is_refused(self):
        for source in (b'<Config><AuthenticationMethod>Forms</AuthenticationMethod></Config>',
                       b'<Config><ApiKey>synthetic</ApiKey><AuthenticationMethod>None</AuthenticationMethod></Config>'):
            with self.assertRaises(RuntimeError): external_config(source)
