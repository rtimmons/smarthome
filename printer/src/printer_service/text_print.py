from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from PIL import Image, ImageDraw

from .label_specs import QL810W_DPI
from .label_templates.helper import FontType, load_font
from .png_upload import PNG_LABEL_SPEC

TEXT_PRINT_VERSION = 1
DEFAULT_TEXT_FILENAME = "text-label.png"
MAX_LINES = 6
MAX_FIELD_CHARACTERS = 256
MAX_TOTAL_CHARACTERS = 2_000

_ALLOWED_FIELDS = frozenset({"version", "filename", "title", "lines", "footer"})
_VARIABLE_PATTERN = re.compile(r"{{([^{}]*)}}")
_VARIABLE_NAMES = frozenset({"Timestamp", "Date", "Time"})

LABEL_MARGIN_INCHES = 0.1
LABEL_MARGIN_PX = round(QL810W_DPI * LABEL_MARGIN_INCHES)
_MAX_TITLE_FONT_PX = 68
_MIN_TITLE_FONT_PX = 24
_MAX_BODY_FONT_PX = 50
_MIN_BODY_FONT_PX = 18
_MAX_FOOTER_FONT_PX = 30
_MIN_FOOTER_FONT_PX = 14
_TITLE_STROKE_PX = 2


class TextPrintValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TextPrintRequest:
    version: int
    filename: str
    title: str | None
    lines: tuple[str, ...]
    footer: str | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "filename": self.filename,
            "title": self.title,
            "lines": list(self.lines),
            "footer": self.footer,
        }


@dataclass(frozen=True)
class RenderedTextLabel:
    image: Image.Image
    filename: str
    title: str | None
    lines: tuple[str, ...]
    footer: str | None
    rendered_at: str


@dataclass(frozen=True)
class _TextBox:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class _LabelLayout:
    title_font: FontType | None
    body_font: FontType
    footer_font: FontType | None
    title_box: _TextBox | None
    body_boxes: tuple[_TextBox, ...]
    body_row_height: int
    footer_box: _TextBox | None
    title_gap: int
    body_gap: int
    footer_gap: int
    width: int
    height: int


def validate_idempotency_key(raw_key: str | None) -> str:
    if raw_key is None:
        raise TextPrintValidationError("Idempotency-Key header is required.")
    if not 1 <= len(raw_key) <= 200:
        raise TextPrintValidationError(
            "Idempotency-Key must contain between 1 and 200 printable ASCII characters."
        )
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in raw_key):
        raise TextPrintValidationError(
            "Idempotency-Key must contain only printable ASCII characters."
        )
    return raw_key


def validate_text_print_request(payload: object) -> TextPrintRequest:
    if not isinstance(payload, Mapping):
        raise TextPrintValidationError("The JSON body must be an object.")

    unknown_fields = sorted(str(field) for field in payload.keys() if field not in _ALLOWED_FIELDS)
    if unknown_fields:
        names = ", ".join(unknown_fields)
        raise TextPrintValidationError(f"Unknown request field(s): {names}.")

    version = payload.get("version")
    if type(version) is not int or version != TEXT_PRINT_VERSION:
        raise TextPrintValidationError(f"version must equal {TEXT_PRINT_VERSION}.")

    filename = _optional_text(payload, "filename")
    if "filename" in payload and not filename:
        raise TextPrintValidationError("filename must not be empty.")
    filename = filename or DEFAULT_TEXT_FILENAME
    title = _optional_text(payload, "title") or None
    footer = _optional_text(payload, "footer") or None

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        raise TextPrintValidationError("lines must be an array containing one to six strings.")
    if not 1 <= len(raw_lines) <= MAX_LINES:
        raise TextPrintValidationError("lines must contain between one and six strings.")

    lines: list[str] = []
    for index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, str):
            raise TextPrintValidationError(f"lines[{index}] must be a string.")
        line = _validated_text(raw_line, f"lines[{index}]")
        lines.append(line)

    fields = [filename, *lines]
    if title is not None:
        fields.append(title)
    if footer is not None:
        fields.append(footer)
    if sum(len(field) for field in fields) > MAX_TOTAL_CHARACTERS:
        raise TextPrintValidationError(
            f"Request text must contain at most {MAX_TOTAL_CHARACTERS:,} characters in total."
        )

    return TextPrintRequest(
        version=TEXT_PRINT_VERSION,
        filename=filename,
        title=title,
        lines=tuple(lines),
        footer=footer,
    )


def canonical_request_hash(text_request: TextPrintRequest) -> str:
    encoded = json.dumps(
        text_request.canonical_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_text_label(
    text_request: TextPrintRequest,
    *,
    render_time: datetime,
) -> RenderedTextLabel:
    if render_time.tzinfo is None or render_time.utcoffset() is None:
        raise ValueError("render_time must be timezone-aware.")

    variables = {
        "Timestamp": render_time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "Date": render_time.strftime("%Y-%m-%d"),
        "Time": render_time.strftime("%H:%M:%S %z"),
    }
    filename = _substitute_variables(text_request.filename, variables)
    title = (
        _substitute_variables(text_request.title, variables)
        if text_request.title is not None
        else None
    )
    lines = tuple(_substitute_variables(line, variables) for line in text_request.lines)
    footer = (
        _substitute_variables(text_request.footer, variables)
        if text_request.footer is not None
        else None
    )

    width, height = PNG_LABEL_SPEC.printable_px
    canvas = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(canvas)
    layout = _find_layout(draw, title=title, lines=lines, footer=footer)
    if layout is None:
        raise TextPrintValidationError(
            "The supplied text cannot fit on a 62 mm label without clipping."
        )

    _draw_layout(canvas, layout, title=title, lines=lines, footer=footer)
    image = canvas.convert("1", dither=Image.Dither.NONE)
    return RenderedTextLabel(
        image=image,
        filename=filename,
        title=title,
        lines=lines,
        footer=footer,
        rendered_at=render_time.isoformat(),
    )


def _optional_text(payload: Mapping[object, object], field: str) -> str:
    if field not in payload:
        return ""
    raw_value = payload[field]
    if not isinstance(raw_value, str):
        raise TextPrintValidationError(f"{field} must be a string.")
    return _validated_text(raw_value, field)


def _validated_text(raw_value: str, field: str) -> str:
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in raw_value):
        raise TextPrintValidationError(f"{field} must not contain newlines or control characters.")
    value = raw_value.strip()
    if len(value) > MAX_FIELD_CHARACTERS:
        raise TextPrintValidationError(
            f"{field} must contain at most {MAX_FIELD_CHARACTERS} Unicode characters."
        )
    for match in _VARIABLE_PATTERN.finditer(value):
        variable = match.group(1)
        if variable not in _VARIABLE_NAMES:
            raise TextPrintValidationError(f"Unknown template variable '{{{{{variable}}}}}'.")
    return value


def _substitute_variables(value: str, variables: Mapping[str, str]) -> str:
    return _VARIABLE_PATTERN.sub(lambda match: variables[match.group(1)], value)


def _find_layout(
    draw: ImageDraw.ImageDraw,
    *,
    title: str | None,
    lines: tuple[str, ...],
    footer: str | None,
) -> _LabelLayout | None:
    available_width = PNG_LABEL_SPEC.width_px - (2 * LABEL_MARGIN_PX)
    available_height = PNG_LABEL_SPEC.height_px - (2 * LABEL_MARGIN_PX)

    for step in range(101):
        scale = 1.0 - (step / 100)
        title_size = _scaled_font_size(_MIN_TITLE_FONT_PX, _MAX_TITLE_FONT_PX, scale)
        body_size = _scaled_font_size(_MIN_BODY_FONT_PX, _MAX_BODY_FONT_PX, scale)
        footer_size = _scaled_font_size(_MIN_FOOTER_FONT_PX, _MAX_FOOTER_FONT_PX, scale)
        title_font = load_font(size_points=title_size) if title is not None else None
        body_font = load_font(size_points=body_size)
        footer_font = load_font(size_points=footer_size) if footer is not None else None

        title_box = (
            _measure(draw, title, title_font, stroke_width=_TITLE_STROKE_PX)
            if title is not None and title_font is not None
            else None
        )
        body_boxes = tuple(_measure(draw, line, body_font) for line in lines)
        footer_box = (
            _measure(draw, footer, footer_font)
            if footer is not None and footer_font is not None
            else None
        )
        body_row_height = max(
            _measure(draw, "Ag", body_font).height,
            *(box.height for box in body_boxes),
        )
        title_gap = max(5, round(12 * scale)) if title_box is not None else 0
        body_gap = max(2, round(6 * scale))
        footer_gap = max(4, round(10 * scale)) if footer_box is not None else 0

        widths = [box.width for box in body_boxes]
        if title_box is not None:
            widths.append(title_box.width)
        if footer_box is not None:
            widths.append(footer_box.width)
        layout_width = max(widths)
        layout_height = (body_row_height * len(body_boxes)) + (body_gap * (len(body_boxes) - 1))
        if title_box is not None:
            layout_height += title_box.height + title_gap
        if footer_box is not None:
            layout_height += footer_gap + footer_box.height

        if layout_width <= available_width and layout_height <= available_height:
            return _LabelLayout(
                title_font=title_font,
                body_font=body_font,
                footer_font=footer_font,
                title_box=title_box,
                body_boxes=body_boxes,
                body_row_height=body_row_height,
                footer_box=footer_box,
                title_gap=title_gap,
                body_gap=body_gap,
                footer_gap=footer_gap,
                width=layout_width,
                height=layout_height,
            )
    return None


def _scaled_font_size(minimum: int, maximum: int, scale: float) -> int:
    return minimum + round((maximum - minimum) * scale)


def _measure(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: FontType,
    *,
    stroke_width: int = 0,
) -> _TextBox:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return _TextBox(
        left=int(left),
        top=int(top),
        width=int(right - left),
        height=int(bottom - top),
    )


def _draw_layout(
    canvas: Image.Image,
    layout: _LabelLayout,
    *,
    title: str | None,
    lines: tuple[str, ...],
    footer: str | None,
) -> None:
    draw = ImageDraw.Draw(canvas)
    y = (canvas.height - layout.height) // 2

    if title is not None and layout.title_font is not None and layout.title_box is not None:
        box = layout.title_box
        draw.text(
            (LABEL_MARGIN_PX - box.left, y - box.top),
            title,
            fill=0,
            font=layout.title_font,
            stroke_width=_TITLE_STROKE_PX,
            stroke_fill=0,
        )
        y += box.height + layout.title_gap

    for index, (line, box) in enumerate(zip(lines, layout.body_boxes, strict=True)):
        line_y = y + ((layout.body_row_height - box.height) // 2)
        draw.text(
            (LABEL_MARGIN_PX - box.left, line_y - box.top),
            line,
            fill=0,
            font=layout.body_font,
        )
        y += layout.body_row_height
        if index < len(lines) - 1:
            y += layout.body_gap

    if footer is not None and layout.footer_font is not None and layout.footer_box is not None:
        y += layout.footer_gap
        box = layout.footer_box
        draw.text(
            (LABEL_MARGIN_PX - box.left, y - box.top),
            footer,
            fill=0,
            font=layout.footer_font,
        )
