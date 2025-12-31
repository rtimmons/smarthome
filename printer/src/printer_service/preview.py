from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from PIL import Image

from .label import LabelMetrics
from .label_specs import BrotherLabelSpec
from .label_templates import LabelTemplate, TemplateFormData


class PreviewPayloadError(Exception):
    pass


@dataclass(frozen=True)
class PreviewPayloadBuilder:
    analyze_label_image: Callable[..., LabelMetrics]
    data_url_for_image: Callable[[Image.Image], str]
    best_by_template: Callable[[], LabelTemplate]
    print_url_for_template: Callable[..., str]
    qr_caption_for_template: Callable[[LabelTemplate, TemplateFormData], str]
    render_qr_label_image: Callable[
        [LabelTemplate, TemplateFormData, str, str],
        Image.Image,
    ]
    jar_qr_url_for_template: Callable[[LabelTemplate, TemplateFormData], str]
    label_spec_from_metadata: Callable[[Image.Image], Optional[BrotherLabelSpec]]
    best_by_text_value: Callable[[TemplateFormData], str]
    compute_best_by: Callable[
        [TemplateFormData],
        tuple[Optional[date], Optional[date], str, str],
    ]

    def build(self, template: LabelTemplate, form_data: TemplateFormData) -> dict:
        try:
            label_image = template.render(form_data)
        except ValueError as exc:
            raise PreviewPayloadError(str(exc)) from exc
        label_metrics = self.analyze_label_image(
            label_image, target_spec=template.preferred_label_spec()
        )
        print_url = self.print_url_for_template(template, form_data, prefer_preset=True)
        qr_caption = self.qr_caption_for_template(template, form_data)
        try:
            qr_image = self.render_qr_label_image(template, form_data, print_url, qr_caption)
        except ValueError as exc:
            raise PreviewPayloadError(str(exc)) from exc
        qr_template = self.best_by_template()
        qr_metrics = self.analyze_label_image(
            qr_image, target_spec=qr_template.preferred_label_spec()
        )

        jar_image = None
        jar_metrics = None
        supplier = form_data.get_str("Supplier", "supplier")
        percentage = form_data.get_str("Percentage", "percentage")
        if supplier or percentage:
            try:
                jar_qr_url = self.jar_qr_url_for_template(template, form_data)
                jar_form_data = dict(form_data)
                jar_form_data["jar_qr_url"] = jar_qr_url
                jar_form_data["jar_label_request"] = "true"
                jar_image = template.render(jar_form_data)
                jar_spec = self.label_spec_from_metadata(jar_image)
                jar_metrics = self.analyze_label_image(jar_image, target_spec=jar_spec)
            except ValueError:
                pass

        payload: dict[str, object] = {
            "status": "preview",
            "template": template.slug,
            "print_url": print_url,
            "qr_print_url": self.print_url_for_template(template, form_data, include_qr_label=True),
            "qr_caption": qr_caption,
            "label": {
                "image": self.data_url_for_image(label_image),
                "metrics": label_metrics.to_dict(),
                "warnings": label_metrics.warnings,
            },
            "qr": {
                "image": self.data_url_for_image(qr_image),
                "metrics": qr_metrics.to_dict(),
                "warnings": qr_metrics.warnings,
            },
        }

        if jar_image and jar_metrics:
            jar_print_url = self.print_url_for_template(template, form_data)
            jar_print_url = jar_print_url.replace("print=true", "jar=true")
            jar_qr_url = self.jar_qr_url_for_template(template, form_data)
            payload["jar_print_url"] = jar_print_url
            payload["jar_qr_url"] = jar_qr_url
            payload["jar"] = {
                "image": self.data_url_for_image(jar_image),
                "metrics": jar_metrics.to_dict(),
                "warnings": jar_metrics.warnings,
            }
        if template.slug == qr_template.slug:
            try:
                base_date, best_by_date, delta_label, prefix = self.compute_best_by(form_data)
                best_by_payload: dict[str, object] = {
                    "delta_label": delta_label,
                    "prefix": prefix,
                    "text": self.best_by_text_value(form_data),
                }
                if base_date is not None:
                    best_by_payload["base_date"] = base_date.isoformat()
                if best_by_date is not None:
                    best_by_payload["best_by_date"] = best_by_date.strftime("%Y-%m-%d")
                payload["best_by"] = best_by_payload
            except ValueError:
                pass
        return payload
