from __future__ import annotations

from typing import Mapping

import pytest

from printer_service.label_templates import TemplateFormData, get_template
from printer_service.label_templates.base import TemplateDefinition


class SampleTemplate(TemplateDefinition):
    @property
    def display_name(self) -> str:
        return "Sample"

    @property
    def form_template(self) -> str:
        return "sample.html"

    def render(self, form_data: TemplateFormData):
        raise NotImplementedError


@pytest.mark.parametrize("slug", ["bluey_label", "bluey_label_2"])
def test_label_template_wraps_mapping(slug: str):
    template = get_template(slug)

    fake_mapping: Mapping[str, str] = {"Line1": "Example"}
    image = template.render(fake_mapping)

    assert image.mode == "1"


def test_template_form_data_accepts_existing_instance():
    form_data = TemplateFormData({"Field": " value "})
    wrapped = TemplateFormData(form_data)
    assert wrapped.get_str("Field") == "value"


def test_template_definition_defaults_raise_without_slug():
    template = SampleTemplate()
    with pytest.raises(RuntimeError):
        template.default_display_name()
    template.bind_slug("sample_template")
    assert template.default_display_name() == "Sample Template"
    assert template.default_form_template() == "sample_template.html"
