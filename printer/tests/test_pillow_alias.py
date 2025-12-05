from PIL import Image


def test_antialias_alias_present():
    # Pillow 10 removed Image.ANTIALIAS; our code restores it for brother_ql.
    assert hasattr(Image, "ANTIALIAS")
    assert Image.ANTIALIAS == Image.Resampling.LANCZOS
