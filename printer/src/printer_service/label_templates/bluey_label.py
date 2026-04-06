from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from PIL.Image import Dither, Resampling

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
METER_BACKGROUND_ALPHA_PERCENT = 45
INITIALS_OPACITY_PERCENT = 50
TITLE_BLOCK_PADDING = int(round(0.16 * QL810W_DPI))
METER_SIDE_WIDTH = 124
METER_SIDE_TOP = 24
METER_SIDE_BOTTOM = 48
METER_TOP_WIDTH = 19
METER_BOTTOM_WIDTH = METER_TOP_WIDTH * 3
METER_DOT_RADIUS = 20
METER_CHIP_PADDING = 3
METER_LABEL_FONT_POINTS = int(INITIALS_FONT_POINTS * 0.75 * 0.75)
METER_TEXT_HALO_SIZE = 7
METER_STRIP_CENTER_INSET = 36
TITLE_TEXT_HALO_SIZE = 13


@dataclass(frozen=True)
class MeterValue:
    reading: int
    label: str


class Template(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Bluey Label"

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
        # Check if this is an explicit jar label request
        jar_request = form_data.get_str("jar_label_request")
        if jar_request:
            return self._render_jar_label(form_data)

        # Otherwise render as regular label
        line1 = form_data.get_str("Line1", "line1")
        line2 = form_data.get_str("Line2", "line2")
        side = form_data.get_str(
            "Side", "Initials", "side", "initials"
        )  # Support both new and old field names
        symbol_choice = form_data.get_str("SymbolName", "symbolname")
        bottom_raw = form_data.get_str(
            "Bottom", "PackageDate", "bottom", "packagedate"
        )  # Support both new and old field names

        options = helper.svg_symbol_options()
        available_slugs = [option["slug"] for option in options]
        symbol_slug = helper.normalize_choice(candidate=symbol_choice, options=available_slugs)
        bottom = bottom_raw
        meter_value = self._parse_meter_value(side=side, percentage=form_data.get_str("Percentage"))

        renderer = LabelDrawingHelper(width=CANVAS_WIDTH_PX, height=CANVAS_HEIGHT_PX)

        background_canvas = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=255)
        helper.draw_background_symbol(
            canvas=background_canvas,
            slug=symbol_slug,
            alpha_percent=(
                METER_BACKGROUND_ALPHA_PERCENT
                if meter_value is not None
                else BACKGROUND_ALPHA_PERCENT
            ),
        )
        renderer.move_to(TOP_MARGIN)

        title_font = helper.load_font(size_points=TITLE_FONT_POINTS)
        initials_font = helper.load_font(size_points=INITIALS_FONT_POINTS)
        date_font = helper.load_font(size_points=DATE_FONT_POINTS)
        title_lines = []
        date_metrics: Optional[helper.Box] = None
        date_y: Optional[int] = None

        if bottom:
            date_metrics = renderer.measure_text(text=bottom, font=date_font)
            date_y = CANVAS_HEIGHT_PX - BOTTOM_MARGIN - date_metrics.height

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
        title_block_padding = TITLE_BLOCK_PADDING

        if title_lines and date_y is not None:
            title_block_height = 0
            for line_index, (_text, metrics, _label_name) in enumerate(title_lines):
                title_block_height += metrics.height
                if line_index == 0 and len(title_lines) > 1:
                    title_block_height += LINE2_OFFSET

            available_height = date_y - SYMBOL_SECTION_SPACING - TOP_MARGIN
            if title_block_height > 0 and available_height > 0:
                total_title_height = (TITLE_REPEAT_COUNT * title_block_height) + (
                    TITLE_BLOCK_PADDING * (TITLE_REPEAT_COUNT - 1)
                )
                if total_title_height > available_height:
                    gaps = max(1, TITLE_REPEAT_COUNT - 1)
                    max_padding = (
                        available_height - (TITLE_REPEAT_COUNT * title_block_height)
                    ) // gaps
                    title_block_padding = max(0, min(TITLE_BLOCK_PADDING, max_padding))

        title_draw_ops: list[tuple[str, int, str]] = []
        if title_lines:
            for repeat_index in range(TITLE_REPEAT_COUNT):
                for line_index, (text, metrics, label_name) in enumerate(title_lines):
                    title_draw_ops.append((text, renderer.current_y, label_name))
                    renderer.move_to(renderer.current_y + metrics.height)
                    if line_index == 0 and len(title_lines) > 1:
                        renderer.advance(LINE2_OFFSET)
                if repeat_index < TITLE_REPEAT_COUNT - 1:
                    renderer.advance(title_block_padding)

        renderer.advance(SYMBOL_SECTION_SPACING)

        if meter_value is not None:
            left_center_x, right_center_x, meter_strip_mask = self._draw_side_meter_background(
                background_canvas=background_canvas,
                meter_value=meter_value,
            )
            meter_geometry: tuple[int, int] | None = (left_center_x, right_center_x)
        else:
            meter_geometry = None
            meter_strip_mask = None

        for text, top, label_name in title_draw_ops:
            self._draw_centered_text_with_halo(
                renderer=renderer,
                background_canvas=background_canvas,
                background_clear_mask=meter_strip_mask,
                text=text,
                font=title_font,
                top=top,
                width_warning=f"{label_name} is wider than the label and will be clipped.",
                height_warning="Text exceeds label height and may be clipped.",
            )

        if meter_value is not None and meter_geometry is not None:
            self._draw_side_meter_foreground(
                renderer=renderer,
                background_canvas=background_canvas,
                meter_value=meter_value,
                left_center_x=meter_geometry[0],
                right_center_x=meter_geometry[1],
            )
        elif side:
            initials_top_margin: Optional[int] = None
            initials_min_top: Optional[int] = None
            initials_center = True
            bbox = renderer.draw.textbbox((0, 0), side, font=initials_font)
            text_width = int(round(bbox[2] - bbox[0]))
            text_height = int(round(bbox[3] - bbox[1]))
            if text_width > 0 and text_height > 0:
                mask = Image.new("L", (text_width, text_height), color=0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.text((-bbox[0], -bbox[1]), side, font=initials_font, fill=255)
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
                text=side,
                font=initials_font,
                side_margin=INITIALS_SIDE_MARGIN,
                vertical_margin=INITIALS_VERTICAL_MARGIN,
                top_margin=initials_top_margin,
                min_top_y=initials_min_top,
                center=initials_center,
                spacing=INITIALS_SIDE_SPACING,
                width_warning="Side text is wider than the label and will be clipped.",
                opacity_percent=INITIALS_OPACITY_PERCENT,
                mask_dither=Image.Dither.ORDERED,
            )

        if bottom and date_metrics is not None and date_y is not None:
            # Measure to anchor the bottom text against the bottom margin; overflow warnings come from the helper.
            height_check: Optional[int] = CANVAS_HEIGHT_PX
            if date_y < 0:
                height_check = None
            renderer.draw_centered_text(
                text=bottom,
                font=date_font,
                top=date_y,
                advance=False,
                width_warning="Bottom text is wider than the label and will be clipped.",
                warn_if_past_bottom=height_check,
                height_warning="Bottom text exceeds label height and may be clipped.",
            )

        # Keep dithering on the background to preserve the faint symbol, but render text without
        # dithering so the repeated side text stays symmetric on both edges.
        background_result = background_canvas.convert("1", dither=Dither.FLOYDSTEINBERG)
        foreground_result = renderer.canvas.convert("1", dither=Dither.NONE)
        result = ImageChops.darker(background_result, foreground_result)

        if renderer.warnings:
            result.info["label_warnings"] = list(renderer.warnings)
        return result

    def _parse_meter_value(self, *, side: str, percentage: str) -> Optional[MeterValue]:
        if side != "=METER":
            return None

        reading_text, separator, label = percentage.partition(":")
        if separator != ":" or not reading_text.strip() or not label.strip():
            raise ValueError("Meter mode requires Percentage in the form reading:label.")

        try:
            reading = int(reading_text.strip())
        except ValueError as exc:
            raise ValueError("Meter mode requires Percentage in the form reading:label.") from exc

        return MeterValue(reading=max(0, min(100, reading)), label=label.strip())

    def _draw_side_meter_background(
        self,
        *,
        background_canvas: Image.Image,
        meter_value: MeterValue,
    ) -> tuple[int, int, Image.Image]:
        left_bounds = (
            INITIALS_SIDE_MARGIN,
            METER_SIDE_TOP,
            INITIALS_SIDE_MARGIN + METER_SIDE_WIDTH,
        )
        right_bounds = (
            CANVAS_WIDTH_PX - INITIALS_SIDE_MARGIN - METER_SIDE_WIDTH,
            METER_SIDE_TOP,
            CANVAS_WIDTH_PX - INITIALS_SIDE_MARGIN,
        )
        combined_mask = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=0)

        left_center_x, left_mask = self._draw_meter(
            background_canvas=background_canvas,
            bounds=left_bounds,
            reading=meter_value.reading,
            center_x=left_bounds[0] + METER_STRIP_CENTER_INSET,
        )
        combined_mask.paste(255, (0, 0), left_mask)
        right_center_x, right_mask = self._draw_meter(
            background_canvas=background_canvas,
            bounds=right_bounds,
            reading=meter_value.reading,
            center_x=right_bounds[2] - METER_STRIP_CENTER_INSET,
        )
        combined_mask.paste(255, (0, 0), right_mask)
        return left_center_x, right_center_x, combined_mask

    def _draw_side_meter_foreground(
        self,
        *,
        renderer: LabelDrawingHelper,
        background_canvas: Image.Image,
        meter_value: MeterValue,
        left_center_x: int,
        right_center_x: int,
    ) -> None:
        self._draw_meter_dot(renderer=renderer, center_x=left_center_x, reading=meter_value.reading)
        self._draw_meter_dot(
            renderer=renderer, center_x=right_center_x, reading=meter_value.reading
        )
        self._draw_meter_chip(
            renderer=renderer,
            background_canvas=background_canvas,
            text=str(meter_value.reading),
            center_x=left_center_x,
            reading=meter_value.reading,
        )
        self._draw_meter_chip(
            renderer=renderer,
            background_canvas=background_canvas,
            text=meter_value.label,
            center_x=right_center_x,
            reading=meter_value.reading,
        )

    def _draw_meter(
        self,
        *,
        background_canvas: Image.Image,
        bounds: tuple[int, int, int],
        reading: int,
        center_x: int,
    ) -> tuple[int, Image.Image]:
        left, top, right = bounds
        tube_top = top
        tube_bottom = CANVAS_HEIGHT_PX - METER_SIDE_BOTTOM
        stem_mask = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=0)
        stem_draw = ImageDraw.Draw(stem_mask)
        half_top = METER_TOP_WIDTH / 2
        half_bottom = METER_BOTTOM_WIDTH / 2
        polygon = [
            (center_x - half_top, tube_top),
            (center_x + half_top, tube_top),
            (center_x + half_bottom, tube_bottom),
            (center_x - half_bottom, tube_bottom),
        ]
        stem_draw.polygon(polygon, fill=255)

        gradient = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=255)
        gradient_pixels = gradient.load()
        assert gradient_pixels is not None
        usable_height = max(1, tube_bottom - tube_top)
        for y in range(tube_top, tube_bottom + 1):
            progress = (y - tube_top) / usable_height
            opacity = min(1.0, max(0.0, (progress / 0.8) ** 0.7))
            shade = int(round(255 * (1.0 - opacity)))
            for x in range(max(0, left - 8), min(CANVAS_WIDTH_PX, right + 8)):
                gradient_pixels[x, y] = shade

        background_canvas.paste(gradient, (0, 0), stem_mask)

        return center_x, stem_mask

    def _draw_meter_dot(self, *, renderer: LabelDrawingHelper, center_x: int, reading: int) -> None:
        chip_font = helper.load_font(size_points=METER_LABEL_FONT_POINTS)
        text_height = renderer.measure_text(text="30", font=chip_font).height
        rect_height = max(1, text_height // 2)
        rect_width = max(METER_BOTTOM_WIDTH + 10, rect_height * 2)
        dot_center_y = self._reading_center_y(reading)
        renderer.draw.rectangle(
            (
                center_x - (rect_width // 2),
                dot_center_y - (rect_height // 2),
                center_x + (rect_width // 2),
                dot_center_y + (rect_height // 2),
            ),
            fill=0,
        )

    def _draw_meter_chip(
        self,
        *,
        renderer: LabelDrawingHelper,
        background_canvas: Image.Image,
        text: str,
        center_x: int,
        reading: int,
    ) -> None:
        chip_font = helper.load_font(size_points=METER_LABEL_FONT_POINTS)
        bbox = renderer.draw.textbbox((0, 0), text, font=chip_font)
        text_width = int(round(bbox[2] - bbox[0]))
        text_height = int(round(bbox[3] - bbox[1]))
        chip_width = text_width + (2 * METER_CHIP_PADDING)
        chip_height = text_height + (2 * METER_CHIP_PADDING)
        dot_center_y = self._reading_center_y(reading)
        chip_top = dot_center_y - (chip_height // 2)
        chip_left = center_x - (chip_width // 2)

        text_x = chip_left + METER_CHIP_PADDING - bbox[0]
        text_y = chip_top + METER_CHIP_PADDING - bbox[1]
        text_mask = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=0)
        text_draw = ImageDraw.Draw(text_mask)
        text_draw.text((text_x, text_y), text, fill=255, font=chip_font)
        halo_mask = text_mask.filter(ImageFilter.MaxFilter(size=METER_TEXT_HALO_SIZE))
        background_canvas.paste(255, (0, 0), halo_mask)
        renderer.canvas.paste(255, (0, 0), halo_mask)
        renderer.canvas.paste(0, (0, 0), text_mask)

    def _reading_center_y(self, reading: int) -> int:
        tube_top = METER_SIDE_TOP
        tube_bottom = CANVAS_HEIGHT_PX - METER_SIDE_BOTTOM
        usable_height = max(1, tube_bottom - tube_top)
        return tube_top + int(round((reading / 100) * usable_height))

    def _draw_centered_text_with_halo(
        self,
        *,
        renderer: LabelDrawingHelper,
        background_canvas: Image.Image,
        background_clear_mask: Image.Image | None,
        text: str,
        font: helper.FontType,
        top: int,
        width_warning: str | None = None,
        height_warning: str | None = None,
    ) -> None:
        metrics = renderer.measure_text(text=text, font=font)
        left = (CANVAS_WIDTH_PX - metrics.width) // 2
        bottom_edge = top + metrics.height
        if metrics.width > CANVAS_WIDTH_PX:
            renderer.add_warning(
                width_warning or "Text is wider than the label and will be clipped."
            )
        if bottom_edge > CANVAS_HEIGHT_PX:
            renderer.add_warning(height_warning or "Text exceeds label height and may be clipped.")

        text_mask = Image.new("L", (CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX), color=0)
        text_draw = ImageDraw.Draw(text_mask)
        text_draw.text((left, top), text, fill=255, font=font)
        halo_mask = text_mask.filter(ImageFilter.MaxFilter(size=TITLE_TEXT_HALO_SIZE))
        if background_clear_mask is not None:
            restricted_halo = ImageChops.multiply(halo_mask, background_clear_mask)
            background_canvas.paste(255, (0, 0), restricted_halo)
        renderer.canvas.paste(255, (0, 0), halo_mask)
        renderer.canvas.paste(0, (0, 0), text_mask)

    def _render_jar_label(self, form_data: TemplateFormData) -> Image.Image:
        """Render a portrait-oriented jar label with HTML table layout."""
        # Extract form data
        line1 = form_data.get_str("Line1", "line1")
        line2 = form_data.get_str("Line2", "line2")
        side = form_data.get_str("Side", "Initials", "side", "initials")
        symbol_choice = form_data.get_str("SymbolName", "symbolname")
        bottom_raw = form_data.get_str("Bottom", "PackageDate", "bottom", "packagedate")
        supplier = form_data.get_str("Supplier", "supplier")
        percentage = form_data.get_str("Percentage", "percentage")

        # Process symbol and bottom date
        options = helper.svg_symbol_options()
        available_slugs = [option["slug"] for option in options]
        symbol_slug = helper.normalize_choice(candidate=symbol_choice, options=available_slugs)
        bottom = bottom_raw

        # Portrait orientation: rotate main label 90° and reduce short edge by 15%
        # Main label canvas: 390×720, so jar label should be 720×(390*0.85) = 720×331
        portrait_width_px = CANVAS_HEIGHT_PX  # 720px (long edge stays same)
        portrait_height_px = int(CANVAS_WIDTH_PX * 0.85)  # 331px (short edge reduced by 15%)

        # Create renderer with portrait dimensions
        renderer = LabelDrawingHelper(width=portrait_width_px, height=portrait_height_px)

        # Create background with symbol
        background_canvas = Image.new("L", (portrait_width_px, portrait_height_px), color=255)
        helper.draw_background_symbol(
            canvas=background_canvas,
            slug=symbol_slug,
            alpha_percent=BACKGROUND_ALPHA_PERCENT,
        )

        # Apply background to renderer canvas
        renderer.canvas.paste(background_canvas, (0, 0))

        # Define fonts with requested size adjustments
        title_font = helper.load_font(
            size_points=int(TITLE_FONT_POINTS * 0.8 * 1.1)
        )  # Increase by 10%
        side_font = helper.load_font(
            size_points=int(INITIALS_FONT_POINTS * 0.5)
        )  # Reduced for better fit
        supplier_font = helper.load_font(
            size_points=int(DATE_FONT_POINTS * 0.8 * 3)
        )  # Triple the size
        bottom_font = helper.load_font(
            size_points=int(DATE_FONT_POINTS * 0.8 * 3)
        )  # Triple the size

        # Layout following HTML table structure:
        # Row 1: Line1 Line2 (centered, colspan=3) with Side below
        # Row 2: Supplier/Percentage | QR Code | Bottom

        # Calculate layout dimensions
        margin = 20
        row1_height = portrait_height_px // 3
        row2_height = portrait_height_px - row1_height - margin
        col_width = (portrait_width_px - 2 * margin) // 3

        # Row 1: Title area (Line1 Line2 + Side)
        renderer.move_to(margin)
        title_text = f"{line1} {line2}".strip()
        title_bottom_y = margin
        if title_text:
            title_metrics = renderer.measure_text(text=title_text, font=title_font)
            renderer.draw_centered_text(
                text=title_text,
                font=title_font,
                width_warning="Title text is wider than the label and will be clipped.",
            )
            title_bottom_y = renderer.current_y

        # Position Side text below title with margin
        if side:
            side_margin = 8  # Reasonable margin between title and side text
            renderer.move_to(title_bottom_y + side_margin)
            renderer.draw_centered_text(
                text=side,
                font=side_font,
                width_warning="Side text is wider than the label and will be clipped.",
            )

        # Row 2 setup
        row2_top = row1_height + margin

        # Left column: Supplier and Percentage
        left_col_x = margin
        if supplier:
            renderer.draw.text((left_col_x, row2_top), supplier, fill=0, font=supplier_font)
        if percentage:
            supplier_height = renderer.measure_text(text=supplier or "", font=supplier_font).height
            percentage_y = row2_top + supplier_height + 5
            renderer.draw.text(
                (left_col_x, percentage_y), percentage, fill=0, font=supplier_font
            )  # Uses same tripled font as supplier

        # Center column: QR Code
        qr_col_x = margin + col_width
        base_qr_size = min(col_width - 10, row2_height - 10)  # Leave some padding
        qr_size = int(
            base_qr_size * 1.15 * 1.15
        )  # Increase QR code size by 15% twice (32.25% total)

        # Generate QR code with form data (excluding print=true)
        qr_data = self._build_jar_qr_data(form_data)
        qr_image = self._create_qr_image(qr_data, target_size=qr_size)

        # Center QR code in its column
        qr_x = qr_col_x + (col_width - qr_image.width) // 2
        qr_y = row2_top + (row2_height - qr_image.height) // 2 - 5  # Move up by 5 pixels
        renderer.canvas.paste(qr_image, (qr_x, qr_y))

        # Right column: Bottom text
        right_col_x = margin + 2 * col_width
        if bottom:
            # Right-align the bottom text in its column
            bottom_metrics = renderer.measure_text(text=bottom, font=bottom_font)
            bottom_x = right_col_x + col_width - bottom_metrics.width - 5
            renderer.draw.text((bottom_x, row2_top), bottom, fill=0, font=bottom_font)

        result = renderer.finalize()
        if renderer.warnings:
            result.info["label_warnings"] = list(renderer.warnings)

        # Set custom label spec for jar labels to avoid dimension warnings
        jar_spec = BrotherLabelSpec(
            code="62-jar",  # Custom code for jar labels
            printable_px=(portrait_width_px, portrait_height_px),  # 720x331
            tape_size_mm=LABEL_SPEC.tape_size_mm,  # Same physical tape
        )
        result.info["label_spec_code"] = jar_spec.code
        result.info["label_spec_width_px"] = str(jar_spec.printable_px[0])
        result.info["label_spec_height_px"] = str(jar_spec.printable_px[1])

        return result

    def _build_jar_qr_data(self, form_data: TemplateFormData) -> str:
        """Build QR code data for jar label (excludes print=true parameter)."""
        # Get the jar QR URL from form data (set by the backend)
        jar_qr_url = form_data.get_str("jar_qr_url")
        if jar_qr_url:
            return jar_qr_url
        # Fallback to a basic URL if not provided
        return "http://localhost:8099/bb"

    def _create_qr_image(self, data: str, target_size: int) -> Image.Image:
        """Create a QR code image with the specified target size, maintaining scannability."""
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            border=1,
            box_size=1,
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")

        # Use the better resizing approach from best_by.py to maintain scannability
        if target_size != qr_image.width:
            modules_count = qr.modules_count
            quiet_zone_modules = qr.border
            total_modules = modules_count + (quiet_zone_modules * 2)

            # Ensure each QR module is at least 2 pixels for scannability
            QR_MIN_MODULE_PX = 2
            module_px = max(QR_MIN_MODULE_PX, int(target_size / max(total_modules, 1)))
            actual_size = total_modules * module_px

            qr_image = qr_image.resize((actual_size, actual_size), resample=Resampling.NEAREST)

        return qr_image


TEMPLATE = Template()
