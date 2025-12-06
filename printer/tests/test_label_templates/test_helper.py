from __future__ import annotations

import io
from pathlib import Path
from typing import cast

import pytest
from PIL import Image, ImageFont
from PIL.Image import Dither

from printer_service.label_templates import helper


def test_label_helper_initializes_canvas_defaults() -> None:
    builder = helper.LabelDrawingHelper(width=100, height=25)
    canvas = builder.canvas

    assert canvas.size == (100, 25)
    assert canvas.mode == "L"
    assert canvas.getpixel((0, 0)) == 255

    builder.draw.rectangle((0, 0, 10, 10), fill=0)
    assert canvas.getpixel((1, 1)) == 0


def test_label_helper_draw_centered_text_advances() -> None:
    builder = helper.LabelDrawingHelper(width=200, height=100)
    font = helper.load_font(size_points=12)

    builder.move_to(10)
    next_y = builder.draw_centered_text(text="Centered", font=font)

    assert next_y > 10
    builder.draw_centered_text(text="Second", font=font)
    assert builder.current_y >= next_y


def test_label_drawing_helper_tracks_state_and_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    context = helper.LabelDrawingHelper(width=120, height=80)
    font = helper.load_font(size_points=18)

    context.move_to(10)
    first_y = context.draw_centered_text(text="Alpha", font=font)

    assert context.current_y == first_y

    context.advance(5)
    context.draw_centered_text(
        text="W" * 40,
        font=font,
        width_warning="too wide",
    )
    assert any("too wide" in warning for warning in context.warnings)

    context.draw_centered_text(
        text="Overflow",
        font=font,
        warn_if_past_bottom=context.current_y - 1,
        height_warning="too tall",
    )
    assert any("too tall" in warning for warning in context.warnings)

    context.draw_centered_text(
        text="Above",
        font=font,
        top=-5,
        advance=False,
        height_warning="above top",
    )
    assert any("above top" in warning for warning in context.warnings)

    def fake_draw_symbol(*, canvas, directory=None, slug, top, horizontal_margin=0):
        symbol_height = 50
        block = Image.new("L", (canvas.width, symbol_height), 0)
        canvas.paste(block, (0, top))
        return top + symbol_height

    monkeypatch.setattr(helper, "_draw_symbol", fake_draw_symbol)
    context.move_to(context.height - 10)
    context.draw_symbol(slug="test")
    assert any("clipped" in warning for warning in context.warnings)

    finalized = context.finalize()
    assert finalized.info["label_warnings"] == context.warnings


def test_label_helper_measure_text_returns_box():
    builder = helper.LabelDrawingHelper(width=150, height=50)
    font = helper.load_font(size_points=16)

    metrics = builder.measure_text(text="Sample", font=font)

    assert metrics.width > 0
    assert metrics.height > 0
    assert metrics[0] == metrics.width
    assert metrics[1] == metrics.height


def test_label_helper_finalize_attaches_warnings():
    builder = helper.LabelDrawingHelper(width=60, height=20)
    font = helper.load_font(size_points=24)
    builder.draw_centered_text(
        text="W" * 40,
        font=font,
        width_warning="test warning",
    )

    result = builder.finalize()

    assert result.mode == "1"
    warnings = result.info["label_warnings"]
    assert "test warning" in warnings


def test_render_svg_symbol_returns_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    svg_path = tmp_path / "icon.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    def fake_svg2png(*, url=None, write_to=None, output_width=None, **_kwargs):
        image = Image.new("LA", (output_width or 10, output_width or 10), (0, 255))
        buffer = write_to or io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        if write_to is None:
            return buffer.getvalue()

    monkeypatch.setattr(helper.cairosvg, "svg2png", fake_svg2png)

    image1 = helper.render_svg_symbol(path=svg_path, output_width=20)
    image2 = helper.render_svg_symbol(path=svg_path, output_width=20)

    assert image1.size == image2.size == (20, 20)
    image1.putpixel((0, 0), (255, 255))
    assert image2.getpixel((0, 0)) != (255, 255)


def test_normalize_choice_validates_options():
    options = ["sleep", "focus"]
    assert helper.normalize_choice(candidate="Sleep", options=options) == "sleep"
    with pytest.raises(ValueError):
        helper.normalize_choice(candidate="invalid", options=options)


def test_normalize_date_parses_and_formats():
    assert helper.normalize_date(raw_value="04/01/24") == "04/01/24"
    with pytest.raises(ValueError):
        helper.normalize_date(raw_value="2024-04-01")


def test_draw_background_symbol_scales_and_centers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    svg_path = tmp_path / "icon.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")
    render_calls: list[int] = []

    def fake_render_svg_symbol(*, path: Path, output_width: int) -> Image.Image:
        render_calls.append(output_width)
        width = output_width
        height = int(round(width * 1.2))
        return Image.new("RGBA", (width, height), (0, 0, 0, 200))

    monkeypatch.setattr(helper, "render_svg_symbol", fake_render_svg_symbol)

    canvas = Image.new("L", (100, 50), 255)
    helper.draw_background_symbol(canvas=canvas, slug="icon", directory=tmp_path, alpha_percent=50)

    assert render_calls == [100, 42]  # scales down to fit height
    assert canvas.getpixel((0, 0)) == 255  # outside the centered symbol remains untouched
    center_pixel = cast(int, canvas.getpixel((canvas.width // 2, canvas.height // 2)))
    assert center_pixel < 255  # alpha-blended symbol darkens the center


def test_draw_background_symbol_validates_alpha_percent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    svg_path = tmp_path / "icon.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    def fake_render_svg_symbol(*, path: Path, output_width: int) -> Image.Image:
        return Image.new("RGBA", (output_width, output_width), (0, 0, 0, 255))

    monkeypatch.setattr(helper, "render_svg_symbol", fake_render_svg_symbol)

    canvas = Image.new("L", (20, 20), 255)
    with pytest.raises(ValueError):
        helper.draw_background_symbol(
            canvas=canvas, slug="icon", directory=tmp_path, alpha_percent=200
        )


def test_draw_repeating_side_text_supports_mask_dithering() -> None:
    width = 160
    height = 120
    font = ImageFont.load_default()

    def build_image(mask_dither: Dither | None, opacity: int = 50) -> Image.Image:
        builder = helper.LabelDrawingHelper(width=width, height=height)
        builder.draw_repeating_side_text(
            text="ABC",
            font=font,
            side_margin=8,
            vertical_margin=10,
            spacing=6,
            opacity_percent=opacity,
            mask_dither=mask_dither,
        )
        return builder.canvas.convert("1", dither=Dither.NONE)

    with_dither = build_image(Dither.ORDERED, 50)
    without_dither = build_image(None, 100)  # Use 100% opacity for non-dithered case

    def count_runs(strip: Image.Image) -> int:
        pixels = strip.load()
        assert pixels is not None
        runs = 0
        in_run = False
        for y in range(strip.height):
            row_has_ink = any(pixels[x, y] == 0 for x in range(strip.width))
            if row_has_ink and not in_run:
                runs += 1
                in_run = True
            elif not row_has_ink and in_run:
                in_run = False
        return runs

    strip_width = 50
    dither_runs_left = count_runs(with_dither.crop((0, 0, strip_width, with_dither.height)))
    dither_runs_right = count_runs(
        with_dither.crop(
            (with_dither.width - strip_width, 0, with_dither.width, with_dither.height)
        )
    )
    assert dither_runs_left == dither_runs_right >= 4

    with_dither_black = sum(1 for value in with_dither.getdata() if value == 0)
    without_dither_black = sum(1 for value in without_dither.getdata() if value == 0)

    # Both images should have some content (black pixels)
    assert with_dither_black > 0
    assert without_dither_black > 0

    # The images should be different (dithering should change the result)
    assert with_dither_black != without_dither_black
