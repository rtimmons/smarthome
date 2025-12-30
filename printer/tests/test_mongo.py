from __future__ import annotations

import printer_service.mongo as mongo


def test_load_mongo_config_from_env(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://user:pass@mongo.example:27018/app")
    monkeypatch.delenv("PRINTER_DEV_RELOAD", raising=False)

    config = mongo.load_mongo_config()

    assert config is not None
    assert config.url == "mongodb://user:pass@mongo.example:27018/app"
    assert config.redacted_url == "mongodb://user:****@mongo.example:27018/app"
    assert config.host == "mongo.example"
    assert config.port == 27018
    assert config.database == "app"
    assert config.source == "env:MONGODB_URL"


def test_load_mongo_config_defaults_to_local_in_dev(monkeypatch):
    monkeypatch.delenv("MONGODB_URL", raising=False)
    monkeypatch.setenv("PRINTER_DEV_RELOAD", "1")

    config = mongo.load_mongo_config()

    assert config is not None
    assert config.url == mongo.DEFAULT_LOCAL_URL
    assert config.source == "default:local"


def test_load_mongo_config_none_without_env(monkeypatch):
    monkeypatch.delenv("MONGODB_URL", raising=False)
    monkeypatch.delenv("PRINTER_DEV_RELOAD", raising=False)

    config = mongo.load_mongo_config()

    assert config is None


def test_mongo_health_reports_invalid_url(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "localhost:27017/app")

    status = mongo.mongo_health()

    assert status["configured"] is False
    assert status["ok"] is False
    assert "scheme" in status["error"] or "host" in status["error"]


def test_mongo_health_success(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://user:pass@db.example:27017/app")

    def _noop_ping(_config, _timeout):
        return None

    monkeypatch.setattr(mongo, "_driver_ping", _noop_ping)

    status = mongo.mongo_health()

    assert status["configured"] is True
    assert status["ok"] is True
    assert status["url"] == "mongodb://user:****@db.example:27017/app"
    assert status["database"] == "app"
    assert status["source"] == "env:MONGODB_URL"
    assert status["error"] is None


def test_mongo_health_redacts_error(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://user:pass@db.example:27017/app")
    monkeypatch.setattr(mongo, "_host_resolves", lambda _host, _port: True)

    def _failing_ping(config, _timeout):
        raise RuntimeError(f"failed to reach {config.url}")

    monkeypatch.setattr(mongo, "_driver_ping", _failing_ping)

    status = mongo.mongo_health()

    assert status["configured"] is True
    assert status["ok"] is False
    assert "mongodb://user:****@db.example:27017/app" in status["error"]
    assert "pass" not in status["error"]


def test_load_mongo_configs_expands_hosts(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://mongodb:27017/app")
    monkeypatch.delenv("PRINTER_DEV_RELOAD", raising=False)
    monkeypatch.setattr(mongo, "_host_resolves", lambda _host, _port: True)

    configs = mongo.load_mongo_configs()

    hosts = [config.host for config in configs]
    assert hosts[0] == "mongodb"
    assert "addon_local_mongodb" in hosts
    assert "addon_mongodb" in hosts


def test_mongo_health_uses_fallback_host(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://mongodb:27017/app")
    monkeypatch.delenv("PRINTER_DEV_RELOAD", raising=False)
    monkeypatch.setattr(
        mongo,
        "_host_resolves",
        lambda host, _port: host in {"mongodb", "addon_local_mongodb"},
    )

    def _ping(config, _timeout):
        if config.host == "mongodb":
            raise RuntimeError("mongodb:27017 not reachable")
        return None

    monkeypatch.setattr(mongo, "_driver_ping", _ping)

    status = mongo.mongo_health()

    assert status["configured"] is True
    assert status["ok"] is True
    assert status["host"] == "addon_local_mongodb"
