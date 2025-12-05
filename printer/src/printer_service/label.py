from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Type, cast

from PIL import Image, PngImagePlugin

# Pillow 10 removed Image.ANTIALIAS; keep an alias for older deps (brother_ql).
if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]

from printer_service.label_specs import (
    QL810W_DPI,
    BrotherLabelSpec,
    DEFAULT_LABEL_CODE,
    resolve_brother_label_spec,
)

SUPPORTED_BACKENDS = {
    "brother-network",
    "escpos-usb",
    "escpos-bluetooth",
    "file",
}

DIMENSION_TOLERANCE_IN = 0.02
LABEL_SPEC_CODE_KEY = "label_spec_code"
LABEL_SPEC_WIDTH_KEY = "label_spec_width_px"
LABEL_SPEC_HEIGHT_KEY = "label_spec_height_px"


def _warning_list_from_info(raw: object) -> List[str]:
    warnings: List[str] = []
    if raw is None:
        return warnings
    if isinstance(raw, str):
        parts = raw.split("\n")
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray)):
        parts = [str(item) for item in raw]
    else:
        parts = [str(raw)]
    for entry in parts:
        text = str(entry).strip()
        if text:
            warnings.append(text)
    return warnings


def _warnings_from_image(image: Image.Image) -> List[str]:
    if not hasattr(image, "info"):
        return []
    return _warning_list_from_info(image.info.get("label_warnings"))


def _pnginfo_from_metadata(
    warnings: Sequence[str], metadata: Optional[Dict[str, str]] = None
) -> Optional[PngImagePlugin.PngInfo]:
    if not warnings and not metadata:
        return None
    pnginfo = PngImagePlugin.PngInfo()
    if warnings:
        pnginfo.add_text("label_warnings", "\n".join(warnings))
    if metadata:
        for key, value in metadata.items():
            pnginfo.add_text(key, value)
    return pnginfo


@dataclass
class LabelMetrics:
    width_px: int
    height_px: int
    width_in: float
    height_in: float
    dpi: int = QL810W_DPI
    fits_target: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "width_in": round(self.width_in, 3),
            "height_in": round(self.height_in, 3),
            "dpi": self.dpi,
            "fits_target": self.fits_target,
            "warnings": list(self.warnings),
        }


def dispatch_image(
    image: Image.Image,
    config: Optional["PrinterConfig"] = None,
    *,
    target_spec: Optional[BrotherLabelSpec] = None,
) -> Optional[Path]:
    """Send a PIL image through the configured backend. Returns output path for file backend."""
    cfg = config or PrinterConfig.from_env()
    backend = cfg.backend
    prepared = _prepare_image_for_dispatch(image, backend, target_spec)
    if backend == "brother-network":
        label_override = target_spec.code if target_spec else None
        _send_to_brother(prepared, cfg, label_override=label_override)
        return None
    elif backend == "escpos-usb":
        _send_to_escpos_usb(prepared, cfg)
        return None
    elif backend == "escpos-bluetooth":
        _send_to_escpos_bluetooth(prepared, cfg)
        return None
    elif backend == "file":
        return _write_to_file(prepared, cfg, target_spec=target_spec)
    raise ValueError(f"Unsupported backend '{backend}'")


def analyze_label_image(
    image: Image.Image,
    config: Optional["PrinterConfig"] = None,
    *,
    target_spec: Optional[BrotherLabelSpec] = None,
) -> LabelMetrics:
    """Return sizing diagnostics for a rendered label image."""
    cfg = config or PrinterConfig.from_env()
    spec: BrotherLabelSpec = target_spec or resolve_brother_label_spec(cfg.brother_label)
    width_px, height_px = image.size
    width_in = width_px / QL810W_DPI
    height_in = height_px / QL810W_DPI
    warnings: List[str] = _warnings_from_image(image)
    fits_target = True

    if cfg.backend == "brother-network":
        target_sorted = sorted(spec.printable_px)
        actual_sorted = sorted((width_px, height_px))
        tolerance_px = int(round(DIMENSION_TOLERANCE_IN * QL810W_DPI))
        short_diff = abs(actual_sorted[0] - target_sorted[0])
        long_diff = abs(actual_sorted[1] - target_sorted[1])
        if short_diff > tolerance_px or long_diff > tolerance_px:
            fits_target = False
            warnings.append(
                (
                    f"Generated image is {width_px}x{height_px}px but label '{spec.code}' "
                    f"expects approximately {target_sorted[0]}x{target_sorted[1]}px of printable area."
                )
            )

    return LabelMetrics(
        width_px=width_px,
        height_px=height_px,
        width_in=width_in,
        height_in=height_in,
        dpi=QL810W_DPI,
        fits_target=fits_target,
        warnings=warnings,
    )


@dataclass
class PrinterConfig:
    backend: str
    brother_uri: Optional[str] = None
    brother_model: str = "QL-810W"
    brother_label: str = DEFAULT_LABEL_CODE
    rotate: str = "auto"
    high_quality: bool = True
    cut: bool = True
    usb_vendor_id: Optional[int] = None
    usb_product_id: Optional[int] = None
    bluetooth_mac: Optional[str] = None
    output_path: Path = Path("label-output.png")

    @classmethod
    def from_env(cls) -> "PrinterConfig":
        backend = os.getenv("PRINTER_BACKEND", "file").strip().lower()
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"Set PRINTER_BACKEND to one of {sorted(SUPPORTED_BACKENDS)}")
        brother_uri = _normalize_brother_uri(
            os.getenv("BROTHER_PRINTER_URI", "tcp://192.168.1.192:9100")
        )
        model = os.getenv("BROTHER_MODEL", "QL-810W")
        label = os.getenv("BROTHER_LABEL", DEFAULT_LABEL_CODE)
        rotate = os.getenv("BROTHER_ROTATE", "auto")
        high_quality = _parse_bool(os.getenv("BROTHER_HQ", "true"))
        cut = _parse_bool(os.getenv("BROTHER_CUT", "true"))
        usb_vendor_id = _parse_int(os.getenv("ESC_POS_VENDOR_ID"), default=0x0FE6)
        usb_product_id = _parse_int(os.getenv("ESC_POS_PRODUCT_ID"), default=0x811E)
        bluetooth_mac = os.getenv("ESC_POS_BLUETOOTH_MAC")
        output_path = Path(os.getenv("PRINTER_OUTPUT_PATH", "label-output.png"))
        return cls(
            backend=backend,
            brother_uri=brother_uri,
            brother_model=model,
            brother_label=label,
            rotate=rotate,
            high_quality=high_quality,
            cut=cut,
            usb_vendor_id=usb_vendor_id,
            usb_product_id=usb_product_id,
            bluetooth_mac=bluetooth_mac,
            output_path=output_path,
        )


def _ensure_monochrome(image: Image.Image) -> Image.Image:
    warnings = _warnings_from_image(image)
    converted = image.convert("1")
    if warnings:
        converted.info["label_warnings"] = list(warnings)
    return converted


def _send_to_brother(
    image: Image.Image,
    cfg: PrinterConfig,
    *,
    label_override: Optional[str] = None,
) -> None:
    from brother_ql.backends.helpers import send
    from brother_ql.conversion import convert
    from brother_ql.raster import BrotherQLRaster

    if not cfg.brother_uri:
        raise ValueError("BROTHER_PRINTER_URI must be configured for brother-network backend.")

    uri = _normalize_brother_uri(cfg.brother_uri)
    if not uri:
        raise ValueError("BROTHER_PRINTER_URI must be configured for brother-network backend.")

    label_code = (label_override or cfg.brother_label or DEFAULT_LABEL_CODE).strip().lower()
    qlr = BrotherQLRaster(cfg.brother_model)
    qlr.exception_on_warning = True
    mono = _ensure_monochrome(image)
    instructions = convert(
        qlr,
        [mono],
        label_code,
        rotate=cfg.rotate,
        hq=cfg.high_quality,
        cut=cfg.cut,
    )
    send(instructions, uri)


def _send_to_escpos_usb(image: Image.Image, cfg: PrinterConfig) -> None:
    from escpos.printer import Usb

    if cfg.usb_vendor_id is None or cfg.usb_product_id is None:
        raise ValueError(
            "ESC_POS_VENDOR_ID and ESC_POS_PRODUCT_ID must be set for escpos-usb backend."
        )
    printer = Usb(cfg.usb_vendor_id, cfg.usb_product_id)
    printer.image(_ensure_monochrome(image))
    printer.cut()


def _send_to_escpos_bluetooth(image: Image.Image, cfg: PrinterConfig) -> None:
    if not cfg.bluetooth_mac:
        raise ValueError("ESC_POS_BLUETOOTH_MAC must be set for escpos-bluetooth backend.")
    printer_class = _resolve_escpos_bluetooth()
    printer = printer_class(cfg.bluetooth_mac)
    printer.image(_ensure_monochrome(image))
    printer.cut()


def _resolve_escpos_bluetooth() -> Type[Any]:
    """Import the ESC/POS Bluetooth printer class lazily to aid static analysis."""
    last_error: ModuleNotFoundError | None = None
    for module_name in ("escpos.printer.bluetooth", "escpos.printer"):
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            last_error = exc
            continue
        bluetooth = getattr(module, "Bluetooth", None)
        if bluetooth is not None:
            return cast(Type[Any], bluetooth)
    if last_error is not None:
        raise RuntimeError("ESC/POS bluetooth support is not installed.") from last_error
    raise RuntimeError("ESC/POS bluetooth implementation not found.")


def _write_to_file(
    image: Image.Image,
    cfg: PrinterConfig,
    *,
    target_spec: Optional[BrotherLabelSpec] = None,
) -> Path:
    path = cfg.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    mono = _ensure_monochrome(image)
    metadata = _metadata_from_spec(target_spec)
    if metadata:
        info = cast(MutableMapping[str | tuple[int, int], Any], mono.info)
        for key, value in metadata.items():
            info[key] = value
    pnginfo = _pnginfo_from_metadata(_warnings_from_image(mono), metadata)
    if pnginfo:
        mono.save(path, format="PNG", pnginfo=pnginfo)
    else:
        mono.save(path, format="PNG")
    return path


def save_label_image(
    image: Image.Image,
    directory: Path,
    *,
    prefix: str = "label",
    target_spec: Optional[BrotherLabelSpec] = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    path = directory / f"{prefix}-{timestamp}.png"
    mono = _ensure_monochrome(image)
    metadata = _metadata_from_spec(target_spec)
    if metadata:
        info = cast(MutableMapping[str | tuple[int, int], Any], mono.info)
        for key, value in metadata.items():
            info[key] = value
    pnginfo = _pnginfo_from_metadata(_warnings_from_image(mono), metadata)
    if pnginfo:
        mono.save(path, format="PNG", pnginfo=pnginfo)
    else:
        mono.save(path, format="PNG")
    return path


def label_spec_from_metadata(image: Image.Image) -> Optional[BrotherLabelSpec]:
    if not hasattr(image, "info"):
        return None
    code = image.info.get(LABEL_SPEC_CODE_KEY)
    width_raw = image.info.get(LABEL_SPEC_WIDTH_KEY)
    height_raw = image.info.get(LABEL_SPEC_HEIGHT_KEY)
    if not width_raw or not height_raw:
        return None
    try:
        width_px = int(width_raw)
        height_px = int(height_raw)
    except (TypeError, ValueError):
        return None
    label_code = str(code or f"{width_px}x{height_px}")
    return BrotherLabelSpec(code=label_code, printable_px=(width_px, height_px))


def _should_rotate_for_print(image: Image.Image, spec: Optional[BrotherLabelSpec]) -> bool:
    if spec is None:
        return False
    width_px, height_px = image.size
    if width_px == height_px:
        return False
    target_width, target_height = spec.printable_px
    if target_width == target_height:
        return False
    image_is_portrait = height_px > width_px
    spec_is_portrait = target_height > target_width
    return image_is_portrait != spec_is_portrait


def _prepare_image_for_dispatch(
    image: Image.Image, backend: str, spec: Optional[BrotherLabelSpec]
) -> Image.Image:
    if backend == "file":
        return image
    if not _should_rotate_for_print(image, spec):
        return image
    rotated = image.transpose(Image.Transpose.ROTATE_90)
    if hasattr(image, "info"):
        rotated.info = dict(image.info)
    return rotated


def _metadata_from_spec(
    spec: Optional[BrotherLabelSpec],
) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if spec is not None:
        metadata.update(
            {
                LABEL_SPEC_CODE_KEY: spec.code,
                LABEL_SPEC_WIDTH_KEY: str(spec.printable_px[0]),
                LABEL_SPEC_HEIGHT_KEY: str(spec.printable_px[1]),
            }
        )
    return metadata


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(raw: Optional[str], *, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    if raw.lower().startswith("0x"):
        return int(raw, 16)
    return int(raw)


def _normalize_brother_uri(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("network://"):
        normalized = f"tcp://{normalized[len('network://') :]}"
    return normalized
