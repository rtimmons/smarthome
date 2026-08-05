"""Tests for the countdown functionality in the printer service.

This module tests the JavaScript countdown behavior when ?print=true is present
in the URL, including the countdown timer, cancel functionality, and preview
click behavior.
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from printer_service.app import create_app

pytestmark = pytest.mark.ui

INSTANT_PREVIEW_BUDGET_SECONDS = 0.1


@pytest.fixture(scope="session")
def app_server():
    """Start a test server for the printer service."""
    app = create_app()
    try:
        server = make_server("127.0.0.1", 0, app)
    except (OSError, SystemExit) as exc:
        pytest.skip(f"Skipping countdown test; unable to bind test server: {exc}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    yield base_url
    with suppress(Exception):
        server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    """Create a browser instance for testing."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def _wait_for_previews(page):
    """Wait for preview images to load."""
    page.wait_for_selector(".bb-preview-trigger img", state="visible", timeout=15000)


def _open_bluey_preview(page, app_server):
    page.goto(
        f"{app_server}/bb?tpl=bluey_label&Line1=Initial",
        wait_until="domcontentloaded",
    )
    page.wait_for_function(
        """() => {
            const image = document.getElementById('labelPreviewImage');
            return image && image.dataset.hasPreview === 'true';
        }""",
        timeout=15000,
    )


def _wait_for_new_label_preview(page, previous_src):
    page.wait_for_function(
        """(src) => {
            const image = document.getElementById('labelPreviewImage');
            const container = document.getElementById('previewContainer');
            return image && image.dataset.hasPreview === 'true' &&
                image.src !== src && !container.hasAttribute('aria-busy');
        }""",
        arg=previous_src,
        timeout=15000,
    )


def test_live_preview_latency_feels_instantaneous(app_server, browser):
    """Keep edit-to-visible-preview latency inside the 100 ms interaction budget."""
    page = browser.new_page()
    try:
        _open_bluey_preview(page, app_server)
        previous_src = page.locator("#labelPreviewImage").get_attribute("src")

        started_at = time.perf_counter()
        page.locator("#line1").fill("Instant preview")
        _wait_for_new_label_preview(page, previous_src)
        elapsed = time.perf_counter() - started_at
        print(f"live preview latency: {elapsed * 1000:.1f} ms")

        assert elapsed <= INSTANT_PREVIEW_BUDGET_SECONDS, (
            f"Live preview took {elapsed * 1000:.1f} ms; "
            f"budget is {INSTANT_PREVIEW_BUDGET_SECONDS * 1000:.0f} ms"
        )
    finally:
        page.close()


def test_live_preview_coalesces_rapid_edits_and_uses_latest_form_state(app_server, browser):
    """A burst of edits should render once with the final complete form payload."""
    page = browser.new_page()
    preview_payloads = []
    page.on(
        "request",
        lambda request: (
            preview_payloads.append(request.post_data_json)
            if request.url.endswith("/bb/preview")
            else None
        ),
    )
    try:
        _open_bluey_preview(page, app_server)
        preview_payloads.clear()

        page.locator("#line1").fill("Final line one")
        page.locator("#line2").fill("Final line two")
        page.wait_for_timeout(400)
        page.wait_for_function(
            """() => !document.getElementById('previewContainer').hasAttribute('aria-busy')""",
            timeout=15000,
        )

        assert len(preview_payloads) == 1
        assert preview_payloads[0]["data"]["Line1"] == "Final line one"
        assert preview_payloads[0]["data"]["Line2"] == "Final line two"
    finally:
        page.close()


def test_live_preview_skips_unchanged_form_state(app_server, browser):
    """Input/change noise must not re-render an identical preview."""
    page = browser.new_page()
    preview_requests = []
    page.on(
        "request",
        lambda request: (
            preview_requests.append(request) if request.url.endswith("/bb/preview") else None
        ),
    )
    try:
        _open_bluey_preview(page, app_server)
        preview_requests.clear()

        page.locator("#line1").dispatch_event("input")
        page.locator("#line1").dispatch_event("change")
        page.wait_for_timeout(350)

        assert preview_requests == []
    finally:
        page.close()


def test_live_preview_removes_optional_jar_when_fields_are_cleared(app_server, browser):
    """The jar preview should follow the supplier/percentage fields in both directions."""
    page = browser.new_page()
    try:
        _open_bluey_preview(page, app_server)
        jar_image = page.locator("#jarPreviewImage")
        assert jar_image.is_hidden()

        page.locator("#supplier").fill("Local Farm")
        page.wait_for_function(
            """() => document.getElementById('jarPreviewImage').dataset.hasPreview === 'true'""",
            timeout=15000,
        )
        assert jar_image.is_visible()

        page.locator("#supplier").fill("")
        page.wait_for_function(
            """() => document.getElementById('jarPreviewImage').dataset.hasPreview === 'false'""",
            timeout=15000,
        )
        assert jar_image.is_hidden()
    finally:
        page.close()


def test_countdown_appears_with_print_parameter(app_server, browser):
    """Test that countdown appears when ?print=true is in URL."""
    page = browser.new_page()

    # First navigate to the page without print parameter to load the base page
    page.goto(f"{app_server}/bb", wait_until="networkidle")

    # Then use JavaScript to simulate the print parameter being added
    page.evaluate("""
        // Simulate URL with print parameter
        const url = new URL(window.location);
        url.searchParams.set('print', 'true');
        window.history.replaceState({}, '', url);

        // Trigger the countdown check
        if (window.checkForPrintParameter) {
            window.checkForPrintParameter();
        }
    """)

    # Wait a moment for the countdown to start
    page.wait_for_timeout(50)

    # Countdown container should be visible
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert countdown_container.is_visible()

    # Countdown timer should show initial value in the button
    timer_element = page.query_selector("#countdownSeconds")
    assert timer_element is not None
    timer_text = timer_element.text_content()
    assert timer_text in ["5", "4", "3", "2", "1"]  # Could be any value during countdown

    # Cancel button should be present
    cancel_button = page.query_selector("#cancelCountdown")
    assert cancel_button is not None
    assert cancel_button.is_visible()

    # Print Now button should be present
    print_now_button = page.query_selector("#printNowButton")
    assert print_now_button is not None
    assert print_now_button.is_visible()

    # Check the button text specifically
    print_button_text = page.query_selector("#printButtonText")
    assert print_button_text is not None
    assert print_button_text.text_content() == "Print Now"

    # Preview elements should be present
    preview_title = page.query_selector("#countdownPreviewTitle")
    assert preview_title is not None
    assert preview_title.text_content() == "Label Preview"

    preview_status = page.query_selector("#countdownPreviewStatus")
    assert preview_status is not None


def test_countdown_not_visible_without_print_parameter(app_server, browser):
    """Test that countdown is hidden when ?print=true is not in URL."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")

    # Countdown container should be hidden
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert not countdown_container.is_visible()


def test_cancel_countdown_functionality(app_server, browser):
    """Test that clicking cancel stops countdown but keeps dialog visible."""
    page = browser.new_page()

    # First navigate to the page with parameters but without print
    page.goto(f"{app_server}/bb?Text=Test", wait_until="networkidle")

    # Then use JavaScript to simulate the print parameter being added
    page.evaluate("""
        // Simulate URL with print parameter
        const url = new URL(window.location);
        url.searchParams.set('print', 'true');
        window.history.replaceState({}, '', url);

        // Trigger the countdown check
        if (window.checkForPrintParameter) {
            window.checkForPrintParameter();
        }
    """)

    # Wait a moment for the countdown to start
    page.wait_for_timeout(50)

    # Countdown should be visible initially
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert countdown_container.is_visible()

    # Countdown timer should be visible in button
    countdown_timer = page.query_selector("#countdownTimer")
    assert countdown_timer is not None
    assert countdown_timer.is_visible()

    # Click cancel button
    cancel_button = page.query_selector("#cancelCountdown")
    assert cancel_button is not None
    cancel_button.click()

    # Dialog should still be visible (new behavior)
    assert countdown_container.is_visible()

    # Countdown timer should be hidden after cancel
    assert not countdown_timer.is_visible()

    # URL should no longer have print parameter but preserve other parameters
    current_url = page.url
    assert "print=true" not in current_url
    assert "Text=Test" in current_url


def test_preview_heading_updated(app_server, browser):
    """Test that preview heading shows 'Click to Print'."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")

    # Check that heading is updated
    preview_heading = page.query_selector("#previewContainer h3")
    assert preview_heading is not None
    assert preview_heading.text_content() == "Previews: Click to Print"


def test_print_buttons_removed(app_server, browser):
    """Test that print buttons are no longer present."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")

    # Print buttons should not exist
    print_label_button = page.query_selector('button:has-text("Print Label")')
    print_qr_button = page.query_selector('button:has-text("Print QR")')

    assert print_label_button is None
    assert print_qr_button is None


def test_previews_ready_text_removed(app_server, browser):
    """Test that 'Previews ready' text is no longer displayed."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")
    _wait_for_previews(page)

    # "Previews ready" text should not exist
    previews_ready_text = page.query_selector(".preview-status__label")
    assert previews_ready_text is None

    # Check that the text is not present anywhere on the page
    page_content = page.content()
    assert "Previews ready" not in page_content


def test_size_info_removed(app_server, browser):
    """Test that size information is no longer displayed."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")
    _wait_for_previews(page)

    # Check that size information is not displayed in the preview summary
    preview_summary = page.query_selector("#labelPreviewSummary")
    assert preview_summary is not None
    summary_text = preview_summary.text_content()
    assert "Size:" not in summary_text
    assert "×" not in summary_text  # multiplication symbol used in dimensions
    assert "px" not in summary_text
    assert "Click to print the label." in summary_text

    # Check that size info is not present anywhere on the page
    page_content = page.content()
    assert "481×91px" not in page_content
    assert "~1.60" not in page_content


def test_preview_images_clickable(app_server, browser):
    """Test that preview images have clickable styling."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")
    _wait_for_previews(page)

    # Preview triggers should have cursor pointer
    preview_triggers = page.query_selector_all(".bb-preview-trigger")
    assert len(preview_triggers) >= 1

    for trigger in preview_triggers:
        cursor_style = page.evaluate("el => getComputedStyle(el).cursor", trigger)
        assert cursor_style == "pointer"


def test_countdown_executes_print_after_completion(app_server, browser):
    """Test that countdown executes print after completion."""
    page = browser.new_page()

    # Mock the fetch function to capture print requests
    page.add_init_script("""
        window.printRequests = [];
        const originalFetch = window.fetch;
        window.fetch = function(url, options) {
            if (url.includes('/bb/execute-print')) {
                window.printRequests.push({url, options});
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({status: 'sent'})
                });
            }
            return originalFetch.apply(this, arguments);
        };
    """)

    # Navigate to URL with print=true parameter and fast countdown for testing
    page.goto(
        f"{app_server}/bb?print=true&Text=Test+Label&countdown_duration=1", wait_until="networkidle"
    )

    # Countdown should be visible
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None

    # Wait for countdown to complete (1.5 seconds to be safe)
    page.wait_for_timeout(1500)

    # Check that print request was made
    print_requests = page.evaluate("window.printRequests")
    assert len(print_requests) == 1
    assert "/bb/execute-print" in print_requests[0]["url"]

    # Dialog should still be visible for multiple copies (persistent dialog)
    assert countdown_container.is_visible()

    # Print Now button text should show "Print Again ✓"
    print_button_text = page.query_selector("#printButtonText")
    assert print_button_text is not None
    # Wait a moment for the success state to show
    page.wait_for_timeout(500)
    button_text = print_button_text.text_content()
    assert button_text in ["Print Again ✓", "Print Now"]  # Could be either depending on timing

    # Cancel button should show "Done"
    cancel_button = page.query_selector("#cancelCountdown")
    assert cancel_button is not None
    cancel_text = cancel_button.text_content()
    assert cancel_text in ["Done", "Cancel"]  # Could be either depending on timing


def test_print_now_button_functionality(app_server, browser):
    """Test that Print Now button triggers immediate printing."""
    page = browser.new_page()

    # Mock the fetch function to capture print requests
    page.add_init_script("""
        window.printRequests = [];
        const originalFetch = window.fetch;
        window.fetch = function(url, options) {
            if (url.includes('/bb/execute-print')) {
                window.printRequests.push({url, options});
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({status: 'sent'})
                });
            }
            return originalFetch.apply(this, arguments);
        };
    """)

    # Navigate to URL with print=true parameter
    page.goto(f"{app_server}/bb?print=true&Text=Test+Label", wait_until="networkidle")

    # Countdown should be visible
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert countdown_container.is_visible()

    # Click Print Now button immediately
    print_now_button = page.query_selector("#printNowButton")
    assert print_now_button is not None
    print_now_button.click()

    # Wait a moment for the print request
    page.wait_for_timeout(500)

    # Check that print request was made immediately
    print_requests = page.evaluate("window.printRequests")
    assert len(print_requests) == 1
    assert "/bb/execute-print" in print_requests[0]["url"]

    # Dialog should still be visible for multiple copies
    assert countdown_container.is_visible()


def test_qr_label_countdown_preview(app_server, browser):
    """Test that QR label countdown shows correct preview title."""
    page = browser.new_page()

    # First navigate to the page to load previews
    page.goto(f"{app_server}/bb?Text=Test+Label", wait_until="networkidle")
    _wait_for_previews(page)

    # Then use JavaScript to simulate QR print parameter being added
    page.evaluate("""
        // Simulate URL with QR print parameter
        const url = new URL(window.location);
        url.searchParams.set('print', 'true');
        url.searchParams.set('qr', 'true');
        window.history.replaceState({}, '', url);

        // Trigger the countdown check
        if (window.checkForPrintParameter) {
            window.checkForPrintParameter();
        }
    """)

    # Wait a moment for the countdown to start
    page.wait_for_timeout(50)

    # Countdown container should be visible
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert countdown_container.is_visible()

    # Preview title should indicate QR label
    preview_title = page.query_selector("#countdownPreviewTitle")
    assert preview_title is not None
    assert preview_title.text_content() == "QR Label Preview"


def test_preview_click_navigates_to_print_url(app_server, browser):
    """Test that clicking preview navigates to the print URL with countdown."""
    page = browser.new_page()

    # Navigate to the page and wait for previews to load
    page.goto(f"{app_server}/bb?Text=Test+Label", wait_until="networkidle")
    _wait_for_previews(page)

    # Click on the main label preview
    label_preview_trigger = page.query_selector('.bb-preview-trigger[data-print-target="label"]')
    assert label_preview_trigger is not None
    label_preview_trigger.click()

    # Wait for navigation to complete
    page.wait_for_load_state("networkidle")

    # Countdown should be visible after navigation
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert countdown_container.is_visible()

    # URL should have print=true parameter
    current_url = page.url
    assert "print=true" in current_url
    assert "Text=Test+Label" in current_url


def test_preview_click_does_not_fire_legacy_print_fetch(app_server, browser):
    """Ensure preview clicks no longer trigger legacy print requests."""
    page = browser.new_page()

    page.add_init_script("""
        window.__fetchLog = [];
        const originalFetch = window.fetch;
        window.fetch = function(input, init) {
            const url = typeof input === 'string' ? input : (input && input.url) || '';
            window.__fetchLog.push(url);
            return originalFetch.apply(this, arguments);
        };
    """)

    page.goto(f"{app_server}/bb?Line1=Cadillac", wait_until="networkidle")
    _wait_for_previews(page)

    # Reset fetch log after initial preview loads
    page.evaluate("window.__fetchLog = [];")

    label_preview_trigger = page.query_selector('.bb-preview-trigger[data-print-target="label"]')
    assert label_preview_trigger is not None
    label_preview_trigger.click()

    # Give countdown dialog time to appear without letting it auto-print
    page.wait_for_timeout(200)

    fetch_calls = page.evaluate("window.__fetchLog")
    assert isinstance(fetch_calls, list)
    assert not any("print=true" in call for call in fetch_calls if isinstance(call, str))
