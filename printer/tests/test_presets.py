from __future__ import annotations

import pytest

from printer_service.label_templates.base import TemplateFormValue
from printer_service.presets import (
    canonical_query_string,
    normalize_template_slug,
    slug_for_params,
    slug_from_query,
)


def test_canonical_query_orders_keys_and_drops_empty_values() -> None:
    params: dict[str, TemplateFormValue] = {
        "Line1": "  Alpha  ",
        "Line2": "",
        "Tags": ["b", " ", "a"],
        "Count": 0,
        "Enabled": False,
        "tpl": "ignored",
        "template": "ignored",
    }
    query = canonical_query_string(" Bluey_Label ", params)
    assert query == "tpl=bluey_label&Count=0&Enabled=false&Line1=Alpha&Tags=b&Tags=a"


@pytest.mark.parametrize(
    ("template", "params", "expected_query", "expected_slug"),
    [
        (
            "best_by",
            {"Text": "Fresh Pasta", "Prefix": "Use by", "Delta": "3 days"},
            "tpl=best_by&Delta=3+days&Prefix=Use+by&Text=Fresh+Pasta",
            "hvS2eIbWbE0",
        ),
        (
            "bluey_label",
            {"Line1": "Oat Milk", "Line2": {"size": "large", "notes": "  "}},
            "tpl=bluey_label&Line1=Oat+Milk&Line2=%7B%22size%22%3A%22large%22%7D",
            "OAN3CIejCdg",
        ),
    ],
)
def test_canonical_query_string_matches_expected_urls(
    template: str,
    params: dict[str, TemplateFormValue],
    expected_query: str,
    expected_slug: str,
) -> None:
    assert canonical_query_string(template, params) == expected_query
    assert slug_for_params(template, params) == expected_slug
    assert f"/p/{slug_for_params(template, params)}" == f"/p/{expected_slug}"


def test_slug_is_deterministic_and_urlsafe() -> None:
    params: dict[str, TemplateFormValue] = {"Line1": "Alpha", "Tags": ["a", "b"]}
    query = canonical_query_string("bluey_label", params)
    slug = slug_from_query(query)
    assert slug == slug_from_query(query)
    assert slug.isascii()
    assert all(ch.isalnum() or ch in "-_" for ch in slug)
    assert len(slug) <= 11


def test_slug_changes_with_form_values() -> None:
    slug_a = slug_for_params("bluey_label", {"Line1": "Alpha"})
    slug_b = slug_for_params("bluey_label", {"Line1": "Bravo"})
    slug_c = slug_for_params("best_by", {"Text": "Alpha"})
    assert slug_a != slug_b
    assert slug_a != slug_c


def _debug_preset_slug() -> None:
    print("Run with .venv/bin/python so printer dependencies are available.")
    template = normalize_template_slug("bluey_label")
    params: dict[str, TemplateFormValue] = {"Line1": "Oat Milk", "Line2": "2025-01-01"}
    query = canonical_query_string(template, params)
    slug = slug_from_query(query)
    print("preset debug:")
    print(f"  query: {query}")
    print(f"  slug: {slug}")


if __name__ == "__main__":
    _debug_preset_slug()
