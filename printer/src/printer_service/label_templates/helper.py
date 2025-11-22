from __future__ import annotations

"""Utilities for label template implementations.

Import this module from template modules to access the common building blocks
that every template is expected to use. The functions exposed here favour strict
typing and sensible defaults for image creation so a new template can be
assembled with autocomplete guidance and the type checker.

Example::

from printer_service.label_templates import helper

    text = form_data.get_str("Line1")
    builder = helper.LabelDrawingHelper(width=203, height=406)
    builder.move_to(24)
    font = helper.load_font(size_points=32)
    builder.draw_centered_text(text=text, font=font)
    image = builder.finalize()
"""

import io
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import (
    Iterable,
    List,
    MutableSequence,
    NamedTuple,
    Sequence,
    Tuple,
    TypedDict,
    Literal,
    Optional,
    TypeAlias,
)

import cairosvg
from PIL import Image, ImageDraw, ImageFont

FontType: TypeAlias = ImageFont.FreeTypeFont | ImageFont.ImageFont

from .base import TemplateFormValue

__all__ = [
    "Box",
    "LabelDrawingHelper",
    "available_symbol_slugs",
    "load_font",
    "normalize_choice",
    "normalize_date",
    "render_svg_symbol",
    "sanitize_lines",
    "SvgSymbolOption",
    "svg_symbol_directory",
    "svg_symbol_options",
    "draw_background_symbol",
]

_MAX_SANITIZED_LINES = 6
_FUTURA_CANDIDATES: Tuple[str, ...] = (
    "Futura.ttc",
    "Futura Medium.ttf",
    "Futura Medium.otf",
    "Futura-Medium.ttf",
    "Futura-Book.ttf",
    "Futura-Normal.ttf",
    "Futura-Bold.ttf",
    "FuturaBT-Medium.ttf",
)


class Box(NamedTuple):
    """Simple width/height tuple with attribute-style access."""

    width: int
    height: int


class SvgSymbolOption(TypedDict):
    slug: str
    label: str


def _iter_candidate_fonts() -> Iterable[str]:
    label_font_path = os.getenv("LABEL_FONT_PATH")
    if label_font_path:
        yield label_font_path
    yield from _FUTURA_CANDIDATES
    yield "DejaVuSans.ttf"


def load_font(*, size_points: int) -> FontType:
    """Load the project default font at ``size_points``."""
    for candidate in _iter_candidate_fonts():
        try:
            return ImageFont.truetype(candidate, size=size_points)
        except OSError:
            continue
    return ImageFont.load_default()


def normalize_choice(
    *,
    candidate: TemplateFormValue,
    options: Sequence[str],
    fallback_index: int = 0,
) -> str:
    """Return a validated lowercase slug chosen from ``options``.

    The result is normalized by trimming whitespace, lowercasing, and replacing
    spaces with underscores so it can be used as a slug or filename stem.
    """
    if not options:
        raise ValueError("No choices are available for this template.")
    normalized = str(candidate or "").strip().lower().replace(" ", "_")
    if not normalized:
        return options[fallback_index]
    if normalized not in options:
        raise ValueError(f"Value '{candidate}' is not one of {sorted(options)}.")
    return normalized


def normalize_date(
    *,
    raw_value: TemplateFormValue,
    input_format: str = "%m/%d/%y",
    output_format: str = "%m/%d/%y",
) -> str:
    """Parse ``raw_value`` using ``input_format`` and reformat it."""
    value = str(raw_value or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, input_format)
    except ValueError as exc:
        raise ValueError(f"Date must match {input_format}.") from exc
    return parsed.strftime(output_format)


def _append_warning(warnings: MutableSequence[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _centered_repeat_positions(
    *, available_height: int, block_height: int, spacing: int, top_offset: int
) -> list[int]:
    """Return y offsets that center repeated blocks within the available height."""
    if available_height <= 0 or block_height <= 0:
        return []
    count = max(1, (available_height + spacing) // (block_height + spacing))
    total_height = (count * block_height) + ((count - 1) * spacing)
    start = top_offset + max(0, (available_height - total_height) // 2)
    return [start + (index * (block_height + spacing)) for index in range(count)]


def _draw_centered_text(
    *,
    draw: ImageDraw.ImageDraw,
    text: str,
    font: FontType,
    canvas_width: int,
    top: int,
    fill: int = 0,
    advance: bool = True,
    margin_bottom: int = 0,
    warnings: MutableSequence[str] | None = None,
    warn_if_wider_than: int | None = None,
    warn_if_past_bottom: int | None = None,
    width_warning: str | None = None,
    height_warning: str | None = None,
) -> int:
    """Draw ``text`` centered in ``canvas_width`` and return the next y value.

    ``fill`` controls the greyscale colour and ``advance`` toggles whether the
    returned value should move to the line following the drawn text.
    """
    metrics = _measure_text(draw=draw, text=text, font=font)
    left = (canvas_width - metrics.width) // 2
    draw.text((left, top), text, fill=fill, font=font)
    bottom_edge = top + metrics.height

    if (
        warnings is not None
        and warn_if_wider_than is not None
        and metrics.width > warn_if_wider_than
    ):
        message = width_warning or "Text is wider than the label and will be clipped."
        _append_warning(warnings, message)

    if (
        warnings is not None
        and warn_if_past_bottom is not None
        and bottom_edge > warn_if_past_bottom
    ):
        message = height_warning or "Text exceeds label height and may be clipped."
        _append_warning(warnings, message)

    if not advance:
        return top
    next_baseline = bottom_edge + margin_bottom
    return next_baseline


# Expose symbol discovery helpers for modules that manage filesystem enumeration directly.
def available_symbol_slugs(*, directory: Path) -> list[str]:
    """Return the sorted list of SVG stem names within ``directory``."""
    return sorted(path.stem for path in directory.glob("*.svg") if path.is_file())


# Expose symbol discovery helpers for modules that manage filesystem enumeration directly.
def svg_symbol_directory() -> Path:
    """Return the default directory containing shared SVG icon assets."""
    return Path(__file__).resolve().parent / "svg_symbols"


# Expose symbol discovery helpers for modules that manage filesystem enumeration directly.
def render_svg_symbol(*, path: Path, output_width: int) -> Image.Image:
    """Rasterise the SVG at ``path`` to a luminance+alpha image."""
    raster = _render_svg_symbol_cached(path.resolve(), output_width)
    return raster.copy()


def draw_background_symbol(
    *,
    canvas: Image.Image,
    slug: str,
    directory: Optional[Path] = None,
    alpha_percent: int = 25,
) -> None:
    """Draw a centered SVG ``slug`` at ``alpha_percent`` opacity behind other content.

    The symbol is rendered to the full canvas width, then scaled proportionally
    if needed to fit the height, keeping the largest unclipped size.
    """
    if not (0 <= alpha_percent <= 100):
        raise ValueError("alpha_percent must be between 0 and 100 inclusive.")

    target_directory = directory or svg_symbol_directory()
    path = (target_directory / f"{slug}.svg").resolve()
    if not path.exists():
        raise ValueError(f"Symbol SVG '{slug}.svg' not found.")

    symbol = render_svg_symbol(path=path, output_width=canvas.width)
    width, height = symbol.size
    if height > canvas.height:
        scale = canvas.height / float(height)
        adjusted_width = max(1, int(round(width * scale)))
        symbol = render_svg_symbol(path=path, output_width=adjusted_width)
        width, height = symbol.size

    symbol_l = symbol.convert("L")
    alpha_scale = alpha_percent / 100.0
    faded_alpha = symbol.getchannel("A").point(lambda value: int(round(value * alpha_scale)))
    left = (canvas.width - width) // 2
    top = (canvas.height - height) // 2
    canvas.paste(symbol_l, (left, top), faded_alpha)


# Provide low-level measurement for components that operate outside the stateful helper.
def _measure_text(
    *,
    draw: ImageDraw.ImageDraw,
    text: str,
    font: FontType,
) -> Box:
    """Return ``(width, height)`` for the given ``text`` and ``font``."""
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(round(bbox[2] - bbox[0]))
    height = int(round(bbox[3] - bbox[1]))
    return Box(width=width, height=height)


def sanitize_lines(lines: Sequence[TemplateFormValue]) -> List[str]:
    """Trim whitespace, drop empty inputs, and enforce the six-line limit."""
    sanitized: List[str] = []
    for line in lines:
        if line is None:
            continue
        text = str(line).strip()
        if text:
            sanitized.append(text)
    return sanitized[:_MAX_SANITIZED_LINES]


# Provide low-level symbol metadata for components that operate outside the stateful helper.
def svg_symbol_options(*, directory: Path | None = None) -> List[SvgSymbolOption]:
    """Return slug/label dictionaries for all SVG symbols in ``directory``."""
    directory = directory or svg_symbol_directory()
    options: List[SvgSymbolOption] = []
    for slug in available_symbol_slugs(directory=directory):
        options.append({"slug": slug, "label": slug.replace("_", " ").title()})
    return options


# Provide low-level drawing for components that operate outside the stateful helper.
def _draw_symbol(
    *,
    canvas: Image.Image,
    directory: Path,
    slug: str,
    top: int,
    horizontal_margin: int = 0,
) -> int:
    """Rasterise and draw the SVG ``slug`` centred on the canvas."""
    path = (directory / f"{slug}.svg").resolve()
    if not path.exists():
        raise ValueError(f"Symbol SVG '{slug}.svg' not found.")
    output_width = canvas.width - (horizontal_margin * 2)
    symbol = render_svg_symbol(path=path, output_width=output_width)
    symbol_l = symbol.convert("L")  # Convert to greyscale for consistent raster quality.
    alpha = symbol.getchannel("A")  # Preserve original alpha channel for masking.
    width, height = symbol.size
    left = (canvas.width - width) // 2
    canvas.paste(symbol_l, (left, top), alpha)
    return top + height


# Provide low-level image finalisation for components that operate outside the stateful helper.
def _finalize_label_image(
    canvas: Image.Image, warnings: Sequence[str] | None = None
) -> Image.Image:
    """Convert ``canvas`` to 1-bit mode and attach optional warning metadata."""
    result = canvas.convert("1")
    if warnings:
        result.info["label_warnings"] = list(warnings)
    return result


class LabelDrawingHelper:
    """Stateful wrapper for building label images with shared context."""

    def __init__(
        self,
        *,
        width: int,
        height: int,
        mode: str = "L",
        color: int = 255,
    ) -> None:
        canvas = Image.new(mode, (width, height), color)
        draw = ImageDraw.Draw(canvas)
        self._canvas: Image.Image = canvas
        self._draw: ImageDraw.ImageDraw = draw
        self._width = width
        self._height = height
        self._current_y = 0
        self._warnings: List[str] = []

    @property
    def canvas(self) -> Image.Image:
        return self._canvas

    @property
    def draw(self) -> ImageDraw.ImageDraw:
        return self._draw

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def current_y(self) -> int:
        return self._current_y

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    def add_warning(self, message: str) -> None:
        """Append a warning if it hasn't already been recorded."""
        _append_warning(self._warnings, message)

    def move_to(self, y: int) -> None:
        self._current_y = y

    def advance(self, offset: int) -> None:
        self._current_y += offset

    def measure_text(self, text: str, font: FontType) -> Box:
        return _measure_text(draw=self._draw, text=text, font=font)

    def draw_centered_text(
        self,
        *,
        text: str,
        font: FontType,
        top: Optional[int] = None,
        fill: int = 0,
        advance: bool = True,
        margin_bottom: int = 0,
        warn_if_wider_than: Literal["auto"] | int | None = "auto",
        warn_if_past_bottom: Literal["auto"] | int | None = "auto",
        width_warning: str | None = None,
        height_warning: str | None = None,
    ) -> int:
        warn_width: Optional[int]
        if warn_if_wider_than == "auto":
            warn_width = self._width
        else:
            warn_width = warn_if_wider_than
        warn_height: Optional[int]
        if warn_if_past_bottom == "auto":
            warn_height = self._height
        else:
            warn_height = warn_if_past_bottom
        actual_top = self._current_y if top is None else top
        next_y = _draw_centered_text(
            draw=self._draw,
            text=text,
            font=font,
            canvas_width=self._width,
            top=actual_top,
            fill=fill,
            advance=advance,
            margin_bottom=margin_bottom,
            warnings=self._warnings,
            warn_if_wider_than=warn_width,
            warn_if_past_bottom=warn_height,
            width_warning=width_warning,
            height_warning=height_warning,
        )
        if height_warning and actual_top < 0:
            _append_warning(self._warnings, height_warning)
        if advance:
            self._current_y = next_y
        return next_y

    def draw_symbol(
        self,
        *,
        directory: Optional[Path] = None,
        slug: str,
        top: Optional[int] = None,
        horizontal_margin: int = 0,
        overflow_warning: str
        | None = "Content extends beyond the label height and may be clipped.",
    ) -> int:
        start_y = self._current_y if top is None else top
        target_directory = directory or svg_symbol_directory()
        next_y = _draw_symbol(
            canvas=self._canvas,
            directory=target_directory,
            slug=slug,
            top=start_y,
            horizontal_margin=horizontal_margin,
        )
        self._current_y = next_y
        if overflow_warning and self._current_y > self._height:
            _append_warning(self._warnings, overflow_warning)
        return next_y

    def draw_repeating_side_text(
        self,
        *,
        text: str,
        font: FontType,
        side_margin: int = 0,
        vertical_margin: int = 0,
        top_margin: int | None = None,
        bottom_margin: int | None = None,
        spacing: int = 0,
        min_top_y: int | None = None,
        center: bool = True,
        width_warning: str | None = None,
        opacity_percent: int = 100,
    ) -> None:
        """Draw rotated ``text`` along both edges, repeating down the label."""
        bbox = self._draw.textbbox((0, 0), text, font=font)
        text_width = int(round(bbox[2] - bbox[0]))
        text_height = int(round(bbox[3] - bbox[1]))
        if text_width <= 0 or text_height <= 0:
            return

        mask = Image.new("L", (text_width, text_height), color=0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.text((-bbox[0], -bbox[1]), text, font=font, fill=255)

        clamped_opacity = max(0, min(opacity_percent, 100))
        effective_mask = (
            mask
            if clamped_opacity == 100
            else mask.point(lambda value: int(round(value * clamped_opacity / 100)))
        )

        left_mask = effective_mask.rotate(90, expand=True)
        right_mask = effective_mask.rotate(-90, expand=True)

        top_gap = vertical_margin if top_margin is None else top_margin
        if min_top_y is not None and min_top_y > top_gap:
            top_gap = min_top_y
        bottom_gap = vertical_margin if bottom_margin is None else bottom_margin
        available_height = max(0, self._height - top_gap - bottom_gap)
        if not center:
            positions: list[int] = []
            current = top_gap
            block_and_spacing = left_mask.height + spacing
            while available_height >= left_mask.height and current + left_mask.height <= (
                top_gap + available_height
            ):
                positions.append(current)
                current += block_and_spacing
                if current > top_gap + available_height:
                    break
        else:
            positions = _centered_repeat_positions(
                available_height=available_height,
                block_height=left_mask.height,
                spacing=spacing,
                top_offset=top_gap,
            )

        left_x = side_margin
        right_x = self._width - side_margin - right_mask.width
        if width_warning and (left_x + left_mask.width > self._width or right_x < 0):
            self.add_warning(width_warning)

        for y in positions:
            self._canvas.paste(0, (left_x, y), left_mask)
            self._canvas.paste(0, (max(0, right_x), y), right_mask)

    def finalize(self) -> Image.Image:
        return _finalize_label_image(self._canvas, self._warnings)


@lru_cache(maxsize=128)
def _render_svg_symbol_cached(path: Path, output_width: int) -> Image.Image:
    buffer = io.BytesIO()
    cairosvg.svg2png(url=str(path), write_to=buffer, output_width=output_width)
    buffer.seek(0)
    return Image.open(buffer).convert("LA")
