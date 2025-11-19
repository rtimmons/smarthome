from __future__ import annotations

from pathlib import Path

from PIL import Image

from printer_service import label as label_module
from printer_service.label import PrinterConfig, dispatch_image
from printer_service.label_specs import BrotherLabelSpec


def _dummy_spec() -> BrotherLabelSpec:
    return BrotherLabelSpec(code="test", printable_px=(200, 100))


def test_dispatch_rotates_portrait_before_brother_printer(monkeypatch) -> None:
    sent = {}

    def fake_send(image, cfg, label_override=None):
        sent["size"] = image.size
        sent["label_override"] = label_override

    monkeypatch.setattr(label_module, "_send_to_brother", fake_send)

    portrait = Image.new("RGB", (100, 200), color="white")
    config = PrinterConfig(
        backend="brother-network",
        brother_uri="tcp://127.0.0.1:9100",
    )

    dispatch_image(portrait, config, target_spec=_dummy_spec())

    assert sent["size"] == (200, 100)
    assert sent["label_override"] == _dummy_spec().code


def test_file_backend_keeps_stored_orientation(monkeypatch, tmp_path: Path) -> None:
    written = {}

    def fake_write(image, cfg, target_spec=None):
        written["size"] = image.size
        written["path"] = cfg.output_path
        return cfg.output_path

    monkeypatch.setattr(label_module, "_write_to_file", fake_write)

    portrait = Image.new("RGB", (100, 200), color="white")
    output_path = tmp_path / "printer-output.png"
    config = PrinterConfig(
        backend="file",
        output_path=output_path,
    )

    result = dispatch_image(portrait, config, target_spec=_dummy_spec())

    assert written["size"] == (100, 200)
    assert result == output_path
