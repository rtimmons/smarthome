"""Static wiki content, isolation and rollback contract tests."""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
from pathlib import Path
import re
import shlex

import unittest
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from jinja2 import Environment, StrictUndefined
import yaml


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

    def test_wiki_identity_defaults_and_independent_overrides_reach_both_actions(self):
        defaults = yaml.safe_load((ROOT / "ansible/group_vars/all.yml").read_text())
        main = yaml.safe_load(ROLE.read_text())
        publish = yaml.safe_load((ROLE.parent / "publish.yml").read_text())
        render = Environment(undefined=StrictUndefined)
        render.filters["quote"] = shlex.quote
        render.filters["bool"] = bool
        for overrides, expected in [({}, (1004, 100)),
                                    ({"qnap_wiki_uid": 2401}, (2401, 100)),
                                    ({"qnap_wiki_gid": 2402}, (1004, 2402)),
                                    ({"qnap_wiki_uid": 2401, "qnap_wiki_gid": 2402}, (2401, 2402))]:
            with self.subTest(overrides=overrides):
                values = dict(qnap_uid=1004, qnap_gid=100,
                              qnap_wiki_root="/share/Container/usenet/wiki",
                              qnap_docker_config_dir="/fixture/docker-client",
                              qnap_docker_executable="/fixture/docker",
                              qnap_wiki_manifest={"release": "a" * 64})
                for key in ("qnap_wiki_uid", "qnap_wiki_gid"):
                    values[key] = overrides.get(key, render.from_string(defaults[key]).render(values))
                for task in (main[-1], publish[-1]):
                    command = render.from_string(task["ansible.builtin.raw"]).render(values)
                    self.assertIn(f"{expected[0]} {expected[1]} /fixture/docker", command)
                self.assertEqual((values["qnap_uid"], values["qnap_gid"]), (1004, 100))

    def test_wiki_boundary_rejects_root_and_missing_runtime_ids(self):
        tasks = yaml.safe_load(ROLE.read_text())
        checks = tasks[0]["ansible.builtin.assert"]["that"]
        render = Environment(undefined=StrictUndefined)
        checks = [render.compile_expression(check) for check in checks if "uid" in check or "gid" in check]
        for uid, gid, allowed in [(1004, 100, True), (2401, 2402, True),
                                  (0, 100, False), (1004, 0, False),
                                  (None, 100, False), (1004, None, False)]:
            with self.subTest(uid=uid, gid=gid):
                self.assertEqual(all(check(qnap_wiki_uid=uid, qnap_wiki_gid=gid)
                                     for check in checks), allowed)

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
