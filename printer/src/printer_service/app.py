from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, TypeGuard
from urllib.parse import urlencode, urljoin

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from PIL import Image, UnidentifiedImageError

from . import label_templates
from .label_templates import TemplateFormData, TemplateFormValue, best_by
from .label import (
    SUPPORTED_BACKENDS,
    PrinterConfig,
    LabelMetrics,
    analyze_label_image,
    dispatch_image,
)


class _IngressPrefixMiddleware:
    def __init__(self, app: Callable[[dict[str, object], Callable[..., Any]], Any]) -> None:
        self.app = app

    def __call__(self, environ: dict, start_response: Callable[..., Any]) -> Any:
        ingress_path = environ.get("HTTP_X_INGRESS_PATH", "")
        if ingress_path:
            prefix = ingress_path.rstrip("/")
            environ["SCRIPT_NAME"] = prefix
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(prefix):
                environ["PATH_INFO"] = path_info[len(prefix) :] or "/"
        return self.app(environ, start_response)


def _is_truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.wsgi_app = _IngressPrefixMiddleware(app.wsgi_app)  # type: ignore[method-assign]

    @app.get("/")
    def index():
        default = label_templates.default_template()
        return redirect(url_for("bb_route", template=default.slug))

    @app.get("/templates/<template_slug>")
    def show_template(template_slug: str):
        slug = _coerce_slug(template_slug)
        return redirect(url_for("bb_route", template=slug))

    @app.get("/bb")
    def bb_route():
        template = _template_from_request(default_template=_best_by_template())
        # Note: print parameter is now handled by JavaScript countdown, not server-side
        return _render_bb_page(template)

    @app.post("/bb/execute-print")
    def execute_print_route():
        """Execute print after countdown completion."""
        template = _template_from_request(default_template=_best_by_template())
        return _print_from_request(template)

    @app.post("/bb/preview")
    def preview_bb():
        payload = request.get_json(silent=True) or {}
        try:
            template, form_data = _template_and_form_from_payload(payload)
            preview = _build_preview_payload(template, form_data)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        return jsonify(preview)

    @app.post("/bb/print")
    def print_bb():
        payload = request.get_json(silent=True) or {}
        try:
            template, form_data = _template_and_form_from_payload(payload)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        include_qr_label = False
        if isinstance(payload, Mapping) and "qr_label" in payload:
            include_qr_label = _is_truthy(str(payload.get("qr_label")))
        return _dispatch_print(template, form_data, include_qr_label=include_qr_label)

    @app.post("/print")
    def print_route():
        config = PrinterConfig.from_env()
        if request.files:
            uploaded = request.files.get("file")
            if uploaded is None or not uploaded.filename:
                return jsonify({"error": "Upload a file under the 'file' field."}), 400
            try:
                image = Image.open(uploaded.stream)
            except (UnidentifiedImageError, OSError):
                return jsonify({"error": "Uploaded file must be a readable image."}), 400
            metrics = analyze_label_image(image, config)
            try:
                result = dispatch_image(image, config)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            return jsonify(_success_payload(result, warnings=metrics.warnings, metrics=metrics))

        payload = request.get_json(silent=True) or {}
        if "backend" in payload:
            candidate = str(payload["backend"]).strip().lower()
            if candidate not in SUPPORTED_BACKENDS:
                return jsonify(
                    {"error": f"backend must be one of {sorted(SUPPORTED_BACKENDS)}"}
                ), 400
            config.backend = candidate

        try:
            image, template_ref = _render_image_from_payload(payload)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        target_spec = template_ref.preferred_label_spec() if template_ref else None
        metrics = analyze_label_image(image, config, target_spec=target_spec)
        try:
            result = dispatch_image(image, config, target_spec=target_spec)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(_success_payload(result, warnings=metrics.warnings, metrics=metrics))

    return app


app = create_app()


def _success_payload(
    path: Optional[os.PathLike[str]],
    *,
    warnings: Optional[List[str]] = None,
    metrics: Optional[LabelMetrics] = None,
) -> dict:
    payload: dict = {"status": "sent"}
    if path:
        payload["output"] = str(path)
    if metrics is not None:
        payload["metrics"] = metrics.to_dict()
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


def _coerce_slug(raw: object) -> str:
    return str(raw or "").strip().lower()


class LabelPayloadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _template_from_request(
    default_template: label_templates.LabelTemplate,
) -> label_templates.LabelTemplate:
    slug = _coerce_slug(
        request.args.get("tpl") or request.args.get("template") or request.args.get("template_slug")
    )
    if slug:
        try:
            return label_templates.get_template(slug)
        except KeyError:
            abort(404)
    return default_template


def _template_and_form_from_payload(
    payload: Mapping[str, object],
) -> tuple[label_templates.LabelTemplate, TemplateFormData]:
    slug = ""
    if "tpl" in payload:
        slug = _coerce_slug(payload.get("tpl"))
    elif "template" in payload:
        slug = _coerce_slug(payload.get("template"))
    else:
        raise LabelPayloadError("Provide 'template'.")
    try:
        template = label_templates.get_template(slug)
    except KeyError:
        raise LabelPayloadError("Unknown template.")
    form_data = _coerce_template_form_data(payload.get("data"))
    if template.slug == _best_by_template().slug:
        form_data = _normalized_best_by_form(form_data)
    return template, form_data


def _form_data_from_args(template: label_templates.LabelTemplate) -> TemplateFormData:
    if template.slug == _best_by_template().slug:
        return _best_by_form_data_from_request()
    control_params = {"tpl", "template", "template_slug", "print", "qr_label", "qr"}
    data: dict[str, TemplateFormValue] = {}
    for key in request.args:
        if key.lower() in control_params:
            continue
        values = request.args.getlist(key)
        if len(values) == 1:
            data[key] = values[0]
        else:
            data[key] = values
    return TemplateFormData(data)


def _build_preview_payload(
    template: label_templates.LabelTemplate, form_data: TemplateFormData
) -> dict:
    try:
        label_image = template.render(form_data)
    except ValueError as exc:
        raise LabelPayloadError(str(exc))
    label_metrics = analyze_label_image(label_image, target_spec=template.preferred_label_spec())
    print_url = _print_url_for_template(template, form_data)
    qr_caption = _qr_caption_for_template(template, form_data)
    try:
        qr_image = _render_qr_label_image(template, form_data, print_url, qr_caption)
    except ValueError as exc:
        raise LabelPayloadError(str(exc))
    qr_template = _best_by_template()
    qr_metrics = analyze_label_image(qr_image, target_spec=qr_template.preferred_label_spec())

    payload: dict[str, object] = {
        "status": "preview",
        "template": template.slug,
        "print_url": print_url,
        "qr_print_url": _print_url_for_template(template, form_data, include_qr_label=True),
        "qr_caption": qr_caption,
        "label": {
            "image": _data_url_for_image(label_image),
            "metrics": label_metrics.to_dict(),
            "warnings": label_metrics.warnings,
        },
        "qr": {
            "image": _data_url_for_image(qr_image),
            "metrics": qr_metrics.to_dict(),
            "warnings": qr_metrics.warnings,
        },
    }
    if template.slug == _best_by_template().slug:
        try:
            base_date, best_by_date, delta_label, prefix = best_by.compute_best_by(form_data)
            payload["best_by"] = {
                "base_date": base_date.isoformat(),
                "best_by_date": best_by_date.strftime("%Y-%m-%d"),
                "delta_label": delta_label,
                "prefix": prefix,
                "text": _best_by_text_value(form_data),
            }
        except ValueError:
            pass
    return payload


def _render_image_from_payload(
    payload: Mapping[str, object],
) -> tuple[Image.Image, label_templates.LabelTemplate]:
    if "template" not in payload:
        if "lines" in payload:
            raise LabelPayloadError(
                "Raw 'lines' payloads are no longer supported. Submit a template slug instead."
            )
        raise LabelPayloadError("Provide 'template'.")
    template, form_data = _template_and_form_from_payload(payload)
    try:
        image = template.render(form_data)
    except ValueError as exc:
        raise LabelPayloadError(str(exc))
    return image, template


def _print_from_request(template: label_templates.LabelTemplate):
    try:
        form_data = _form_data_from_args(template)
    except LabelPayloadError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    include_qr_label = _is_truthy(request.args.get("qr") or request.args.get("qr_label"))

    # Execute the print
    print_result = _dispatch_print(template, form_data, include_qr_label=include_qr_label)

    # Check if print was successful (status code 200)
    if hasattr(print_result, "status_code") and print_result.status_code != 200:
        return print_result
    elif isinstance(print_result, tuple) and len(print_result) == 2:
        # Handle tuple response (response, status_code)
        response, status_code = print_result
        if status_code != 200:
            return print_result

    # Print was successful - return the result directly (JSON response)
    return print_result


def _render_bb_page(template: label_templates.LabelTemplate):
    return render_template(
        template.form_template,
        templates=label_templates.all_templates(),
        active_template=template,
        form_context=template.form_context(),
        initial_query=request.args,
    )


def _render_print_image(
    template: label_templates.LabelTemplate,
    form_data: TemplateFormData,
    *,
    include_qr_label: bool,
) -> tuple[Image.Image, Optional[LabelMetrics], Optional[label_templates.LabelTemplate]]:
    if include_qr_label:
        print_url = _print_url_for_template(template, form_data)
        qr_caption = _qr_caption_for_template(template, form_data)
        qr_image = _render_qr_label_image(template, form_data, print_url, qr_caption)
        qr_template = _best_by_template()
        metrics = analyze_label_image(qr_image, target_spec=qr_template.preferred_label_spec())
        return qr_image, metrics, qr_template
    try:
        image = template.render(form_data)
    except ValueError as exc:
        raise LabelPayloadError(str(exc))
    metrics = analyze_label_image(image, target_spec=template.preferred_label_spec())
    return image, metrics, template


def _dispatch_print(
    template: label_templates.LabelTemplate,
    form_data: TemplateFormData,
    *,
    include_qr_label: bool,
):
    config = PrinterConfig.from_env()
    try:
        image, metrics, metrics_template = _render_print_image(
            template, form_data, include_qr_label=include_qr_label
        )
    except LabelPayloadError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    target_spec = metrics_template.preferred_label_spec() if metrics_template else None
    try:
        result = dispatch_image(image, config, target_spec=target_spec)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    response_payload = _success_payload(
        result, warnings=metrics.warnings if metrics else None, metrics=metrics
    )
    response_payload["template"] = template.slug
    if include_qr_label:
        response_payload["qr_label"] = True
    if template.slug == _best_by_template().slug:
        text_value = _best_by_text_value(form_data)
        if text_value:
            response_payload["text"] = text_value
        else:
            try:
                base_date, best_by_date, delta_label, _prefix = best_by.compute_best_by(form_data)
                response_payload.update(
                    {
                        "best_by_date": best_by_date.strftime("%Y-%m-%d"),
                        "base_date": base_date.strftime("%Y-%m-%d"),
                        "delta": delta_label,
                    }
                )
            except ValueError:
                pass
    return jsonify(response_payload)


def _qr_caption_for_template(
    template: label_templates.LabelTemplate, form_data: TemplateFormData
) -> str:
    best_by_template = _best_by_template()
    if template.slug == best_by_template.slug:
        text_value = _best_by_text_value(form_data)
        if text_value:
            return f"Print: {text_value}"
        try:
            _base_date, _best_by_date, delta_label, prefix = best_by.compute_best_by(form_data)
        except ValueError as exc:
            raise LabelPayloadError(str(exc))
        return f"Print {prefix}+{delta_label.title()}"
    explicit = form_data.get_str("QrText", "qr_text")
    if explicit:
        return explicit
    headline = form_data.get_str("Line1", "line1") or form_data.get_str("Title", "title")
    if headline:
        return f"Print {template.display_name}: {headline}"
    return f"Print {template.display_name}"


def _render_qr_label_image(
    template: label_templates.LabelTemplate,
    form_data: TemplateFormData,
    print_url: str,
    qr_caption: str,
) -> Image.Image:
    qr_template = _best_by_template()
    qr_form_data = TemplateFormData({"QrUrl": print_url, "QrText": qr_caption})
    return qr_template.render(qr_form_data)


def _query_params_from_form_data(form_data: TemplateFormData) -> dict[str, object]:
    params: dict[str, object] = {}
    for key, value in form_data.items():
        if isinstance(value, Mapping):
            params[key] = str(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            params[key] = [str(item) for item in value]
        elif value is None:
            params[key] = ""
        else:
            params[key] = str(value)
    return params


def _print_url_for_template(
    template: label_templates.LabelTemplate,
    form_data: TemplateFormData,
    *,
    include_qr_label: bool = False,
) -> str:
    params = {
        **_query_params_from_form_data(form_data),
        "tpl": template.slug,
        "print": "true",
    }
    if include_qr_label:
        params["qr"] = "true"
    return _build_public_url(_best_by_relative_path(), params)


# TODO: move best by label and related code its own python module `printer/src/printer_service/best_by.py`. There should not be best-by-specific code in this file.
def _best_by_form_data_from_request() -> TemplateFormData:
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
                if not _is_template_form_value(value):
                    raise LabelPayloadError(
                        f"{canonical} must be a string, number, boolean, or null."
                    )
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
    text_value = _best_by_text_value(form_data)
    if text_value:
        has_base = bool(form_data.get_str("BaseDate", "base_date"))
        has_delta = bool(form_data.get_str("Delta", "delta"))
        if has_base or has_delta:
            raise LabelPayloadError("Text cannot be combined with base/offset dates.")
    return _normalized_best_by_form(form_data)


def _best_by_template() -> label_templates.LabelTemplate:
    try:
        return label_templates.get_template("best_by")
    except KeyError:
        return label_templates.get_template("bb_2_weeks")


def _request_arg_keys_lower() -> set[str]:
    try:
        return {key.lower() for key in request.args.keys()}
    except RuntimeError:
        return set()


def _delta_param_name_from_request(default: str = "offset") -> str:
    raw_keys = _request_arg_keys_lower()
    if "offset" in raw_keys:
        return "offset"
    if "delta" in raw_keys:
        return "delta"
    return default


def _best_by_text_value(form_data: TemplateFormData) -> str:
    raw = form_data.get_str("Text", "text")
    decoded = raw.replace("+", " ")
    return " ".join(decoded.split())


def _normalized_best_by_form(form_data: TemplateFormData) -> TemplateFormData:
    text_value = _best_by_text_value(form_data)
    if not text_value:
        return form_data
    data = dict(form_data.items())
    data["Text"] = text_value
    return TemplateFormData(data)


def _best_by_relative_path() -> str:
    """Return the Best By route path without any ingress/script prefix."""
    return "bb"


def _base_service_url() -> str:
    """Resolve the externally reachable base URL for direct (non-ingress) access."""
    override_host = os.getenv("PUBLIC_SERVICE_HOST")
    override_port = os.getenv("PUBLIC_SERVICE_PORT") or os.getenv("FLASK_PORT")
    override_scheme = os.getenv("PUBLIC_SERVICE_SCHEME")
    base_path = os.getenv("PUBLIC_SERVICE_PATH", "/") or "/"

    host_header = request.host or "localhost"
    if ":" in host_header:
        host_only, host_port = host_header.split(":", 1)
    else:
        host_only, host_port = host_header, ""

    scheme = override_scheme or request.scheme or "http"
    host = override_host or host_only
    port = override_port or host_port

    normalized_path = base_path if base_path.startswith("/") else f"/{base_path}"
    if not normalized_path.endswith("/"):
        normalized_path = f"{normalized_path}/"

    netloc = f"{host}:{port}" if port else host
    return f"{scheme}://{netloc}{normalized_path}"


def _build_public_url(path_fragment: str, params: Optional[Mapping[str, object]] = None) -> str:
    base_url = _base_service_url()
    base = base_url if base_url.endswith("/") else f"{base_url}/"
    url = urljoin(base, path_fragment.lstrip("/"))
    query = urlencode(params or {}, doseq=True)
    return f"{url}?{query}" if query else url


def _data_url_for_image(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def main() -> None:
    host = os.getenv("FLASK_HOST", "::")
    port = int(os.getenv("FLASK_PORT", "8099"))
    reload_enabled = _should_enable_dev_reload()
    extra_files = _dev_extra_files() if reload_enabled else None
    forwarded_prefix = os.getenv("INGRESS_ENTRY")
    app.run(
        host=host,
        port=port,
        debug=reload_enabled,
        use_reloader=reload_enabled,
        extra_files=extra_files,
        threaded=True,
    )


def _coerce_template_form_data(candidate: object) -> TemplateFormData:
    if isinstance(candidate, TemplateFormData):
        return candidate
    if not isinstance(candidate, Mapping):
        raise LabelPayloadError("Provide 'data' as an object of form inputs.")
    for key, value in candidate.items():
        if not isinstance(key, str):
            raise LabelPayloadError("Form data keys must be strings.")
        if not _is_template_form_value(value):
            raise LabelPayloadError("Form data values must be strings, numbers, booleans, or null.")
    return TemplateFormData(candidate)


def _is_template_form_value(value: object) -> TypeGuard[TemplateFormValue]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _is_template_form_value(item_value)
            for key, item_value in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return all(_is_template_form_value(item) for item in value)
    return False


def _should_enable_dev_reload() -> bool:
    raw = os.getenv("PRINTER_DEV_RELOAD")
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized not in {"0", "false", "off", ""}


def _dev_extra_files() -> List[str]:
    # Ensure Flask's reloader also watches template and static assets.
    package_root = Path(__file__).resolve().parent
    watch_roots = [
        package_root / "templates",
        package_root / "static",
    ]
    extensions = {".html", ".js"}
    extra: List[str] = []
    for root in watch_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in extensions:
                extra.append(str(path))
    return extra


__all__ = ["app", "create_app", "main"]


if __name__ == "__main__":
    main()
