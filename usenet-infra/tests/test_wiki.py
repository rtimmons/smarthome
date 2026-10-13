"""Static wiki content, isolation and rollback contract tests."""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
ROLE = ROOT / "ansible/roles/qnap_wiki/tasks/main.yml"


class WikiParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.sources: list[str] = []
        self.tags: list[str] = []
        self.lang = ""
        self.has_viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.lang = values.get("lang", "") or ""
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"] or "")
        if tag in {"img", "script"} and values.get("src"):
            self.sources.append(values["src"] or "")
        if tag == "link" and values.get("href"):
            self.sources.append(values["href"] or "")
        if tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = True


class WikiDeploymentTests(unittest.TestCase):
    def test_compose_is_pinned_non_root_and_mounts_only_static_inputs(self):
        compose = (WIKI / "compose.yaml").read_text()
        for required in (
            "usenet-wiki:caddy-2.11.4-nonroot",
            'user: "${WIKI_UID:?Set the dedicated NAS UID}:${WIKI_GID:?Set the dedicated NAS GID}"',
            "read_only: true", "cap_drop:", "- ALL", "no-new-privileges:true",
            "create_host_path: false", "${WIKI_BIND_ADDRESS", "${WIKI_PORT:-8090}:8090",
        ):
            self.assertIn(required, compose)
        for forbidden in ("docker.sock", "privileged:", "/share/FromDrobo", "/library", "/run/secrets"):
            self.assertNotIn(forbidden, compose)
        self.assertEqual((WIKI / ".dockerignore").read_text().splitlines(),
                         ["**", "!Dockerfile", "!.dockerignore"])

    def test_caddy_has_no_admin_tls_logging_or_dynamic_backend(self):
        config = (WIKI / "Caddyfile").read_text()
        for required in ("admin off", "auto_https off", "persist_config off", "output discard", "file_server"):
            self.assertIn(required, config)
        for forbidden in ("reverse_proxy", "php_fastcgi", "cgi", "basicauth", "basic_auth"):
            self.assertNotIn(forbidden, config)

    def test_role_is_scoped_and_rolls_back_a_failed_candidate(self):
        tasks = ROLE.read_text()
        helper = (ROOT.parent / "wiki/apply.sh").read_text()
        self.assertIn("qnap_wiki_bind_address == '192.168.1.66'", tasks)
        self.assertIn("qnap_wiki_port | int == 8090", tasks)
        self.assertIn(".env.rollback", helper)
        self.assertIn("down --remove-orphans", helper)
        self.assertIn("No other QNAP service was changed", helper)
        self.assertNotIn("docker system prune", helper)
        self.assertNotIn("compose/qnap", helper)


if __name__ == "__main__":
    unittest.main()
