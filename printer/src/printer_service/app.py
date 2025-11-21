from __future__ import annotations

import base64
import math
import os
import time
from collections.abc import Mapping
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List, Optional, TypeGuard

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from PIL import Image, UnidentifiedImageError

from . import label_templates
from .label_templates import TemplateFormData, TemplateFormValue, best_by
from .label import (
    SUPPORTED_BACKENDS,
    PrinterConfig,
    LabelMetrics,
    analyze_label_image,
    dispatch_image,
    label_spec_from_metadata,
    save_label_image,
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


PRINT_COOLDOWN_SECONDS = 5
_last_print_at: Optional[float] = None


def _now() -> float:
    return time.monotonic()


def _cooldown_remaining() -> float:
    if _last_print_at is None:
        return 0.0
    elapsed = _now() - _last_print_at
    return max(0.0, PRINT_COOLDOWN_SECONDS - elapsed)


def _mark_print_sent() -> None:
    global _last_print_at
    _last_print_at = _now()


def _cooldown_response():
    remaining = _cooldown_remaining()
    if remaining <= 0:
        return None
    retry_after = int(math.ceil(remaining))
    response = jsonify({"error": f"Printer cooling down. Try again in {retry_after}s."})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def _is_truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def create_app() -> Flask:
    app = Flask(__name__)
    output_dir = Path(os.getenv("LABEL_OUTPUT_DIR", "label-output")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app.wsgi_app = _IngressPrefixMiddleware(app.wsgi_app)  # type: ignore[method-assign]

    @app.get("/")
    def index():
        default = label_templates.default_template()
        return redirect(url_for("show_template", template_slug=default.slug))

    @app.get("/templates/<template_slug>")
    def show_template(template_slug: str):
        slug = _coerce_slug(template_slug)
        best_by_template = _best_by_template()
        if slug == best_by_template.slug:
            target = url_for("best_by_route")
            query = request.query_string.decode("utf-8")
            if query:
                target = f"{target}?{query}"
            return redirect(target)
        try:
            active = label_templates.get_template(slug)
        except KeyError:
            abort(404)
        templates = label_templates.all_templates()
        return render_template(
            active.form_template,
            templates=templates,
            active_template=active,
            form_context=active.form_context(),
        )

    @app.get("/bb")
    def best_by_route():
        try:
            form_data = _best_by_form_data_from_request()
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        wants_print = _is_truthy(request.args.get("print"))
        wants_qr_label = _is_truthy(request.args.get("qr_label"))
        print_params = _best_by_print_params(form_data)
        print_url = url_for("best_by_route", _external=True, **print_params)
        if wants_print:
            config = PrinterConfig.from_env()
            try:
                base_date, best_by_date, delta_label = best_by.compute_best_by(form_data)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            has_custom = len(print_params) > 1
            qr_text = "Print" if not has_custom else f"Print Best By +{delta_label.title()}"
            qr_url = print_url
            return _send_best_by_print(
                form_data=form_data,
                config=config,
                qr_url=qr_url if wants_qr_label else None,
                qr_text=qr_text if wants_qr_label else None,
                base_date=base_date,
                best_by_date=best_by_date,
                delta_label=delta_label,
            )
        return _render_best_by_page(form_data)

    @app.get("/labels")
    def list_labels():
        return jsonify({"labels": _recent_labels(output_dir)})

    @app.post("/labels")
    def create_label():
        payload = request.get_json(silent=True) or {}
        try:
            image, template = _render_image_from_payload(payload)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        target_spec = template.preferred_label_spec()
        metrics = analyze_label_image(image, target_spec=target_spec)
        path = save_label_image(
            image,
            output_dir,
            target_spec=target_spec,
        )
        label = _serialize_label(path)
        return jsonify(
            {
                "status": "stored",
                "label": label,
                "metrics": metrics.to_dict(),
                "warnings": metrics.warnings,
            }
        )

    @app.post("/bb2w")
    def create_and_print_bb2w():
        config = PrinterConfig.from_env()
        try:
            form_data = _best_by_form_data_from_request()
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        return _send_best_by_print(form_data=form_data, config=config)

    @app.post("/labels/preview")
    def preview_label():
        payload = request.get_json(silent=True) or {}
        try:
            image, template = _render_image_from_payload(payload)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code
        metrics = analyze_label_image(image, target_spec=template.preferred_label_spec())
        data_url = _data_url_for_image(image)
        return jsonify(
            {
                "status": "preview",
                "image": data_url,
                "metrics": metrics.to_dict(),
                "warnings": metrics.warnings,
            }
        )

    @app.get("/labels/<path:filename>")
    def serve_label(filename: str):
        safe_name = _safe_filename(filename)
        path = (output_dir / safe_name).resolve()
        if not str(path).startswith(str(output_dir)):
            abort(403)
        if not path.exists():
            abort(404)
        return send_file(path, mimetype="image/png")

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
            cooldown = _cooldown_response()
            if cooldown is not None:
                return cooldown
            metrics = analyze_label_image(image, config)
            try:
                result = dispatch_image(image, config)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            _mark_print_sent()
            return jsonify(_success_payload(result, warnings=metrics.warnings, metrics=metrics))

        payload = request.get_json(silent=True) or {}
        if "backend" in payload:
            candidate = str(payload["backend"]).strip().lower()
            if candidate not in SUPPORTED_BACKENDS:
                return jsonify(
                    {"error": f"backend must be one of {sorted(SUPPORTED_BACKENDS)}"}
                ), 400
            config.backend = candidate

        image: Optional[Image.Image] = None
        template_ref: Optional[label_templates.LabelTemplate] = None
        stored_spec = None
        if "filename" in payload:
            safe_name = _safe_filename(str(payload["filename"]))
            path = output_dir / safe_name
            try:
                image = _load_stored_label(path)
            except LabelPayloadError as exc:
                return jsonify({"error": str(exc)}), exc.status_code
            stored_spec = label_spec_from_metadata(image)
        else:
            cooldown = _cooldown_response()
            if cooldown is not None:
                return cooldown
            try:
                image, template_ref = _render_image_from_payload(payload)
            except LabelPayloadError as exc:
                return jsonify({"error": str(exc)}), exc.status_code
        if image is None:  # pragma: no cover - defensive guard
            return jsonify({"error": "Unable to prepare label image."}), 500
        target_spec = template_ref.preferred_label_spec() if template_ref else stored_spec
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


def _safe_filename(raw: str) -> str:
    return Path(raw).name


def _serialize_label(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "url": url_for("serve_label", filename=path.name),
        "mtime": stat.st_mtime,
    }


def _recent_labels(directory: Path, limit: int = 100) -> List[dict]:
    files = [(path, path.stat().st_mtime) for path in directory.glob("*.png") if path.is_file()]
    files.sort(key=lambda item: item[1], reverse=True)
    top = [path for path, _ in files[:limit]]
    return [_serialize_label(path) for path in top]


def _coerce_slug(raw: object) -> str:
    return str(raw or "").strip().lower()


class LabelPayloadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _render_image_from_payload(
    payload: Mapping[str, object],
) -> tuple[Image.Image, label_templates.LabelTemplate]:
    if "template" in payload:
        slug = _coerce_slug(payload.get("template"))
        try:
            template = label_templates.get_template(slug)
        except KeyError:
            raise LabelPayloadError("Unknown template.")
        form_data = _coerce_template_form_data(payload.get("data"))
        try:
            image = template.render(form_data)
        except ValueError as exc:
            raise LabelPayloadError(str(exc))
        return image, template
    if "lines" in payload:
        raise LabelPayloadError(
            "Raw 'lines' payloads are no longer supported. Submit a template slug instead."
        )
    raise LabelPayloadError("Provide 'template'.")


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
    ):
        candidate = request.args.get(key)
        if candidate and canonical not in data:
            data[canonical] = candidate
    return TemplateFormData(data)


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


def _best_by_print_params(
    form_data: TemplateFormData,
    *,
    include_qr_label: bool = False,
) -> dict[str, str]:
    params: dict[str, str] = {"print": "true"}
    raw_request_keys = _request_arg_keys_lower()
    base_date_raw = form_data.get_str("BaseDate", "base_date")
    if base_date_raw:
        try:
            parsed_base = date.fromisoformat(base_date_raw)
        except ValueError:
            parsed_base = None
        if parsed_base and parsed_base != best_by._today():
            params["baseDate"] = parsed_base.isoformat()
    delta_raw = form_data.get_str("Delta", "delta")
    delta_param_name = _delta_param_name_from_request()
    provided_delta_param = delta_param_name in raw_request_keys
    if delta_raw:
        try:
            delta_value, _ = best_by._parse_delta_string(delta_raw)
        except ValueError:
            delta_value = best_by.DEFAULT_DELTA
        if delta_value != best_by.DEFAULT_DELTA or provided_delta_param:
            params[delta_param_name] = delta_raw.strip()
    if include_qr_label:
        params["qr_label"] = "true"
    return params


def _render_best_by_page(form_data: TemplateFormData):
    template_ref = _best_by_template()
    try:
        base_date, best_by_date, delta_label = best_by.compute_best_by(form_data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    delta_value = form_data.get_str("Delta", "delta") or best_by.DEFAULT_DELTA_LABEL
    print_params = _best_by_print_params(form_data)
    print_url = url_for("best_by_route", _external=True, **print_params)
    qr_print_url = url_for(
        "best_by_route",
        _external=True,
        **_best_by_print_params(form_data, include_qr_label=True),
    )
    qr_caption = f"Print Best By +{delta_label.title()}"

    try:
        base_label_preview = template_ref.render(form_data)
        qr_label_preview_data = _data_url_for_image(
            template_ref.render(
                TemplateFormData(
                    {**dict(form_data.items()), "QrUrl": print_url, "QrText": qr_caption}
                )
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    today_iso = best_by._today().isoformat()
    best_by_preview_url = _data_url_for_image(base_label_preview)

    return render_template(
        template_ref.form_template,
        templates=label_templates.all_templates(),
        active_template=template_ref,
        form_context=template_ref.form_context(),
        base_date_value=base_date.isoformat(),
        delta_value=delta_value,
        best_by_date=best_by_date.strftime("%Y-%m-%d"),
        print_url=print_url,
        qr_print_url=qr_print_url,
        qr_label_preview_url=qr_label_preview_data,
        best_by_preview_url=best_by_preview_url,
        qr_caption=qr_caption,
        delta_label=delta_label,
        today_iso=today_iso,
    )


def _send_best_by_print(
    form_data: TemplateFormData,
    *,
    config: PrinterConfig,
    qr_url: Optional[str] = None,
    qr_text: Optional[str] = None,
    base_date: Optional[date] = None,
    best_by_date: Optional[date] = None,
    delta_label: Optional[str] = None,
):
    try:
        computed_base, computed_best_by, computed_delta = best_by.compute_best_by(form_data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    base_date = base_date or computed_base
    best_by_date = best_by_date or computed_best_by
    delta_label = delta_label or computed_delta

    payload_data = dict(form_data.items())
    if qr_url:
        payload_data["QrUrl"] = qr_url
    if qr_text:
        payload_data["QrText"] = qr_text
    payload_form = TemplateFormData(payload_data)
    template_ref = _best_by_template()

    cooldown = _cooldown_response()
    if cooldown is not None:
        return cooldown

    try:
        image = template_ref.render(payload_form)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    target_spec = template_ref.preferred_label_spec()
    metrics = analyze_label_image(image, config, target_spec=target_spec)
    try:
        dispatch_target = dispatch_image(image, config, target_spec=target_spec)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _mark_print_sent()

    response_payload = _success_payload(dispatch_target, warnings=metrics.warnings, metrics=metrics)
    response_payload.update(
        {
            "template": template_ref.slug,
            "best_by_date": best_by_date.strftime("%Y-%m-%d"),
            "base_date": base_date.strftime("%Y-%m-%d"),
            "delta": delta_label,
        }
    )
    return jsonify(response_payload)


def _load_stored_label(path: Path) -> Image.Image:
    if not path.exists():
        raise LabelPayloadError("Label not found.", status_code=404)
    try:
        with Image.open(path) as stored:
            return stored.copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise LabelPayloadError("Stored label is unreadable.", status_code=500) from exc


def _data_url_for_image(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def main() -> None:
    host = os.getenv("FLASK_HOST", "0.0.0.0")
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
    return value is None or isinstance(value, (str, int, float, bool))


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
