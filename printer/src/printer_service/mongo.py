from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import ParseResult, urlparse, urlunparse

DEFAULT_DB = "smarthome"
DEFAULT_LOCAL_URL = "mongodb://localhost:27017/smarthome"
DEFAULT_PORT = 27017


@dataclass(frozen=True)
class MongoConfig:
    url: str
    redacted_url: str
    host: str
    port: int
    database: Optional[str]
    source: str


def _is_truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _redact_mongo_url(parsed: ParseResult) -> str:
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    password = parsed.password
    port = parsed.port
    auth = ""
    if username:
        if password:
            auth = f"{username}:****@"
        else:
            auth = f"{username}@"
    netloc = f"{auth}{hostname}"
    if port:
        netloc = f"{netloc}:{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def _load_mongo_url() -> tuple[Optional[str], Optional[str]]:
    raw = os.getenv("MONGODB_URL")
    if raw and raw.strip():
        return raw.strip(), "env:MONGODB_URL"
    if _is_truthy(os.getenv("PRINTER_DEV_RELOAD")):
        return DEFAULT_LOCAL_URL, "default:local"
    return None, None


def load_mongo_config() -> Optional[MongoConfig]:
    raw, source = _load_mongo_url()
    if not raw or not source:
        return None
    parsed = urlparse(raw)
    if not parsed.scheme:
        raise ValueError("MONGODB_URL must include a scheme (mongodb://).")
    host = parsed.hostname
    if not host:
        raise ValueError("MONGODB_URL must include a host.")
    port = parsed.port or DEFAULT_PORT
    database = parsed.path.lstrip("/") or None
    redacted = _redact_mongo_url(parsed)
    return MongoConfig(
        url=raw,
        redacted_url=redacted,
        host=host,
        port=port,
        database=database,
        source=source,
    )


def _tcp_ping(host: str, port: int, timeout_seconds: float) -> None:
    with socket.create_connection((host, port), timeout=timeout_seconds):
        return None


def _driver_ping(config: MongoConfig, timeout_seconds: float) -> None:
    try:
        from pymongo import MongoClient  # type: ignore[import-not-found]
    except Exception:
        _tcp_ping(config.host, config.port, timeout_seconds)
        return
    client = MongoClient(
        config.url,
        serverSelectionTimeoutMS=max(int(timeout_seconds * 1000), 1),
    )
    try:
        client.admin.command("ping")
    finally:
        client.close()


def mongo_health(timeout_seconds: float = 1.0) -> dict[str, object]:
    try:
        config = load_mongo_config()
    except ValueError as exc:
        return {
            "configured": False,
            "ok": False,
            "error": str(exc),
            "source": "env:MONGODB_URL",
        }

    if config is None:
        return {
            "configured": False,
            "ok": None,
        }

    start = time.monotonic()
    error: Optional[str] = None
    ok = True
    try:
        _driver_ping(config, timeout_seconds)
    except Exception as exc:
        ok = False
        error = str(exc)
        if config.url and error:
            error = error.replace(config.url, config.redacted_url)
    latency_ms = int((time.monotonic() - start) * 1000)
    database = config.database or (DEFAULT_DB if config.source == "default:local" else None)
    return {
        "configured": True,
        "ok": ok,
        "url": config.redacted_url,
        "host": config.host,
        "port": config.port,
        "database": database,
        "source": config.source,
        "latency_ms": latency_ms,
        "error": error,
    }


__all__ = ["MongoConfig", "load_mongo_config", "mongo_health"]
