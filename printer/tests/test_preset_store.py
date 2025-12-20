from __future__ import annotations

from typing import Any

import pytest

import printer_service.presets as presets
from printer_service.presets import PresetStore, canonical_params, canonical_query_string, slug_for_params


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self._docs.sort(key=lambda doc: doc.get(key, ""), reverse=reverse)
        return self

    def limit(self, limit: int):
        self._docs = self._docs[:limit]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, _query):
        return FakeCursor(list(self._docs.values()))

    def find_one(self, query, projection=None):
        slug = query.get("slug")
        if not slug:
            return None
        doc = self._docs.get(slug)
        if doc is None:
            return None
        if projection:
            return {key: doc.get(key) for key, enabled in projection.items() if enabled}
        return doc

    def find_one_and_update(self, query, update, upsert, return_document):
        slug = query.get("slug")
        if not slug:
            return None
        doc = self._docs.get(slug)
        is_new = doc is None
        if doc is None:
            if not upsert:
                return None
            doc = {"slug": slug}
        if "$setOnInsert" in update and is_new:
            for key, value in update["$setOnInsert"].items():
                doc.setdefault(key, value)
        if "$set" in update:
            doc.update(update["$set"])
        self._docs[slug] = doc
        return doc

    def delete_one(self, query):
        slug = query.get("slug")
        if slug in self._docs:
            del self._docs[slug]
            return FakeDeleteResult(1)
        return FakeDeleteResult(0)


class FakeClient:
    def close(self) -> None:
        return None


def _make_store(collection: FakeCollection) -> PresetStore:
    store = PresetStore.__new__(PresetStore)
    store._client = FakeClient()
    store._collection = collection
    return store


def test_preset_store_upsert_normalizes_payload() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    params = {
        "Line1": " Oat ",
        "Line2": "",
        "Tags": ["b", " ", "a"],
        "Count": 0,
        "Enabled": False,
        "template": "ignored",
    }

    preset = store.upsert_preset("  Oat Milk  ", "Bluey_Label", params)

    expected_query = canonical_query_string("bluey_label", params)
    expected_slug = slug_for_params("bluey_label", params)
    assert preset.slug == expected_slug
    assert preset.name == "Oat Milk"
    assert preset.template == "bluey_label"
    assert preset.query == expected_query
    assert preset.params == canonical_params(params)
    assert store.find_by_slug(expected_slug) is not None


def test_preset_store_upsert_preserves_created_at(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    times = iter(
        [
            "2024-01-01T00:00:00+00:00",
            "2024-01-01T00:01:00+00:00",
        ]
    )
    monkeypatch.setattr(presets, "_utc_now_iso", lambda: next(times))
    params = {"Line1": "Oat"}

    first = store.upsert_preset("Oat Milk", "bluey_label", params)
    second = store.upsert_preset("Oat Milk Updated", "bluey_label", params)

    assert first.slug == second.slug
    assert first.created_at == "2024-01-01T00:00:00+00:00"
    assert second.created_at == "2024-01-01T00:00:00+00:00"
    assert second.updated_at == "2024-01-01T00:01:00+00:00"
    assert second.name == "Oat Milk Updated"


def test_preset_store_list_presets_sorting(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    times = iter(
        [
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
        ]
    )
    monkeypatch.setattr(presets, "_utc_now_iso", lambda: next(times))

    store.upsert_preset("Alpha", "bluey_label", {"Line1": "A"})
    store.upsert_preset("Bravo", "bluey_label", {"Line1": "B"})

    names = [preset.name for preset in store.list_presets()]
    assert names == ["Alpha", "Bravo"]

    updated = [preset.name for preset in store.list_presets(sort_by="updated")]
    assert updated == ["Bravo", "Alpha"]


def test_preset_store_find_slug_for_params() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    params = {"Line1": "Oat"}
    preset = store.upsert_preset("Oat", "bluey_label", params)

    assert store.find_slug_for_params("bluey_label", params) == preset.slug
    assert store.find_slug_for_params("bluey_label", {"Line1": "Other"}) is None


def test_preset_store_delete() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    preset = store.upsert_preset("Oat", "bluey_label", {"Line1": "Oat"})

    assert store.delete_preset(preset.slug) is True
    assert store.delete_preset(preset.slug) is False
