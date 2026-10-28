"""Verify injected credential boundaries without a gateway or package installs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


LAUNCHER = Path(__file__).with_name("run.sh")
SYNTHETIC_KEY = "synthetic-unifi-fixture-token"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name).resolve()
        launcher_dir = self.root / "network-infra/unifi-mcp"
        launcher_dir.mkdir(parents=True)
        (self.root / ".python-version").write_text("3.14.6\n")
        self.started = self.root / "uvx-started"
        self.uvx = self.root / "uvx"
        self.write_program(self.uvx, """
import json, os, pathlib, sys
pathlib.Path(os.environ['FIXTURE_STARTED']).touch()
print(json.dumps({
    'key_matches': os.environ.get('UNIFI_API_KEY') == os.environ['FIXTURE_EXPECTED'],
    'duplicate_absent': 'UBIQUITI_API_KEY' not in os.environ,
    'debug_absent': 'DEBUG' not in os.environ,
    'database_absent': 'DATABASE_URL' not in os.environ,
    'settings': {k: os.environ.get(k) for k in (
        'UNIFI_API_TYPE', 'UNIFI_LOCAL_HOST', 'UNIFI_PROFILE', 'UNIFI_READ_ONLY',
        'UNIFI_DRY_RUN', 'UNIFI_STDIO_ROLE', 'MCP_SERVER_TRANSPORT',
        'UNIFI_SITE_MANAGER_ENABLED', 'AGNOST_ENABLED', 'SUPERMEMORY_ENABLED',
        'UNIFI_METRICS_ENABLED', 'LOG_API_REQUESTS', 'UV_CACHE_DIR',
        'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR')},
    'cwd': os.getcwd(), 'args': sys.argv[1:],
    'protocol_input_preserved': sys.stdin.read() == 'synthetic-mcp-initialize\\n'
}))
""")
        self.launcher = launcher_dir / "run.sh"
        self.launcher.write_text(
            LAUNCHER.read_text()
            .replace("/opt/homebrew/bin/uvx", str(self.uvx))
        )
        self.environment = {
            "PATH": os.environ["PATH"],
            "FIXTURE_STARTED": str(self.started),
            "FIXTURE_EXPECTED": SYNTHETIC_KEY,
        }

    @staticmethod
    def write_program(path, program):
        path.write_text("#!" + sys.executable + "\n" + program)
        path.chmod(0o700)

    def run_launcher(self, arguments=(), **updates):
        result = subprocess.run(
            ["/bin/bash", "-x", str(self.launcher), *arguments],
            env=self.environment | updates,
            cwd=self.root,
            input="synthetic-mcp-initialize\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotIn(SYNTHETIC_KEY, result.stdout + result.stderr)
        self.assertNotIn("synthetic-unrelated-value", result.stdout + result.stderr)
        return result

    def test_injected_key_mapping_preserves_approval_mode_boundary_and_protocol_input(self):
        result = self.run_launcher(
            UBIQUITI_API_KEY=SYNTHETIC_KEY,
            DEBUG="true",
            DATABASE_URL="synthetic-database-value",
            UNIFI_READ_ONLY="true",
            UNIFI_STDIO_ROLE="viewer",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value["protocol_input_preserved"])
        self.assertTrue(value["key_matches"])
        self.assertTrue(value["duplicate_absent"])
        self.assertTrue(value["debug_absent"])
        self.assertTrue(value["database_absent"])
        self.assertEqual(value["settings"] | {
            "UV_CACHE_DIR": "cache", "UV_TOOL_DIR": "tools", "UV_TOOL_BIN_DIR": "bin",
        }, {
            "UNIFI_API_TYPE": "local", "UNIFI_LOCAL_HOST": "192.168.1.1",
            "UNIFI_PROFILE": "network", "UNIFI_READ_ONLY": "false",
            "UNIFI_DRY_RUN": "false", "UNIFI_STDIO_ROLE": "admin",
            "MCP_SERVER_TRANSPORT": "stdio", "UNIFI_SITE_MANAGER_ENABLED": "false",
            "AGNOST_ENABLED": "false", "SUPERMEMORY_ENABLED": "false",
            "UNIFI_METRICS_ENABLED": "false", "LOG_API_REQUESTS": "false",
            "UV_CACHE_DIR": "cache", "UV_TOOL_DIR": "tools", "UV_TOOL_BIN_DIR": "bin",
        })
        self.assertEqual(value["cwd"], str(self.launcher.parent))
        self.assertEqual(value["settings"]["UV_CACHE_DIR"], str(self.root / "build/unifi-mcp/uv-cache"))
        self.assertEqual(value["settings"]["UV_TOOL_DIR"], str(self.root / "build/unifi-mcp/tools"))
        self.assertEqual(value["settings"]["UV_TOOL_BIN_DIR"], str(self.root / "build/unifi-mcp/bin"))
        self.assertEqual(value["args"], [
            "--python", "3.14.6", "--from",
            "git+https://github.com/enuno/unifi-mcp-server.git@12b4c6e964f920806e2604ab8554e98a4b92536f",
            "python", str(self.launcher.parent / "server.py"),
        ])

    def test_check_uses_the_same_source_and_credential_boundary(self):
        server = self.run_launcher(UBIQUITI_API_KEY=SYNTHETIC_KEY)
        check = self.run_launcher(arguments=("--check",), UBIQUITI_API_KEY=SYNTHETIC_KEY)
        self.assertEqual(check.returncode, 0, check.stderr)
        value = json.loads(check.stdout)
        self.assertTrue(value["key_matches"])
        self.assertEqual(value["args"][:-2], json.loads(server.stdout)["args"][:-2])
        self.assertEqual(value["args"][-2:], ["python", str(self.launcher.parent / "check.py")])

    def test_invalid_arguments_do_not_access_credentials_or_start_server(self):
        result = self.run_launcher(arguments=("--unknown",))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.started.exists())

    def test_missing_key_never_starts_server(self):
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.started.exists())
        self.assertIn("set UBIQUITI_API_KEY", result.stderr)

    def test_multiline_or_blank_export_never_starts_server(self):
        for value in (SYNTHETIC_KEY + "\nextra", "   ", "synthetic token"):
            with self.subTest(value=value):
                result = self.run_launcher(UBIQUITI_API_KEY=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.started.exists())


if __name__ == "__main__":
    unittest.main()
