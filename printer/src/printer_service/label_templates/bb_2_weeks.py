from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PIL import Image, ImageDraw

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI
from printer_service.label_templates import bluey_label
from printer_service.label_templates import helper as helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

FONT_POINTS = 48
HORIZONTAL_PADDING = 20
MIN_LENGTH_PX = bluey_label.CANVAS_HEIGHT_PX // 2  # keep length tight but readable
MARGIN_TOTAL_PX = int(round(QL810W_DPI / 8))  # add 1/8" total margin to text height


def _measure_text_size(text: str, font) -> tuple[int, int]:
    dummy = Image.new("L", (1, 1), 255)
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(round(bbox[2] - bbox[0]))
    height = int(round(bbox[3] - bbox[1]))
    return width, height


def _today() -> date:
    return date.today()


def _resolve_base_date(form_data: TemplateFormData) -> date:
    raw_base_date = form_data.get_str("BaseDate", "base_date")
    if raw_base_date:
        try:
            return date.fromisoformat(raw_base_date)
        except ValueError as exc:
            raise ValueError("BaseDate must match YYYY-MM-DD.") from exc
    return _today()


class Template(TemplateDefinition):
    def __init__(self) -> None:
        super().__init__()
        self._last_spec: Optional[BrotherLabelSpec] = None

    @property
    def display_name(self) -> str:
        return "BB 2 Weeks"

    @property
    def form_template(self) -> str:
        return self.default_form_template()

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return self._last_spec or bluey_label.LABEL_SPEC

    def render(self, form_data: TemplateFormData) -> Image.Image:
        base_date = _resolve_base_date(form_data)
        best_by_date = base_date + timedelta(days=14)
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
        return renderer.finalize()


TEMPLATE = Template()
