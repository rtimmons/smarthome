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
import importlib
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

import pytest
from PIL import Image

from printer_service.label_templates import (
    best_by,
    bluey_label,
    daily_snapshot,
    receipt_checklist,
)
from printer_service.label_templates.base import TemplateFormData

# Directory for baseline images
BASELINE_DIR = Path(__file__).parent / "baselines"
BASELINE_DIR.mkdir(exist_ok=True)


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

    if regenerate or not baseline_path.exists():
        # Generate/update baseline
        rendered.save(baseline_path)
        print(f"Generated baseline: {baseline_path}")
        return

    # Compare against baseline
    baseline = Image.open(baseline_path)

    if not _images_match(rendered, baseline, tolerance):
        # Save the diff for inspection
        diff_path = BASELINE_DIR / f"DIFF_{baseline_name}"
        rendered.save(diff_path)

        raise AssertionError(
            f"Visual regression failure: {baseline_name}\n"
            f"  Expected: {baseline_path}\n"
            f"  Got: {diff_path}\n"
            f"  Image size: expected={baseline.size}, got={rendered.size}\n"
            f"  To update all baselines: pytest {__file__} --regenerate-baselines"
        )


@pytest.fixture
def regenerate_baselines(request):
    """Fixture to check if --regenerate-baselines flag was passed."""
    return request.config.getoption("--regenerate-baselines", default=False)


# =============================================================================
# Best By Template Tests
# =============================================================================


@pytest.fixture
def mock_best_by_date(monkeypatch):
    """Fix the current date for best_by tests."""
    monkeypatch.setattr(best_by, "_today", lambda: date(2025, 11, 17))


@pytest.fixture
def mock_receipt_datetime(monkeypatch):
    """Fix the current date/time for receipt checklist tests."""
    fixed_date = date(2025, 12, 6)
    fixed_datetime = datetime(2025, 12, 6, 9, 30, 0)
    monkeypatch.setattr(receipt_checklist, "_today", lambda: fixed_date)
    monkeypatch.setattr(receipt_checklist, "_now", lambda: fixed_datetime)
    return fixed_date


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
            "QrUrl": "http://[::1]:8099/bb?Line1=Durban&Line2=Poison&SymbolName=awake&Initials=DP&PackageDate=07%2F20%2F25&tpl=bluey_label_2&print=true",
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
    """Best By label builds a detailed caption from a Bluey Label 2 QR URL."""
    template = best_by.TEMPLATE
    form_data = TemplateFormData(
        {
            "QrUrl": "http://[::1]:8099/bb?Line1=Lion&Line2=Mane&SymbolName=awake&Initials=LM&PackageDate=07%2F11%2F25&tpl=bluey_label_2&print=true",
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
# Receipt Checklist Tests
# =============================================================================


def test_receipt_default_items(mock_receipt_datetime, regenerate_baselines):
    """Receipt checklist with default items."""
    template = receipt_checklist.TEMPLATE
    form_data = TemplateFormData(
        {
            "items[]": [
                "Breakfast",
                "Lunch",
                "Dinner",
                "Meds AM",
                "Meds PM",
                "Hydrate x8",
                "Exercise",
                "Notes",
            ],
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "receipt_default.png", regenerate=regenerate_baselines)


def test_receipt_custom_items(mock_receipt_datetime, regenerate_baselines):
    """Receipt checklist with custom items."""
    template = receipt_checklist.TEMPLATE
    form_data = TemplateFormData(
        {
            "items[]": [
                "Buy milk",
                "Call dentist",
                "Pay bills",
                "Water plants",
            ],
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "receipt_custom.png", regenerate=regenerate_baselines)


def test_receipt_with_qr(mock_receipt_datetime, regenerate_baselines):
    """Receipt checklist with QR code."""
    template = receipt_checklist.TEMPLATE
    form_data = TemplateFormData(
        {
            "items[]": [
                "Task 1",
                "Task 2",
                "Task 3",
            ],
            "qr_base": "https://example.com/checklist/",
            "date": "2025-11-17",
        }
    )

    image = template.render(form_data)
    assert_visual_match(
        image, "receipt_with_qr.png", tolerance=0.001, regenerate=regenerate_baselines
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


def test_bluey_label_between_field(regenerate_baselines):
    """Bluey label with Between field text between Line1 and Line2."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Leftovers",
            "Line2": "Casserole",
            "Between": "from yesterday",
            "Side": "LC",
            "Bottom": "12/10/25",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_between_field.png", regenerate=regenerate_baselines)


def test_bluey_label_between_only(regenerate_baselines):
    """Bluey label with Between field but only one title line (should not show Between)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Single Line",
            "Between": "should not appear",
            "Side": "SL",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_between_only.png", regenerate=regenerate_baselines)


def test_bluey_label_inversion_0_percent(regenerate_baselines):
    """Bluey label with 0% inversion (normal appearance)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Normal",
            "Line2": "Label",
            "Side": "NL",
            "Bottom": "12/10/25",
            "Inversion": "0",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_inversion_0.png", regenerate=regenerate_baselines)


def test_bluey_label_inversion_50_percent(regenerate_baselines):
    """Bluey label with 50% inversion (partial inversion)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Half",
            "Line2": "Inverted",
            "Side": "HI",
            "Bottom": "12/10/25",
            "Inversion": "50",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_inversion_50.png", regenerate=regenerate_baselines)


def test_bluey_label_inversion_100_percent(regenerate_baselines):
    """Bluey label with 100% inversion (fully inverted)."""
    template = bluey_label.TEMPLATE
    form_data = TemplateFormData(
        {
            "Line1": "Fully",
            "Line2": "Inverted",
            "Side": "FI",
            "Bottom": "12/10/25",
            "Inversion": "100",
        }
    )

    image = template.render(form_data)
    assert_visual_match(image, "bluey_inversion_100.png", regenerate=regenerate_baselines)


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


# =============================================================================
# Daily Snapshot Tests (if applicable)
# =============================================================================

# Note: daily_snapshot may require complex payload.
# Add tests here if the template is being used in production.


def test_daily_snapshot_basic(regenerate_baselines):
    """Test daily snapshot template with basic widget data."""
    form_data = daily_snapshot.TemplateFormData(
        {
            "widgets": '[{"type": "date_heading", "payload": {"label": "Mon Dec 9, 2024"}}, {"type": "calendar_month", "payload": {"year": 2024, "month": 12, "month_label": "December 2024", "weeks": [[{"day": 1, "status": "past"}, {"day": 2, "status": "past"}, {"day": 3, "status": "past"}, {"day": 4, "status": "past"}, {"day": 5, "status": "past"}, {"day": 6, "status": "past"}, {"day": 7, "status": "past"}], [{"day": 8, "status": "past"}, {"day": 9, "status": "today"}, {"day": 10, "status": "future"}, {"day": 11, "status": "future"}, {"day": 12, "status": "future"}, {"day": 13, "status": "future"}, {"day": 14, "status": "future"}]]}}]'
        }
    )

    image = daily_snapshot.Template().render(form_data)
    assert_visual_match(image, "daily_snapshot_basic.png", regenerate_baselines)
