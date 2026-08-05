from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

import printer_service.presets as presets
from printer_service.label_templates import TemplateFormValue
from printer_service.presets import (
    Preset,
    PresetStore,
    canonical_params,
    canonical_query_string,
    slug_for_params,
)

if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.collection import Collection


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
        self.find_one_and_update_calls: list[dict[str, Any]] = []

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

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        self.find_one_and_update_calls.append(
            {
                "query": query,
                "update": update,
                "upsert": upsert,
                "return_document": return_document,
            }
        )
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
        if "$inc" in update:
            for key, value in update["$inc"].items():
                doc[key] = doc.get(key, 0) + value
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
    store._client = cast("MongoClient", FakeClient())
    store._collection = cast("Collection", collection)
    return store


def test_preset_store_upsert_normalizes_payload() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    params: dict[str, TemplateFormValue] = {
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
    assert preset.print_count == 0
    assert store.find_by_slug(expected_slug) is not None


def test_preset_from_document_defaults_legacy_print_count_to_zero() -> None:
    preset = Preset.from_document(
        {
            "slug": "legacy",
            "name": "Legacy preset",
            "template": "bluey_label",
            "query": "tpl=bluey_label&Line1=Legacy",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
    )

    assert preset.print_count == 0


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
    params: dict[str, TemplateFormValue] = {"Line1": "Oat"}

    first = store.upsert_preset("Oat Milk", "bluey_label", params)
    second = store.upsert_preset("Oat Milk Updated", "bluey_label", params)

    assert first.slug == second.slug
    assert first.created_at == "2024-01-01T00:00:00+00:00"
    assert second.created_at == "2024-01-01T00:00:00+00:00"
    assert second.updated_at == "2024-01-01T00:01:00+00:00"
    assert second.name == "Oat Milk Updated"
    assert second.print_count == 0


def test_preset_store_list_presets_defaults_to_newest_created() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    collection._docs = _sortable_preset_documents()

    assert [preset.name for preset in store.list_presets()] == ["Alpha", "Bravo", "Charlie"]


@pytest.mark.parametrize(
    ("sort_by", "expected_names"),
    [
        ("name", ["Alpha", "Bravo", "Charlie"]),
        ("slug", ["Charlie", "Bravo", "Alpha"]),
        ("template", ["Bravo", "Alpha", "Charlie"]),
        ("created", ["Charlie", "Bravo", "Alpha"]),
        ("updated", ["Alpha", "Bravo", "Charlie"]),
        ("prints", ["Charlie", "Alpha", "Bravo"]),
    ],
)
def test_preset_store_sorts_every_supported_column_in_both_directions(
    sort_by: str, expected_names: list[str]
) -> None:
    collection = FakeCollection()
    collection._docs = _sortable_preset_documents()
    store = _make_store(collection)

    ascending = [preset.name for preset in store.list_presets(sort_by=sort_by, direction="asc")]
    descending = [preset.name for preset in store.list_presets(sort_by=sort_by, direction="desc")]

    assert ascending == expected_names
    assert descending == list(reversed(expected_names))


def _sortable_preset_documents() -> dict[str, dict[str, Any]]:
    return {
        "zulu": {
            "slug": "zulu",
            "name": "Alpha",
            "template": "best_by",
            "query": "tpl=best_by&Text=Alpha",
            "params": {"Text": "Alpha"},
            "created_at": "2024-03-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
            "print_count": 2,
        },
        "alpha": {
            "slug": "alpha",
            "name": "Charlie",
            "template": "bluey_label",
            "query": "tpl=bluey_label&Line1=Charlie",
            "params": {"Line1": "Charlie"},
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-03-01T00:00:00+00:00",
            "print_count": 1,
        },
        "mike": {
            "slug": "mike",
            "name": "Bravo",
            "template": "bb_2_weeks",
            "query": "tpl=bb_2_weeks&Text=Bravo",
            "params": {"Text": "Bravo"},
            "created_at": "2024-02-01T00:00:00+00:00",
            "updated_at": "2024-02-01T00:00:00+00:00",
            "print_count": 3,
        },
    }


def test_preset_store_find_slug_for_params() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    params: dict[str, TemplateFormValue] = {"Line1": "Oat"}
    preset = store.upsert_preset("Oat", "bluey_label", params)

    assert store.find_slug_for_params("bluey_label", params) == preset.slug
    assert store.find_slug_for_params("bluey_label", {"Line1": "Other"}) is None


def test_preset_store_record_print_atomically_increments_without_upserting() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    preset = store.upsert_preset("Oat", "bluey_label", {"Line1": "Oat"})
    original_updated_at = preset.updated_at

    first = store.record_print(preset.slug)
    second = store.record_print(preset.slug)

    assert first is not None
    assert first.print_count == 1
    assert second is not None
    assert second.print_count == 2
    assert second.updated_at == original_updated_at
    assert collection.find_one_and_update_calls[-1]["update"]["$inc"]["print_count"] == 1
    assert collection.find_one_and_update_calls[-1]["upsert"] is False

    assert store.record_print("missing") is None
    assert "missing" not in collection._docs


def test_preset_store_delete() -> None:
    collection = FakeCollection()
    store = _make_store(collection)
    preset = store.upsert_preset("Oat", "bluey_label", {"Line1": "Oat"})

    assert store.delete_preset(preset.slug) is True
    assert store.delete_preset(preset.slug) is False


def test_preset_store_exposes_index_helpers() -> None:
    assert hasattr(PresetStore, "ensure_indexes")


def test_get_cached_store_uses_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _fake_from_env():
        calls["count"] += 1
        return None

    monkeypatch.setattr(presets.PresetStore, "from_env", _fake_from_env)

    presets.reset_cached_store()
    assert presets.get_cached_store() is None
    assert presets.get_cached_store() is None
    assert calls["count"] == 1


def test_get_cached_store_backs_off_after_init_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    now = {"value": 100.0}

    def _fake_monotonic() -> float:
        return now["value"]

    def _raise_connection_error():
        calls["count"] += 1
        raise ConnectionError("mongodb unavailable")

    monkeypatch.setattr(presets.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(presets.PresetStore, "from_env", _raise_connection_error)

    presets.reset_cached_store()
    with pytest.raises(ConnectionError):
        presets.get_cached_store()

    assert presets.get_cached_store() is None
    assert calls["count"] == 1

    now["value"] += presets._STORE_ERROR_TTL_SECONDS + 0.1
    with pytest.raises(ConnectionError):
        presets.get_cached_store()
    assert calls["count"] == 2


def test_cached_store_close_is_noop() -> None:
    class FakeTrackedClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    store = PresetStore.__new__(PresetStore)
    store._client = cast("MongoClient", FakeTrackedClient())
    store._collection = cast("Collection", FakeCollection())
    store._cached = True

    store.close()
    assert store._client.closed is False

    store._cached = False
    store.close()
    assert store._client.closed is True
