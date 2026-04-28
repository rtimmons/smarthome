"""Visual regression tests for label templates.

These tests capture the current rendering behavior of each template
to ensure refactoring doesn't inadvertently change the visual output.

## How It Works

1. Each test renders a label with specific parameters
2. The rendered image is compared pixel-by-pixel against a baseline
3. Baselines are stored in tests/baselines/ and checked into git
4. Tests fail if the rendering differs from the baseline

## Running Tests

Run all tests (recommended):
    just test

Run only visual regression tests:
    .venv/bin/pytest tests/test_visual_regression.py -v

Regenerate all baselines (after intentional visual changes):
    .venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v

Regenerate a single baseline:
    .venv/bin/pytest tests/test_visual_regression.py::test_name --regenerate-baselines -v

## When Tests Fail

If a test fails, a DIFF_*.png file is created showing the new rendering.
Compare the baseline and diff files to understand what changed:
    - Intentional change: Regenerate baselines and commit
    - Unintentional change: Fix the code to match the baseline

## Adding New Tests

1. Add test function to this file
2. Run with --regenerate-baselines to create baseline
3. Commit both the test and the baseline image

See docs/testing.md for complete documentation.
"""

from __future__ import annotations

import hashlib
import html
import importlib
from datetime import datetime
from datetime import date
from pathlib import Path
from typing import Tuple

import pytest
from PIL import Image

from printer_service.label_templates import (
    best_by,
    bluey_label,
)
from printer_service.label_templates.base import TemplateFormData

# Directory for baseline images
BASELINE_DIR = Path(__file__).parent / "baselines"
BASELINE_DIR.mkdir(exist_ok=True)
VISUAL_REPORT_PATH = BASELINE_DIR / "visual-diff-report.html"


def _diff_path_for(baseline_name: str) -> Path:
    """Return the diff image path for a baseline."""
    return BASELINE_DIR / f"DIFF_{baseline_name}"


def _enhanced_diff_path_for(baseline_name: str) -> Path:
    """Return the enhanced diff image path for a baseline."""
    return BASELINE_DIR / f"ENHANCED_{Path(baseline_name).stem}.png"


def _write_visual_report() -> None:
    """Write a browser-friendly side-by-side report for current diffs."""
    diff_paths = sorted(BASELINE_DIR.glob("DIFF_*.png"))
    if not diff_paths:
        VISUAL_REPORT_PATH.unlink(missing_ok=True)
        return

    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    cases: list[str] = []

    for diff_path in diff_paths:
        baseline_name = diff_path.name.removeprefix("DIFF_")
        baseline_path = BASELINE_DIR / baseline_name
        if baseline_path.exists():
            expected_markup = (
                f'<img src="{html.escape(baseline_path.name, quote=True)}" '
                f'alt="Expected {html.escape(baseline_name)}">'
            )
        else:
            expected_markup = '<div class="missing">Expected baseline is missing.</div>'

        cases.append(
            f"""
            <section class="case">
              <div class="case-header">
                <h2>{html.escape(baseline_name)}</h2>
                <p>{html.escape(str(baseline_path))}</p>
              </div>
              <div class="comparison">
                <article class="panel">
                  <h3>Expected Baseline</h3>
                  <p class="panel-meta">{html.escape(baseline_path.name)}</p>
                  {expected_markup}
                </article>
                <article class="panel">
                  <h3>Actual Render</h3>
                  <p class="panel-meta">{html.escape(diff_path.name)}</p>
                  <img src="{html.escape(diff_path.name, quote=True)}" alt="Actual {html.escape(baseline_name)}">
                </article>
              </div>
            </section>
            """
        )

    report_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Printer Visual Regression Report</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4f1eb;
        --surface: #fffdf9;
        --surface-strong: #ffffff;
        --border: #d9d1c7;
        --text: #1f1a17;
        --muted: #6e6258;
        --expected: #2f6b3b;
        --actual: #a12a2a;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        background: linear-gradient(180deg, #fbf8f2 0%, var(--bg) 100%);
        color: var(--text);
      }}
      header {{
        position: sticky;
        top: 0;
        z-index: 1;
        padding: 1rem 1.5rem;
        border-bottom: 1px solid var(--border);
        background: rgba(255, 253, 249, 0.94);
        backdrop-filter: blur(8px);
      }}
      h1, h2, h3, p {{
        margin: 0;
      }}
      header p {{
        margin-top: 0.35rem;
        color: var(--muted);
      }}
      main {{
        padding: 1.25rem;
        display: grid;
        gap: 1rem;
      }}
      .case {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 18px;
        box-shadow: 0 12px 32px rgba(43, 31, 17, 0.08);
        overflow: hidden;
      }}
      .case-header {{
        padding: 1rem 1.25rem;
        border-bottom: 1px solid var(--border);
        background: linear-gradient(135deg, #fffdf9 0%, #f6efe5 100%);
      }}
      .case-header p {{
        margin-top: 0.35rem;
        color: var(--muted);
        font-size: 0.95rem;
        word-break: break-all;
      }}
      .comparison {{
        display: grid;
        grid-template-columns: repeat(2, minmax(280px, 1fr));
        gap: 1rem;
        padding: 1rem;
      }}
      .panel {{
        background: var(--surface-strong);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.9rem;
      }}
      .panel h3 {{
        margin-bottom: 0.75rem;
        font-family: "Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 0.95rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
      .panel-meta {{
        margin-bottom: 0.75rem;
        color: var(--muted);
        font-family: "Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 0.85rem;
        word-break: break-all;
      }}
      .panel:first-child h3 {{
        color: var(--expected);
      }}
      .panel:last-child h3 {{
        color: var(--actual);
      }}
      img {{
        display: block;
        width: 100%;
        height: auto;
        background: white;
        border: 1px solid #ece4d9;
        border-radius: 10px;
      }}
      .missing {{
        padding: 1rem;
        border: 1px dashed var(--border);
        border-radius: 10px;
        color: var(--muted);
        background: #faf6ef;
      }}
      @media (max-width: 900px) {{
        .comparison {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <header>
      <h1>Printer Visual Regression Report</h1>
      <p>{len(diff_paths)} failing baseline(s) • generated {html.escape(generated_at)}</p>
    </header>
    <main>{"".join(cases)}</main>
  </body>
</html>
"""
    VISUAL_REPORT_PATH.write_text(report_html, encoding="utf-8")


def _remove_stale_visual_artifacts(baseline_name: str) -> None:
    """Remove stale diff artifacts and refresh the report if needed."""
    removed_artifact = False
    for artifact_path in (_diff_path_for(baseline_name), _enhanced_diff_path_for(baseline_name)):
        if artifact_path.exists():
            artifact_path.unlink()
            removed_artifact = True

    if removed_artifact:
        _write_visual_report()


def _image_hash(image: Image.Image) -> str:
    """Compute SHA256 hash of image pixels for quick comparison.

    This provides a fast path for exact match detection before doing
    expensive pixel-by-pixel comparison.

    Args:
        image: PIL Image to hash

    Returns:
        Hex string of SHA256 hash of raw pixel data
    """
    return hashlib.sha256(image.tobytes()).hexdigest()


def _images_match(img1: Image.Image, img2: Image.Image, tolerance: float = 0.0) -> bool:
    """Compare two images pixel-by-pixel.

    First checks if images have the same dimensions and mode. Then uses SHA256
    hash for fast exact-match detection. If tolerance is non-zero, performs
    pixel-by-pixel comparison and calculates difference ratio.

    Args:
        img1: First image
        img2: Second image
        tolerance: Allowed difference ratio (0.0 = exact match, 1.0 = 100% different).
                  Use small tolerance (e.g., 0.001) for QR codes which can vary slightly.

    Returns:
        True if images match within tolerance, False otherwise
    """
    if img1.size != img2.size:
        return False

    if img1.mode != img2.mode:
        return False

    # Fast path: exact match via hash
    if tolerance == 0.0 and _image_hash(img1) == _image_hash(img2):
        return True

    # Pixel-by-pixel comparison
    pixels1 = img1.load()
    pixels2 = img2.load()
    if pixels1 is None or pixels2 is None:
        return False

    width, height = img1.size
    total_pixels = width * height
    different_pixels = 0

    for y in range(height):
        for x in range(width):
            if pixels1[x, y] != pixels2[x, y]:
                different_pixels += 1

    difference_ratio = different_pixels / total_pixels if total_pixels > 0 else 0.0
    return difference_ratio <= tolerance


def assert_visual_match(
    rendered: Image.Image,
    baseline_name: str,
    tolerance: float = 0.0,
    regenerate: bool = False,
) -> None:
    """Assert that rendered image matches the baseline.

    This is the main entry point for visual regression testing. It compares
    the rendered image against a stored baseline and fails if they differ.

    Workflow:
    1. If baseline doesn't exist or regenerate=True: Save rendered as baseline
    2. Otherwise: Load baseline and compare pixel-by-pixel
    3. If mismatch: Save DIFF_*.png and raise AssertionError with helpful message

    Args:
        rendered: The image rendered by the template
        baseline_name: Name of the baseline file (e.g., "best_by_simple.png").
                      Should be descriptive and unique per test case.
        tolerance: Allowed difference ratio (0.0 to 1.0, default: 0.0 = exact match).
                  Use 0.001 for QR codes to handle minor rendering variations.
        regenerate: If True, update the baseline with the new rendering.
                   Automatically set to True via --regenerate-baselines flag.

    Raises:
        AssertionError: If images don't match within tolerance and regenerate is False.
                       Error message includes paths to baseline and diff files.

    Example:
        >>> image = template.render(form_data)
        >>> assert_visual_match(image, "my_test.png", regenerate=regenerate_baselines)
    """
    baseline_path = BASELINE_DIR / baseline_name
    diff_path = _diff_path_for(baseline_name)

    if regenerate or not baseline_path.exists():
        # Generate/update baseline
        rendered.save(baseline_path)
        _remove_stale_visual_artifacts(baseline_name)
        print(f"Generated baseline: {baseline_path}")
        return

    # Compare against baseline
    baseline = Image.open(baseline_path)

    if _images_match(rendered, baseline, tolerance):
        _remove_stale_visual_artifacts(baseline_name)
        return

    # Save the diff for inspection
    rendered.save(diff_path)
    _write_visual_report()

    raise AssertionError(
        f"Visual regression failure: {baseline_name}\n"
        f"  Expected: {baseline_path}\n"
        f"  Got: {diff_path}\n"
        f"  HTML report: {VISUAL_REPORT_PATH}\n"
        f"  Image size: expected={baseline.size}, got={rendered.size}\n"
        f"  To update all baselines: pytest {__file__} --regenerate-baselines"
    )


@pytest.fixture
def regenerate_baselines(request):
    """Fixture to check if --regenerate-baselines flag was passed."""
    return request.config.getoption("--regenerate-baselines", default=False)


def test_visual_report_generated_for_failures(tmp_path, monkeypatch):
    """Failed comparisons should leave behind a browser-friendly report."""
    monkeypatch.setitem(globals(), "BASELINE_DIR", tmp_path)
    monkeypatch.setitem(globals(), "VISUAL_REPORT_PATH", tmp_path / "visual-diff-report.html")

    baseline_name = "example.png"
    baseline = Image.new("RGB", (12, 12), "white")
    actual = Image.new("RGB", (12, 12), "black")
    baseline.save(tmp_path / baseline_name)

    with pytest.raises(AssertionError) as exc_info:
        assert_visual_match(actual, baseline_name)

    diff_path = tmp_path / f"DIFF_{baseline_name}"
    report_path = tmp_path / "visual-diff-report.html"
    assert diff_path.exists()
    assert report_path.exists()

    report_html = report_path.read_text(encoding="utf-8")
    assert baseline_name in report_html
    assert f"DIFF_{baseline_name}" in report_html
    assert str(report_path) in str(exc_info.value)

    assert_visual_match(baseline.copy(), baseline_name)
    assert not diff_path.exists()
    assert not report_path.exists()


# =============================================================================
# Best By Template Tests
# =============================================================================


@pytest.fixture
def mock_best_by_date(monkeypatch):
    """Fix the current date for best_by tests."""
    monkeypatch.setattr(best_by, "_today", lambda: date(2025, 11, 17))


def test_best_by_simple_date(mock_best_by_date, regenerate_baselines):
    """Best By label with default 2-week offset."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData({})

    image = template.render(form_data)
    assert_visual_match(image, "best_by_simple.png", regenerate=regenerate_baselines)


def test_best_by_custom_prefix(mock_best_by_date, regenerate_baselines):
    """Best By label with custom prefix."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "Prefix": "Use By: ",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_custom_prefix.png", regenerate=regenerate_baselines)


def test_best_by_one_month(mock_best_by_date, regenerate_baselines):
    """Best By label with 1 month offset."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "Delta": "1 month",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_one_month.png", regenerate=regenerate_baselines)


def test_best_by_custom_text(mock_best_by_date, regenerate_baselines):
    """Best By label with custom text override."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "Text": "Freeze within 24h",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_custom_text.png", regenerate=regenerate_baselines)


def test_best_by_offset_three_weeks(regenerate_baselines):
    """Best By label with explicit base date and 3-week offset."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "BaseDate": "2025-12-04",
            "Offset": "3 weeks",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_offset_three_weeks.png", regenerate=regenerate_baselines)


def test_best_by_prefix_zero_offset(regenerate_baselines):
    """Best By label with prefix override and zero offset."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "BaseDate": "2025-12-04",
            "Offset": "0",
            "Prefix": "Made: ",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_prefix_zero_offset.png", regenerate=regenerate_baselines)


def test_best_by_prefix_double_colon_zero_offset(regenerate_baselines):
    """Best By label with double-colon prefix and zero offset."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "BaseDate": "2025-12-04",
            "Offset": "0",
            "Prefix": "Made:: ",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "best_by_prefix_double_colon_zero_offset.png", regenerate=regenerate_baselines
    )


def test_best_by_prefix_only_base_date_unset(mock_best_by_date, regenerate_baselines):
    """Best By label omits the date when base date is forced but empty."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "BaseDate": "",
            "Prefix": "Test",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "best_by_prefix_only.png", regenerate=regenerate_baselines)


def test_best_by_qr_code_simple(mock_best_by_date, regenerate_baselines):
    """Best By label with QR code (uses default caption)."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "https://example.com/recipe/123",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    # QR codes can vary slightly, use small tolerance
    assert_visual_match(
        image, "best_by_qr_simple.png", tolerance=0.001, regenerate=regenerate_baselines
    )


def test_best_by_qr_code_with_text(mock_best_by_date, regenerate_baselines):
    """Best By label with QR code and caption text."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "https://example.com/recipe/456",
            "QrText": "Soup",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "best_by_qr_with_text.png", tolerance=0.001, regenerate=regenerate_baselines
    )


def test_best_by_qr_code_long_text(mock_best_by_date, regenerate_baselines):
    """Best By label with QR code and long caption text (tests wrapping)."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "https://example.com/recipe/789",
            "QrText": "Chicken Noodle Soup Batch #47",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "best_by_qr_long_text.png", tolerance=0.001, regenerate=regenerate_baselines
    )


def test_best_by_qr_code_caption_from_url(mock_best_by_date, regenerate_baselines):
    """Best By label builds a detailed caption from the QR URL when caption is empty."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?Line1=Durban&Line2=Poison&SymbolName=awake&Side=DP&Bottom=07%2F20%2F25&tpl=bluey_label&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_caption_from_url.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


def test_best_by_qr_code_caption_from_url_lion(mock_best_by_date, regenerate_baselines):
    """Best By label builds a detailed caption from a Bluey label QR URL."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?Line1=Lion&Line2=Mane&SymbolName=awake&Side=LM&Bottom=07%2F11%2F25&tpl=bluey_label&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_caption_lion_mane.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


def test_best_by_qr_code_caption_from_offset(mock_best_by_date, regenerate_baselines):
    """Best By label shows the offset embedded in the QR URL."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?BaseDate=2025-12-04&Offset=2+Months&tpl=best_by&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_offset_two_months.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


def test_best_by_qr_code_caption_from_delta(mock_best_by_date, regenerate_baselines):
    """Best By label shows the delta embedded in the QR URL."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?BaseDate=2025-12-04&Delta=3+weeks&tpl=best_by&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_delta_three_weeks.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


def test_best_by_qr_code_caption_with_prefix(mock_best_by_date, regenerate_baselines):
    """Best By label respects prefix override in QR caption."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?BaseDate=2025-12-04&Offset=0&Prefix=Made%3A+&tpl=best_by&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_caption_prefix_zero_offset.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


def test_best_by_qr_code_caption_with_double_colon_prefix(mock_best_by_date, regenerate_baselines):
    """Best By label respects double-colon prefix in QR caption."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?BaseDate=2025-12-04&Offset=0&Prefix=Made%3A%3A+&tpl=best_by&print=true",
            "QrText": "",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image,
        "best_by_qr_caption_prefix_double_colon_zero_offset.png",
        tolerance=0.001,
        regenerate=regenerate_baselines,
    )


# =============================================================================
# Bluey Label Tests
# =============================================================================


def test_bluey_label_default(regenerate_baselines):
    """Bluey label with default/empty parameters."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData({})

    image = template.render(form_data)
    assert_visual_match(image, "bluey_default.png", regenerate=regenerate_baselines)


def test_bluey_label_repeated_titles(regenerate_baselines):
    """Bluey label repeats the title block with padding."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Leftovers",
            "Line2": "Casserole",
            "SymbolName": "sun",
            "Side": "xy",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_repeated_titles.png", regenerate=regenerate_baselines)


def test_bluey_label_long_text(regenerate_baselines):
    """Bluey label with long text that pushes width/height warnings."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Extremely long casserole name that will clip on the label",
            "Line2": "Another long line to stress layout and spacing",
            "Side": "ABCDEFGH",
            "Bottom": "11/17/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_long_text.png", regenerate=regenerate_baselines)


def test_bluey_label_missing_symbol(regenerate_baselines):
    """Bluey label falls back gracefully when symbol choice is missing."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Fallback",
            "SymbolName": "",
            "Side": "xy",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_missing_symbol.png", regenerate=regenerate_baselines)


def test_bluey_label_initials_only(regenerate_baselines):
    """Bluey label renders side text when title lines are missing."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Side": "SIDE",
            "Bottom": "11/17/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_initials_only.png", regenerate=regenerate_baselines)


def test_bluey_label_full_fields(regenerate_baselines):
    """Bluey label with typical filled inputs."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Durban",
            "Line2": "Poison",
            "SymbolName": "awake",
            "Side": "DP",
            "Bottom": "07/20/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_full_fields.png", regenerate=regenerate_baselines)


def test_bluey_label_full_fields_super(regenerate_baselines):
    """Bluey label with typical filled inputs and Line1 set to Super."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Super",
            "Line2": "Poison",
            "SymbolName": "awake",
            "Side": "DP",
            "Bottom": "07/20/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_full_fields_super.png", regenerate=regenerate_baselines)


def test_bluey_label_alt_symbol(regenerate_baselines):
    """Bluey label with alternate symbol and side text."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Party Snacks",
            "Line2": "Label",
            "SymbolName": "balloon-2",
            "Side": "PS",
            "Bottom": "12/31/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_alt_symbol.png", regenerate=regenerate_baselines)


def test_bluey_label_meter_mode(regenerate_baselines):
    """Bluey label replaces side text with mirrored meters in meter mode."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Chili",
            "Line2": "Peppers",
            "SymbolName": "awake",
            "Side": "=METER",
            "Bottom": "12/19/25",
            "Percentage": "30:SH",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_meter_mode.png", regenerate=regenerate_baselines)


def test_bluey_label_meter_mode_zero_with_alt_symbol(regenerate_baselines):
    """Bluey meter mode handles a low reading with an alternate symbol."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Mint",
            "Line2": "Tea",
            "SymbolName": "balloon-2",
            "Side": "=METER",
            "Bottom": "01/02/26",
            "Percentage": "0:DRY",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "bluey_meter_mode_zero_alt_symbol.png", regenerate=regenerate_baselines
    )


def test_bluey_label_meter_mode_long_text_high_reading(regenerate_baselines):
    """Bluey meter mode stays stable with longer titles and a high reading."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Fermented",
            "Line2": "Blueberries",
            "SymbolName": "sleep",
            "Side": "=METER",
            "Bottom": "08/30/26",
            "Percentage": "100:AGED",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "bluey_meter_mode_long_text_high_reading.png", regenerate=regenerate_baselines
    )


def test_bluey_jar_label_basic(regenerate_baselines):
    """Bluey jar label with basic supplier and percentage fields."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Spice",
            "Line2": "Mix",
            "Side": "SM",
            "Bottom": "12/31/25",
            "Supplier": "Local Farm",
            "Percentage": "100%",
            "jar_label_request": "true",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_jar_basic.png", regenerate=regenerate_baselines)


def test_bluey_jar_label_supplier_only(regenerate_baselines):
    """Bluey jar label with only supplier field (should trigger jar rendering)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Herbs",
            "Line2": "Dried",
            "Side": "HD",
            "Supplier": "Garden Co",
            "jar_label_request": "true",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_jar_supplier_only.png", regenerate=regenerate_baselines)


def test_bluey_jar_label_percentage_only(regenerate_baselines):
    """Bluey jar label with only percentage field (should trigger jar rendering)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Organic",
            "Line2": "Flour",
            "Side": "OF",
            "Bottom": "06/15/25",
            "Percentage": "95%",
            "jar_label_request": "true",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_jar_percentage_only.png", regenerate=regenerate_baselines)


def test_bluey_jar_label_full_fields(regenerate_baselines):
    """Bluey jar label with all fields populated."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Premium",
            "Line2": "Coffee",
            "SymbolName": "awake",
            "Side": "PC",
            "Bottom": "03/20/26",
            "Supplier": "Mountain Roasters",
            "Percentage": "100% Arabica",
            "jar_qr_url": "http://localhost:8099/bb?Line1=Premium&Line2=Coffee&tpl=bluey_label",
            "jar_label_request": "true",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_jar_full_fields.png", regenerate=regenerate_baselines)
