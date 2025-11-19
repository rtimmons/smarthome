from __future__ import annotations

import base64
import os
from collections.abc import Callable, Mapping
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, TypeGuard

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from PIL import Image, UnidentifiedImageError

from . import label_templates
from .label_templates import bb_2_weeks
from .label_templates import TemplateFormData, TemplateFormValue
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
    def __init__(self, app: Callable[[dict[str, Any], Callable], Any]) -> None:
        self.app = app

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Any:
        ingress_path = environ.get("HTTP_X_INGRESS_PATH", "")
        if ingress_path:
            prefix = ingress_path.rstrip("/")
            environ["SCRIPT_NAME"] = prefix
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(prefix):
                environ["PATH_INFO"] = path_info[len(prefix) :] or "/"
        return self.app(environ, start_response)


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
        data: dict[str, TemplateFormValue] = {}

        payload = request.get_json(silent=True)
        if isinstance(payload, Mapping):
            for key in ("BaseDate", "base_date"):
                if key in payload:
                    value = payload[key]
                    if not _is_template_form_value(value):
                        return (
                            jsonify(
                                {"error": "BaseDate must be a string, number, boolean, or null."}
                            ),
                            400,
                        )
                    data["BaseDate"] = value
                    break
        query_base_date = request.args.get("base_date") or request.args.get("BaseDate")
        if query_base_date and "BaseDate" not in data:
            data["BaseDate"] = query_base_date

        form_data = TemplateFormData(data)
        render_payload = {"template": "bb_2_weeks", "data": form_data}
        try:
            image, template_ref = _render_image_from_payload(render_payload)
        except LabelPayloadError as exc:
            return jsonify({"error": str(exc)}), exc.status_code

        base_date = bb_2_weeks._resolve_base_date(form_data)
        best_by_date = base_date + timedelta(days=14)

        target_spec = template_ref.preferred_label_spec()
        metrics = analyze_label_image(image, config, target_spec=target_spec)
        stored_path = save_label_image(
            image,
            output_dir,
            prefix="bb2w",
            target_spec=target_spec,
        )
        try:
            dispatch_target = dispatch_image(image, config, target_spec=target_spec)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        response_payload = _success_payload(
            dispatch_target, warnings=metrics.warnings, metrics=metrics
        )
        response_payload.update(
            {
                "label": _serialize_label(stored_path),
                "template": template_ref.slug,
                "best_by_date": best_by_date.strftime("%Y-%m-%d"),
            }
        )
        return jsonify(response_payload)

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
