from __future__ import annotations

from collections.abc import Mapping
from typing import Callable, TypeAlias

from flask import request

from . import label_templates
from .label_templates import TemplateFormData, TemplateFormValue

PayloadError: TypeAlias = type[Exception]
TemplateValueValidator: TypeAlias = Callable[[object], bool]


def best_by_form_data_from_request(
    *,
    payload_error: PayloadError,
    is_template_form_value: TemplateValueValidator,
) -> TemplateFormData:
    data: dict[str, TemplateFormValue] = {}
    payload = request.get_json(silent=True)
    if isinstance(payload, Mapping):
        for key, canonical in (
            ("BaseDate", "BaseDate"),
            ("base_date", "BaseDate"),
            ("baseDate", "BaseDate"),
            ("Delta", "Delta"),
            ("delta", "Delta"),
            ("Offset", "Delta"),
            ("offset", "Delta"),
            ("Text", "Text"),
            ("text", "Text"),
            ("Prefix", "Prefix"),
            ("prefix", "Prefix"),
        ):
            if key in payload and canonical not in data:
                value = payload[key]
                if not is_template_form_value(value):
                    raise payload_error(f"{canonical} must be a string, number, boolean, or null.")
                data[canonical] = value

    for key, canonical in (
        ("baseDate", "BaseDate"),
        ("base_date", "BaseDate"),
        ("BaseDate", "BaseDate"),
        ("delta", "Delta"),
        ("Delta", "Delta"),
        ("offset", "Delta"),
        ("Offset", "Delta"),
        ("text", "Text"),
        ("Text", "Text"),
        ("prefix", "Prefix"),
        ("Prefix", "Prefix"),
    ):
        candidate = request.args.get(key)
        # Use 'is not None' to allow empty strings (e.g., prefix="")
        if candidate is not None and canonical not in data:
            data[canonical] = candidate
    form_data = TemplateFormData(data)
    text_value = best_by_text_value(form_data)
    if text_value:
        has_base = bool(form_data.get_str("BaseDate", "base_date"))
        has_delta = bool(form_data.get_str("Delta", "delta"))
        if has_base or has_delta:
            raise payload_error("Text cannot be combined with base/offset dates.")
    return normalized_best_by_form(form_data)


def best_by_template() -> label_templates.LabelTemplate:
    try:
        return label_templates.get_template("best_by")
    except KeyError:
        return label_templates.get_template("bb_2_weeks")


def request_arg_keys_lower() -> set[str]:
    try:
        return {key.lower() for key in request.args.keys()}
    except RuntimeError:
        return set()


def delta_param_name_from_request(default: str = "offset") -> str:
    raw_keys = request_arg_keys_lower()
    if "offset" in raw_keys:
        return "offset"
    if "delta" in raw_keys:
        return "delta"
    return default


def best_by_text_value(form_data: TemplateFormData) -> str:
    raw = form_data.get_str("Text", "text")
    decoded = raw.replace("+", " ")
    return " ".join(decoded.split())


def normalized_best_by_form(form_data: TemplateFormData) -> TemplateFormData:
    text_value = best_by_text_value(form_data)
    if not text_value:
        return form_data
    data = dict(form_data.items())
    data["Text"] = text_value
    return TemplateFormData(data)


def best_by_relative_path() -> str:
    """Return the Best By route path without any ingress/script prefix."""
    return "bb"


__all__ = [
    "best_by_form_data_from_request",
    "best_by_relative_path",
    "best_by_template",
    "best_by_text_value",
    "delta_param_name_from_request",
    "normalized_best_by_form",
    "request_arg_keys_lower",
]
