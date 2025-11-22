from __future__ import annotations

import threading
from contextlib import suppress

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


def test_dark_mode_inverts_previews(app_server, browser):
    page = browser.new_page(color_scheme="dark")
    page.goto(f"{app_server}/bb", wait_until="networkidle")
    _wait_for_previews(page)

    filter_value = page.eval_on_selector(
        ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
    )
    assert "invert" in filter_value.lower()

    page.hover(".bb-preview-trigger img")
    page.wait_for_timeout(200)
    hover_filter = page.eval_on_selector(
        ".bb-preview-trigger img", "el => getComputedStyle(el).filter"
    )
    hover_filter_normalized = hover_filter.strip().lower()
    assert hover_filter_normalized in {"none", ""} or "invert" not in hover_filter_normalized
