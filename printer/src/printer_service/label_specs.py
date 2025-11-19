from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

QL810W_DPI = 300


@dataclass(frozen=True)
class BrotherLabelSpec:
    """Metadata describing a Brother die-cut or continuous label."""

    code: str
    printable_px: Tuple[int, int]
    total_px: Optional[Tuple[int, int]] = None
    tape_size_mm: Optional[Tuple[int, int]] = None

    @property
    def width_px(self) -> int:
        return self.printable_px[0]

    @property
    def height_px(self) -> int:
        return self.printable_px[1]

    @property
    def width_in(self) -> float:
        return self.width_px / QL810W_DPI

    @property
    def height_in(self) -> float:
        return self.height_px / QL810W_DPI

    @property
    def tape_width_in(self) -> Optional[float]:
        if not self.tape_size_mm or not self.tape_size_mm[0]:
            return None
        return millimetres_to_inches(self.tape_size_mm[0])

    @property
    def tape_height_in(self) -> Optional[float]:
        if not self.tape_size_mm or not self.tape_size_mm[1]:
            return None
        return millimetres_to_inches(self.tape_size_mm[1])


DEFAULT_LABEL_CODE = "29x90"
DEFAULT_SPEC = BrotherLabelSpec(
    code=DEFAULT_LABEL_CODE,
    printable_px=(306, 991),
    total_px=(342, 1061),
    tape_size_mm=(29, 90),
)


def millimetres_to_inches(value_mm: float) -> float:
    return value_mm / 25.4


@lru_cache(maxsize=32)
def resolve_brother_label_spec(label_code: Optional[str]) -> BrotherLabelSpec:
    """Return printable dimensions for the requested Brother label code.

    Falls back to a sensible default (DK-1201 / 29x90) if the code is unknown or
    if we cannot import the driver metadata within the current environment.
    """
    normalized = (label_code or DEFAULT_LABEL_CODE).strip().lower()
    try:
        from brother_ql.devicedependent import label_type_specs
    except Exception:
        return DEFAULT_SPEC

    spec = label_type_specs.get(normalized)
    if spec is None:
        return DEFAULT_SPEC

    printable = spec.get("dots_printable") or spec.get("dots_total")
    if not printable or not all(printable):
        return DEFAULT_SPEC

    total = spec.get("dots_total")
    total_px: Optional[Tuple[int, int]]
    if total and all(total):
        total_px = (int(total[0]), int(total[1]))
    else:
        total_px = None

    tape = spec.get("tape_size")
    tape_size_mm: Optional[Tuple[int, int]]
    if tape and all(tape):
        tape_size_mm = (int(tape[0]), int(tape[1]))
    else:
        tape_size_mm = None

    printable_px = (int(printable[0]), int(printable[1]))

    return BrotherLabelSpec(
        code=normalized,
        printable_px=printable_px,
        total_px=total_px,
        tape_size_mm=tape_size_mm,
    )
