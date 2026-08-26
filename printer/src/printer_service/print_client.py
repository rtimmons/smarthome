from __future__ import annotations

import argparse
import json
import os
import secrets
import ssl
import stat
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

from werkzeug.datastructures import FileStorage

from .png_upload import MAX_UPLOAD_BYTES, PNGUploadError, prepare_png_upload

DEFAULT_SERVICE_HOST = "homeassistant.local"
DEFAULT_SERVICE_PORT = 8099
DEFAULT_TIMEOUT_SECONDS = 45.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_TOKEN_BYTES = 64 * 1024


class PrintClientError(RuntimeError):
    """A safe, user-facing print client error."""


class PrintTransportError(PrintClientError):
    """The service did not return an HTTP response."""


class AmbiguousPrintError(PrintClientError):
    """The connection failed after print dispatch began."""


@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    preview_path: str
    print_path: str
    timeout_seconds: float
    bearer_token: str | None
    token_source: str | None
    ca_file: Path | None

    def endpoint(self, route: str) -> str:
        return urljoin(self.base_url, route.lstrip("/"))


@dataclass(frozen=True)
class LocalPNG:
    path: Path
    payload: bytes
    source_size: tuple[int, int]
    target_size: tuple[int, int]
    rotated: bool


class PNGPoster(Protocol):
    def __call__(
        self,
        config: ClientConfig,
        endpoint: str,
        *,
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    """Keep POST bodies and bearer credentials away from redirect targets."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def resolve_config(env: Mapping[str, str] | None = None) -> ClientConfig:
    values = os.environ if env is None else env
    explicit_url = values.get("PRINTER_SERVICE_URL", "").strip()
    if explicit_url:
        base_url = _normalize_base_url(explicit_url)
    else:
        scheme = (
            values.get("PRINTER_SERVICE_SCHEME") or values.get("PUBLIC_SERVICE_SCHEME") or "http"
        ).strip()
        host = (
            values.get("PRINTER_SERVICE_HOST")
            or values.get("PUBLIC_SERVICE_HOST")
            or values.get("HA_HOST")
            or DEFAULT_SERVICE_HOST
        ).strip()
        raw_port = (
            values.get("PRINTER_SERVICE_PORT")
            or values.get("PUBLIC_SERVICE_PORT")
            or str(DEFAULT_SERVICE_PORT)
        ).strip()
        service_path = (
            values.get("PRINTER_SERVICE_PATH") or values.get("PUBLIC_SERVICE_PATH") or "/"
        ).strip()
        port = _parse_port(raw_port)
        base_url = _base_url_from_parts(scheme, host, port, service_path)

    preview_path = _normalize_route(
        values.get("PRINTER_PREVIEW_PATH", "png/preview"),
        name="PRINTER_PREVIEW_PATH",
    )
    print_path = _normalize_route(
        values.get("PRINTER_PRINT_PATH", "png/print"),
        name="PRINTER_PRINT_PATH",
    )
    timeout_seconds = _parse_timeout(values.get("PRINTER_SERVICE_TIMEOUT", ""))
    bearer_token, token_source = _load_bearer_token(values)

    raw_ca_file = values.get("PRINTER_SERVICE_CA_FILE", "").strip()
    ca_file = Path(raw_ca_file).expanduser().resolve() if raw_ca_file else None
    if ca_file is not None and not ca_file.is_file():
        raise PrintClientError(f"PRINTER_SERVICE_CA_FILE is not a file: {ca_file}")

    return ClientConfig(
        base_url=base_url,
        preview_path=preview_path,
        print_path=print_path,
        timeout_seconds=timeout_seconds,
        bearer_token=bearer_token,
        token_source=token_source,
        ca_file=ca_file,
    )


def validate_local_png(raw_path: str | Path) -> LocalPNG:
    path = Path(raw_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PrintClientError(f"PNG file does not exist: {path}") from exc
    if not resolved.is_file():
        raise PrintClientError(f"PNG path is not a regular file: {resolved}")

    try:
        file_size = resolved.stat().st_size
    except OSError as exc:
        raise PrintClientError(f"Could not inspect PNG file: {exc}") from exc
    if file_size > MAX_UPLOAD_BYTES:
        raise PrintClientError("PNG files must be 10 MB or smaller.")

    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise PrintClientError(f"Could not read PNG file: {exc}") from exc

    upload = FileStorage(
        stream=BytesIO(payload),
        filename=resolved.name,
        content_type="image/png",
    )
    try:
        prepared = prepare_png_upload(upload)
    except PNGUploadError as exc:
        raise PrintClientError(str(exc)) from exc

    return LocalPNG(
        path=resolved,
        payload=payload,
        source_size=prepared.source_size,
        target_size=prepared.image.size,
        rotated=prepared.rotated,
    )


def execute_print(
    raw_path: str | Path,
    config: ClientConfig,
    *,
    preview_only: bool = False,
    poster: PNGPoster | None = None,
    output: Callable[[str], None] = print,
) -> dict[str, Any]:
    local_png = validate_local_png(raw_path)
    post_png = poster or _post_png

    rotation_note = "; portrait rotated to landscape" if local_png.rotated else ""
    output(
        f"Local PNG valid: {local_png.path.name} "
        f"({local_png.source_size[0]}x{local_png.source_size[1]} px{rotation_note}; "
        f"target {local_png.target_size[0]}x{local_png.target_size[1]} px)."
    )

    preview = post_png(
        config,
        config.endpoint(config.preview_path),
        filename=local_png.path.name,
        payload=local_png.payload,
    )
    _validate_preview_response(preview)
    output(f"Server preflight passed at {config.base_url}")

    if preview_only:
        output("Preview-only check complete; no label was printed.")
        return preview

    # Deliberately do not retry or switch endpoints after this call begins. A lost
    # response cannot prove whether the physical printer already received the label.
    try:
        result = post_png(
            config,
            config.endpoint(config.print_path),
            filename=local_png.path.name,
            payload=local_png.payload,
        )
    except PrintTransportError as exc:
        raise AmbiguousPrintError(
            "The connection failed after the print request began. The outcome is unknown, "
            "so the client did not retry; check the printer before running the command again."
        ) from exc

    if result.get("status") != "sent":
        raise PrintClientError(
            "The printer service returned a successful HTTP response without status='sent'. "
            "The client did not retry."
        )

    output(f"Print accepted: {local_png.path.name}")
    for warning in _response_warnings(result):
        output(f"Warning: {warning}")
    return result


def _post_png(
    config: ClientConfig,
    endpoint: str,
    *,
    filename: str,
    payload: bytes,
) -> dict[str, Any]:
    body, content_type = _multipart_body(filename, payload)
    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        "User-Agent": "smarthome-printer-client/1",
    }
    if config.bearer_token is not None:
        headers["Authorization"] = f"Bearer {config.bearer_token}"

    request = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        ssl_context = ssl.create_default_context(
            cafile=str(config.ca_file) if config.ca_file else None
        )
    except OSError as exc:
        raise PrintClientError(f"Could not load the configured TLS trust: {exc}") from exc
    opener = build_opener(_NoRedirectHandler(), HTTPSHandler(context=ssl_context))

    try:
        response = opener.open(request, timeout=config.timeout_seconds)
    except HTTPError as exc:
        response_body = _read_response_bytes(exc)
        detail = _response_error_detail(response_body)
        suffix = f": {detail}" if detail else ""
        if exc.code in {401, 403}:
            suffix += (
                " (configure PRINTER_SERVICE_TOKEN_FILE or use the add-on's direct mapped port)"
            )
        elif 300 <= exc.code < 400:
            suffix += (
                " (redirects are disabled for print requests; configure the final service URL)"
            )
        raise PrintClientError(f"Printer service returned HTTP {exc.code}{suffix}") from exc
    except (TimeoutError, URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise PrintTransportError(f"Could not reach printer service: {reason}") from exc

    with response:
        response_body = _read_response_bytes(response)

    try:
        decoded = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrintClientError("Printer service returned a non-JSON response.") from exc
    if not isinstance(decoded, dict):
        raise PrintClientError("Printer service returned a JSON response with the wrong shape.")
    return decoded


def _multipart_body(filename: str, payload: bytes) -> tuple[bytes, str]:
    boundary = f"smarthome-{secrets.token_hex(18)}"
    safe_filename = "".join(
        character if 32 <= ord(character) < 127 and character not in {'"', "\\"} else "_"
        for character in filename
    )
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'
        "Content-Type: image/png\r\n"
        "\r\n"
    ).encode("ascii")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + payload + suffix, f"multipart/form-data; boundary={boundary}"


def _validate_preview_response(payload: Mapping[str, Any]) -> None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        raise PrintClientError("Printer preview response did not include label metrics.")
    if metrics.get("fits_target") is not True:
        raise PrintClientError(
            "Printer preview reported that the PNG does not fit the label target."
        )


def _response_warnings(payload: Mapping[str, Any]) -> list[str]:
    raw_warnings = payload.get("warnings")
    if not isinstance(raw_warnings, list):
        return []
    return [str(item) for item in raw_warnings if str(item).strip()]


def _read_response_bytes(response: Any) -> bytes:
    payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise PrintClientError("Printer service response exceeded 5 MB.")
    return payload


def _response_error_detail(payload: bytes) -> str:
    try:
        decoded = json.loads(payload)
    except UnicodeDecodeError, json.JSONDecodeError:
        return ""
    if not isinstance(decoded, Mapping):
        return ""
    detail = decoded.get("error")
    return str(detail).strip() if detail is not None else ""


def _load_bearer_token(values: Mapping[str, str]) -> tuple[str | None, str | None]:
    inline_token = values.get("PRINTER_SERVICE_TOKEN", "").strip()
    raw_token_file = values.get("PRINTER_SERVICE_TOKEN_FILE", "").strip()
    if inline_token and raw_token_file:
        raise PrintClientError(
            "Set only one of PRINTER_SERVICE_TOKEN or PRINTER_SERVICE_TOKEN_FILE."
        )
    if inline_token:
        _validate_token(inline_token)
        return inline_token, "environment"
    if not raw_token_file:
        return None, None

    token_file = Path(raw_token_file).expanduser().resolve()
    if not token_file.is_file():
        raise PrintClientError(f"PRINTER_SERVICE_TOKEN_FILE is not a file: {token_file}")
    try:
        file_mode = stat.S_IMODE(token_file.stat().st_mode)
    except OSError as exc:
        raise PrintClientError(f"Could not inspect bearer token file: {exc}") from exc
    if file_mode & 0o077:
        raise PrintClientError(
            "PRINTER_SERVICE_TOKEN_FILE must not be accessible by group or other users; "
            f"run: chmod 600 {token_file}"
        )
    try:
        token_payload = token_file.read_bytes()
    except OSError as exc:
        raise PrintClientError(f"Could not read bearer token file: {exc}") from exc
    if len(token_payload) > MAX_TOKEN_BYTES:
        raise PrintClientError("PRINTER_SERVICE_TOKEN_FILE is unexpectedly large.")
    try:
        token = token_payload.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise PrintClientError("PRINTER_SERVICE_TOKEN_FILE must contain UTF-8 text.") from exc
    _validate_token(token)
    return token, "file"


def _validate_token(token: str) -> None:
    if not token:
        raise PrintClientError("The configured printer bearer token is empty.")
    if any(character.isspace() for character in token):
        raise PrintClientError("The configured printer bearer token contains whitespace.")


def _normalize_base_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise PrintClientError("PRINTER_SERVICE_URL must use http or https.")
    if not parsed.hostname:
        raise PrintClientError("PRINTER_SERVICE_URL must include a host.")
    if any(character.isspace() for character in parsed.netloc):
        raise PrintClientError("PRINTER_SERVICE_URL contains whitespace in its host.")
    try:
        parsed.port
    except ValueError as exc:
        raise PrintClientError("PRINTER_SERVICE_URL contains an invalid port.") from exc
    if parsed.username is not None or parsed.password is not None:
        raise PrintClientError(
            "Do not put credentials in PRINTER_SERVICE_URL; use PRINTER_SERVICE_TOKEN_FILE."
        )
    if parsed.query or parsed.fragment:
        raise PrintClientError("PRINTER_SERVICE_URL must not include a query string or fragment.")
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _base_url_from_parts(scheme: str, host: str, port: int, path: str) -> str:
    if scheme not in {"http", "https"}:
        raise PrintClientError("PRINTER_SERVICE_SCHEME must be http or https.")
    if not host or any(character.isspace() for character in host):
        raise PrintClientError("PRINTER_SERVICE_HOST must be a hostname or address.")
    host_for_url = host
    if ":" in host and not host.startswith("["):
        host_for_url = f"[{host}]"
    normalized_path = path or "/"
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return _normalize_base_url(f"{scheme}://{host_for_url}:{port}{normalized_path}")


def _normalize_route(raw_route: str, *, name: str) -> str:
    route = raw_route.strip().lstrip("/")
    if not route or urlsplit(route).scheme or ".." in route.split("/"):
        raise PrintClientError(f"{name} must be a relative service path.")
    if "?" in route or "#" in route:
        raise PrintClientError(f"{name} must not include a query string or fragment.")
    return route


def _parse_port(raw_port: str) -> int:
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise PrintClientError("PRINTER_SERVICE_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise PrintClientError("PRINTER_SERVICE_PORT must be between 1 and 65535.")
    return port


def _parse_timeout(raw_timeout: str) -> float:
    if not raw_timeout.strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise PrintClientError("PRINTER_SERVICE_TIMEOUT must be a number of seconds.") from exc
    if not 1 <= timeout <= 300:
        raise PrintClientError("PRINTER_SERVICE_TIMEOUT must be between 1 and 300 seconds.")
    return timeout


def describe_config(config: ClientConfig) -> list[str]:
    auth = "none" if config.token_source is None else f"bearer token from {config.token_source}"
    ca_source = "system trust store" if config.ca_file is None else str(config.ca_file)
    return [
        f"Service URL: {config.base_url}",
        f"Preview endpoint: {config.endpoint(config.preview_path)}",
        f"Print endpoint: {config.endpoint(config.print_path)}",
        f"Authentication: {auth}",
        f"TLS trust: {ca_source}",
        f"Request timeout: {config.timeout_seconds:g} seconds",
        "Automatic print retries: disabled",
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printer-png",
        description="Validate, preflight, and print one PNG through the printer add-on.",
    )
    parser.add_argument("file", nargs="?", help="PNG file to validate and print")
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="run local and server validation without printing",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="show resolved non-secret endpoint and authentication settings",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = resolve_config()
        if args.show_config:
            for line in describe_config(config):
                print(line)
            return 0
        if not args.file:
            parser.error("a PNG file is required unless --show-config is used")
        execute_print(args.file, config, preview_only=args.preview_only)
    except PrintClientError as exc:
        sys.stdout.flush()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
