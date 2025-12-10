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

    # Countdown timer should show initial value
    timer_element = page.query_selector("#countdownTimer")
    assert timer_element is not None
    timer_text = timer_element.text_content()
    assert timer_text in ["5", "4", "3", "2", "1"]  # Could be any value during countdown

    # Cancel button should be present
    cancel_button = page.query_selector("#cancelCountdown")
    assert cancel_button is not None
    assert cancel_button.is_visible()


def test_countdown_not_visible_without_print_parameter(app_server, browser):
    """Test that countdown is hidden when ?print=true is not in URL."""
    page = browser.new_page()
    page.goto(f"{app_server}/bb", wait_until="networkidle")

    # Countdown container should be hidden
    countdown_container = page.query_selector("#printCountdownContainer")
    assert countdown_container is not None
    assert not countdown_container.is_visible()


def test_cancel_countdown_functionality(app_server, browser):
    """Test that clicking cancel hides countdown and removes print parameter."""
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

    # Click cancel button
    cancel_button = page.query_selector("#cancelCountdown")
    assert cancel_button is not None
    cancel_button.click()

    # Countdown should be hidden
    assert not countdown_container.is_visible()

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

    # URL should no longer have print=true parameter but should preserve other params
    current_url = page.url
    assert "print=true" not in current_url
    assert "Text=Test+Label" in current_url
    # countdown_duration should also be cleaned up
    assert "countdown_duration" not in current_url
