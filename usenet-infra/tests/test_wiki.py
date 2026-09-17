"""Static wiki content, isolation and rollback contract tests."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
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


class WikiContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (WIKI / "index.html").read_text()
        cls.css = (WIKI / "styles.css").read_text()
        cls.parser = WikiParser()
        cls.parser.feed(cls.html)

    def test_local_links_assets_and_fragments_resolve(self):
        for reference in [*self.parser.hrefs, *self.parser.sources]:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            if reference.startswith("#"):
                self.assertIn(reference[1:], self.parser.ids, reference)
                continue
            path = parsed.path
            self.assertTrue((WIKI / path).is_file(), reference)
            if parsed.fragment:
                self.assertIn(parsed.fragment, self.parser.ids, reference)

    def test_external_shortcuts_are_exact_and_never_token_bearing(self):
        external = {href for href in self.parser.hrefs if urlsplit(href).scheme}
        required = {
            "http://10.77.0.1:18080/",
            "http://10.77.0.1:19696/",
            "http://10.77.0.1:19696/radarr/",
            "http://10.77.0.1:19696/sonarr/",
            "http://192.168.1.66:1337/",
            "http://192.168.1.66:32400/web",
            "https://nzbgeek.info/dashboard.php?mycart",
            "https://nzbfinder.ws/cart",
            "https://www.eweka.nl/en/myeweka",
            "https://console.hetzner.com/",
            "https://sabnzbd.org/wiki/introduction/quick-setup",
            "https://wiki.servarr.com/",
            "https://support.plex.tv/articles/",
            "https://docs.hetzner.com/storage/storage-box/",
        }
        self.assertEqual(external, required)
        for href in external:
            self.assertIsNone(re.search(r"(?:api[_-]?key|token|auth|password)=", href, re.I), href)

    def test_explains_required_workflows_boundaries_and_terms(self):
        for phrase in (
            "Use a cart", "Use Radarr or Sonarr", "Canonical library",
            "Temporary scratch", "Local copy", "Backups", "Reference, not live health",
            "Retention", "Completion", "PAR2 repair", "Unpacking", "RSS", "Quality profile",
            "just usenet-cloud-health", "just usenet-cart-import-status",
        ):
            self.assertIn(phrase, self.html)
        self.assertIn("Still needs acceptance", self.html)
        self.assertIn("No live controls", self.html)

    def test_accessibility_and_mobile_contract(self):
        self.assertEqual(self.parser.lang, "en")
        self.assertTrue(self.parser.has_viewport)
        self.assertNotIn("script", self.parser.tags)
        self.assertIn('class="skip-link"', self.html)
        self.assertIn('aria-label="Mobile table of contents"', self.html)
        self.assertIn("a:focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("@media (max-width: 680px)", self.css)

    def test_diagram_and_favicon_are_accessible_valid_svg(self):
        for name in ("ecosystem.svg", "favicon.svg"):
            ET.parse(WIKI / "assets" / name)
        diagram = ET.parse(WIKI / "assets/ecosystem.svg").getroot()
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        self.assertIsNotNone(diagram.find("svg:title", namespace))
        self.assertIsNotNone(diagram.find("svg:desc", namespace))


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
        self.assertIn("qnap_wiki_bind_address == '192.168.1.66'", tasks)
        self.assertIn("qnap_wiki_port | int == 8090", tasks)
        self.assertIn("TCP {{ qnap_wiki_port | int }} belongs to another container", tasks)
        self.assertIn("Preserve the current release environment for rollback", tasks)
        self.assertIn("Restore the previous release or stop the failed first deployment", tasks)
        self.assertIn("down --remove-orphans", tasks)
        self.assertIn("No other QNAP service was changed", tasks)
        self.assertNotIn("docker system prune", tasks)
        self.assertNotIn("compose/qnap", tasks)


if __name__ == "__main__":
    unittest.main()
