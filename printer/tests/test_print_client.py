from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

import printer_service.print_client as print_client
from printer_service.print_client import (
    AmbiguousPrintError,
    ClientConfig,
    PrintClientError,
    PrintTransportError,
    describe_config,
    execute_print,
    resolve_config,
    validate_local_png,
)


def _write_png(path: Path, *, size: tuple[int, int] = (390, 720)) -> Path:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (255, 255, 255, 255)).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return path


def _config() -> ClientConfig:
    return ClientConfig(
        base_url="http://printer.test:8099/base/",
        preview_path="png/preview",
        print_path="png/print",
        timeout_seconds=45,
        bearer_token=None,
        token_source=None,
        ca_file=None,
    )


def test_resolve_config_uses_shared_public_service_and_ha_conventions() -> None:
    config = resolve_config(
        {
            "HA_HOST": "kitchen-ha.local",
            "PUBLIC_SERVICE_SCHEME": "https",
            "PUBLIC_SERVICE_PORT": "9443",
            "PUBLIC_SERVICE_PATH": "/printer",
        }
    )

    assert config.base_url == "https://kitchen-ha.local:9443/printer/"
    assert config.endpoint(config.print_path) == ("https://kitchen-ha.local:9443/printer/png/print")
    assert config.bearer_token is None


def test_explicit_service_url_and_private_token_file(tmp_path: Path) -> None:
    token_file = tmp_path / "printer-token"
    token_file.write_text("secret-token\n")
    token_file.chmod(0o600)

    config = resolve_config(
        {
            "PRINTER_SERVICE_URL": "https://labels.example.test/custom",
            "PRINTER_SERVICE_TOKEN_FILE": str(token_file),
        }
    )

    assert config.base_url == "https://labels.example.test/custom/"
    assert config.bearer_token == "secret-token"
    assert config.token_source == "file"
    assert all("secret-token" not in line for line in describe_config(config))


def test_token_file_rejects_group_or_other_access(tmp_path: Path) -> None:
    token_file = tmp_path / "printer-token"
    token_file.write_text("secret-token")
    token_file.chmod(0o644)

    with pytest.raises(PrintClientError, match="chmod 600"):
        resolve_config({"PRINTER_SERVICE_TOKEN_FILE": str(token_file)})


def test_service_url_rejects_embedded_credentials() -> None:
    with pytest.raises(PrintClientError, match="Do not put credentials"):
        resolve_config({"PRINTER_SERVICE_URL": "https://user:password@labels.test/"})


def test_http_transport_sends_bearer_token_without_reporting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Any] = []

    class FakeResponse:
        def read(self, _size: int = -1) -> bytes:
            return b'{"metrics":{"fits_target":true}}'

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeOpener:
        def open(self, request: Any, *, timeout: float) -> FakeResponse:
            assert timeout == 45
            requests.append(request)
            return FakeResponse()

    monkeypatch.setattr(print_client, "build_opener", lambda *_handlers: FakeOpener())
    config = ClientConfig(
        base_url="https://labels.example.test/",
        preview_path="png/preview",
        print_path="png/print",
        timeout_seconds=45,
        bearer_token="secret-token",
        token_source="file",
        ca_file=None,
    )

    response = print_client._post_png(
        config,
        config.endpoint(config.preview_path),
        filename="durban.png",
        payload=b"png-payload",
    )

    assert response == {"metrics": {"fits_target": True}}
    assert requests[0].get_header("Authorization") == "Bearer secret-token"
    assert all("secret-token" not in line for line in describe_config(config))


def test_validate_local_png_uses_upload_normalization(tmp_path: Path) -> None:
    png_path = _write_png(tmp_path / "durban.png")

    local_png = validate_local_png(png_path)

    assert local_png.path == png_path
    assert local_png.source_size == (390, 720)
    assert local_png.target_size == (720, 390)
    assert local_png.rotated is True


def test_execute_print_preflights_then_prints_exactly_once(tmp_path: Path) -> None:
    png_path = _write_png(tmp_path / "durban.png")
    calls: list[tuple[str, str, bytes]] = []
    messages: list[str] = []

    def poster(
        config: ClientConfig,
        endpoint: str,
        *,
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]:
        del config
        calls.append((endpoint, filename, payload))
        if endpoint.endswith("/png/preview"):
            return {"metrics": {"fits_target": True}}
        return {"status": "sent", "metrics": {"fits_target": True}}

    result = execute_print(png_path, _config(), poster=poster, output=messages.append)

    assert result["status"] == "sent"
    assert [call[0] for call in calls] == [
        "http://printer.test:8099/base/png/preview",
        "http://printer.test:8099/base/png/print",
    ]
    assert all(call[1] == "durban.png" for call in calls)
    assert calls[0][2] == calls[1][2]
    assert sum(endpoint.endswith("/png/print") for endpoint, _name, _body in calls) == 1
    assert messages[-1] == "Print accepted: durban.png"


def test_preview_only_never_calls_print_endpoint(tmp_path: Path) -> None:
    png_path = _write_png(tmp_path / "durban.png", size=(720, 390))
    calls: list[str] = []

    def poster(
        config: ClientConfig,
        endpoint: str,
        *,
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]:
        del config, filename, payload
        calls.append(endpoint)
        return {"metrics": {"fits_target": True}}

    execute_print(png_path, _config(), preview_only=True, poster=poster, output=lambda _x: None)

    assert calls == ["http://printer.test:8099/base/png/preview"]


def test_print_transport_failure_is_ambiguous_and_not_retried(tmp_path: Path) -> None:
    png_path = _write_png(tmp_path / "durban.png")
    calls: list[str] = []

    def poster(
        config: ClientConfig,
        endpoint: str,
        *,
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]:
        del config, filename, payload
        calls.append(endpoint)
        if endpoint.endswith("/png/preview"):
            return {"metrics": {"fits_target": True}}
        raise PrintTransportError("connection reset")

    with pytest.raises(AmbiguousPrintError, match="outcome is unknown"):
        execute_print(png_path, _config(), poster=poster, output=lambda _x: None)

    assert sum(endpoint.endswith("/png/print") for endpoint in calls) == 1
