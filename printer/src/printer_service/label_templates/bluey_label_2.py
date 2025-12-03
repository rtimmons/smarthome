from __future__ import annotations

from typing import List, Optional

from PIL import Image, ImageChops, ImageDraw

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
TITLE_REPEAT_COUNT = 4

# Font sizes balance hierarchy without overrunning the 1.3" height.
TITLE_FONT_POINTS = 60
INITIALS_FONT_POINTS = 48
DATE_FONT_POINTS = 18
BACKGROUND_ALPHA_PERCENT = 25
INITIALS_OPACITY_PERCENT = 50
TITLE_BLOCK_PADDING = int(round(0.16 * QL810W_DPI))


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

        background_canvas = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=255)
        helper.draw_background_symbol(
            canvas=background_canvas,
            slug=symbol_slug,
            alpha_percent=BACKGROUND_ALPHA_PERCENT,
        )
        renderer.move_to(TOP_MARGIN)

        title_font = helper.load_font(size_points=TITLE_FONT_POINTS)
        initials_font = helper.load_font(size_points=INITIALS_FONT_POINTS)
        date_font = helper.load_font(size_points=DATE_FONT_POINTS)
        title_lines = []

        if line1:
            title_lines.append(
                (
                    line1,
                    renderer.measure_text(text=line1, font=title_font),
                    "Line 1",
                )
            )
        if line2:
            title_lines.append(
                (
                    line2,
                    renderer.measure_text(text=line2, font=title_font),
                    "Line 2",
                )
            )

        max_title_width = max((metrics.width for _, metrics, _ in title_lines), default=0)

        if title_lines:
            for repeat_index in range(TITLE_REPEAT_COUNT):
                for line_index, (text, _metrics, label_name) in enumerate(title_lines):
                    renderer.draw_centered_text(
                        text=text,
                        font=title_font,
                        width_warning=f"{label_name} is wider than the label and will be clipped.",
                        height_warning="Text exceeds label height and may be clipped.",
                    )
                    if line_index == 0 and len(title_lines) > 1:
                        renderer.advance(LINE2_OFFSET)
                if repeat_index < TITLE_REPEAT_COUNT - 1:
                    renderer.advance(TITLE_BLOCK_PADDING)

        renderer.advance(SYMBOL_SECTION_SPACING)

        if initials:
            initials_top_margin: Optional[int] = None
            initials_min_top: Optional[int] = None
            initials_center = True
            bbox = renderer.draw.textbbox((0, 0), initials, font=initials_font)
            text_width = int(round(bbox[2] - bbox[0]))
            text_height = int(round(bbox[3] - bbox[1]))
            if text_width > 0 and text_height > 0:
                mask = Image.new("L", (text_width, text_height), color=0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.text((-bbox[0], -bbox[1]), initials, font=initials_font, fill=255)
                left_mask = mask.rotate(90, expand=True)
                initials_footprint = INITIALS_SIDE_MARGIN + left_mask.width
                remaining_width = CANVAS_WIDTH_PX - (2 * initials_footprint)
                should_clip = max_title_width > remaining_width
                if should_clip:
                    safe_top = max(INITIALS_VERTICAL_MARGIN, renderer.current_y)
                    initials_top_margin = safe_top
                    initials_min_top = safe_top
                    initials_center = False
            renderer.draw_repeating_side_text(
                text=initials,
                font=initials_font,
                side_margin=INITIALS_SIDE_MARGIN,
                vertical_margin=INITIALS_VERTICAL_MARGIN,
                top_margin=initials_top_margin,
                min_top_y=initials_min_top,
                center=initials_center,
                spacing=INITIALS_SIDE_SPACING,
                width_warning="Initials are wider than the label and will be clipped.",
                opacity_percent=INITIALS_OPACITY_PERCENT,
                mask_dither=Image.Dither.ORDERED,
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

        # Keep dithering on the background to preserve the faint symbol, but render text without
        # dithering so the repeated side text stays symmetric on both edges.
        background_result = background_canvas.convert("1", dither=Image.FLOYDSTEINBERG)
        foreground_result = renderer.canvas.convert("1", dither=Image.NONE)
        result = ImageChops.darker(background_result, foreground_result)
        if renderer.warnings:
            result.info["label_warnings"] = list(renderer.warnings)
        return result


TEMPLATE = Template()
