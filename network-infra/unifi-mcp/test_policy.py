"""Synthetic policy boundary checks; never access a controller."""

import unittest
from policy import guard, load_policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_every_write_defaults_to_preview(self):
        for name in self.policy["write_tools"]:
            with self.subTest(tool=name):
                self.assertTrue(guard(name, {"site_id": "default"}, self.policy)["dry_run"])

    def test_every_write_requires_confirmation(self):
        for name in self.policy["write_tools"]:
            with self.subTest(tool=name), self.assertRaises(ValueError):
                guard(name, {"site_id": "default", "dry_run": False}, self.policy)

    def test_explicit_apply_is_supported(self):
        args = guard("update_network", {"site_id": "default", "dry_run": False, "confirm": True}, self.policy)
        self.assertFalse(args["dry_run"])
        self.assertEqual(args["controller"], "default")

    def test_invalid_scope_and_ambiguous_flags_are_denied(self):
        for args in ({"site_id": "other"}, {"controller": "other"}, {},
                     {"site_id": "default", "dry_run": "false"},
                     {"site_id": "default", "confirm": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                guard("update_network", args, self.policy)

    def test_unknown_tools_are_denied_even_with_confirmation(self):
        with self.assertRaises(ValueError):
            guard("debug_api_request", {"confirm": True}, self.policy)

    def test_reads_do_not_require_confirmation(self):
        self.assertEqual(guard("health_check", {}, self.policy), {})
