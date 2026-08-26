from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, UnidentifiedImageError

from .label import save_label_image
from .label_specs import BrotherLabelSpec

DEFAULT_PRINTED_LABELS_DIR = Path("/data/printed-labels")
PRINTED_LABELS_DIR_ENV = "PRINTED_LABELS_DIR"
_LABEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,199}$")
_UNSAFE_PREFIX_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


class PrintedLabelNotFound(LookupError):
    pass


@dataclass(frozen=True)
class PrintedLabel:
    id: str
    name: str
    created_at: str
    last_printed_at: str | None
    print_count: int
    width_px: int
    height_px: int
    size_bytes: int
    path: Path

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("path", None)
        return payload


class PrintedLabelStore:
    """Filesystem archive for PNGs sent through the upload/CLI print flow."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.RLock()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PrintedLabelStore:
        values = os.environ if env is None else env
        configured = values.get(PRINTED_LABELS_DIR_ENV, "").strip()
        return cls(Path(configured) if configured else DEFAULT_PRINTED_LABELS_DIR)

    def archive(
        self,
        image: Image.Image,
        source_name: str,
        *,
        target_spec: BrotherLabelSpec | None = None,
    ) -> PrintedLabel:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            now = _utc_now()
            display_name = _display_name(source_name)
            prefix = _archive_prefix(display_name)
            unique_prefix = f"{now.strftime('%Y%m%dt%H%M%S%fz')}-{prefix}-{uuid.uuid4().hex[:8]}"
            path = save_label_image(
                image,
                self.directory,
                prefix=unique_prefix,
                target_spec=target_spec,
            )
            label = PrintedLabel(
                id=path.stem,
                name=display_name,
                created_at=now.isoformat(),
                last_printed_at=None,
                print_count=0,
                width_px=image.width,
                height_px=image.height,
                size_bytes=path.stat().st_size,
                path=path,
            )
            try:
                self._write_metadata(label)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return label

    def list_labels(
        self,
        *,
        sort_by: str = "created",
        direction: str = "desc",
        limit: int = 500,
    ) -> list[PrintedLabel]:
        with self._lock:
            if not self.directory.exists():
                return []
            labels: list[PrintedLabel] = []
            for path in self.directory.glob("*.png"):
                if not path.is_file() or not _is_valid_label_id(path.stem):
                    continue
                try:
                    labels.append(self._read_label(path.stem))
                except PrintedLabelNotFound, OSError:
                    continue

            sorters = {
                "name": lambda label: label.name.casefold(),
                "created": lambda label: label.created_at,
                "last_printed": lambda label: label.last_printed_at or "",
                "prints": lambda label: label.print_count,
            }
            sorter = sorters.get(sort_by, sorters["created"])
            labels.sort(key=sorter, reverse=direction != "asc")
            return labels[: max(0, limit)]

    def get(self, label_id: str) -> PrintedLabel:
        with self._lock:
            return self._read_label(label_id)

    def load_image(self, label_id: str) -> tuple[PrintedLabel, Image.Image]:
        with self._lock:
            label = self._read_label(label_id)
            try:
                with Image.open(label.path) as source:
                    if source.format != "PNG":
                        raise OSError("Archived label is not a PNG image.")
                    source.load()
                    image = source.copy()
                    image.info = dict(source.info)
            except (UnidentifiedImageError, OSError, SyntaxError) as exc:
                raise OSError("Archived label PNG is unreadable.") from exc
            return label, image

    def record_print(self, label_id: str) -> PrintedLabel:
        with self._lock:
            label = self._read_label(label_id)
            updated = replace(
                label,
                last_printed_at=_utc_now().isoformat(),
                print_count=label.print_count + 1,
                size_bytes=label.path.stat().st_size,
            )
            self._write_metadata(updated)
            return updated

    def delete(self, label_id: str) -> bool:
        with self._lock:
            _validate_label_id(label_id)
            png_path = self._png_path(label_id)
            metadata_path = self._metadata_path(label_id)
            existed = png_path.is_file() or metadata_path.is_file()
            png_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            return existed

    def _read_label(self, label_id: str) -> PrintedLabel:
        _validate_label_id(label_id)
        path = self._png_path(label_id)
        if not path.is_file():
            raise PrintedLabelNotFound("Printed label not found.")

        metadata = self._read_metadata(label_id)
        stat_result = path.stat()
        fallback_created_at = datetime.fromtimestamp(
            stat_result.st_mtime, tz=timezone.utc
        ).isoformat()
        width_px = _metadata_int(metadata, "width_px")
        height_px = _metadata_int(metadata, "height_px")
        if width_px < 1 or height_px < 1:
            try:
                with Image.open(path) as source:
                    width_px, height_px = source.size
            except UnidentifiedImageError, OSError, SyntaxError:
                width_px, height_px = 0, 0

        return PrintedLabel(
            id=label_id,
            name=_display_name(str(metadata.get("name") or f"{label_id}.png")),
            created_at=str(metadata.get("created_at") or fallback_created_at),
            last_printed_at=_optional_text(metadata.get("last_printed_at")),
            print_count=max(0, _metadata_int(metadata, "print_count")),
            width_px=max(0, width_px),
            height_px=max(0, height_px),
            size_bytes=stat_result.st_size,
            path=path,
        )

    def _read_metadata(self, label_id: str) -> dict[str, Any]:
        path = self._metadata_path(label_id)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError, UnicodeDecodeError, json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_metadata(self, label: PrintedLabel) -> None:
        payload = label.to_dict()
        payload["version"] = 1
        path = self._metadata_path(label.id)
        temporary = path.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _png_path(self, label_id: str) -> Path:
        return self.directory / f"{label_id}.png"

    def _metadata_path(self, label_id: str) -> Path:
        return self.directory / f"{label_id}.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _display_name(raw_name: str) -> str:
    normalized = str(raw_name or "").replace("\\", "/").rsplit("/", 1)[-1]
    normalized = "".join(character for character in normalized if character.isprintable()).strip()
    if not normalized:
        return "label.png"
    if not normalized.lower().endswith(".png"):
        normalized = f"{normalized}.png"
    return normalized[:180]


def _archive_prefix(display_name: str) -> str:
    stem = Path(display_name).stem
    normalized = _UNSAFE_PREFIX_PATTERN.sub("-", stem).strip("-._").lower()
    return (normalized or "label")[:60]


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _metadata_int(metadata: Mapping[str, object], key: str) -> int:
    raw = metadata.get(key)
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if not isinstance(raw, str):
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _is_valid_label_id(label_id: str) -> bool:
    return bool(_LABEL_ID_PATTERN.fullmatch(str(label_id or "")))


def _validate_label_id(label_id: str) -> None:
    if not _is_valid_label_id(label_id):
        raise PrintedLabelNotFound("Printed label not found.")
