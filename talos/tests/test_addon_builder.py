from __future__ import annotations

import json

from rich.console import Console

from talos import addon_builder
from talos.timing import DeployTimer
import pytest


def test_discover_addons_finds_known_services():
    addons = addon_builder.discover_addons()
    # Expect our core add-ons to be present; this guards against path mistakes.
    for name in ("grid-dashboard", "sonos-api", "mongodb", "printer"):
        assert name in addons


def test_build_context_reads_runtime_versions():
    addons = addon_builder.discover_addons()
    first = next(iter(addons.keys()))
    ctx = addon_builder.build_context(first, addons)
    addon = ctx["addon"]
    assert "node_version" in addon and addon["node_version"]
    assert "python_version" in addon and addon["python_version"]


def test_build_context_supports_per_addon_node_version():
    addons = addon_builder.discover_addons()
    ctx = addon_builder.build_context("node-sonos-http-api", addons)
    assert ctx["addon"]["node_version"] == "22.21.1"
    assert ctx["addon"]["node_major"] == "22"


def test_generated_mongodb_configuration_is_system_cold_backup():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("mongodb", addons)
    rendered = addon_builder.render_template(
        addon_builder.jinja_env(), "config.yaml.j2", context
    )
    assert "startup: system" in rendered
    assert "backup: cold" in rendered


def test_generated_configuration_supports_backup_hooks_and_excludes():
    addons = addon_builder.discover_addons()
    addons["printer"] = {
        **addons["printer"],
        "backup": "hot",
        "backup_pre": "echo pre",
        "backup_post": "echo post",
        "backup_exclude": ["cache", "tmp/*"],
    }
    context = addon_builder.build_context("printer", addons)
    rendered = addon_builder.render_template(
        addon_builder.jinja_env(), "config.yaml.j2", context
    )
    assert "backup: hot" in rendered
    assert 'backup_pre: "echo pre"' in rendered
    assert 'backup_post: "echo post"' in rendered
    assert "- cache" in rendered
    assert "- tmp/*" in rendered


def test_cold_backup_rejects_hot_backup_hooks():
    addons = addon_builder.discover_addons()
    addons["mongodb"] = {**addons["mongodb"], "backup_pre": "unsafe"}
    with pytest.raises(Exception, match="cannot combine"):
        addon_builder.build_context("mongodb", addons)


def test_remote_deploy_script_uses_quiet_wrapper_without_fixed_reload_sleep():
    script = addon_builder.render_remote_deploy_script(
        slug="grid_dashboard",
        remote_tar="/root/grid_dashboard.tar.gz",
        remote_addon_dir="/addons/grid_dashboard",
        remote_addons_dir="/addons",
        verbose=False,
        health_port=3000,
        health_path="/",
    )

    assert 'VERBOSE="false"' in script
    assert 'run_metric "remote.reload" reload_addons' in script
    assert 'run_metric "remote.stop" run_quiet ha apps stop' in script
    assert 'run_metric "remote.rebuild" run_quiet ha apps rebuild' in script
    assert "__TALOS_METRIC__" in script
    assert 'ha --raw-json apps info "$ADDON_ID"' in script
    assert 'http://supervisor/addons/"$ADDON_ID"/options' in script
    assert "HEALTH_PORT=3000" in script
    assert "HEALTH_PATH=/" in script
    assert "READINESS_ATTEMPTS=60" in script
    assert 'run_metric "remote.state" wait_for_started' in script
    assert 'run_metric "remote.readiness" wait_for_readiness' in script
    assert ".data.ip_address" in script
    assert '"http://${curl_host}:${HEALTH_PORT}${HEALTH_PATH}"' in script
    assert 'nc -z -w 2 "$addon_ip" "$HEALTH_PORT"' in script
    assert '${HEALTH_PATH}" 2>/dev/null' in script
    assert "127.0.0.1" not in script
    assert "Readiness probe exhausted retries at $LAST_HEALTH_TARGET" in script
    assert "sleep 2" not in script
    assert "need_port_mapping" not in script


def test_remote_metrics_are_recorded_and_hidden():
    timer = DeployTimer(Console(), enabled=True)
    visible = addon_builder._record_remote_metrics(
        "before\n__TALOS_METRIC__\tremote.stop\t1000\t1250\tok\nafter\n",
        "grid-dashboard",
        timer,
    )

    assert visible == "before\nafter"
    assert timer.events[0]["name"] == "addon.remote.stop"
    assert timer.events[0]["seconds"] == 0.25
    assert timer.events[0]["addon"] == "grid-dashboard"


def test_generated_dockerfile_caches_dependencies_before_source():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("grid-dashboard", addons)
    dockerfile = addon_builder.render_template(
        addon_builder.jinja_env(), "Dockerfile.j2", context
    )

    dependency_copy = "COPY app/package.json app/package-lock.json"
    source_copy = "COPY app/ /opt/grid-dashboard/app/"
    assert dockerfile.index(dependency_copy) < dockerfile.index("RUN npm ci")
    assert dockerfile.index("RUN npm ci") < dockerfile.index(source_copy)


def test_git_cloned_addons_require_an_immutable_ref_and_frozen_install():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("node-sonos-http-api", addons)
    dockerfile = addon_builder.render_template(
        addon_builder.jinja_env(), "Dockerfile.j2", context
    )

    ref = "3776f0ee2261c924c7b7204de121a38100a08ca7"
    assert context["addon"]["git_clone"]["ref"] == ref
    assert f"git checkout --detach {ref}" in dockerfile
    assert 'test "$(git rev-parse HEAD)" =' in dockerfile
    assert "npm ci --omit=dev" in dockerfile
    assert "npm install --production" not in dockerfile
    assert dockerfile.index("dependency-lock/package-lock.json") < dockerfile.index(
        "npm ci --omit=dev"
    )
    assert dockerfile.index("/overlay/.") < dockerfile.index("npm ci --omit=dev")
    assert dockerfile.index("patch -p1") < dockerfile.index("npm ci --omit=dev")


def test_sonos_security_overlay_checks_every_runtime_import_after_install():
    repo_root = addon_builder.REPO_ROOT
    package = json.loads(
        (repo_root / "node-sonos-http-api/dependency-lock/package.json").read_text()
    )
    security_patch = (
        repo_root / "node-sonos-http-api/patches/dependency-security.patch"
    ).read_text()
    scanner = (
        repo_root
        / "node-sonos-http-api/overlay/tools/check-runtime-dependencies.js"
    ).read_text()

    assert package["scripts"]["postinstall"] == (
        "node tools/check-runtime-dependencies.js"
    )
    assert "diff --git a/lib/actions/siriusXM.js" in security_patch
    assert "-const request = require('request-promise');" in security_patch
    assert "require.resolve(specifier" in scanner
    assert "process.exit(1)" in scanner


def test_mongodb_image_matches_the_persisted_8_2_feature_compatibility_line():
    dockerfile = (addon_builder.REPO_ROOT / "mongodb/Dockerfile").read_text()

    assert dockerfile.startswith(
        "# MongoDB Community Edition 8.x for Home Assistant\nFROM mongo:8.2.12\n"
    )


def test_git_cloned_addons_reject_moving_refs():
    addons = addon_builder.discover_addons()
    addons["node-sonos-http-api"] = {
        **addons["node-sonos-http-api"],
        "git_clone": {
            **addons["node-sonos-http-api"]["git_clone"],
            "ref": "master",
        },
    }

    with pytest.raises(Exception, match="40-character commit SHA"):
        addon_builder.build_context("node-sonos-http-api", addons)


def test_python_context_exposes_runtime_and_build_dependencies():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("printer", addons)

    assert "flask" in context["addon"]["python_dependencies"]
    assert "hatchling" in context["addon"]["python_build_dependencies"]
    assert context["addon"]["deploy_health_path"] == "/health/mongo"


def test_python_dependencies_are_exported_from_uv_lock_with_hashes(tmp_path):
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("printer", addons)

    addon_builder.export_python_requirements(context["addon"], tmp_path)

    requirements = (tmp_path / "requirements.lock").read_text(encoding="utf-8")
    build_requirements = (tmp_path / "build-requirements.lock").read_text(
        encoding="utf-8"
    )
    assert "flask==" in requirements
    assert "pillow==12.3.0" in requirements
    assert "pytest==" not in requirements
    assert "--hash=sha256:" in requirements
    assert "hatchling==" in build_requirements
    assert "wheel==" in build_requirements
    assert "--hash=sha256:" in build_requirements


def test_python_dockerfile_installs_hash_locked_application_dependencies():
    addons = addon_builder.discover_addons()
    context = addon_builder.build_context("printer", addons)
    dockerfile = addon_builder.render_template(
        addon_builder.jinja_env(), "Dockerfile.j2", context
    )

    assert "COPY app/requirements.lock app/build-requirements.lock" in dockerfile
    assert "pip install --no-cache-dir --require-hashes --no-deps" in dockerfile
    assert "--no-build-isolation -r /tmp/app-metadata/requirements.lock" in dockerfile
    assert 'ENV PYTHONPATH="/opt/printer/app/src"' in dockerfile
    assert "FROM python:3.14.6-alpine" in dockerfile
    assert "pip install --no-cache-dir --upgrade" not in dockerfile


def test_slow_stopping_node_addons_exec_the_service_as_pid_one():
    grid_run = (addon_builder.REPO_ROOT / "grid-dashboard/ExpressServer/run.sh").read_text()
    sonos_run = (addon_builder.REPO_ROOT / "sonos-api/run.sh").read_text()

    assert "exec ./node_modules/.bin/tsx src/server/index.ts" in grid_run
    assert "exec node dist/server/index.js" in sonos_run
    assert "npm start" not in grid_run
    assert "npm start" not in sonos_run
