import warnings

from PIL import Image

from printer_service import label


def test_antialias_alias_present():
    # Pillow 10 removed Image.ANTIALIAS; our code restores it for brother_ql.
    label._ensure_antialias_alias()
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert hasattr(Image, "ANTIALIAS")
        assert Image.ANTIALIAS == Image.Resampling.LANCZOS
