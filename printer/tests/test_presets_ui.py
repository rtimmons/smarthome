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

    def list_presets(
        self, *, sort_by: str = "created", direction: str = "desc", limit: int = 200
    ) -> list[Preset]:
        presets = list(self._presets.values())
        sort_attributes = {
            "name": "name",
            "slug": "slug",
            "template": "template",
            "created": "created_at",
            "updated": "updated_at",
            "prints": "print_count",
        }
        attribute = sort_attributes.get(sort_by, "created_at")
        presets.sort(key=lambda preset: getattr(preset, attribute), reverse=direction != "asc")
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
            print_count=existing.print_count if existing else 0,
        )
        self._presets[slug] = preset
        return preset

    def record_print(self, slug: str) -> Preset | None:
        existing = self._presets.get(slug)
        if existing is None:
            return None
        preset = Preset(
            slug=existing.slug,
            name=existing.name,
            template=existing.template,
            query=existing.query,
            params=existing.params,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            print_count=existing.print_count + 1,
        )
        self._presets[slug] = preset
        return preset

    def seed_preset(
        self,
        *,
        slug: str,
        name: str,
        template: str,
        created_at: str,
        updated_at: str,
        print_count: int,
    ) -> Preset:
        params = {"Line1": name}
        preset = Preset(
            slug=slug,
            name=name,
            template=template,
            query=canonical_query_string(template, params),
            params=params,
            created_at=created_at,
            updated_at=updated_at,
            print_count=print_count,
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


def _seed_sortable_presets(store: FakePresetStore) -> None:
    store.seed_preset(
        slug="zulu",
        name="Alpha",
        template="best_by",
        created_at="2024-03-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        print_count=2,
    )
    store.seed_preset(
        slug="alpha",
        name="Charlie",
        template="bluey_label",
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-03-01T00:00:00+00:00",
        print_count=1,
    )
    store.seed_preset(
        slug="mike",
        name="Bravo",
        template="bb_2_weeks",
        created_at="2024-02-01T00:00:00+00:00",
        updated_at="2024-02-01T00:00:00+00:00",
        print_count=3,
    )


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
        row_locator = page.locator("#presetListBody tr")
        row_locator.wait_for(timeout=5000)
        row_text = row_locator.first.text_content()
        assert row_text
        assert "Oat Milk" in row_text
        assert preset.slug in row_text
        assert "bluey_label" in row_text
        cells = row_locator.first.locator("td").all_text_contents()
        assert len(cells) == 6
        assert cells[:3] == ["Oat Milk", preset.slug, "bluey_label"]
        assert cells[3].strip()
        assert cells[4].strip() == "0"
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
        page.wait_for_selector('#presetListBody tr:has-text("Quick Pick")', timeout=5000)
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

        row = page.locator("#presetListBody tr", has_text="Quick Pick")
        row.locator('button:has-text("Delete")').click()
        page.wait_for_selector("#presetEmpty", state="visible", timeout=5000)
        page.close()

    _run_playwright(run)
    assert len(fake_store._presets) == 0


def test_preset_table_defaults_to_newest_and_sorts_every_data_column(app_server, fake_store):
    _seed_sortable_presets(fake_store)
    target_url = f"{app_server}/bb?tpl=bluey_label"

    def run(browser):
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(target_url, wait_until="networkidle")
        page.wait_for_selector("#presetListBody tr", timeout=5000)

        def wait_for_names(expected):
            page.wait_for_function(
                """
                expected => Array.from(
                    document.querySelectorAll('#presetListBody tr td:first-child')
                ).map(cell => cell.textContent.trim()).join('|') === expected.join('|')
                """,
                arg=expected,
                timeout=5000,
            )

        wait_for_names(["Alpha", "Bravo", "Charlie"])
        assert page.locator("#presetList").evaluate("node => node.tagName") == "TABLE"
        panel_box = page.locator("#presetPanel").bounding_box()
        form_grid_box = page.locator(".form-grid").bounding_box()
        assert panel_box is not None
        assert form_grid_box is not None
        assert panel_box["width"] >= form_grid_box["width"] - 1
        cell_padding = page.locator("#presetListBody td").first.evaluate(
            "node => Number.parseFloat(getComputedStyle(node).paddingTop)"
        )
        assert cell_padding >= 12

        sort_buttons = page.locator("button[data-preset-sort]")
        assert sort_buttons.count() == 5
        assert set(
            sort_buttons.evaluate_all("nodes => nodes.map(node => node.dataset.presetSort)")
        ) == {
            "name",
            "slug",
            "template",
            "created",
            "prints",
        }
        assert sort_buttons.evaluate_all("nodes => nodes.every(node => node.tagName === 'BUTTON')")

        created_header = page.locator('th:has(button[data-preset-sort="created"])')
        assert created_header.get_attribute("aria-sort") == "descending"

        ascending_names = {
            "created": ["Charlie", "Bravo", "Alpha"],
            "name": ["Alpha", "Bravo", "Charlie"],
            "slug": ["Charlie", "Bravo", "Alpha"],
            "template": ["Bravo", "Alpha", "Charlie"],
            "prints": ["Charlie", "Alpha", "Bravo"],
        }
        for sort_by, expected in ascending_names.items():
            button = page.locator(f'button[data-preset-sort="{sort_by}"]')
            header = page.locator(f'th:has(button[data-preset-sort="{sort_by}"])')

            button.click()
            wait_for_names(expected)
            assert header.get_attribute("aria-sort") == "ascending"

            button.click()
            wait_for_names(list(reversed(expected)))
            assert header.get_attribute("aria-sort") == "descending"

        name_button = page.locator('button[data-preset-sort="name"]')
        name_button.focus()
        name_button.press("Enter")
        wait_for_names(["Alpha", "Bravo", "Charlie"])
        assert (
            page.locator('th:has(button[data-preset-sort="name"])').get_attribute("aria-sort")
            == "ascending"
        )

        rows = page.locator("#presetListBody tr")
        displayed = {
            (row.locator("td").nth(0).text_content() or "").strip(): row.locator(
                "td"
            ).all_text_contents()
            for row in rows.all()
        }
        assert all(cells[3].strip() for cells in displayed.values())
        assert {name: cells[4].strip() for name, cells in displayed.items()} == {
            "Alpha": "2",
            "Bravo": "3",
            "Charlie": "1",
        }
        page.close()

    _run_playwright(run)
