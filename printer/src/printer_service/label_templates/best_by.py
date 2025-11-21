from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI
from printer_service.label_templates import bluey_label
from printer_service.label_templates import helper as helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

FONT_POINTS = 48
QR_CAPTION_POINTS = 28
QR_TARGET_HEIGHT_IN = 0.5
HORIZONTAL_PADDING = 20
MIN_LENGTH_PX = bluey_label.CANVAS_HEIGHT_PX // 2  # keep length tight but readable
MARGIN_TOTAL_PX = int(round(QL810W_DPI / 8))  # add 1/8" total margin to text height
QR_MARGIN_PX = 14
QR_GAP_PX = 10

DEFAULT_DELTA_LABEL = "2 weeks"
DEFAULT_DELTA = timedelta(days=14)
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


def describe_delta(form_data: TemplateFormData) -> str:
    return _resolve_delta(form_data)[1]


def compute_best_by(form_data: TemplateFormData) -> Tuple[date, date, str]:
    base_date = _resolve_base_date(form_data)
    delta, delta_label = _resolve_delta(form_data)
    return base_date, base_date + delta, delta_label


def _qr_image(qr_url: str, target_height_px: Optional[int] = None) -> Image.Image:
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        border=1,
        box_size=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")
    if target_height_px is None or target_height_px == qr_image.height:
        return qr_image
    return qr_image.resize((target_height_px, target_height_px), resample=Image.NEAREST)


def _render_qr_label(*, qr_url: str, caption: str, template_slug: str) -> Image.Image:
    qr_height_px = max(int(round(QR_TARGET_HEIGHT_IN * QL810W_DPI)), 120)
    qr_image = _qr_image(qr_url, target_height_px=qr_height_px)

    font = helper.load_font(size_points=QR_CAPTION_POINTS)
    text_width, text_height = _measure_text_size(caption, font)

    width_px = max(qr_image.width + (QR_MARGIN_PX * 2), text_width + (QR_MARGIN_PX * 2))
    height_px = QR_MARGIN_PX + qr_image.height + QR_GAP_PX + text_height + QR_MARGIN_PX

    renderer = helper.LabelDrawingHelper(width=width_px, height=height_px)
    qr_left = (width_px - qr_image.width) // 2
    renderer.canvas.paste(qr_image, (qr_left, QR_MARGIN_PX))
    renderer.advance(QR_MARGIN_PX + qr_image.height + QR_GAP_PX)
    renderer.draw_centered_text(text=caption, font=font, warn_if_past_bottom=None)

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

        base_date, best_by_date, delta_label = compute_best_by(form_data)
        text = f"Best By: {best_by_date.strftime('%Y-%m-%d')}"

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
    "compute_best_by",
    "describe_delta",
    "_qr_image",
    "_render_text_label",
    "_resolve_base_date",
    "_parse_delta_string",
    "_resolve_delta",
    "_today",
]
