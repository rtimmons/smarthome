from __future__ import annotations

import base64
import importlib
import io
from pathlib import Path

import pytest
from PIL import Image

import printer_service.presets as presets
from printer_service.label_specs import BrotherLabelSpec


def _image_bytes(
    *,
    image_format: str = "PNG",
    size: tuple[int, int] = (390, 720),
) -> io.BytesIO:
    buffer = io.BytesIO()
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    color = (255, 255, 255) if mode == "RGB" else (255, 255, 255, 255)
    Image.new(mode, size, color).save(buffer, format=image_format)
    buffer.seek(0)
    return buffer


@pytest.fixture
def png_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    presets.reset_cached_store()
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(tmp_path / "printer-output.png"))
    monkeypatch.setenv("BROTHER_LABEL", "62")
    app_module = importlib.import_module("printer_service.app")
    app_module = importlib.reload(app_module)
    monkeypatch.setattr(
        app_module,
        "mongo_health",
        lambda: {"configured": False, "ok": True},
    )
    flask_app = app_module.create_app()
    return app_module, flask_app, tmp_path


def test_png_page_is_a_peer_navigation_route(png_environment) -> None:
    _app_module, flask_app, _tmp_path = png_environment

    response = flask_app.test_client().get("/png")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Best By" in html
    assert "Bluey Label" in html
    assert 'href="/png"' in html
    assert "PNG Upload" in html
    assert 'id="pngDropZone"' in html
    assert 'data-ephemeral-upload="true"' in html
    assert 'data-preview-url="/png/preview"' in html
    assert 'data-print-url="/png/print"' in html
    assert 'id="printCountdownContainer"' in html
    assert 'id="pngPrintTrigger"' in html
    assert "Presets" not in html


def test_png_preview_validates_rotates_and_normalizes_portrait_upload(png_environment) -> None:
    _app_module, flask_app, _tmp_path = png_environment

    response = flask_app.test_client().post(
        "/png/preview",
        data={"file": (_image_bytes(), "poison.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["filename"] == "poison.png"
    assert payload["source"] == {"width_px": 390, "height_px": 720}
    assert payload["rotated"] is True
    assert payload["metrics"]["width_px"] == 720
    assert payload["metrics"]["height_px"] == 390
    assert payload["metrics"]["fits_target"] is True
    encoded = payload["image"].partition(",")[2]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as preview:
        assert preview.format == "PNG"
        assert preview.size == (720, 390)


@pytest.mark.parametrize(
    ("upload", "filename", "expected_error"),
    [
        (io.BytesIO(b"not an image"), "broken.png", "not a readable PNG"),
        (_image_bytes(image_format="JPEG"), "photo.png", "must be a PNG"),
        (io.BytesIO(), "empty.png", "is empty"),
    ],
)
def test_png_preview_rejects_invalid_files(
    png_environment,
    upload: io.BytesIO,
    filename: str,
    expected_error: str,
) -> None:
    _app_module, flask_app, _tmp_path = png_environment

    response = flask_app.test_client().post(
        "/png/preview",
        data={"file": (upload, filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert expected_error in response.get_json()["error"]


def test_png_print_dispatches_normalized_image_without_retaining_upload(
    png_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, flask_app, tmp_path = png_environment
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, *, target_spec=None):
        dispatched["size"] = image.size
        dispatched["backend"] = config.backend
        dispatched["target_spec"] = target_spec
        return None

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)
    client = flask_app.test_client()

    preview_response = client.post(
        "/png/preview",
        data={"file": (_image_bytes(), "poison.png")},
        content_type="multipart/form-data",
    )
    missing_print_response = client.post("/png/print")
    print_response = client.post(
        "/png/print",
        data={"file": (_image_bytes(), "poison.png")},
        content_type="multipart/form-data",
    )

    assert preview_response.status_code == 200
    assert missing_print_response.status_code == 400
    assert missing_print_response.get_json()["error"] == "Choose a PNG file to continue."
    assert print_response.status_code == 200
    assert print_response.get_json()["status"] == "sent"
    assert dispatched["size"] == (720, 390)
    assert dispatched["backend"] == "file"
    target_spec = dispatched["target_spec"]
    assert isinstance(target_spec, BrotherLabelSpec)
    assert target_spec.code == "62"
    assert list(tmp_path.iterdir()) == []
