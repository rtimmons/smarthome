from __future__ import annotations

import threading
from contextlib import suppress
import re

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from printer_service.app import create_app


@pytest.fixture(scope="session")
def app_server():
    app = create_app()
    try:
        server = make_server("127.0.0.1", 0, app)
    except (OSError, SystemExit) as exc:  # e.g. sandboxed environments that block binding
        pytest.skip(f"Skipping preview test; unable to bind test server: {exc}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    yield base_url
    with suppress(Exception):
        server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def _wait_for_previews(page):
    page.wait_for_selector(".bb-preview-trigger img", state="visible", timeout=15000)


def _has_significant_invert(filter_value: str, *, threshold: float = 0.1) -> bool:
    match = re.search(r"invert\(([^)]+)\)", filter_value)
    if match:
        try:
            amount = float(match.group(1))
            return amount > threshold
        except ValueError:
            return "invert" in filter_value
    return "invert" in filter_value


def _force_dark_theme(page):
    theme_select = page.query_selector("#themeSelect")
    if theme_select is None:
        pytest.skip("Theme selector not available; cannot verify dark mode previews.")
    page.select_option("#themeSelect", "dark")
    page.wait_for_timeout(100)


def test_dark_mode_inverts_previews(app_server, browser):
    page = browser.new_page(color_scheme="dark")
    page.goto(f"{app_server}/bb", wait_until="networkidle")
    _force_dark_theme(page)
    _wait_for_previews(page)

    filter_value = page.eval_on_selector(
        ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
    )
    assert _has_significant_invert(filter_value.lower(), threshold=0.2)

    page.hover(".bb-preview-trigger img")
    page.wait_for_timeout(200)
    hover_filter = page.eval_on_selector(
        ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
    )
    hover_filter_normalized = hover_filter.strip().lower()
    assert hover_filter_normalized in {"none", ""} or not _has_significant_invert(
        hover_filter_normalized, threshold=0.01
    )
