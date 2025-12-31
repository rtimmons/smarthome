from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional, Protocol

from PIL import Image

from .label import LabelMetrics, PrinterConfig
from .label_specs import BrotherLabelSpec
from .label_templates import LabelTemplate, TemplateFormData


class SuccessPayloadBuilder(Protocol):
    def __call__(
        self,
        path: Optional[object],
        *,
        warnings: Optional[list[str]] = None,
        metrics: Optional[LabelMetrics] = None,
    ) -> dict: ...


@dataclass(frozen=True)
class PrintDispatchService:
    analyze_label_image: Callable[..., LabelMetrics]
    dispatch_image: Callable[..., Optional[object]]
    config_from_env: Callable[[], PrinterConfig]
    print_url_for_template: Callable[..., str]
    qr_caption_for_template: Callable[[LabelTemplate, TemplateFormData], str]
    render_qr_label_image: Callable[[LabelTemplate, TemplateFormData, str, str], Image.Image]
    jar_qr_url_for_template: Callable[[LabelTemplate, TemplateFormData], str]
    label_spec_from_metadata: Callable[[Image.Image], Optional[BrotherLabelSpec]]
    best_by_template: Callable[[], LabelTemplate]
    best_by_text_value: Callable[[TemplateFormData], str]
    compute_best_by: Callable[[TemplateFormData], tuple[Optional[date], Optional[date], str, str]]
    success_payload: SuccessPayloadBuilder
    payload_error: Callable[[str], Exception]

    def dispatch(
        self,
        template: LabelTemplate,
        form_data: TemplateFormData,
        *,
        include_qr_label: bool,
        include_jar_label: bool = False,
    ) -> dict:
        config = self.config_from_env()
        image, metrics, metrics_template = self._render_print_image(
            template,
            form_data,
            include_qr_label=include_qr_label,
            include_jar_label=include_jar_label,
        )
        target_spec = metrics_template.preferred_label_spec() if metrics_template else None
        result = self.dispatch_image(image, config, target_spec=target_spec)
        response_payload = self.success_payload(
            result,
            warnings=metrics.warnings if metrics else None,
            metrics=metrics,
        )
        response_payload["template"] = template.slug
        if include_qr_label:
            response_payload["qr_label"] = True
        if template.slug == self.best_by_template().slug:
            text_value = self.best_by_text_value(form_data)
            if text_value:
                response_payload["text"] = text_value
            else:
                try:
                    base_date, best_by_date, delta_label, _prefix = self.compute_best_by(form_data)
                    if best_by_date is not None:
                        response_payload["best_by_date"] = best_by_date.strftime("%Y-%m-%d")
                    if base_date is not None:
                        response_payload["base_date"] = base_date.strftime("%Y-%m-%d")
                    response_payload["delta"] = delta_label
                except ValueError:
                    pass
        return response_payload

    def _render_print_image(
        self,
        template: LabelTemplate,
        form_data: TemplateFormData,
        *,
        include_qr_label: bool,
        include_jar_label: bool = False,
    ) -> tuple[Image.Image, LabelMetrics, LabelTemplate]:
        if include_qr_label:
            print_url = self.print_url_for_template(template, form_data, prefer_preset=True)
            qr_caption = self.qr_caption_for_template(template, form_data)
            try:
                qr_image = self.render_qr_label_image(template, form_data, print_url, qr_caption)
            except ValueError as exc:
                raise self.payload_error(str(exc)) from exc
            qr_template = self.best_by_template()
            metrics = self.analyze_label_image(
                qr_image, target_spec=qr_template.preferred_label_spec()
            )
            return qr_image, metrics, qr_template
        if include_jar_label:
            jar_qr_url = self.jar_qr_url_for_template(template, form_data)
            jar_form_data = dict(form_data)
            jar_form_data["jar_qr_url"] = jar_qr_url
            jar_form_data["jar_label_request"] = "true"
            try:
                image = template.render(jar_form_data)
            except ValueError as exc:
                raise self.payload_error(str(exc)) from exc
            jar_spec = self.label_spec_from_metadata(image)
            metrics = self.analyze_label_image(image, target_spec=jar_spec)
            return image, metrics, template
        try:
            image = template.render(form_data)
        except ValueError as exc:
            raise self.payload_error(str(exc)) from exc
        metrics = self.analyze_label_image(image, target_spec=template.preferred_label_spec())
        return image, metrics, template
