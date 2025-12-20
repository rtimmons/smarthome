from __future__ import annotations

import importlib
import io
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image, ImageFont

from printer_service.label_specs import resolve_brother_label_spec
from printer_service.label_templates import bluey_label as bluey_module
from printer_service.label_templates.base import TemplateFormData
from printer_service.presets import (
    Preset,
    canonical_query_string,
    normalize_template_slug,
    slug_for_params,
)

TEST_LABEL_CODE = "29x90"
TEST_LABEL_SPEC = resolve_brother_label_spec(TEST_LABEL_CODE)
EXPECTED_WIDTH_PX, EXPECTED_HEIGHT_PX = TEST_LABEL_SPEC.printable_px
EXPECTED_WIDTH_IN = TEST_LABEL_SPEC.width_in
EXPECTED_HEIGHT_IN = TEST_LABEL_SPEC.height_in
EXPECTED_CANVAS = (EXPECTED_WIDTH_PX, EXPECTED_HEIGHT_PX)
BLUEY_EXPECTED_CANVAS = (bluey_module.CANVAS_WIDTH_PX, bluey_module.CANVAS_HEIGHT_PX)
BLUEY_EXPECTED_WIDTH_IN = bluey_module.LABEL_HEIGHT_IN
BLUEY_EXPECTED_HEIGHT_IN = bluey_module.LABEL_WIDTH_IN


class FakePresetStore:
    def __init__(self) -> None:
        self._presets: dict[str, Preset] = {}

    def list_presets(self, *, sort_by: str = "name", limit: int = 200) -> list[Preset]:
        presets = list(self._presets.values())
        if sort_by == "updated":
            presets.sort(key=lambda preset: preset.updated_at, reverse=True)
        else:
            presets.sort(key=lambda preset: preset.name)
        return presets[:limit]

    def find_by_slug(self, slug: str) -> Preset | None:
        return self._presets.get(slug)

    def find_slug_for_params(self, template_slug: str, params: dict) -> str | None:
        slug = slug_for_params(template_slug, params)
        return slug if slug in self._presets else None

    def upsert_preset(self, name: str, template_slug: str, params: dict) -> Preset:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required.")
        template = normalize_template_slug(template_slug)
        query = canonical_query_string(template, params)
        slug = slug_for_params(template, params)
        now = datetime.now(timezone.utc).isoformat()
        existing = self._presets.get(slug)
        created_at = existing.created_at if existing else now
        preset = Preset(
            slug=slug,
            name=normalized_name,
            template=template,
            query=query,
            params=dict(params),
            created_at=created_at,
            updated_at=now,
        )
        self._presets[slug] = preset
        return preset

    def delete_preset(self, slug: str) -> bool:
        return self._presets.pop(slug, None) is not None

    def close(self) -> None:
        return None


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


def _use_fake_preset_store(
    monkeypatch: pytest.MonkeyPatch, app_module: types.ModuleType, store: FakePresetStore
) -> None:
    monkeypatch.setattr(
        app_module.PresetStore,
        "from_env",
        classmethod(lambda cls: store),
    )


@pytest.fixture
def test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    return _build_test_environment(tmp_path, monkeypatch)


def test_bb_preview_returns_dual_images(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("bluey_label").slug
    response = client.post(
        "/bb/preview",
        json={"template": template_slug, "data": {"Line1": "Alpha"}},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "preview"
    assert payload["template"] == template_slug
    assert payload["label"]["image"].startswith("data:image/png;base64,")
    assert payload["qr"]["image"].startswith("data:image/png;base64,")
    metrics = payload["label"]["metrics"]
    assert metrics["width_px"] == BLUEY_EXPECTED_CANVAS[0]
    assert metrics["height_px"] == BLUEY_EXPECTED_CANVAS[1]
    assert metrics["width_in"] == pytest.approx(BLUEY_EXPECTED_WIDTH_IN, rel=0, abs=0.01)
    assert metrics["height_in"] == pytest.approx(BLUEY_EXPECTED_HEIGHT_IN, rel=0, abs=0.01)


def test_bb_preview_uses_preset_slug_for_qr_url(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()
    store = FakePresetStore()
    _use_fake_preset_store(monkeypatch, app_module, store)

    template_slug = templates_module.get_template("bluey_label").slug
    params = {"Line1": "Oat Milk"}
    preset = store.upsert_preset("Oat Milk", template_slug, params)

    response = client.post(
        "/bb/preview",
        json={"template": template_slug, "data": params},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    parsed = urlparse(payload["print_url"])
    assert parsed.path.endswith(f"/p/{preset.slug}")
    assert parsed.query == ""


def test_bb_preview_qr_url_falls_back_without_preset(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()
    store = FakePresetStore()
    _use_fake_preset_store(monkeypatch, app_module, store)

    template_slug = templates_module.get_template("bluey_label").slug
    params = {"Line1": "Beta"}

    response = client.post(
        "/bb/preview",
        json={"template": template_slug, "data": params},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    parsed = urlparse(payload["print_url"])
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/bb")
    assert query.get("print") == ["true"]


def test_bb_preview_validates_payload(test_environment: Tuple) -> None:
    _, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.default_template().slug
    response = client.post(
        "/bb/preview",
        json={"template": template_slug},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["error"] == "Provide 'data' as an object of form inputs."


def test_bb_print_dispatches_label(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("bluey_label").slug
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["backend"] = config.backend
        return tmp_path / "printed.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Use the new execute-print endpoint
    response = client.post("/bb/execute-print", query_string={"tpl": template_slug})

    assert response.status_code == 200  # Returns JSON response
    assert dispatched["called"] is True
    assert dispatched["backend"] == "file"

    # Should return JSON response
    data = response.get_json()
    assert data is not None


def test_bb_print_can_send_qr_label(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("bluey_label").slug
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["backend"] = config.backend
        return tmp_path / "qr.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Use the new execute-print endpoint
    response = client.post(
        "/bb/execute-print",
        query_string={"tpl": template_slug, "qr": "true"},
    )

    assert response.status_code == 200  # Returns JSON response
    assert dispatched["called"] is True

    # Should return JSON response
    data = response.get_json()
    assert data is not None


def test_bb_print_can_send_jar_label(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("bluey_label").slug
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["backend"] = config.backend
        return tmp_path / "jar.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Use the new execute-print endpoint with jar parameter
    response = client.post(
        "/bb/execute-print",
        query_string={
            "tpl": template_slug,
            "jar": "true",
            "Line1": "Test",
            "Line2": "Jar",
            "Supplier": "Test Supplier",
            "Percentage": "100%",
        },
    )

    assert response.status_code == 200  # Returns JSON response
    assert dispatched["called"] is True

    # Should return JSON response
    data = response.get_json()
    assert data is not None


def test_sanitize_lines_trims_and_limits(test_environment: Tuple) -> None:
    helper_module = importlib.import_module("printer_service.label_templates.helper")
    helper_module = importlib.reload(helper_module)
    lines = ["  keep  ", "", "   ", None, "B", "C", "D", "E", "F", "G"]
    assert helper_module.sanitize_lines(lines) == ["keep", "B", "C", "D", "E", "F"]


@pytest.mark.parametrize("bluey_slug", ["bluey_label"])
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


def test_bluey_initials_repeat_along_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    helper_module = importlib.import_module("printer_service.label_templates.helper")
    bluey_template = importlib.reload(
        importlib.import_module("printer_service.label_templates.bluey_label")
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
        importlib.import_module("printer_service.label_templates.bluey_label")
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


@pytest.mark.parametrize("bluey_slug", ["bluey_label"])
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
        brother_label="29x90",
        rotate="auto",
        high_quality=True,
        cut=True,
    )
    image = Image.new("1", (EXPECTED_WIDTH_PX + 100, EXPECTED_HEIGHT_PX + 100), color=1)
    metrics = label_module.analyze_label_image(image, config)
    assert metrics.fits_target is False
    assert metrics.warnings


def test_bb_print_parameter_loads_page_with_countdown(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that ?print=true loads page normally (countdown handled by JS)."""
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    # Test with print=true parameter
    response = client.get("/bb?print=true&Text=Test+Label")

    # Should load page normally (200) - countdown handled by JavaScript
    assert response.status_code == 200

    # Should contain countdown container
    assert b"printCountdownContainer" in response.data


def test_bb_execute_print_endpoint_triggers_print(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that POST /bb/execute-print triggers print and returns JSON."""
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("best_by").slug
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["backend"] = config.backend
        return tmp_path / "printed.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Test execute-print endpoint
    response = client.post("/bb/execute-print?Text=Test+Label")

    # Should return JSON (200) with print result
    assert response.status_code == 200
    assert dispatched["called"] is True

    # Should return JSON response
    data = response.get_json()
    assert data is not None
    assert "status" in data


def test_bb_execute_print_endpoint_with_qr_parameter(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that POST /bb/execute-print handles QR parameter correctly."""
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    template_slug = templates_module.get_template("best_by").slug
    dispatched: dict[str, object] = {}

    def fake_dispatch(image, config, **_kwargs):
        dispatched["called"] = True
        dispatched["qr_requested"] = True
        return tmp_path / "printed_qr.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Test execute-print endpoint with QR parameter
    response = client.post("/bb/execute-print?qr=true&Text=Test+QR")

    # Should return JSON (200) with print result
    assert response.status_code == 200
    assert dispatched["called"] is True

    # Should return JSON response
    data = response.get_json()
    assert data is not None
    assert "status" in data


def test_bb_execute_print_endpoint_handles_print_errors(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that execute-print endpoint returns errors as JSON."""
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    def fake_dispatch_error(image, config, **_kwargs):
        raise ValueError("Printer not available")

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch_error)

    # Test execute-print endpoint with error
    response = client.post("/bb/execute-print?Text=Test+Error")

    # Should return error (400) as JSON
    assert response.status_code == 400
    assert response.json["error"] == "Printer not available"


def test_no_cooldown_on_rapid_prints(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that rapid successive prints work without cooldown errors."""
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()

    dispatched_count = 0

    def fake_dispatch(image, config, **_kwargs):
        nonlocal dispatched_count
        dispatched_count += 1
        return tmp_path / f"printed_{dispatched_count}.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)

    # Make three rapid successive print requests
    for i in range(3):
        response = client.post(f"/bb/execute-print?Text=Test+Label+{i}")
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert data["status"] == "sent"
        # Should not have any cooldown errors
        assert "error" not in data

    # All three prints should have been dispatched
    assert dispatched_count == 3


def test_presets_create_list_delete(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()
    store = FakePresetStore()
    _use_fake_preset_store(monkeypatch, app_module, store)

    template_slug = templates_module.get_template("bluey_label").slug
    response = client.post(
        "/presets",
        json={"name": "Oat Milk", "template": template_slug, "data": {"Line1": "Oat Milk"}},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    preset = payload["preset"]
    assert preset["name"] == "Oat Milk"
    slug = preset["slug"]

    response = client.get("/presets")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["count"] == 1
    assert payload["presets"][0]["slug"] == slug

    response = client.delete(f"/presets/{slug}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["deleted"] is True

    response = client.get("/presets")
    payload = response.get_json()
    assert payload is not None
    assert payload["count"] == 0


def test_preset_redirects_to_bb(test_environment: Tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    app_module, templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()
    store = FakePresetStore()
    _use_fake_preset_store(monkeypatch, app_module, store)

    template_slug = templates_module.get_template("bluey_label").slug
    params = {"Line1": "Oat Milk"}
    preset = store.upsert_preset("Oat Milk", template_slug, params)

    response = client.get(f"/p/{preset.slug}")

    assert response.status_code == 302
    expected_query = canonical_query_string(template_slug, params)
    assert response.headers["Location"].endswith(f"/bb?{expected_query}")


def test_preset_missing_returns_404(
    test_environment: Tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, _templates_module, flask_app, _labels_dir, _ = test_environment
    client = flask_app.test_client()
    store = FakePresetStore()
    _use_fake_preset_store(monkeypatch, app_module, store)

    response = client.get("/p/missing")

    assert response.status_code == 404
