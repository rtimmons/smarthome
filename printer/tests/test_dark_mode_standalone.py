#!/usr/bin/env python3
"""
Standalone test for dark mode functionality.
This runs independently to avoid asyncio conflicts with the main test suite.
"""

import re
import sys
import threading
from contextlib import suppress

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from printer_service.app import create_app


def _wait_for_previews(page):
    page.wait_for_selector(".bb-preview-trigger img", state="visible", timeout=15000)


def _has_significant_invert(filter_value: str, *, threshold: float = 0.1) -> bool:
    match = re.search(r"invert\(([^)]+)\)", filter_value)
    if match:
        try:
            amount = float(match.group(1))
            return amount > threshold
        except ValueError:
            return False
    return False


def _force_dark_theme(page):
    theme_select = page.query_selector("#themeSelect")
    if theme_select is None:
        raise Exception("Theme selector not available; cannot verify dark mode previews.")
    page.select_option("#themeSelect", "dark")
    page.wait_for_timeout(100)


def test_dark_mode_inverts_previews():
    """Test that dark mode properly inverts preview images."""
    # Start test server
    app = create_app()
    try:
        server = make_server("127.0.0.1", 0, app)
    except (OSError, SystemExit) as exc:
        print(f"❌ Unable to bind test server: {exc}")
        return False

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(color_scheme="dark")
                page.goto(f"{base_url}/bb", wait_until="networkidle")
                _force_dark_theme(page)
                _wait_for_previews(page)

                filter_value = page.eval_on_selector(
                    ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
                )
                assert _has_significant_invert(filter_value.lower(), threshold=0.2), (
                    f"Expected significant invert filter, got: {filter_value}"
                )

                page.hover(".bb-preview-trigger img")
                page.wait_for_timeout(200)
                hover_filter = page.eval_on_selector(
                    ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
                )
                hover_filter_normalized = hover_filter.strip().lower()
                assert hover_filter_normalized in {"none", ""} or not _has_significant_invert(
                    hover_filter_normalized, threshold=0.01
                ), f"Expected no invert on hover, got: {hover_filter}"

                print("✅ Dark mode test passed")
                return True
            finally:
                browser.close()
    except Exception as e:
        print(f"❌ Dark mode test failed: {e}")
        return False
    finally:
        with suppress(Exception):
            server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    success = test_dark_mode_inverts_previews()
    sys.exit(0 if success else 1)
