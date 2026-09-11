from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_catalogctl import catalogctl


SPEC = importlib.util.spec_from_file_location(
    "healthcheck", Path(__file__).parents[1] / "scripts" / "healthcheck.py"
)
assert SPEC and SPEC.loader
healthcheck = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = healthcheck
SPEC.loader.exec_module(healthcheck)


class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.env = mock.patch.dict(os.environ, {
            "CATALOG_REMOTE": "storage:catalog",
            "CATALOG_STATE_ROOT": str(self.base / "state"),
            "CATALOG_STAGING_ROOT": str(self.base / "staging"),
            "CATALOG_DASHBOARD_STATUS_PATH": str(self.base / "dashboard.json"),
        })
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_resolved_failures_remain_auditable_without_failing_health(self) -> None:
        settings = catalogctl.Settings.from_env()
        catalogctl.record_failure(settings, "pull", "authorized-test", ValueError("checksum failed"))
        check = healthcheck.failure_check()
        self.assertEqual(check.status, "fail")
        self.assertIn("1 unresolved failure", check.detail)
        self.assertNotIn("checksum failed", check.detail)
        catalogctl.resolve_failures(settings, "authorized-test")
        self.assertEqual(healthcheck.failure_check().status, "ok")
        self.assertEqual(len(list((settings.state_root / "failures").glob("*.json"))), 1)

    def test_abandoned_operation_fails_transfer_health(self) -> None:
        settings = catalogctl.Settings.from_env()
        catalogctl.atomic_json(settings.state_root / "operations" / "authorized-test.json", {
            "id": "operation-id", "item": "authorized-test", "operation": "pull", "status": "running"
        })
        check = healthcheck.qnap_transfer_check()
        self.assertEqual(check.status, "fail")
        self.assertIn("1 failed or stalled", check.detail)

    def test_active_operation_is_healthy(self) -> None:
        settings = catalogctl.Settings.from_env()
        fake = SimpleNamespace(lock_fds=())
        with catalogctl.cache_lock(settings, fake) as lock:
            with catalogctl.cache_operation(settings, "pull", "authorized-test", lock):
                check = healthcheck.qnap_transfer_check()
                self.assertEqual(check.status, "ok")
                self.assertIn("1 active", check.detail)

    def test_untracked_partial_is_interrupted(self) -> None:
        (self.base / "staging" / "authorized-test.partial").mkdir(parents=True)
        check = healthcheck.qnap_transfer_check()
        self.assertEqual(check.status, "fail")
        self.assertIn("interrupted staging", check.detail)

    def test_dashboard_readiness_does_not_claim_authentication_was_verified(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        with mock.patch.dict(os.environ, {"QNAP_DASHBOARD_HEALTH_URL": "http://dashboard:1337/api/GetReadyz"}):
            with mock.patch.object(healthcheck, "open_request", return_value=response):
                check = healthcheck.dashboard_check()
        self.assertEqual(check.status, "ok")
        self.assertIn("separate acceptance test", check.detail)

    def test_dashboard_unreachable_fails(self) -> None:
        with mock.patch.dict(os.environ, {"QNAP_DASHBOARD_HEALTH_URL": "http://dashboard:1337/api/GetReadyz"}):
            with mock.patch.object(healthcheck, "open_request", side_effect=OSError("connection refused")):
                self.assertEqual(healthcheck.dashboard_check().status, "fail")

    def test_refresh_heartbeat_reports_errors_and_staleness(self) -> None:
        path = self.base / "dashboard.json"
        self.assertEqual(healthcheck.dashboard_data_check().status, "fail")
        path.write_text(json.dumps({"updated_at": time.time(), "error": None, "snapshot": {}}))
        self.assertEqual(healthcheck.dashboard_data_check().status, "ok")
        path.write_text(json.dumps({"updated_at": time.time() - 1000, "error": None, "snapshot": {}}))
        self.assertIn("stale", healthcheck.dashboard_data_check().detail)
        path.write_text(json.dumps({"updated_at": time.time(), "error": "Storage Box unavailable", "snapshot": {}}))
        check = healthcheck.dashboard_data_check()
        self.assertEqual(check.status, "fail")
        self.assertIn("catalog refresh failed", check.detail)
        self.assertNotIn("Storage Box unavailable", check.detail)

    def test_sab_key_is_in_post_body_and_prowlarr_key_stays_in_header(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{}'
        with mock.patch.object(healthcheck, "open_request", return_value=response) as send:
            healthcheck.get_json("http://127.0.0.1:8080/api", form={"mode": "warnings", "apikey": "private-sab-key"})
            sab = send.call_args.args[0]
            self.assertEqual(sab.get_method(), "POST")
            self.assertEqual(sab.full_url, "http://127.0.0.1:8080/api")
            self.assertEqual(urllib.parse.parse_qs(sab.data.decode())["apikey"], ["private-sab-key"])
            healthcheck.get_json("http://127.0.0.1:9696/api/v1/health", headers={"X-Api-Key": "private-prowlarr-key"})
            prowlarr = send.call_args.args[0]
            self.assertEqual(prowlarr.get_header("X-api-key"), "private-prowlarr-key")
            self.assertIsNone(prowlarr.data)
            self.assertNotIn("private", prowlarr.full_url)

    def test_authenticated_requests_disable_environment_proxies_and_redirects(self) -> None:
        request = healthcheck.urllib.request.Request("http://127.0.0.1:8080/api", data=b"apikey=private")
        with mock.patch.object(healthcheck.urllib.request, "build_opener") as build:
            healthcheck.open_request(request)
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsNone(handlers[1].redirect_request(request, None, 302, "private", {}, "https://elsewhere.invalid"))
        build.return_value.open.assert_called_once_with(request, timeout=10)

    def test_raw_application_messages_states_and_versions_never_reach_report(self) -> None:
        secret = "private-app-key-and-title"
        with mock.patch.dict(os.environ, {"SABNZBD_API_KEY": secret, "PROWLARR_API_KEY": secret}):
            for warning_type, expected in [("ERROR", "fail"), ("CRITICAL", "fail"), ("WARNING", "warn")]:
                with self.subTest(warning_type=warning_type), mock.patch.object(healthcheck, "get_json", side_effect=[
                    {"status": {"status": secret}}, {"warnings": [{"type": warning_type, "text": secret}]},
                    {"version": secret}, [{"type": "warning", "message": secret, "wikiUrl": "https://example.invalid/?apikey=" + secret}],
                ]):
                    checks = healthcheck.app_checks()
                self.assertEqual([check.status for check in checks], [expected, "fail"])
                self.assertNotIn(secret, repr(checks))
            with mock.patch.object(healthcheck, "get_json", side_effect=[
                {"status": {"status": secret}}, {"warnings": []}, {"version": secret}, [],
            ]):
                checks = healthcheck.app_checks()
            self.assertEqual([check.status for check in checks], ["ok", "ok"])
            self.assertNotIn(secret, repr(checks))

    def test_request_failures_hide_url_credentials_body_and_reason(self) -> None:
        secret = "private-http-key"
        with mock.patch.dict(os.environ, {"SABNZBD_API_KEY": secret, "PROWLARR_API_KEY": secret}):
            for failure in [
                urllib.error.HTTPError("https://example.invalid/?apikey=" + secret, 403, secret, {}, io.BytesIO(secret.encode())),
                urllib.error.URLError("https://username:" + secret + "@example.invalid"),
                ValueError(secret), OSError(secret), RuntimeError(secret),
            ]:
                with self.subTest(failure=type(failure).__name__), mock.patch.object(healthcheck, "get_json", side_effect=failure):
                    checks = healthcheck.app_checks()
                self.assertEqual([check.status for check in checks], ["fail", "fail"])
                self.assertNotIn(secret, repr(checks))

    def test_malformed_app_payloads_fail_closed_without_tracebacks(self) -> None:
        with mock.patch.dict(os.environ, {"SABNZBD_API_KEY": "private", "PROWLARR_API_KEY": "private"}):
            for payload in [None, [], {"status": False, "error": "private"}]:
                with mock.patch.object(healthcheck, "get_json", return_value=payload):
                    checks = healthcheck.app_checks()
                self.assertEqual([check.status for check in checks], ["fail", "fail"])
                self.assertNotIn("private", repr(checks))

    def test_rclone_errors_never_echo_command_url_or_stderr(self) -> None:
        secret = "private-storage-password"
        failure = healthcheck.subprocess.CalledProcessError(1, ["rclone", "about", ":sftp,pass=" + secret + ":"], stderr=secret)
        with mock.patch.object(healthcheck.subprocess, "run", side_effect=[failure, mock.Mock(returncode=0)]) as run:
            check = healthcheck.storage_check()
        self.assertEqual(check.status, "warn")
        self.assertNotIn(secret, repr(check))
        self.assertTrue(all(call.kwargs["timeout"] == 60 for call in run.call_args_list))
        with mock.patch.object(healthcheck.subprocess, "run", side_effect=failure):
            check = healthcheck.storage_check()
        self.assertEqual(check.status, "fail")
        self.assertNotIn(secret, repr(check))

    def test_catalog_and_dashboard_failures_hide_record_content(self) -> None:
        secret = "private-token-title-and-path"
        settings = catalogctl.Settings.from_env()
        catalogctl.record_failure(settings, "pull", secret, ValueError(secret))
        self.assertNotIn(secret, repr(healthcheck.failure_check()))
        catalogctl.atomic_json(settings.state_root / "operations" / "authorized-test.json", {
            "id": "operation-id", "item": secret, "operation": "pull", "status": "failed", "error": secret,
        })
        self.assertNotIn(secret, repr(healthcheck.qnap_transfer_check()))
        (self.base / "dashboard.json").write_text(json.dumps({"updated_at": time.time(), "error": secret}))
        self.assertNotIn(secret, repr(healthcheck.dashboard_data_check()))
        with mock.patch.dict(os.environ, {"QNAP_DASHBOARD_HEALTH_URL": "https://example.invalid/?key=" + secret}):
            with mock.patch.object(healthcheck, "open_request", side_effect=ValueError(secret)):
                self.assertNotIn(secret, repr(healthcheck.dashboard_check()))

    def test_text_and_json_output_hide_unexpected_exceptions_and_environment_values(self) -> None:
        secret = "private-environment-value"
        for args in [[], ["--json"]]:
            with self.subTest(args=args), mock.patch.object(sys, "argv", ["healthcheck", *args]):
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors), mock.patch.object(healthcheck, "collect_checks", side_effect=ValueError(secret)):
                    self.assertEqual(healthcheck.main(), 1)
                self.assertNotIn(secret, output.getvalue() + errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())
                if args:
                    self.assertEqual(json.loads(output.getvalue())[0]["status"], "fail")
        with mock.patch.dict(os.environ, {"CATALOG_ROLE": secret}), mock.patch.object(healthcheck, "storage_check"), mock.patch.object(healthcheck, "failure_check"):
            self.assertNotIn(secret, healthcheck.collect_checks()[-1].detail)

    def test_cloud_health_loads_with_older_catalog_without_qnap_operation_records(self) -> None:
        older_catalog = SimpleNamespace(
            CatalogError=catalogctl.CatalogError,
            Settings=catalogctl.Settings,
            read_json_records=catalogctl.read_json_records,
        )
        spec = importlib.util.spec_from_file_location("healthcheck_legacy_catalog", SPEC.origin)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"catalogctl": older_catalog, spec.name: module}):
            spec.loader.exec_module(module)
            with mock.patch.dict(os.environ, {
                "CATALOG_ROLE": "cloud", "CATALOG_PROMOTION_ROOT": str(self.base / "complete"),
                "SCRATCH_MIN_FREE_BYTES": "0", "SABNZBD_API_KEY": "", "PROWLARR_API_KEY": "",
            }), mock.patch.object(module, "storage_check", return_value=module.Check("storage_box", "ok", "reachable")):
                checks = module.collect_checks()
            self.assertNotIn("fail", [check.status for check in checks])
            self.assertIn("catalog_failures", [check.name for check in checks])
            self.assertNotIn("qnap_transfers", [check.name for check in checks])
            qnap = module.qnap_transfer_check()
            self.assertEqual(qnap.status, "fail")
            self.assertIn("must be updated", qnap.detail)


if __name__ == "__main__":
    unittest.main()
