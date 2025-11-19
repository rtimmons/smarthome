from __future__ import annotations

from typing import List

from PIL import Image

from printer_service.label import PrinterConfig
from printer_service.label_specs import resolve_brother_label_spec
from printer_service.label_templates import helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

LABEL_SPEC = resolve_brother_label_spec(PrinterConfig.from_env().brother_label)
WIDTH_PX, HEIGHT_PX = LABEL_SPEC.printable_px
TOP_MARGIN = 48
LINE_SPACING = 64
FONT_SIZE = 44


class Template(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Kitchen Label Printer"

    @property
    def form_template(self) -> str:
        return "kitchen_label_printer.html"

    def render(self, form_data: TemplateFormData) -> Image.Image:
        raw_lines: List[str] = [
            form_data.get_str("line1"),
            form_data.get_str("line2"),
            form_data.get_str("line3"),
        ]
        lines = helper.sanitize_lines(raw_lines)
        renderer = helper.LabelDrawingHelper(width=WIDTH_PX, height=HEIGHT_PX)
        renderer.move_to(TOP_MARGIN)
        font = helper.load_font(size_points=FONT_SIZE)
        for index, line in enumerate(lines, start=1):
            if not line:
                continue
            renderer.draw_centered_text(
                text=line,
                font=font,
                width_warning=f"Line {index} is wider than the label and will be clipped.",
                height_warning="Text exceeds label height and may be clipped.",
            )
            if index < len(lines):
                renderer.advance(LINE_SPACING)
        return renderer.finalize()


TEMPLATE = Template()
