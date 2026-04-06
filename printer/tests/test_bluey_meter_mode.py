from __future__ import annotations

import pytest

from printer_service.label_templates import bluey_label
from printer_service.label_templates.base import TemplateFormData


def test_bluey_meter_mode_requires_reading_and_label() -> None:
    template = bluey_label.TEMPLATE

    with pytest.raises(
        ValueError, match="Meter mode requires Percentage in the form reading:label."
    ):
        template.render(
            TemplateFormData(
                {
                    "Line1": "Cadillac",
                    "Line2": "Ranbows",
                    "Side": "=METER",
                    "Percentage": "30",
                }
            )
        )
