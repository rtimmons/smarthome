from __future__ import annotations

import urllib.parse
import math
from datetime import date, timedelta
from typing import Optional, Tuple

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI
from printer_service.label_templates import bluey_label
from printer_service.label_templates import helper as helper
from printer_service.label_templates.base import (
    TemplateContext,
    TemplateDefinition,
    TemplateFormData,
)

FONT_POINTS = 48
# Target a ~0.5\" printed QR so it stays readable while keeping the label compact.
QR_TARGET_HEIGHT_IN = 0.5
QR_MIN_MODULE_PX = 2
HORIZONTAL_PADDING = 20
MIN_LENGTH_PX = bluey_label.CANVAS_HEIGHT_PX // 2  # keep length tight but readable
MARGIN_TOTAL_PX = int(round(QL810W_DPI / 8))  # add 1/8" total margin to text height
QR_MARGIN_PX = 2
QR_TEXT_GAP_PX = 16
QR_LABEL_MIN_HEIGHT_PX = 120
QR_TEXT_FONT_POINTS = 28
QR_TEXT_MAX_LINES = 4
QR_TEXT_LINE_GAP_PX = 6
QR_TEXT_VERTICAL_PADDING_PX = 10
QR_TEXT_HORIZONTAL_PADDING_PX = 12

DEFAULT_DELTA_LABEL = "2 weeks"
DEFAULT_DELTA = timedelta(days=14)
DEFAULT_PREFIX = "Best By: "
_DELTA_MULTIPLIERS = {
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}


def _measure_text_size(text: str, font) -> tuple[int, int]:
    dummy = Image.new("L", (1, 1), 255)
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(round(bbox[2] - bbox[0]))
    height = int(round(bbox[3] - bbox[1]))
    return width, height


def _trim_text_to_width(text: str, font, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if _measure_text_size(text, font)[0] <= max_width:
        return text

    ellipsis = "..."
    ellipsis_width, _ = _measure_text_size(ellipsis, font)
    if ellipsis_width > max_width:
        # Fall back to the smallest visible slice we can fit.
        for char in text:
            if _measure_text_size(char, font)[0] <= max_width:
                return char
        return ""

    for end in range(len(text), 0, -1):
        candidate = text[:end].rstrip()
        if not candidate:
            continue
        candidate_with_ellipsis = f"{candidate}{ellipsis}"
        if _measure_text_size(candidate_with_ellipsis, font)[0] <= max_width:
            return candidate_with_ellipsis
    return ""


def _wrap_caption_lines(text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Wrap caption text into ``max_lines`` respecting ``max_width`` per line."""
    if max_width <= 0 or max_lines <= 0:
        return []
    normalized = " ".join(text.split())
    if not normalized:
        return []

    lines: list[str] = []
    current = ""
    words = normalized.split(" ")
    index = 0
    while index < len(words):
        word = words[index]
        candidate = word if not current else f"{current} {word}"
        if _measure_text_size(candidate, font)[0] <= max_width:
            current = candidate
            index += 1
            continue

        if current:
            lines.append(current)
        else:
            lines.append(_trim_text_to_width(word, font, max_width))
            index += 1
        current = ""
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and index < len(words):
        lines[-1] = _trim_text_to_width(lines[-1], font, max_width)
    return lines


def _measure_text_block_height(lines: list[str], font, line_gap: int) -> int:
    if not lines:
        return 0
    height = sum(_measure_text_size(line, font)[1] for line in lines)
    height += line_gap * (len(lines) - 1)
    return height


def _normalize_caption_piece(raw: str, *, title_case: bool = False) -> str:
    cleaned = " ".join(str(raw).split())
    if not cleaned:
        return ""
    if title_case:
        return cleaned.replace("_", " ").title()
    return cleaned


def _extract_query_value(query: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = query.get(key)
        if values:
            return values[0]
    return ""


def _build_qr_caption(qr_url: str, caption: str, delta_label: str) -> str:
    provided = " ".join((caption or "").split())
    parsed = urllib.parse.urlparse(qr_url)
    query = urllib.parse.parse_qs(parsed.query)
    template_slug = _normalize_caption_piece(
        _extract_query_value(query, "tpl", "template"), title_case=True
    )
    details: list[str] = []

    detail_keys = [
        ("Line1", False),
        ("Line2", False),
        ("SymbolName", True),
        ("Initials", False),
        ("PackageDate", False),
    ]
    for key, title_case in detail_keys:
        value = _normalize_caption_piece(
            _extract_query_value(query, key, key.lower()), title_case=title_case
        )
        if value:
            details.append(value)

    if template_slug:
        prefix = f"Print {template_slug}"
    elif provided:
        prefix = provided
    else:
        prefix = f"Print Best By +{delta_label.title()}"

    if details:
        return f"{prefix}: {', '.join(details)}"
    if provided:
        return provided
    return prefix


def _today() -> date:
    return date.today()


def _parse_delta_string(raw: str | None) -> Tuple[timedelta, str]:
    if raw is None:
        return DEFAULT_DELTA, DEFAULT_DELTA_LABEL
    normalized_raw = " ".join(str(raw).strip().lower().split())
    if not normalized_raw:
        return DEFAULT_DELTA, DEFAULT_DELTA_LABEL
    parts = normalized_raw.split(" ")
    magnitude_token = parts[0]
    unit_token = parts[1] if len(parts) > 1 else "days"
    try:
        magnitude = int(magnitude_token)
    except (TypeError, ValueError) as exc:
        raise ValueError("Delta must start with an integer.") from exc
    unit = unit_token.rstrip("s")
    multiplier = _DELTA_MULTIPLIERS.get(unit)
    if multiplier is None:
        raise ValueError("Delta must use days, weeks, months, or years.")
    days = magnitude * multiplier
    normalized_unit = unit if abs(magnitude) == 1 else f"{unit}s"
    return timedelta(days=days), f"{magnitude} {normalized_unit}"


def _resolve_base_date(form_data: TemplateFormData) -> date:
    raw_base_date = form_data.get_str("BaseDate", "base_date")
    if raw_base_date:
        try:
            return date.fromisoformat(raw_base_date)
        except ValueError as exc:
            raise ValueError("BaseDate must match YYYY-MM-DD.") from exc
    return _today()


def _resolve_delta(form_data: TemplateFormData) -> Tuple[timedelta, str]:
    raw_delta = form_data.get_str("Delta", "delta")
    return _parse_delta_string(raw_delta or None)


def _resolve_prefix(form_data: TemplateFormData) -> str:
    # Use .get() instead of .get_str() to preserve spaces
    # Check if prefix was explicitly provided (even if empty)
    if "Prefix" in form_data:
        raw_prefix = form_data.get("Prefix")
        return str(raw_prefix) if raw_prefix is not None else ""
    if "prefix" in form_data:
        raw_prefix = form_data.get("prefix")
        return str(raw_prefix) if raw_prefix is not None else ""
    return DEFAULT_PREFIX


def describe_delta(form_data: TemplateFormData) -> str:
    return _resolve_delta(form_data)[1]


def compute_best_by(form_data: TemplateFormData) -> Tuple[date, date, str, str]:
    base_date = _resolve_base_date(form_data)
    delta, delta_label = _resolve_delta(form_data)
    prefix = _resolve_prefix(form_data)
    return base_date, base_date + delta, delta_label, prefix


def _qr_image(qr_url: str, target_height_px: Optional[int] = None) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        border=1,
        box_size=1,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")
    modules_count = qr.modules_count
    quiet_zone_modules = qr.border
    total_modules = modules_count + (quiet_zone_modules * 2)

    qr_image.info["modules_count"] = modules_count
    qr_image.info["quiet_zone_modules"] = quiet_zone_modules

    if target_height_px is not None and target_height_px != qr_image.height:
        module_px = max(QR_MIN_MODULE_PX, int(math.ceil(target_height_px / max(total_modules, 1))))
        target_size_px = max(qr_image.width, total_modules * module_px)
        qr_image = qr_image.resize((target_size_px, target_size_px), resample=Image.NEAREST)

    qr_image.info["qr_overlay_applied"] = False
    return qr_image


def _render_qr_label(*, qr_url: str, caption: str, template_slug: str) -> Image.Image:
    width_px, height_px = bluey_label.LABEL_SPEC.printable_px
    max_qr_height_px = max(height_px - (QR_MARGIN_PX * 2), QR_LABEL_MIN_HEIGHT_PX)
    qr_target_height = max(int(round(QR_TARGET_HEIGHT_IN * QL810W_DPI)), QR_LABEL_MIN_HEIGHT_PX)
    qr_height_px = min(max_qr_height_px, qr_target_height)
    qr_image = _qr_image(qr_url, target_height_px=qr_height_px)

    caption_text = caption
    text_font = helper.load_font(size_points=QR_TEXT_FONT_POINTS)
    text_area_left = QR_MARGIN_PX + qr_image.width + QR_TEXT_GAP_PX
    text_area_right = width_px - QR_TEXT_HORIZONTAL_PADDING_PX
    max_text_width = max(text_area_right - (text_area_left + QR_TEXT_HORIZONTAL_PADDING_PX), 1)
    wrapped_caption = _wrap_caption_lines(
        caption_text,
        text_font,
        max_text_width,
        QR_TEXT_MAX_LINES,
    )
    text_height_px = _measure_text_block_height(wrapped_caption, text_font, QR_TEXT_LINE_GAP_PX)

    qr_label_height_px = max(
        qr_image.height + (QR_MARGIN_PX * 2),
        max(QR_LABEL_MIN_HEIGHT_PX, text_height_px + (QR_TEXT_VERTICAL_PADDING_PX * 2)),
    )
    renderer = helper.LabelDrawingHelper(width=width_px, height=qr_label_height_px)
    qr_left = QR_MARGIN_PX
    qr_top = max((qr_label_height_px - qr_image.height) // 2, QR_MARGIN_PX)
    renderer.canvas.paste(qr_image, (qr_left, qr_top))

    text_left = text_area_left + QR_TEXT_HORIZONTAL_PADDING_PX
    text_top = max((qr_label_height_px - text_height_px) // 2, QR_TEXT_VERTICAL_PADDING_PX)
    current_y = text_top
    for line in wrapped_caption:
        renderer.draw.text((text_left, current_y), line, fill=0, font=text_font)
        line_height = _measure_text_size(line, text_font)[1]
        current_y += line_height + QR_TEXT_LINE_GAP_PX

    spec = BrotherLabelSpec(
        code=bluey_label.LABEL_SPEC.code,
        printable_px=(width_px, qr_label_height_px),
        tape_size_mm=bluey_label.LABEL_SPEC.tape_size_mm,
    )
    result = renderer.finalize()
    result.info["template_slug"] = template_slug
    return result


def _render_text_label(*, text: str, template_slug: str) -> Image.Image:
    if not text.strip():
        raise ValueError("Text must not be empty.")
    font = helper.load_font(size_points=FONT_POINTS)
    text_width, text_height = _measure_text_size(text, font)
    width_px = max(text_width + (HORIZONTAL_PADDING * 2), MIN_LENGTH_PX)
    height_px = max(text_height + MARGIN_TOTAL_PX, text_height + 1)

    renderer = helper.LabelDrawingHelper(width=width_px, height=height_px)
    top = max((height_px - text_height) // 2, 0)
    renderer.draw_centered_text(text=text, font=font, top=top)

    result = renderer.finalize()
    result.info["template_slug"] = template_slug
    result.info["text"] = text
    return result


class Template(TemplateDefinition):
    def __init__(self) -> None:
        super().__init__()
        self._last_spec: Optional[BrotherLabelSpec] = None

    @property
    def display_name(self) -> str:
        return "Best By"

    @property
    def form_template(self) -> str:
        return self.default_form_template()

    def get_form_context(self) -> TemplateContext:
        return {
            "base_date_default": _today().isoformat(),
            "delta_default": DEFAULT_DELTA_LABEL,
            "prefix_default": DEFAULT_PREFIX,
        }

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return self._last_spec or bluey_label.LABEL_SPEC

    def render(self, form_data: TemplateFormData) -> Image.Image:
        if form_data.get_str("QrUrl", "qr_url"):
            delta_label = describe_delta(form_data)
            caption = form_data.get_str("QrText", "qr_text")
            resolved_caption = _build_qr_caption(
                form_data.get_str("QrUrl", "qr_url"), caption or "", delta_label
            )
            image = _render_qr_label(
                qr_url=form_data.get_str("QrUrl", "qr_url"),
                caption=resolved_caption,
                template_slug=self.slug,
            )
            self._last_spec = BrotherLabelSpec(
                code=bluey_label.LABEL_SPEC.code,
                printable_px=image.size,
                tape_size_mm=bluey_label.LABEL_SPEC.tape_size_mm,
            )
            return image

        text_value = form_data.get_str("Text", "text")
        if text_value:
            normalized_text = " ".join(text_value.split())
            image = _render_text_label(text=normalized_text, template_slug=self.slug)
            self._last_spec = BrotherLabelSpec(
                code=bluey_label.LABEL_SPEC.code,
                printable_px=image.size,
                tape_size_mm=bluey_label.LABEL_SPEC.tape_size_mm,
            )
            image.info["text"] = normalized_text
            return image

        base_date, best_by_date, delta_label, prefix = compute_best_by(form_data)
        text = f"{prefix}{best_by_date.strftime('%Y-%m-%d')}"

        font = helper.load_font(size_points=FONT_POINTS)
        text_width, text_height = _measure_text_size(text, font)
        width_px = max(text_width + (HORIZONTAL_PADDING * 2), MIN_LENGTH_PX)
        height_px = max(text_height + MARGIN_TOTAL_PX, text_height + 1)

        renderer = helper.LabelDrawingHelper(width=width_px, height=height_px)
        top = max((height_px - text_height) // 2, 0)
        renderer.draw_centered_text(text=text, font=font, top=top)

        self._last_spec = BrotherLabelSpec(
            code=bluey_label.LABEL_SPEC.code,
            printable_px=(width_px, height_px),
            tape_size_mm=bluey_label.LABEL_SPEC.tape_size_mm,
        )
        result = renderer.finalize()
        result.info["template_slug"] = self.slug
        result.info["best_by_date"] = best_by_date.isoformat()
        result.info["delta_label"] = delta_label
        return result


TEMPLATE = Template()

__all__ = [
    "Template",
    "TEMPLATE",
    "DEFAULT_DELTA",
    "DEFAULT_DELTA_LABEL",
    "DEFAULT_PREFIX",
    "compute_best_by",
    "describe_delta",
    "_qr_image",
    "_render_text_label",
    "_resolve_base_date",
    "_resolve_prefix",
    "_parse_delta_string",
    "_resolve_delta",
    "_today",
]
