from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Optional, Tuple

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI
from printer_service.label_templates import bluey_label
from printer_service.label_templates import helper as helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

FONT_POINTS = 48
QR_CAPTION_POINTS = 22
QR_TARGET_HEIGHT_IN = 0.24
QR_MIN_MODULE_PX = 2
HORIZONTAL_PADDING = 20
MIN_LENGTH_PX = bluey_label.CANVAS_HEIGHT_PX // 2  # keep length tight but readable
MARGIN_TOTAL_PX = int(round(QL810W_DPI / 8))  # add 1/8" total margin to text height
QR_MARGIN_PX = 8
QR_GAP_PX = 0
QR_OVERLAY_MAX_COVERAGE = 0.32  # keep masked area within the high error-correction budget
QR_OVERLAY_WIDTH_RATIO = 0.9
QR_OVERLAY_MIN_MODULES = 6
QR_OVERLAY_PADDING_MODULES = 1
QR_OVERLAY_FONT_POINTS = 24
QR_OVERLAY_MIN_FONT_POINTS = 8
QR_OVERLAY_LINE_GAP_PX = 0
QR_OVERLAY_MAX_LINES = 5
QR_OVERLAY_STROKE_PX = 1
QR_OVERLAY_X_BIAS = -0.08  # shift left (fraction of QR width)
QR_OVERLAY_Y_BIAS = -0.08  # shift up (fraction of QR height)

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


def _wrap_overlay_text(text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Wrap overlay text ignoring word boundaries; truncate last line if needed."""
    if max_width <= 0 or max_lines <= 0:
        return []
    cleaned = text.strip()
    if not cleaned:
        return []

    lines: list[str] = []
    current = ""
    for char in cleaned:
        proposed = f"{current}{char}"
        if _measure_text_size(proposed, font)[0] <= max_width:
            current = proposed
        else:
            if current:
                lines.append(current)
            current = char
            if len(lines) == max_lines - 1:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and len(cleaned) > sum(len(line) for line in lines):
        # Trim the last line so it still fits when we had to stop early.
        last = _trim_text_to_width(lines[-1], font, max_width)
        lines[-1] = last
    return lines


def _measure_text_block_height(lines: list[str], font) -> int:
    if not lines:
        return 0
    height = sum(_measure_text_size(line, font)[1] for line in lines)
    height += QR_OVERLAY_LINE_GAP_PX * (len(lines) - 1)
    return height


def _maybe_apply_overlay(
    qr_image: Image.Image,
    overlay_text: str | None,
    *,
    modules_count: int,
    quiet_zone_modules: int,
) -> Image.Image:
    if not overlay_text:
        return qr_image
    normalized_text = " ".join(overlay_text.split())
    if not normalized_text or modules_count <= 0:
        return qr_image

    total_modules = modules_count + (quiet_zone_modules * 2)
    if total_modules <= 0:
        return qr_image
    module_px = qr_image.width // total_modules
    if module_px <= 0:
        return qr_image

    max_overlay_modules = int(math.sqrt((modules_count * modules_count) * QR_OVERLAY_MAX_COVERAGE))
    overlay_modules = min(
        max_overlay_modules,
        int(round(modules_count * QR_OVERLAY_WIDTH_RATIO)),
        modules_count,
    )
    if overlay_modules < QR_OVERLAY_MIN_MODULES:
        return qr_image

    overlay_size_px = overlay_modules * module_px
    padding_px = QR_OVERLAY_PADDING_MODULES * module_px
    content_box_px = overlay_size_px - (padding_px * 2)
    if content_box_px <= 0:
        return qr_image

    font = None
    wrapped_lines: list[str] = []
    text_height_px = 0
    max_text_width = int(round(content_box_px * QR_OVERLAY_WIDTH_RATIO))
    max_text_height = content_box_px
    for points in range(QR_OVERLAY_FONT_POINTS, QR_OVERLAY_MIN_FONT_POINTS - 1, -2):
        candidate_font = helper.load_font(size_points=points)
        lines = _wrap_overlay_text(
            normalized_text, candidate_font, max_text_width, QR_OVERLAY_MAX_LINES
        )
        text_height = _measure_text_block_height(lines, candidate_font)
        if lines and text_height <= max_text_height:
            font = candidate_font
            wrapped_lines = lines
            text_height_px = text_height
            break
    if font is None or not wrapped_lines or text_height_px <= 0:
        return qr_image

    qr_with_overlay = qr_image.copy()
    draw = ImageDraw.Draw(qr_with_overlay)
    text_top = (qr_image.height - text_height_px) // 2
    bias_y = int(qr_image.height * QR_OVERLAY_Y_BIAS)
    y = max(0, min(qr_image.height - text_height_px, text_top + bias_y))
    for line in wrapped_lines:
        line_width, line_height = _measure_text_size(line, font)
        base_x = (qr_image.width - line_width) // 2
        bias_x = int(qr_image.width * QR_OVERLAY_X_BIAS)
        x = max(0, min(qr_image.width - line_width, base_x + bias_x))
        draw.text(
            (x, y),
            line,
            fill=0,
            font=font,
            stroke_width=QR_OVERLAY_STROKE_PX,
            stroke_fill=255,
        )
        y += line_height + QR_OVERLAY_LINE_GAP_PX

    qr_with_overlay.info.update(qr_image.info)
    qr_with_overlay.info["qr_overlay_applied"] = True
    return qr_with_overlay


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


def _qr_image(
    qr_url: str, target_height_px: Optional[int] = None, overlay_text: str | None = None
) -> Image.Image:
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        border=1,
        box_size=2,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")
    modules_count = qr.modules_count
    quiet_zone_modules = qr.border
    total_modules = modules_count + (quiet_zone_modules * 2)

    qr_image.info["modules_count"] = modules_count
    qr_image.info["quiet_zone_modules"] = quiet_zone_modules
    qr_image.info["qr_overlay_applied"] = False

    if target_height_px is not None and target_height_px != qr_image.height:
        module_px = max(QR_MIN_MODULE_PX, int(round(target_height_px / max(total_modules, 1))))
        target_size_px = max(qr_image.width, total_modules * module_px)
        qr_image = qr_image.resize((target_size_px, target_size_px), resample=Image.NEAREST)

    qr_image = _maybe_apply_overlay(
        qr_image,
        overlay_text,
        modules_count=modules_count,
        quiet_zone_modules=quiet_zone_modules,
    )
    return qr_image


def _render_qr_label(*, qr_url: str, caption: str, template_slug: str) -> Image.Image:
    qr_height_px = max(int(round(QR_TARGET_HEIGHT_IN * QL810W_DPI)), 70)
    qr_image = _qr_image(
        qr_url,
        target_height_px=qr_height_px,
        overlay_text=caption or "Print Best By +2 Weeks",
    )

    width_px = qr_image.width + (QR_MARGIN_PX * 2)
    height_px = QR_MARGIN_PX + qr_image.height + QR_MARGIN_PX

    renderer = helper.LabelDrawingHelper(width=width_px, height=height_px)
    qr_left = (width_px - qr_image.width) // 2
    renderer.canvas.paste(qr_image, (qr_left, QR_MARGIN_PX))
    renderer.advance(QR_MARGIN_PX + qr_image.height)

    spec = BrotherLabelSpec(
        code=bluey_label.LABEL_SPEC.code,
        printable_px=(width_px, height_px),
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

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return self._last_spec or bluey_label.LABEL_SPEC

    def render(self, form_data: TemplateFormData) -> Image.Image:
        if form_data.get_str("QrUrl", "qr_url"):
            delta_label = describe_delta(form_data)
            caption = form_data.get_str("QrText", "qr_text")
            fallback_caption = f"Best By +{delta_label.title()}"
            image = _render_qr_label(
                qr_url=form_data.get_str("QrUrl", "qr_url"),
                caption=caption or fallback_caption,
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
