from __future__ import annotations

from typing import List, Optional

from PIL import Image

from printer_service.label_specs import BrotherLabelSpec, QL810W_DPI
from printer_service.label_templates import helper as helper
from printer_service.label_templates.helper import LabelDrawingHelper, SvgSymbolOption
from printer_service.label_templates.base import (
    TemplateContext,
    TemplateDefinition,
    TemplateFormData,
)

# Bluey targets the 2.4" x 1.3" roll but rotates the artwork so it runs lengthwise.
LABEL_WIDTH_IN = 2.4
LABEL_HEIGHT_IN = 1.3
WIDTH_PX = int(LABEL_WIDTH_IN * QL810W_DPI)
HEIGHT_PX = int(LABEL_HEIGHT_IN * QL810W_DPI)
CANVAS_WIDTH_PX = HEIGHT_PX
CANVAS_HEIGHT_PX = WIDTH_PX
LABEL_SPEC = BrotherLabelSpec(
    code="62",
    printable_px=(WIDTH_PX, HEIGHT_PX),
    tape_size_mm=(int(round(LABEL_WIDTH_IN * 25.4)), int(round(LABEL_HEIGHT_IN * 25.4))),
)

# Re-tuned spacing keeps the stacked layout readable on the shorter canvas.
BASE_TOP_MARGIN = 18
EXTRA_TOP_MARGIN = int(round(0.25 * QL810W_DPI))  # add ~1/4" of blank space up top
TOP_MARGIN = BASE_TOP_MARGIN + EXTRA_TOP_MARGIN
BOTTOM_MARGIN = 24
LINE2_OFFSET = 4
SYMBOL_SECTION_SPACING = 10
INITIALS_SIDE_MARGIN = 10
INITIALS_VERTICAL_MARGIN = 18
INITIALS_SIDE_SPACING = 10

# Font sizes balance hierarchy without overrunning the 1.3" height.
TITLE_FONT_POINTS = 60
INITIALS_FONT_POINTS = 60
DATE_FONT_POINTS = 36
BACKGROUND_ALPHA_PERCENT = 25


class Template(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Bluey Label 2"

    @property
    def form_template(self) -> str:
        return "bluey_label.html"

    def get_form_context(self) -> TemplateContext:
        options: List[SvgSymbolOption] = helper.svg_symbol_options()
        return {
            "svg_symbol_options": options,
            "default_svg_symbol": options[0]["slug"] if options else "",
        }

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return LABEL_SPEC

    def render(self, form_data: TemplateFormData) -> Image.Image:
        line1 = form_data.get_str("Line1", "line1")
        line2 = form_data.get_str("Line2", "line2")
        initials = form_data.get_str("Initials", "initials")
        symbol_choice = form_data.get_str("SymbolName", "symbolname")
        package_date_raw = form_data.get_str("PackageDate", "packagedate")

        options = helper.svg_symbol_options()
        available_slugs = [option["slug"] for option in options]
        symbol_slug = helper.normalize_choice(candidate=symbol_choice, options=available_slugs)
        package_date = helper.normalize_date(raw_value=package_date_raw)

        renderer = LabelDrawingHelper(width=CANVAS_WIDTH_PX, height=CANVAS_HEIGHT_PX)
        helper.draw_background_symbol(
            canvas=renderer.canvas,
            slug=symbol_slug,
            alpha_percent=BACKGROUND_ALPHA_PERCENT,
        )
        renderer.move_to(TOP_MARGIN)

        title_font = helper.load_font(size_points=TITLE_FONT_POINTS)
        initials_font = helper.load_font(size_points=INITIALS_FONT_POINTS)
        date_font = helper.load_font(size_points=DATE_FONT_POINTS)

        if line1:
            renderer.draw_centered_text(
                text=line1,
                font=title_font,
                width_warning="Line 1 is wider than the label and will be clipped.",
                height_warning="Text exceeds label height and may be clipped.",
            )
        if line2:
            if line1:
                renderer.advance(LINE2_OFFSET)
            renderer.draw_centered_text(
                text=line2,
                font=title_font,
                width_warning="Line 2 is wider than the label and will be clipped.",
                height_warning="Text exceeds label height and may be clipped.",
            )

        renderer.advance(SYMBOL_SECTION_SPACING)

        if initials:
            renderer.draw_repeating_side_text(
                text=initials,
                font=initials_font,
                side_margin=INITIALS_SIDE_MARGIN,
                vertical_margin=INITIALS_VERTICAL_MARGIN,
                spacing=INITIALS_SIDE_SPACING,
                width_warning="Initials are wider than the label and will be clipped.",
            )

        if package_date:
            # Measure to anchor the date against the bottom margin; overflow warnings come from the helper.
            date_metrics = renderer.measure_text(text=package_date, font=date_font)
            date_y = CANVAS_HEIGHT_PX - BOTTOM_MARGIN - date_metrics.height
            height_check: Optional[int] = CANVAS_HEIGHT_PX
            if date_y < 0:
                height_check = None
            renderer.draw_centered_text(
                text=package_date,
                font=date_font,
                top=date_y,
                advance=False,
                width_warning="Date text is wider than the label and will be clipped.",
                warn_if_past_bottom=height_check,
                height_warning="Date text exceeds label height and may be clipped.",
            )

        portrait_canvas = renderer.canvas
        result = portrait_canvas.convert("1")
        if renderer.warnings:
            result.info["label_warnings"] = list(renderer.warnings)
        return result


TEMPLATE = Template()
