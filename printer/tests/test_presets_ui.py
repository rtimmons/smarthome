"""UI tests for preset controls in the printer service."""

from __future__ import annotations

import threading
from contextlib import suppress
from datetime import datetime, timezone
from importlib import import_module

import pytest
from werkzeug.serving import make_server

from printer_service.presets import Preset, canonical_query_string, slug_for_params

app_module = import_module("printer_service.app")

pytestmark = pytest.mark.ui


class FakePresetStore:
    def __init__(self) -> None:
        self._presets: dict[str, Preset] = {}

    def list_presets(self, *, sort_by: str = "name", limit: int = 200) -> list[Preset]:
        presets = list(self._presets.values())
        if sort_by == "updated":
            presets.sort(key=lambda preset: preset.updated_at, reverse=True)
        else:
            presets.sort(key=lambda preset: preset.name)
        return presets[:limit]

    def find_by_slug(self, slug: str) -> Preset | None:
        return self._presets.get(slug)

    def find_slug_for_params(self, template_slug: str, params: dict) -> str | None:
        slug = slug_for_params(template_slug, params)
        return slug if slug in self._presets else None

    def upsert_preset(self, name: str, template_slug: str, params: dict) -> Preset:
        safe_params = dict(params)
        slug = slug_for_params(template_slug, safe_params)
        now = datetime.now(timezone.utc).isoformat()
        existing = self._presets.get(slug)
        created_at = existing.created_at if existing else now
        preset = Preset(
            slug=slug,
            name=name,
            template=template_slug,
            query=canonical_query_string(template_slug, safe_params),
            params=safe_params,
            created_at=created_at,
            updated_at=now,
        )
        self._presets[slug] = preset
        return preset

    def delete_preset(self, slug: str) -> bool:
        return self._presets.pop(slug, None) is not None

    def close(self) -> None:
        return None


@pytest.fixture
def fake_store() -> FakePresetStore:
    return FakePresetStore()


@pytest.fixture
def app_server(fake_store: FakePresetStore, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "_get_preset_store", lambda: fake_store)
    app = app_module.create_app()
    try:
        server = make_server("127.0.0.1", 0, app)
    except (OSError, SystemExit) as exc:
        pytest.skip(f"Skipping preset UI test; unable to bind test server: {exc}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    yield base_url
    with suppress(Exception):
        server.shutdown()
    thread.join(timeout=5)


def _run_playwright(action):
    error: dict[str, Exception] = {}

    def runner():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    action(browser)
                finally:
                    browser.close()
        except Exception as exc:
            error["exception"] = exc

    # Avoid sync Playwright conflicts if an asyncio loop is active in the test thread.
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=30)
    if thread.is_alive():
        raise RuntimeError("Playwright test timed out.")
    if "exception" in error:
        raise error["exception"]


def test_preset_list_renders_seeded_preset(app_server, fake_store):
    params = {"Line1": "Oat", "Line2": "Milk"}
    preset = fake_store.upsert_preset("Oat Milk", "bluey_label", params)
    target_url = f"{app_server}/bb?tpl=bluey_label"

    def run(browser):
        page = browser.new_page()
        page.goto(target_url, wait_until="networkidle")
        row_locator = page.locator("#presetListBody .preset-row")
        row_locator.wait_for(timeout=5000)
        row_text = row_locator.first.text_content()
        assert row_text
        assert "Oat Milk" in row_text
        assert preset.slug in row_text
        assert "bluey_label" in row_text
        page.close()

    _run_playwright(run)


def test_save_and_delete_preset_flow(app_server, fake_store):
    target_url = f"{app_server}/bb?tpl=bluey_label"

    def run(browser):
        page = browser.new_page()
        page.goto(target_url, wait_until="networkidle")
        page.wait_for_selector("#qrPreviewUrl", state="visible", timeout=5000)
        initial_href = page.locator("#qrPreviewUrlLink").get_attribute("href")
        assert initial_href
        assert "/p/" not in initial_href

        def handle_dialog(dialog):
            if dialog.type == "prompt":
                dialog.accept("Quick Pick")
            else:
                dialog.accept()

        page.on("dialog", handle_dialog)
        page.click("#savePresetButton")
        page.wait_for_selector('#presetListBody .preset-row:has-text("Quick Pick")', timeout=5000)
        page.wait_for_function(
            """
            () => {
                const link = document.getElementById('qrPreviewUrlLink');
                return link && link.getAttribute('href') && link.getAttribute('href').includes('/p/');
            }
            """,
            timeout=5000,
        )
        updated_href = page.locator("#qrPreviewUrlLink").get_attribute("href")
        assert updated_href
        assert "/p/" in updated_href
        assert len(fake_store._presets) == 1

        row = page.locator("#presetListBody .preset-row", has_text="Quick Pick")
        row.locator('button:has-text("Delete")').click()
        page.wait_for_selector("#presetEmpty", state="visible", timeout=5000)
        page.close()

    _run_playwright(run)
    assert len(fake_store._presets) == 0
