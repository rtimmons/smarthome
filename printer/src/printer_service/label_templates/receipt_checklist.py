from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import urlencode, urljoin

import qrcode  # type: ignore[import-untyped]
from PIL import Image, ImageDraw
from PIL.Image import Resampling

from printer_service.label_specs import QL810W_DPI, BrotherLabelSpec, resolve_brother_label_spec
from printer_service.label_templates import helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

LABEL_SPEC = resolve_brother_label_spec(os.getenv("RECEIPT_LABEL", "29x90"))
WIDTH_PX, HEIGHT_PX = LABEL_SPEC.printable_px

HEADER_FONT = helper.load_font(size_points=46)
BODY_FONT = helper.load_font(size_points=34)
META_FONT = helper.load_font(size_points=24)

CHECKBOX_SIZE = 32
CHECKBOX_LEFT = 28
CHECKBOX_SPACING = 96
CHECKBOX_TOP = 180
TEXT_LEFT = CHECKBOX_LEFT + CHECKBOX_SIZE + 16
MAX_ITEMS = 8

QR_TARGET_HEIGHT_IN = 0.75
QR_MARGIN = 18

OUTLINE_THICKNESS = 3
CORNER_MARK_SIZE = 18
FINGER_GUIDE_LENGTH = 48
FINGER_GUIDE_THICKNESS = 10


def _default_items() -> list[str]:
    return [
        "Breakfast",
        "Lunch",
        "Dinner",
        "Meds AM",
        "Meds PM",
        "Hydrate x8",
        "Exercise",
        "Notes",
    ][:MAX_ITEMS]


def _normalize_items(raw: Iterable[str]) -> list[str]:
    return helper.sanitize_lines([item for item in raw][:MAX_ITEMS])


def _today() -> date:
    return date.today()


def _now() -> datetime:
    return datetime.now()


@dataclass(frozen=True)
class ReceiptLayout:
    width_px: int = WIDTH_PX
    height_px: int = HEIGHT_PX
    checkbox_left: int = CHECKBOX_LEFT
    checkbox_top: int = CHECKBOX_TOP
    checkbox_size: int = CHECKBOX_SIZE
    checkbox_spacing: int = CHECKBOX_SPACING
    text_left: int = TEXT_LEFT
    max_items: int = MAX_ITEMS
    qr_height_px: int = max(int(round(QR_TARGET_HEIGHT_IN * QL810W_DPI)), 120)
    qr_margin: int = QR_MARGIN
    outline_thickness: int = OUTLINE_THICKNESS
    corner_mark_size: int = CORNER_MARK_SIZE


LAYOUT = ReceiptLayout()


class Template(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Receipt Checklist"

    @property
    def form_template(self) -> str:
        return "receipt_checklist.html"

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return LABEL_SPEC

    def get_form_context(self) -> dict:
        today = _today().strftime("%Y-%m-%d")
        return {
            "default_items": _default_items(),
            "default_date": today,
            "default_qr_base": os.getenv(
                "RECEIPT_QR_BASE_URL",
                "http://localhost:4010/receipt/upload",
            ),
        }

    def render(self, form_data: TemplateFormData) -> Image.Image:
        items = _normalize_items(_iter_items(form_data))
        receipt_date = form_data.get_str("date") or _today().isoformat()
        qr_base = form_data.get_str("qr_base") or os.getenv(
            "RECEIPT_QR_BASE_URL", "http://localhost:4010/receipt/upload"
        )
        receipt_id = form_data.get_str("receipt_id") or _now().strftime("%Y%m%d")
        qr_url = _build_qr_url(
            base=qr_base,
            receipt_date=receipt_date,
            items=items,
            receipt_id=receipt_id,
        )

        renderer = helper.LabelDrawingHelper(width=LAYOUT.width_px, height=LAYOUT.height_px)
        _draw_outline(renderer)
        _draw_fiducials(renderer)
        _draw_header(renderer, receipt_date=receipt_date)
        _draw_checkboxes(renderer, items)
        _draw_qr(renderer, qr_url)
        _draw_upload_text(renderer, qr_url)
        return renderer.finalize()


def _iter_items(form_data: TemplateFormData) -> Sequence[str]:
    fields: list[str] = []
    for index in range(1, MAX_ITEMS + 1):
        fields.append(form_data.get_str(f"item{index}", f"Item{index}", f"Line{index}"))
    provided = [value for value in fields if value.strip()]
    if provided:
        return provided
    return _default_items()


def _draw_outline(renderer: helper.LabelDrawingHelper) -> None:
    draw = renderer.draw
    thickness = LAYOUT.outline_thickness
    rect = (0, 0, LAYOUT.width_px - 1, LAYOUT.height_px - 1)
    for offset in range(thickness):
        draw.rectangle(
            (
                rect[0] + offset,
                rect[1] + offset,
                rect[2] - offset,
                rect[3] - offset,
            ),
            outline=0,
        )
    mark = LAYOUT.corner_mark_size
    coords: list[Tuple[int, int]] = [
        (0, 0),
        (LAYOUT.width_px - mark, 0),
        (0, LAYOUT.height_px - mark),
        (LAYOUT.width_px - mark, LAYOUT.height_px - mark),
    ]
    for x, y in coords:
        draw.rectangle((x, y, x + mark, y + mark), fill=0)


def _draw_fiducials(renderer: helper.LabelDrawingHelper) -> None:
    draw = renderer.draw
    mid_y = LAYOUT.height_px // 2
    thickness = FINGER_GUIDE_THICKNESS
    length = FINGER_GUIDE_LENGTH
    edge_margin = 4
    # Left center guide
    draw.rectangle(
        (edge_margin, mid_y - (length // 2), edge_margin + thickness, mid_y + (length // 2)),
        fill=0,
    )
    # Right center guide
    draw.rectangle(
        (
            LAYOUT.width_px - edge_margin - thickness,
            mid_y - (length // 2),
            LAYOUT.width_px - edge_margin,
            mid_y + (length // 2),
        ),
        fill=0,
    )
    # Top center guide
    draw.rectangle(
        (
            (LAYOUT.width_px // 2) - (length // 2),
            edge_margin,
            (LAYOUT.width_px // 2) + (length // 2),
            edge_margin + thickness,
        ),
        fill=0,
    )
    # Bottom center guide
    draw.rectangle(
        (
            (LAYOUT.width_px // 2) - (length // 2),
            LAYOUT.height_px - edge_margin - thickness,
            (LAYOUT.width_px // 2) + (length // 2),
            LAYOUT.height_px - edge_margin,
        ),
        fill=0,
    )


def _draw_header(renderer: helper.LabelDrawingHelper, *, receipt_date: str) -> None:
    renderer.move_to(24)
    renderer.draw_centered_text(
        text="Daily Checklist",
        font=HEADER_FONT,
        warn_if_past_bottom=LAYOUT.height_px,
    )
    renderer.advance(10)
    renderer.draw_centered_text(
        text=f"Date: {receipt_date}",
        font=BODY_FONT,
        warn_if_past_bottom=LAYOUT.height_px,
    )
    renderer.advance(32)


def _draw_checkboxes(renderer: helper.LabelDrawingHelper, items: Sequence[str]) -> None:
    draw = renderer.draw
    y = LAYOUT.checkbox_top
    for index, item in enumerate(items[: LAYOUT.max_items]):
        box_left = LAYOUT.checkbox_left
        box_top = y
        box_right = box_left + LAYOUT.checkbox_size
        box_bottom = box_top + LAYOUT.checkbox_size
        draw.rectangle((box_left, box_top, box_right, box_bottom), outline=0, width=3)
        renderer.draw.text((LAYOUT.text_left, box_top + 4), item, fill=0, font=BODY_FONT)
        y += LAYOUT.checkbox_spacing

    renderer.add_warning(
        "Detected checkbox layout for receipt scanning; keep photo as straight as possible."
    )


def _draw_qr(renderer: helper.LabelDrawingHelper, qr_url: str) -> None:
    qr_height_px = LAYOUT.qr_height_px
    qr_image = _qr_image(qr_url, target_height_px=qr_height_px)
    width_px = qr_image.width + (LAYOUT.qr_margin * 2)
    height_px = qr_image.height + (LAYOUT.qr_margin * 2)
    canvas = Image.new("L", (width_px, height_px), color=255)
    renderer.canvas.paste(
        canvas, (LAYOUT.width_px - width_px - LAYOUT.qr_margin, LAYOUT.height_px - height_px)
    )
    renderer.canvas.paste(
        qr_image,
        (
            LAYOUT.width_px - width_px - LAYOUT.qr_margin + LAYOUT.qr_margin,
            LAYOUT.height_px - height_px + LAYOUT.qr_margin,
        ),
    )
    draw = ImageDraw.Draw(renderer.canvas)
    caption_top = LAYOUT.height_px - height_px - 8
    caption = "Scan to upload"
    draw.text(
        (LAYOUT.width_px - width_px - LAYOUT.qr_margin, caption_top),
        caption,
        fill=0,
        font=META_FONT,
    )


def _draw_upload_text(renderer: helper.LabelDrawingHelper, qr_url: str) -> None:
    draw = renderer.draw
    max_width = LAYOUT.width_px - (LAYOUT.qr_margin * 2)
    text_lines = _wrap_text(f"Upload: {qr_url}", draw, META_FONT, max_width)
    left = LAYOUT.qr_margin
    line_height = getattr(META_FONT, "size", 24) + 2
    total_height = len(text_lines) * line_height
    qr_bottom = LAYOUT.height_px - LAYOUT.qr_margin
    top = max(LAYOUT.qr_margin, qr_bottom - total_height - 6)
    for line in text_lines:
        draw.text((left, top), line, fill=0, font=META_FONT)
        top += line_height


def _qr_image(qr_url: str, target_height_px: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        box_size=4,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("L")
    if qr_image.height != target_height_px:
        qr_image = qr_image.resize(
            (int(round(qr_image.width * target_height_px / qr_image.height)), target_height_px),
            resample=Resampling.NEAREST,
        )
    qr_image.info["qr_url"] = qr_url
    return qr_image


def _build_qr_url(*, base: str, receipt_date: str, items: Sequence[str], receipt_id: str) -> str:
    query = urlencode(
        {
            "date": receipt_date,
            "receipt_id": receipt_id,
            "items": json.dumps(items),
            "layout": "receipt_checklist_v1",
        }
    )
    return urljoin(base, f"?{query}")


def _wrap_text(
    text: str, draw: ImageDraw.ImageDraw, font: helper.FontType, max_width: int
) -> List[str]:
    words = text.split(" ")
    lines: List[str] = []
    current: List[str] = []
    for word in words:
        trial = " ".join([*current, word]).strip()
        if not trial:
            continue
        bbox = draw.textbbox((0, 0), trial, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


TEMPLATE = Template()
