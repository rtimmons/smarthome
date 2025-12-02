# Testing Guide

## Agent Notes
- Follow the repo-wide expectations in `../../CLAUDE.md#agent-expectations-repo-wide` (sandbox/git-lock permission, use `just`/env wrappers, "prepare to commit" steps).

This document describes the testing infrastructure for the printer service.

## Overview

The printer service has comprehensive test coverage including:
- **Unit tests** - Test individual functions and modules
- **Integration tests** - Test Flask API endpoints and workflows
- **Visual regression tests** - Ensure label rendering remains pixel-perfect

## Running Tests

### Run All Tests (Recommended)

```bash
# From the printer directory
just test
```

This runs the full test suite including:
- Code formatting checks (ruff)
- Type checking (mypy)
- All pytest tests

### Run Specific Tests

For more targeted test runs, use pytest directly:

```bash
# Run only visual regression tests
.venv/bin/pytest tests/test_visual_regression.py -v

# Run only app integration tests
.venv/bin/pytest tests/test_app.py -v

# Run a single test
.venv/bin/pytest tests/test_visual_regression.py::test_kitchen_label_three_lines -v

# Run tests matching a keyword
.venv/bin/pytest tests/ -k kitchen -v
.venv/bin/pytest tests/ -k best_by -v
```

## Visual Regression Testing

Visual regression tests ensure that refactoring doesn't inadvertently change the visual output of labels. These tests compare rendered images pixel-by-pixel against baseline images stored in `tests/baselines/`.

### How It Works

1. **Baseline images** (`tests/baselines/*.png`) are the "source of truth"
2. Tests render labels and compare them against baselines
3. If pixels don't match, the test fails and creates a `DIFF_*.png` file
4. You can visually compare the baseline vs. the diff to understand what changed

### When to Regenerate Baselines

Regenerate baselines **only** when you intentionally change the visual output:

```bash
# Regenerate ALL baselines
.venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v

# Regenerate a specific baseline
.venv/bin/pytest tests/test_visual_regression.py::test_kitchen_label_three_lines --regenerate-baselines -v
```

**Important:** Review the changes carefully before committing new baselines to git!

### Test Coverage

Visual regression tests cover these scenarios:

#### Best By Labels (7 tests)
- `test_best_by_simple_date` - Default 2-week offset
- `test_best_by_custom_prefix` - Custom prefix ("Use By: ")
- `test_best_by_one_month` - 1-month offset
- `test_best_by_custom_text` - Free-form text override
- `test_best_by_qr_code_simple` - QR code without overlay
- `test_best_by_qr_code_with_text` - QR code with short overlay
- `test_best_by_qr_code_long_text` - QR code with long overlay (tests wrapping)

#### Kitchen Labels (4 tests)
- `test_kitchen_label_three_lines` - All three lines filled
- `test_kitchen_label_two_lines` - Two lines
- `test_kitchen_label_single_line` - Single line
- `test_kitchen_label_long_text` - Very long text (tests clipping)

#### Receipt Checklists (3 tests)
- `test_receipt_default_items` - Default checklist items
- `test_receipt_custom_items` - Custom items
- `test_receipt_with_qr` - Checklist with QR code

#### Bluey Labels (2 tests)
- `test_bluey_label_default` - bluey_label template
- `test_bluey_label_2_default` - bluey_label_2 template

### Understanding Test Failures

When a visual regression test fails:

```
AssertionError: Visual regression failure: kitchen_three_lines.png
  Expected: /path/to/tests/baselines/kitchen_three_lines.png
  Got: /path/to/tests/baselines/DIFF_kitchen_three_lines.png
  Image size: expected=(306, 991), got=(306, 991)
  To update all baselines: pytest tests/test_visual_regression.py --regenerate-baselines
```

This means:
1. The rendered label differs from the baseline
2. A `DIFF_*.png` file was created with the new rendering
3. Open both files side-by-side to see what changed
4. If the change is intentional, regenerate baselines
5. If the change is unintentional, fix the code

### Adding New Visual Tests

To add a new visual regression test:

1. **Add the test function** to `tests/test_visual_regression.py`:

```python
def test_my_new_label(regenerate_baselines):
    """Description of what this label tests."""
    template = my_template.TEMPLATE
    form_data = TemplateFormData({
        "param1": "value1",
        "param2": "value2",
    })

    image = template.render(form_data)
    assert_visual_match(image, "my_new_label.png", regenerate=regenerate_baselines)
```

2. **Generate the baseline** (first run only):

```bash
.venv/bin/pytest tests/test_visual_regression.py::test_my_new_label --regenerate-baselines -v
```

3. **Verify the test passes**:

```bash
.venv/bin/pytest tests/test_visual_regression.py::test_my_new_label -v
```

4. **Commit both the test and baseline**:

```bash
git add tests/test_visual_regression.py tests/baselines/my_new_label.png
```

## Test Infrastructure

### Fixtures

- `test_environment` - Creates isolated Flask app with temporary storage
- `mock_best_by_date` - Fixes date to `2025-11-17` for reproducible tests
- `regenerate_baselines` - Reads `--regenerate-baselines` CLI flag

### Test Utilities

- `assert_visual_match()` - Compares rendered image against baseline
- `_images_match()` - Pixel-by-pixel comparison with tolerance
- `_image_hash()` - Fast SHA256 comparison for exact matches

### Fake CairoSVG

Tests use a fake `cairosvg` module (defined in `tests/conftest.py`) to avoid system dependencies. The fake implementation returns placeholder PNG data.

## Continuous Integration

Tests are designed to be deterministic and should pass consistently in CI environments:

- Visual tests use fixed dates (`mock_best_by_date` fixture)
- QR codes use small tolerance (0.001) to handle minor rendering variations
- All external dependencies are mocked or controlled

## Troubleshooting

### Tests fail with "cairosvg not found"

This is expected in test environments. The test suite provides a fake cairosvg implementation via `tests/conftest.py`. No action needed.

### Visual tests fail with "difference ratio" errors

This means the rendered image differs from the baseline:

1. Check if you made intentional changes to the rendering code
2. Review the `DIFF_*.png` file to see what changed
3. If intentional, regenerate baselines with `--regenerate-baselines`
4. If unintentional, investigate and fix the rendering code

### QR code tests randomly fail

QR codes can have minor rendering variations. Tests use `tolerance=0.001` to handle this. If failures persist:

1. Check if the QR code library was updated
2. Regenerate baselines if the new rendering is acceptable
3. Increase tolerance if needed (with caution)

### Baseline images are missing

If you see "baseline file not found" errors:

```bash
# Generate all missing baselines
.venv/bin/pytest tests/test_visual_regression.py --regenerate-baselines -v
```

Then commit the generated baselines to git.

## Git Workflow

### Files to Commit

✅ **Always commit:**
- Test files: `tests/test_*.py`
- Baseline images: `tests/baselines/*.png`
- This documentation: `TESTING.md`

❌ **Never commit:**
- Diff images: `tests/baselines/DIFF_*.png` (auto-ignored by `.gitignore`)
- Temporary test files: `label-output/`, `.pytest_cache/`

### Before Refactoring

1. Run all tests to establish a baseline:
   ```bash
   just test
   ```

2. Ensure all tests pass before making changes

3. After refactoring, run tests again to verify no regressions

### Reviewing Visual Changes

When reviewing PRs with baseline changes:

1. Check the diff for each baseline image
2. Ask: "Is this visual change intentional?"
3. Verify the test description matches the change
4. Request regeneration if baselines were updated incorrectly

## Performance

- **Test suite execution time**: ~2 seconds for all 84 tests
- **Visual regression tests**: ~0.3 seconds for 16 tests
- **Baseline generation**: Same as normal test run

Fast test execution enables rapid iteration during development.
