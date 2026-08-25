from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from .label_specs import BrotherLabelSpec
from .label_templates.bluey_label import LABEL_SPEC as BLUEY_LABEL_SPEC

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PIXELS = 25_000_000
PNG_LABEL_SPEC = BrotherLabelSpec(
    code=BLUEY_LABEL_SPEC.code,
    printable_px=BLUEY_LABEL_SPEC.printable_px,
    total_px=BLUEY_LABEL_SPEC.total_px,
    tape_size_mm=BLUEY_LABEL_SPEC.tape_size_mm,
)


class PNGUploadError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedPNG:
    filename: str
    source_size: tuple[int, int]
    image: Image.Image
    rotated: bool


def prepare_png_upload(uploaded: FileStorage | None) -> PreparedPNG:
    if uploaded is None or not uploaded.filename:
        raise PNGUploadError("Choose a PNG file to continue.")

    payload = uploaded.stream.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise PNGUploadError("PNG files must be 10 MB or smaller.")
    if not payload:
        raise PNGUploadError("The uploaded PNG is empty.")

    try:
        with Image.open(BytesIO(payload)) as source:
            if source.format != "PNG":
                raise PNGUploadError("The uploaded file must be a PNG image.")
            width, height = source.size
            if width < 1 or height < 1:
                raise PNGUploadError("The uploaded PNG has invalid dimensions.")
            if width * height > MAX_UPLOAD_PIXELS:
                raise PNGUploadError("PNG images may contain at most 25 million pixels.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except PNGUploadError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise PNGUploadError("The uploaded file is not a readable PNG image.") from exc

    flattened = Image.new("RGB", image.size, "white")
    flattened.paste(image, mask=image.getchannel("A"))
    rotated = flattened.height > flattened.width
    if rotated:
        flattened = flattened.transpose(Image.Transpose.ROTATE_90)

    target_width, target_height = PNG_LABEL_SPEC.printable_px
    fitted = ImageOps.contain(
        flattened,
        (target_width, target_height),
        method=Image.Resampling.LANCZOS,
    )
    prepared = Image.new("RGB", (target_width, target_height), "white")
    offset = (
        (target_width - fitted.width) // 2,
        (target_height - fitted.height) // 2,
    )
    prepared.paste(fitted, offset)

    return PreparedPNG(
        filename=uploaded.filename,
        source_size=(width, height),
        image=prepared,
        rotated=rotated,
    )
