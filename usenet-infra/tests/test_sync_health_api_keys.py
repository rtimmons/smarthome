from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "sync-health-api-keys.py"
SPEC = importlib.util.spec_from_file_location("sync_health_api_keys", MODULE_PATH)
assert SPEC and SPEC.loader
sync_health_api_keys = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync_health_api_keys
SPEC.loader.exec_module(sync_health_api_keys)


class SyncHealthApiKeysTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.sab = root / "sabnzbd.ini"
        self.prowlarr = root / "config.xml"
        self.defaults = root / "catalog.env.defaults"
        self.destination = root / "catalog.env"
        self.sab.write_text(
            "__version__ = 19\n[misc]\napi_key = sab-secret\n", encoding="utf-8"
        )
        self.prowlarr.write_text(
            "<Config><ApiKey>prowlarr-secret</ApiKey></Config>\n", encoding="utf-8"
        )
        self.defaults.write_text(
            "CATALOG_ROLE=cloud\nSABNZBD_API_KEY=\nPROWLARR_API_KEY=\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_renders_generated_keys_without_changing_defaults(self) -> None:
        changed = sync_health_api_keys.render_env(
            self.defaults,
            self.destination,
            {
                "SABNZBD_API_KEY": sync_health_api_keys.sabnzbd_api_key(self.sab),
                "PROWLARR_API_KEY": sync_health_api_keys.prowlarr_api_key(self.prowlarr),
            },
        )
        self.assertTrue(changed)
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"),
            "CATALOG_ROLE=cloud\n"
            "SABNZBD_API_KEY=sab-secret\n"
            "PROWLARR_API_KEY=prowlarr-secret\n",
        )
        self.assertNotIn("secret", self.defaults.read_text(encoding="utf-8"))
        self.assertEqual(os.stat(self.destination).st_mode & 0o777, 0o640)

    def test_second_render_is_idempotent(self) -> None:
        values = {
            "SABNZBD_API_KEY": "sab-secret",
            "PROWLARR_API_KEY": "prowlarr-secret",
        }
        self.assertTrue(
            sync_health_api_keys.render_env(self.defaults, self.destination, values)
        )
        self.assertFalse(
            sync_health_api_keys.render_env(self.defaults, self.destination, values)
        )

    def test_default_changes_replace_stale_values(self) -> None:
        self.destination.write_text(
            "CATALOG_ROLE=old\nSABNZBD_API_KEY=old\nPROWLARR_API_KEY=old\n",
            encoding="utf-8",
        )
        self.defaults.write_text(
            "CATALOG_ROLE=cloud\nSTORAGE_WARN_FRACTION=0.80\n",
            encoding="utf-8",
        )
        sync_health_api_keys.render_env(
            self.defaults,
            self.destination,
            {"SABNZBD_API_KEY": "sab-new", "PROWLARR_API_KEY": "prowlarr-new"},
        )
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"),
            "CATALOG_ROLE=cloud\n"
            "STORAGE_WARN_FRACTION=0.80\n"
            "SABNZBD_API_KEY=sab-new\n"
            "PROWLARR_API_KEY=prowlarr-new\n",
        )

    def test_duplicate_managed_keys_are_removed(self) -> None:
        self.defaults.write_text(
            "SABNZBD_API_KEY=first\nSABNZBD_API_KEY=stale\n",
            encoding="utf-8",
        )
        sync_health_api_keys.render_env(
            self.defaults,
            self.destination,
            {"SABNZBD_API_KEY": "sab-new"},
        )
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"),
            "SABNZBD_API_KEY=sab-new\n",
        )

    def test_unchanged_content_repairs_permissions(self) -> None:
        values = {
            "SABNZBD_API_KEY": "sab-secret",
            "PROWLARR_API_KEY": "prowlarr-secret",
        }
        sync_health_api_keys.render_env(self.defaults, self.destination, values)
        os.chmod(self.destination, 0o644)
        self.assertTrue(
            sync_health_api_keys.render_env(self.defaults, self.destination, values)
        )
        self.assertEqual(os.stat(self.destination).st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
