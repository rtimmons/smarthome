from __future__ import annotations

import io
import sys
import types
from typing import Optional

from PIL import Image


def _install_fake_cairosvg() -> None:
    if "cairosvg" in sys.modules:
        return

    fake_cairosvg = types.ModuleType("cairosvg")

    def svg2png(
        *,
        url: Optional[str] = None,
        file_obj: Optional[io.BytesIO] = None,
        write_to: Optional[io.BufferedIOBase] = None,
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
        **_kwargs,
    ) -> Optional[bytes]:
        size = int(output_width or output_height or 120)
        placeholder = Image.new("LA", (size, size), (0, 0))
        buffer = io.BytesIO()
        placeholder.save(buffer, format="PNG")
        payload = buffer.getvalue()

        if write_to is not None:
            write_to.write(payload)
            return None
        if file_obj is not None:
            file_obj.write(payload)
            file_obj.seek(0)
            return None
        return payload

    fake_cairosvg.svg2png = svg2png  # type: ignore[attr-defined]
    sys.modules["cairosvg"] = fake_cairosvg


_install_fake_cairosvg()


def pytest_addoption(parser):
    """Add custom pytest option for regenerating baselines."""
    parser.addoption(
        "--regenerate-baselines",
        action="store_true",
        default=False,
        help="Regenerate all baseline images for visual regression tests",
    )
