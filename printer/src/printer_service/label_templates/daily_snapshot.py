from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Mapping, MutableSequence, Sequence, TypedDict

from PIL import Image, ImageDraw

from printer_service.label import PrinterConfig
from printer_service.label_specs import BrotherLabelSpec, resolve_brother_label_spec
from printer_service.label_templates import helper
from printer_service.label_templates.base import TemplateDefinition, TemplateFormData

LABEL_SPEC = resolve_brother_label_spec(PrinterConfig.from_env().brother_label)
WIDTH_PX, HEIGHT_PX = LABEL_SPEC.printable_px

BACKGROUND = (255, 255, 255)
TEXT = (18, 18, 24)
MUTED = (120, 126, 140)
SUBTLE = (180, 186, 196)
RED = (200, 40, 36)
WHITE = (255, 255, 255)
GRID = (216, 220, 228)

TOP_MARGIN = 24
SIDE_MARGIN = 14


class _CalendarDay(TypedDict, total=False):
    day: int
    status: str
    label: str


class _CalendarMonthPayload(TypedDict):
    year: int
    month: int
    month_label: str
    weeks: Sequence[Sequence[_CalendarDay]]


class _DateHeadingPayload(TypedDict):
    iso_date: str
    weekday: str
    label: str


@dataclass
class _Widget:
    type: str
    payload: Mapping[str, object]


class Template(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Daily Snapshot"

    @property
    def form_template(self) -> str:
        return "daily_snapshot.html"

    def preferred_label_spec(self) -> BrotherLabelSpec:
        return LABEL_SPEC

    def get_form_context(self) -> Mapping[str, object]:
        example_widgets = [
            {
                "type": "date_heading",
                "payload": {
                    "iso_date": "2024-09-10",
                    "weekday": "Tuesday",
                    "label": "Tue Sep 10, 2024",
                },
            },
            {
                "type": "calendar_month",
                "payload": {
                    "year": 2024,
                    "month": 9,
                    "month_label": "September",
                    "weeks": [
                        [
                            {"day": 1, "status": "past"},
                            {"day": 2, "status": "past"},
                            {"day": 3, "status": "past"},
                            {"day": 4, "status": "past"},
                            {"day": 5, "status": "past"},
                            {"day": 6, "status": "past"},
                            {"day": 7, "status": "past"},
                        ],
                        [
                            {"day": 8, "status": "past"},
                            {"day": 9, "status": "past"},
                            {"day": 10, "status": "today"},
                            {"day": 11, "status": "future"},
                            {"day": 12, "status": "future"},
                            {"day": 13, "status": "future"},
                            {"day": 14, "status": "future"},
                        ],
                        [
                            {"day": 15, "status": "future"},
                            {"day": 16, "status": "future"},
                            {"day": 17, "status": "future"},
                            {"day": 18, "status": "future"},
                            {"day": 19, "status": "future"},
                            {"day": 20, "status": "future"},
                            {"day": 21, "status": "future"},
                        ],
                        [
                            {"day": 22, "status": "future"},
                            {"day": 23, "status": "future"},
                            {"day": 24, "status": "future"},
                            {"day": 25, "status": "future"},
                            {"day": 26, "status": "future"},
                            {"day": 27, "status": "future"},
                            {"day": 28, "status": "future"},
                        ],
                        [
                            {"day": 29, "status": "future"},
                            {"day": 30, "status": "future"},
                            {"status": "empty"},
                            {"status": "empty"},
                            {"status": "empty"},
                            {"status": "empty"},
                            {"status": "empty"},
                        ],
                    ],
                },
            },
        ]
        return {"example_widgets_json": json.dumps(example_widgets, indent=2)}

    def render(self, form_data: TemplateFormData) -> Image.Image:
        renderer = helper.LabelDrawingHelper(
            width=WIDTH_PX,
            height=HEIGHT_PX,
            mode="RGB",
            color=BACKGROUND,
        )
        renderer.move_to(TOP_MARGIN)

        widgets = _normalize_widgets(form_data.get("widgets"))
        if not widgets:
            renderer.add_warning("No widgets provided; nothing to render.")

        for widget in widgets:
            widget_type = widget.type.lower()
            if widget_type == "date_heading":
                _render_date_heading(renderer, widget.payload)
                renderer.advance(12)
            elif widget_type == "calendar_month":
                _render_calendar_month(renderer, widget.payload)
            else:
                renderer.add_warning(f"Unsupported widget type '{widget.type}'. Skipped.")

        return renderer.finalize(monochrome=False)


def _normalize_widgets(raw: object) -> List[_Widget]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, Sequence) or isinstance(raw, (bytes, bytearray, str)):
        return []

    widgets: List[_Widget] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        widget_type = str(entry.get("type", "")).strip()
        payload_raw = entry.get("payload")
        if not isinstance(payload_raw, Mapping):
            continue
        widgets.append(_Widget(type=widget_type, payload=payload_raw))
    return widgets


def _render_date_heading(
    renderer: helper.LabelDrawingHelper, payload: Mapping[str, object]
) -> None:
    label = str(payload.get("label") or payload.get("iso_date") or "").strip()
    weekday = str(payload.get("weekday") or "").strip()
    heading_text = label.upper() if label else weekday.upper()
    if not heading_text:
        renderer.add_warning("Date heading widget missing label/weekday.")
        return

    font = helper.load_font(size_points=34)
    renderer.draw_centered_text(text=heading_text, font=font, fill=TEXT)

    divider_y = renderer.current_y + 6
    renderer.draw.line(
        (SIDE_MARGIN, divider_y, renderer.width - SIDE_MARGIN, divider_y),
        fill=GRID,
        width=2,
    )
    renderer.move_to(divider_y + 12)


def _render_calendar_month(
    renderer: helper.LabelDrawingHelper, payload: Mapping[str, object]
) -> None:
    weeks_raw = payload.get("weeks")
    if not isinstance(weeks_raw, Sequence):
        renderer.add_warning("Calendar widget missing weeks; nothing to draw.")
        return
    weeks: Sequence[Sequence[_CalendarDay]] = []
    sanitized_weeks: List[Sequence[_CalendarDay]] = []
    for week in weeks_raw:
        if isinstance(week, Sequence):
            sanitized_weeks.append([_sanitize_day(day) for day in week[:7]])
    weeks = sanitized_weeks
    if not weeks:
        renderer.add_warning("Calendar widget contained no week data.")
        return

    month_label = str(payload.get("month_label") or "").strip()
    year = payload.get("year")
    if not month_label and isinstance(year, int):
        month_label = f"{year}"

    month_font = helper.load_font(size_points=26)
    weekday_font = helper.load_font(size_points=18)
    day_font = helper.load_font(size_points=20)

    if month_label:
        renderer.draw_centered_text(text=month_label, font=month_font, fill=TEXT, margin_bottom=6)

    weekdays = ["S", "M", "T", "W", "T", "F", "S"]
    weekday_y = renderer.current_y
    _draw_weekday_headers(renderer.draw, weekdays, weekday_font, weekday_y)
    renderer.move_to(weekday_y + _measure_text_height(renderer.draw, "W", weekday_font) + 10)

    rows = max(len(weeks), 1)
    grid_top = renderer.current_y
    available_height = renderer.height - grid_top - 12
    cell_height = max(28, min(80, available_height // rows if rows else 40))
    cell_width = max(32, (renderer.width - (SIDE_MARGIN * 2)) // 7)

    y = grid_top
    for week in weeks:
        x = SIDE_MARGIN
        for day in week[:7]:
            _draw_day_cell(
                draw=renderer.draw,
                x=x,
                y=y,
                width=cell_width,
                height=cell_height,
                day=day,
                font=day_font,
                warnings=renderer.warnings,
            )
            x += cell_width
        y += cell_height
    renderer.move_to(y)


def _sanitize_day(day: object) -> _CalendarDay:
    if not isinstance(day, Mapping):
        return {"status": "empty"}
    status = str(day.get("status") or "empty").lower()
    label = str(day.get("label") or "").strip()
    day_number = day.get("day")
    if not label and isinstance(day_number, int):
        label = str(day_number)
    return {"status": status or "empty", "label": label}


def _draw_weekday_headers(
    draw: ImageDraw.ImageDraw, weekdays: Sequence[str], font, top: int
) -> None:
    if not weekdays:
        return
    cell_width = (WIDTH_PX - (SIDE_MARGIN * 2)) // 7
    x = SIDE_MARGIN
    for name in weekdays:
        text = name.upper()
        width, height = _measure_text(draw, text, font)
        draw.text(
            (x + (cell_width - width) // 2, top),
            text,
            font=font,
            fill=MUTED,
        )
        x += cell_width


def _draw_day_cell(
    *,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    day: _CalendarDay,
    font,
    warnings: MutableSequence[str],
) -> None:
    status = day.get("status", "empty")
    label = str(day.get("label") or "").strip()
    if not label:
        label = ""

    text_color = TEXT
    fill_color = None
    if status == "today":
        fill_color = RED
        text_color = WHITE
    elif status == "past":
        text_color = MUTED
    elif status == "empty":
        text_color = SUBTLE

    if fill_color:
        draw.rounded_rectangle(
            (x + 1, y + 1, x + width - 2, y + height - 2),
            radius=6,
            fill=fill_color,
        )
    draw.rectangle((x, y, x + width, y + height), outline=GRID, width=1)

    if label:
        text_width, text_height = _measure_text(draw, label, font)
        text_x = x + (width - text_width) // 2
        text_y = y + (height - text_height) // 2
        draw.text((text_x, text_y), label, fill=text_color, font=font)
        if text_width > width:
            _add_warning(warnings, "Day label clipped horizontally.")
        if text_y < y or text_y + text_height > y + height:
            _add_warning(warnings, "Day label clipped vertically.")


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(round(bbox[2] - bbox[0]))
    height = int(round(bbox[3] - bbox[1]))
    return width, height


def _measure_text_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    _, height = _measure_text(draw, text, font)
    return height


def _add_warning(warnings: MutableSequence[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


TEMPLATE = Template()
