"""Browser coverage for the saved-PNG archive workflow."""

from __future__ import annotations

import threading
from contextlib import suppress
from pathlib import Path
from typing import Callable

import pytest
from PIL import Image
from playwright.sync_api import Browser, sync_playwright
from werkzeug.serving import make_server

from printer_service.app import create_app

pytestmark = pytest.mark.ui


def _run_playwright(action: Callable[[Browser], None]) -> None:
    error: dict[str, Exception] = {}

    def runner() -> None:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    action(browser)
                finally:
                    browser.close()
        except Exception as exc:
            error["exception"] = exc

    # Keep the sync Playwright client out of any asyncio loop used by another UI test.
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=30)
    if thread.is_alive():
        raise RuntimeError("Saved-PNG Playwright test timed out.")
    if "exception" in error:
        raise error["exception"]


@pytest.fixture
def png_archive_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archive_dir = tmp_path / "printed-labels"
    source_path = tmp_path / "poison.png"
    Image.new("RGB", (390, 720), "white").save(source_path, format="PNG")
    monkeypatch.setenv("PRINTED_LABELS_DIR", str(archive_dir))
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(tmp_path / "printer-output.png"))
    app = create_app()
    try:
        server = make_server("127.0.0.1", 0, app)
    except (OSError, SystemExit) as exc:
        pytest.skip(f"Skipping saved-PNG UI test; unable to bind test server: {exc}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", source_path, archive_dir
    with suppress(Exception):
        server.shutdown()
    thread.join(timeout=5)


def test_upload_reprint_and_delete_saved_png_from_ui(png_archive_server) -> None:
    base_url, source_path, archive_dir = png_archive_server

    def run(browser: Browser) -> None:
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        try:
            page.goto(f"{base_url}/png", wait_until="networkidle")
            page.wait_for_selector("#pngArchiveEmpty", state="visible", timeout=5000)

            page.locator("#pngFile").set_input_files(source_path)
            page.wait_for_function(
                """() => document.getElementById('labelPreviewImage').dataset.hasPreview === 'true'""",
                timeout=5000,
            )
            page.locator("#pngPrintTrigger").click()
            page.locator("#printNowButton").click()
            row = page.locator('#pngArchiveListBody tr:has-text("poison.png")')
            row.wait_for(timeout=5000)
            assert row.locator("td").nth(3).text_content() == "1"
            assert page.locator("[data-png-archive-sort]").count() == 3
            assert (
                page.locator('[data-png-archive-sort-header="created"]').get_attribute("aria-sort")
                == "descending"
            )
            page.wait_for_selector("#printCountdownContainer", state="hidden", timeout=5000)

            row.locator('button:has-text("Reprint")').click()
            page.wait_for_selector("#printCountdownContainer", state="visible", timeout=5000)
            page.locator("#printNowButton").click()
            page.wait_for_function(
                """() => {
                    const cell = document.querySelector('#pngArchiveListBody tr td:nth-child(4)');
                    return cell && cell.textContent.trim() === '2';
                }""",
                timeout=5000,
            )
            assert len(list(archive_dir.glob("*.png"))) == 1

            page.on("dialog", lambda dialog: dialog.accept())
            page.locator('#pngArchiveListBody button:has-text("Delete")').click()
            page.wait_for_selector("#pngArchiveEmpty", state="visible", timeout=5000)
            assert list(archive_dir.glob("*.png")) == []
        finally:
            page.close()

    _run_playwright(run)
