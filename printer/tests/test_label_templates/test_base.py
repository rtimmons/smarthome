from __future__ import annotations

from typing import Mapping

import pytest

from printer_service.label_templates.base import TemplateFormData, TemplateFormValue


class MappingFixture:
    def __init__(self, data: Mapping[str, TemplateFormValue]):
        self.data = data


def test_template_form_data_read_only_mapping_behavior():
    original = {"Line1": "Apples", "Count": 4}
    form_data = TemplateFormData(original)

    original["Line1"] = "Oranges"

    assert form_data["Line1"] == "Apples"
    assert dict(form_data.items()) == {"Line1": "Apples", "Count": 4}


@pytest.mark.parametrize(
    "source,expected",
    [
        ({"Line1": " Tea "}, "Tea"),
        ({"Line1": None}, ""),
        ({"Extra": "value"}, ""),
        ({"alias": "Chosen"}, "Chosen"),
    ],
)
def test_get_str_normalizes_and_supports_aliases(source, expected):
    data = TemplateFormData(source)

    assert data.get_str("Line1", "alias") == expected


def test_get_str_returns_default_when_missing():
    data = TemplateFormData({})

    assert data.get_str("missing", default="fallback") == "fallback"


def test_get_str_preserves_leading_alias_order():
    data = TemplateFormData({"Second": "two"})

    assert data.get_str("Primary", "Second", "Third") == "two"
