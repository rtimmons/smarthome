from __future__ import annotations

import html
import importlib
import io
import re
import sys
import types
from datetime import date
from pathlib import Path
from typing import Tuple
from urllib.parse import parse_qsl, urlparse

import pytest
from PIL import Image, ImageDraw, ImageFont

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI, resolve_brother_label_spec
from printer_service.label_templates import bluey_label as bluey_module
from printer_service.label_templates.base import TemplateFormData
from printer_service.label_templates import helper as helper

TEST_LABEL_CODE = "29x90"
TEST_LABEL_SPEC = resolve_brother_label_spec(TEST_LABEL_CODE)
EXPECTED_WIDTH_PX, EXPECTED_HEIGHT_PX = TEST_LABEL_SPEC.printable_px
EXPECTED_WIDTH_IN = TEST_LABEL_SPEC.width_in
EXPECTED_HEIGHT_IN = TEST_LABEL_SPEC.height_in
EXPECTED_CANVAS = (EXPECTED_WIDTH_PX, EXPECTED_HEIGHT_PX)
BLUEY_EXPECTED_CANVAS = (bluey_module.CANVAS_WIDTH_PX, bluey_module.CANVAS_HEIGHT_PX)
BLUEY_EXPECTED_WIDTH_IN = bluey_module.LABEL_HEIGHT_IN
BLUEY_EXPECTED_HEIGHT_IN = bluey_module.LABEL_WIDTH_IN


def _count_runs(strip: Image.Image) -> int:
    width, height = strip.size
    pixels = strip.load()
    assert pixels is not None
    has_ink = []
    for y in range(height):
        row_has_ink = False
        for x in range(width):
            if pixels[x, y] == 0:
                row_has_ink = True
                break
        has_ink.append(row_has_ink)

    runs = 0
    in_run = False
    for row_has_ink in has_ink:
        if row_has_ink and not in_run:
            runs += 1
            in_run = True
        elif not row_has_ink and in_run:
            in_run = False
    return runs


def _build_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create an isolated app instance with temporary storage."""
    labels_dir = tmp_path / "labels"
    printer_output = tmp_path / "printer-output.png"
    monkeypatch.setenv("LABEL_OUTPUT_DIR", str(labels_dir))
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(printer_output))
    monkeypatch.setenv("BROTHER_LABEL", TEST_LABEL_CODE)

    try:
        importlib.import_module("cairosvg")
    except Exception:
        sys.modules.pop("cairosvg", None)

        fake_cairosvg = types.ModuleType("cairosvg")

        def svg2png(*, url=None, write_to=None, output_width=None, output_height=None, **_kwargs):
            width = int(output_width or output_height or 120)
            placeholder = Image.new("RGBA", (width, width), (0, 0, 0, 0))
            buffer = write_to or io.BytesIO()
            placeholder.save(buffer, format="PNG")
            buffer.seek(0)
            if write_to is None:
                return buffer.getvalue()

        setattr(fake_cairosvg, "svg2png", svg2png)
        sys.modules["cairosvg"] = fake_cairosvg

    templates_module = importlib.import_module("printer_service.label_templates")
    templates_module = importlib.reload(templates_module)
    app_module = importlib.import_module("printer_service.app")
    app_module = importlib.reload(app_module)
    flask_app = app_module.create_app()
    return app_module, templates_module, flask_app, labels_dir, printer_output


@pytest.fixture
def test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create an isolated app instance with temporary storage."""
    return _build_test_environment(tmp_path, monkeypatch)


@pytest.fixture
def test_environment_public_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUBLIC_SERVICE_HOST", "homeassistant.local")
    monkeypatch.setenv("PUBLIC_SERVICE_PORT", "8099")
    return _build_test_environment(tmp_path, monkeypatch)


def _extract_print_url_page(body: str) -> str:
    match = re.search(r"Print URL:\s*<code>([^<]+)</code>", body, flags=re.IGNORECASE)
    assert match is not None
    return html.unescape(match.group(1))


def test_create_label_persists_file_and_lists_recent(
    test_environment: Tuple, tmp_path: Path
) -> None:
    app_module, templates_module, flask_app, labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("kitchen_label_printer").slug
    response = client.post(
        "/labels",
        json={
            "template": template_slug,
            "data": {"line1": "Soup", "line2": "10/24", "line3": "Shelf 2"},
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    payload = response.json
    metrics = payload["metrics"]
    assert metrics["width_px"] == EXPECTED_WIDTH_PX
    assert metrics["height_px"] == EXPECTED_HEIGHT_PX
    assert metrics["width_in"] == pytest.approx(EXPECTED_WIDTH_IN, rel=0, abs=0.01)
    assert metrics["height_in"] == pytest.approx(EXPECTED_HEIGHT_IN, rel=0, abs=0.01)
    assert metrics["fits_target"] is True
    assert payload["warnings"] == []
    label = payload["label"]
    stored_path = labels_dir / label["name"]
    assert stored_path.exists(), "Generated label should be written to disk"

    listing = client.get("/labels")
    assert listing.status_code == 200
    names = [item["name"] for item in listing.json["labels"]]
    assert label["name"] in names
    assert names == sorted(names, reverse=True), "Recent labels should be newest first"


@pytest.mark.parametrize("bluey_slug", ["bluey_label", "bluey_label_2"])
def test_preview_returns_data_url_without_writing_to_disk(
    test_environment: Tuple, bluey_slug: str
) -> None:
    _, templates_module, flask_app, labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template(bluey_slug).slug

    before = list(labels_dir.glob("*.png"))
    assert before == []

    response = client.post(
        "/labels/preview",
        json={"template": template_slug, "data": {}},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "preview"
    assert payload["image"].startswith("data:image/png;base64,")
    metrics = payload["metrics"]
    assert metrics["width_px"] == BLUEY_EXPECTED_CANVAS[0]
    assert metrics["height_px"] == BLUEY_EXPECTED_CANVAS[1]
    assert metrics["width_in"] == pytest.approx(BLUEY_EXPECTED_WIDTH_IN, rel=0, abs=0.01)
    assert metrics["height_in"] == pytest.approx(BLUEY_EXPECTED_HEIGHT_IN, rel=0, abs=0.01)
    assert payload["warnings"] == []

    after = list(labels_dir.glob("*.png"))
    assert after == []


def test_preview_validates_payload(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.default_template().slug

    response = client.post(
        "/labels/preview",
        json={"template": template_slug},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["error"] == "Provide 'data' as an object of form inputs."


@pytest.mark.parametrize("bluey_slug", ["bluey_label", "bluey_label_2"])
def test_bluey_label_create_accepts_empty_fields(test_environment: Tuple, bluey_slug: str) -> None:
    _, templates_module, flask_app, labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template(bluey_slug).slug

    response = client.post(
        "/labels",
        json={"template": template_slug, "data": {}},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    stored_path = labels_dir / response.json["label"]["name"]
    assert stored_path.exists()


def test_print_existing_label_invokes_dispatch(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_module, templates_module, flask_app, labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("kitchen_label_printer").slug
    create = client.post(
        "/labels",
        json={"template": template_slug, "data": {"line1": "Batch"}},
    )
    label_name = create.json["label"]["name"]

    dispatched = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["backend"] = config.backend
        # Simulate file backend returning an output location
        return tmp_path / "printed.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    response = client.post(
        "/print",
        json={"filename": label_name},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.json["output"].endswith("printed.png")
    assert dispatched["called"] is True
    assert dispatched["backend"] == "file"


def test_print_missing_label_returns_not_found(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.post(
        "/print",
        json={"filename": "does-not-exist.png"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 404
    assert response.json["error"] == "Label not found."


def test_print_rejects_unreadable_label(test_environment: Tuple) -> None:
    _, _, flask_app, labels_dir, _ = test_environment
    client = flask_app.test_client()

    bad_path = labels_dir / "invalid.png"
    bad_path.write_bytes(b"not-an-image")

    response = client.post(
        "/print",
        json={"filename": bad_path.name},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 500
    assert response.json["error"] == "Stored label is unreadable."


def test_sanitize_lines_trims_and_limits(test_environment: Tuple) -> None:
    helper_module = importlib.import_module("printer_service.label_templates.helper")
    helper_module = importlib.reload(helper_module)
    lines = ["  keep  ", "", "   ", None, "B", "C", "D", "E", "F", "G"]
    assert helper_module.sanitize_lines(lines) == ["keep", "B", "C", "D", "E", "F"]


@pytest.mark.parametrize("bluey_slug", ["bluey_label", "bluey_label_2"])
def test_bluey_template_renders_expected_canvas(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, bluey_slug: str
) -> None:
    _, templates_module, _, _, _ = test_environment
    bluey_template = templates_module.get_template(bluey_slug)
    helper_module = importlib.import_module("printer_service.label_templates.helper")

    def fake_svg2png(*, url=None, write_to=None, output_width=None, **_kwargs):
        width = int(output_width or 120)
        placeholder = Image.new("RGBA", (width, 60), (0, 0, 0, 0))
        placeholder.save(write_to, format="PNG")
        write_to.seek(0)

    monkeypatch.setattr(helper_module.cairosvg, "svg2png", fake_svg2png)

    image = bluey_template.render(
        {
            "Line1": "Granddaddy Purp",
            "Line2": "Shelf 2",
            "SymbolName": "Sleep",
            "Initials": "GDP",
            "PackageDate": "07/11/25",
        }
    )
    assert image.size == BLUEY_EXPECTED_CANVAS
    assert image.mode == "1"


@pytest.mark.parametrize("bluey_slug", ["bluey_label", "bluey_label_2"])
def test_bluey_template_renders_with_minimal_data(test_environment: Tuple, bluey_slug: str) -> None:
    _, templates_module, _, _, _ = test_environment
    bluey_template = templates_module.get_template(bluey_slug)

    image = bluey_template.render({})

    assert image.size == BLUEY_EXPECTED_CANVAS
    assert image.mode == "1"


def test_bluey_initials_repeat_along_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    helper_module = importlib.import_module("printer_service.label_templates.helper")
    bluey_template = importlib.reload(
        importlib.import_module("printer_service.label_templates.bluey_label_2")
    ).TEMPLATE

    monkeypatch.setattr(helper_module, "load_font", lambda size_points: ImageFont.load_default())
    monkeypatch.setattr(helper_module, "draw_background_symbol", lambda *args, **kwargs: None)

    image = bluey_template.render(TemplateFormData({"Initials": "ABC"}))

    strip_width = 80
    left_runs = _count_runs(image.crop((0, 0, strip_width, image.height)))
    right_runs = _count_runs(image.crop((image.width - strip_width, 0, image.width, image.height)))

    assert left_runs == right_runs
    assert left_runs >= 4


def test_bluey_initials_clip_count_when_title_is_wide(monkeypatch: pytest.MonkeyPatch) -> None:
    helper_module = importlib.import_module("printer_service.label_templates.helper")
    bluey_template = importlib.reload(
        importlib.import_module("printer_service.label_templates.bluey_label_2")
    ).TEMPLATE

    monkeypatch.setattr(helper_module, "load_font", lambda size_points: ImageFont.load_default())
    monkeypatch.setattr(helper_module, "draw_background_symbol", lambda *args, **kwargs: None)

    strip_width = 80
    narrow_image = bluey_template.render(
        TemplateFormData({"Line1": "Foo", "Line2": "Bar", "Initials": "FP"})
    )
    narrow_runs = _count_runs(narrow_image.crop((0, 0, strip_width, narrow_image.height)))

    wide_image = bluey_template.render(
        TemplateFormData({"Line1": "W" * 140, "Line2": "Bar", "Initials": "FP"})
    )
    wide_runs_left = _count_runs(wide_image.crop((0, 0, strip_width, wide_image.height)))
    wide_runs_right = _count_runs(
        wide_image.crop((wide_image.width - strip_width, 0, wide_image.width, wide_image.height))
    )

    assert wide_runs_left == wide_runs_right
    assert wide_runs_left >= 1
    assert wide_runs_left < narrow_runs


@pytest.mark.parametrize("bluey_slug", ["bluey_label", "bluey_label_2"])
def test_bluey_template_rejects_unknown_symbol(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, bluey_slug: str
) -> None:
    _, templates_module, _, _, _ = test_environment
    bluey_template = templates_module.get_template(bluey_slug)
    helper_module = importlib.import_module("printer_service.label_templates.helper")

    def fake_svg2png(*args, **kwargs):
        raise AssertionError("SVG rasterization should not run for invalid symbols.")

    monkeypatch.setattr(helper_module.cairosvg, "svg2png", fake_svg2png)

    with pytest.raises(ValueError):
        bluey_template.render(
            {
                "Line1": "Hybrid",
                "SymbolName": "Unknown Symbol",
                "Initials": "HYB",
                "PackageDate": "07/11/25",
            }
        )


def test_analyze_label_image_warns_for_oversized_label(monkeypatch: pytest.MonkeyPatch) -> None:
    label_module = importlib.import_module("printer_service.label")
    label_module = importlib.reload(label_module)
    config = label_module.PrinterConfig(
        backend="brother-network",
        brother_uri="network://printer",
    )
    large_image = Image.new("L", (820, 720), 255)
    metrics = label_module.analyze_label_image(large_image, config)
    assert metrics.fits_target is False
    assert metrics.warnings


def test_send_to_brother_normalizes_network_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    label_module = importlib.reload(importlib.import_module("printer_service.label"))
    fake_calls = {}

    helpers_module = types.ModuleType("brother_ql.backends.helpers")
    setattr(
        helpers_module,
        "send",
        lambda instructions, uri: fake_calls.update({"uri": uri, "instructions": instructions}),
    )

    conversion_module = types.ModuleType("brother_ql.conversion")
    setattr(conversion_module, "convert", lambda *args, **kwargs: ["instructions"])

    class FakeRaster:
        def __init__(self, model: str) -> None:
            self.model = model
            self.exception_on_warning = False

    raster_module = types.ModuleType("brother_ql.raster")
    setattr(raster_module, "BrotherQLRaster", FakeRaster)

    backends_module = types.ModuleType("brother_ql.backends")
    setattr(backends_module, "helpers", helpers_module)

    package_module = types.ModuleType("brother_ql")
    setattr(package_module, "backends", backends_module)
    setattr(package_module, "conversion", conversion_module)
    setattr(package_module, "raster", raster_module)

    monkeypatch.setitem(sys.modules, "brother_ql", package_module)
    monkeypatch.setitem(sys.modules, "brother_ql.backends", backends_module)
    monkeypatch.setitem(sys.modules, "brother_ql.backends.helpers", helpers_module)
    monkeypatch.setitem(sys.modules, "brother_ql.conversion", conversion_module)
    monkeypatch.setitem(sys.modules, "brother_ql.raster", raster_module)

    image = Image.new("1", EXPECTED_CANVAS, 0)
    config = label_module.PrinterConfig(
        backend="brother-network",
        brother_uri="network://192.168.1.50:9100",
    )

    label_module._send_to_brother(image, config)

    assert fake_calls["uri"] == "tcp://192.168.1.50:9100"


def test_best_by_dispatch_uses_supported_brother_code(monkeypatch: pytest.MonkeyPatch) -> None:
    label_module = importlib.reload(importlib.import_module("printer_service.label"))
    best_by_module = importlib.import_module("printer_service.label_templates.best_by")
    monkeypatch.setattr(best_by_module, "_today", lambda: date(2025, 11, 17))

    observed = {}

    helpers_module = types.ModuleType("brother_ql.backends.helpers")
    setattr(helpers_module, "send", lambda instructions, uri: observed.update({"uri": uri}))

    def fake_convert(_qlr, _images, label_code, **_kwargs):
        observed["label_code"] = label_code
        return ["instructions"]

    conversion_module = types.ModuleType("brother_ql.conversion")
    setattr(conversion_module, "convert", fake_convert)

    class FakeRaster:
        def __init__(self, model: str) -> None:
            self.model = model
            self.exception_on_warning = False

    raster_module = types.ModuleType("brother_ql.raster")
    setattr(raster_module, "BrotherQLRaster", FakeRaster)

    backends_module = types.ModuleType("brother_ql.backends")
    setattr(backends_module, "helpers", helpers_module)

    package_module = types.ModuleType("brother_ql")
    setattr(package_module, "backends", backends_module)
    setattr(package_module, "conversion", conversion_module)
    setattr(package_module, "raster", raster_module)

    monkeypatch.setitem(sys.modules, "brother_ql", package_module)
    monkeypatch.setitem(sys.modules, "brother_ql.backends", backends_module)
    monkeypatch.setitem(sys.modules, "brother_ql.backends.helpers", helpers_module)
    monkeypatch.setitem(sys.modules, "brother_ql.conversion", conversion_module)
    monkeypatch.setitem(sys.modules, "brother_ql.raster", raster_module)

    template = importlib.reload(best_by_module).TEMPLATE
    image = template.render(TemplateFormData({}))
    target_spec = template.preferred_label_spec()

    config = label_module.PrinterConfig(
        backend="brother-network",
        brother_uri="network://printer",
    )

    label_module.dispatch_image(image, config, target_spec=target_spec)

    assert observed["label_code"] == best_by_module.bluey_label.LABEL_SPEC.code


def test_analyze_label_image_honors_target_spec_override() -> None:
    label_module = importlib.reload(importlib.import_module("printer_service.label"))
    config = label_module.PrinterConfig(
        backend="brother-network",
        brother_uri="network://printer",
        brother_label="29x90",
    )
    override_spec = BrotherLabelSpec(code="continuous-24x13", printable_px=BLUEY_EXPECTED_CANVAS)
    image = Image.new("1", BLUEY_EXPECTED_CANVAS, 0)
    metrics = label_module.analyze_label_image(image, config, target_spec=override_spec)
    assert metrics.fits_target is True
    assert metrics.warnings == []


def test_kitchen_preview_reports_clipping_warning(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _, _ = test_environment
    client = flask_app.test_client()
    slug = templates_module.get_template("kitchen_label_printer").slug

    response = client.post(
        "/labels/preview",
        json={"template": slug, "data": {"line1": "d" * 80}},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    warnings = response.json["warnings"]
    assert warnings
    assert any("clipped" in warning.lower() for warning in warnings)


def test_print_preserves_clipping_warning(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _, _ = test_environment
    client = flask_app.test_client()
    slug = templates_module.get_template("kitchen_label_printer").slug

    create = client.post(
        "/labels",
        json={"template": slug, "data": {"line1": "d" * 80}},
        headers={"Accept": "application/json"},
    )
    assert create.status_code == 200
    assert any("clipped" in warning.lower() for warning in create.json["warnings"])

    label_name = create.json["label"]["name"]
    response = client.post(
        "/print",
        json={"filename": label_name},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    warnings = response.json.get("warnings", [])
    assert warnings
    assert any("clipped" in warning.lower() for warning in warnings)


def test_print_uses_stored_label_spec_metadata(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _, _ = test_environment
    client = flask_app.test_client()
    slug = templates_module.get_template("bluey_label").slug

    create = client.post(
        "/labels",
        json={"template": slug, "data": {"Line1": "Bluey"}},
        headers={"Accept": "application/json"},
    )
    assert create.status_code == 200
    label_name = create.json["label"]["name"]

    response = client.post(
        "/print",
        json={"filename": label_name},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    payload = response.json
    metrics = payload["metrics"]
    assert metrics["width_px"] == BLUEY_EXPECTED_CANVAS[0]
    assert metrics["height_px"] == BLUEY_EXPECTED_CANVAS[1]
    assert metrics["fits_target"] is True
    assert not payload.get("warnings")


def test_bb_endpoint_creates_and_prints_label(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, flask_app, labels_dir, printer_output = test_environment
    client = flask_app.test_client()

    best_by_module = importlib.import_module("printer_service.label_templates.best_by")
    monkeypatch.setattr(best_by_module, "_today", lambda: date(2025, 11, 17))

    response = client.get(
        "/bb", query_string={"print": "true"}, headers={"Accept": "application/json"}
    )

    assert response.status_code == 200
    payload = response.json
    assert payload["best_by_date"] == "2025-12-01"
    metrics = payload["metrics"]
    font = helper.load_font(size_points=48)
    dummy = Image.new("L", (1, 1), 255)
    draw = ImageDraw.Draw(dummy)
    text_bbox = draw.textbbox((0, 0), "Best By: 2025-12-01", font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    margin_px = int(round(QL810W_DPI / 8))
    min_height = text_height + margin_px
    min_width = max(text_width + 40, bluey_module.CANVAS_HEIGHT_PX // 2)
    assert metrics["height_px"] >= min_height
    assert metrics["width_px"] >= min_width
    assert metrics["fits_target"] is True
    assert not list(labels_dir.glob("*.png"))
    assert printer_output.exists()


def test_bb_endpoint_accepts_base_date_override(test_environment: Tuple) -> None:
    _, _, flask_app, labels_dir, printer_output = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"print": "true", "baseDate": "2025-02-10"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json["best_by_date"] == "2025-02-24"
    assert printer_output.exists()
    assert not list(labels_dir.glob("*.png"))


def test_bb_endpoint_accepts_delta_override(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    best_by_module = importlib.import_module("printer_service.label_templates.best_by")
    monkeypatch.setattr(best_by_module, "_today", lambda: date(2025, 5, 1))

    response = client.get(
        "/bb",
        query_string={"print": "true", "delta": "3 weeks"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json["best_by_date"] == "2025-05-22"


def test_bb2w_route_remains_supported(test_environment: Tuple) -> None:
    _, _, flask_app, labels_dir, printer_output = test_environment
    client = flask_app.test_client()

    response = client.post("/bb2w", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json["status"] == "sent"
    assert response.json["template"] in {"best_by", "bb_2_weeks"}
    assert printer_output.exists()
    assert not list(labels_dir.glob("*.png"))


def test_bb_endpoint_rejects_invalid_base_date(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"print": "true", "BaseDate": "invalid-date"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert "BaseDate" in response.json["error"]


def test_bb_page_print_url_excludes_default_params(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get("/bb")

    assert response.status_code == 200
    print_url = _extract_print_url_page(response.get_data(as_text=True))
    parsed = urlparse(print_url)
    params = dict(parse_qsl(parsed.query))

    assert params == {"print": "true"}


def test_bb_page_print_url_includes_explicit_params(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"baseDate": "2025-02-10", "delta": "1 month"},
    )

    assert response.status_code == 200
    print_url = _extract_print_url_page(response.get_data(as_text=True))
    parsed = urlparse(print_url)
    params = dict(parse_qsl(parsed.query))

    assert params["print"] == "true"
    assert params["baseDate"] == "2025-02-10"
    assert params["delta"] == "1 month"


def test_bb_page_respects_offset_alias_in_print_url(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get("/bb", query_string={"offset": "2 weeks"})

    assert response.status_code == 200
    print_url = _extract_print_url_page(response.get_data(as_text=True))
    parsed = urlparse(print_url)
    params = dict(parse_qsl(parsed.query))

    assert params["print"] == "true"
    assert params["offset"] == "2 weeks"


def test_bb_page_print_url_uses_public_port_and_path(test_environment_public_port: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment_public_port
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        environ_overrides={
            "HTTP_HOST": "homeassistant.local:8123",
            "HTTP_X_INGRESS_PATH": "/api/hassio_ingress/XYZ",
        },
    )

    assert response.status_code == 200
    print_url = _extract_print_url_page(response.get_data(as_text=True))
    parsed = urlparse(print_url)
    params = dict(parse_qsl(parsed.query))

    assert parsed.netloc == "homeassistant.local:8099"
    assert parsed.path == "/bb"
    assert params["print"] == "true"


def test_bb_page_renders_dual_previews(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    best_by_module = importlib.import_module("printer_service.label_templates.best_by")
    monkeypatch.setattr(best_by_module, "_today", lambda: date(2025, 11, 20))
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get("/bb")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "2025-12-04" in body
    images = re.findall(r"src=\"(data:image/png;base64,[^\"]+)\"", body)
    assert len(images) >= 2


def test_bb_endpoint_prints_qr_label_when_requested(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"print": "true", "qr_label": "true"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json["status"] == "sent"
    assert response.json["template"] in {"best_by", "bb_2_weeks"}


def test_bb_endpoint_supports_text_mode_print(test_environment: Tuple) -> None:
    _, _, flask_app, labels_dir, printer_output = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"print": "true", "text": "Best+By+2025-12-01"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json
    assert payload["text"] == "Best By 2025-12-01"
    assert "best_by_date" not in payload
    assert printer_output.exists()
    assert not list(labels_dir.glob("*.png"))


def test_bb_endpoint_rejects_text_and_date_mix(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get(
        "/bb",
        query_string={"text": "Custom", "baseDate": "2025-02-10"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert "Text cannot be combined" in response.json["error"]


def test_bb_page_switches_to_text_mode(test_environment: Tuple) -> None:
    _, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    response = client.get("/bb", query_string={"text": "Alpha+Beta"})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="textValue"' in body
    assert 'id="baseDate"' not in body
    print_url = _extract_print_url_page(body)
    parsed = urlparse(print_url)
    params = dict(parse_qsl(parsed.query))
    assert params["text"] == "Alpha Beta"
    assert params["print"] == "true"


def test_print_cools_down_after_jobs(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, _, flask_app, _, _ = test_environment
    client = flask_app.test_client()

    current_time = {"value": 100.0}

    def fake_now():
        return current_time["value"]

    monkeypatch.setattr(app_module, "_now", fake_now)
    app_module._last_print_at = None

    first = client.get("/bb", query_string={"print": "true"})
    assert first.status_code == 200

    second = client.get("/bb", query_string={"print": "true"})
    assert second.status_code == 429

    current_time["value"] += app_module.PRINT_COOLDOWN_SECONDS + 0.1
    third = client.get("/bb", query_string={"print": "true"})
    assert third.status_code == 200
