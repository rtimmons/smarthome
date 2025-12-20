from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlencode

from .label_templates import TemplateFormValue
from .mongo import DEFAULT_DB, MongoConfig, load_mongo_config

if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.collection import Collection


_CONTROL_PARAM_KEYS = {"tpl", "template", "template_slug"}


@dataclass(frozen=True)
class Preset:
    slug: str
    name: str
    template: str
    query: str
    params: Optional[Mapping[str, object]]
    created_at: str
    updated_at: str

    @classmethod
    def from_document(cls, doc: Mapping[str, object]) -> "Preset":
        params = doc.get("params")
        return cls(
            slug=str(doc.get("slug") or ""),
            name=str(doc.get("name") or ""),
            template=str(doc.get("template") or ""),
            query=str(doc.get("query") or ""),
            params=params if isinstance(params, Mapping) else None,
            created_at=str(doc.get("created_at") or ""),
            updated_at=str(doc.get("updated_at") or ""),
        )


class PresetStore:
    def __init__(self, client: "MongoClient", database: str) -> None:
        self._client = client
        self._collection: Collection = client[database]["presets"]

    @classmethod
    def from_env(cls) -> Optional["PresetStore"]:
        config = load_mongo_config()
        if config is None:
            return None
        MongoClient = _require_pymongo()
        client = MongoClient(config.url, serverSelectionTimeoutMS=2000)
        store = cls(client, _resolve_database(config))
        store.ensure_indexes()
        return store

    @property
    def collection(self) -> Collection:
        return self._collection

    def close(self) -> None:
        self._client.close()

    def ensure_indexes(self) -> None:
        self._collection.create_index("slug", unique=True)
        self._collection.create_index("name")
        self._collection.create_index("updated_at")

    def list_presets(self, *, sort_by: str = "name", limit: int = 200) -> list[Preset]:
        if sort_by == "updated":
            sort_key, sort_dir = "updated_at", -1
        else:
            sort_key, sort_dir = "name", 1
        cursor = self._collection.find({}).sort(sort_key, sort_dir).limit(limit)
        return [Preset.from_document(doc) for doc in cursor]

    def find_by_slug(self, slug: str) -> Optional[Preset]:
        normalized = str(slug or "").strip()
        if not normalized:
            return None
        doc = self._collection.find_one({"slug": normalized})
        return Preset.from_document(doc) if doc else None

    def find_slug_for_params(
        self, template_slug: str, params: Mapping[str, TemplateFormValue]
    ) -> Optional[str]:
        canonical_query = canonical_query_string(template_slug, params)
        slug = slug_from_query(canonical_query)
        doc = self._collection.find_one({"slug": slug}, {"slug": 1})
        return slug if doc else None

    def upsert_preset(
        self,
        name: str,
        template_slug: str,
        params: Mapping[str, TemplateFormValue],
    ) -> Preset:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required.")
        normalized_template = normalize_template_slug(template_slug)
        canonical_query = canonical_query_string(normalized_template, params)
        slug = slug_from_query(canonical_query)
        now = _utc_now_iso()
        payload = {
            "slug": slug,
            "name": normalized_name,
            "template": normalized_template,
            "query": canonical_query,
            "params": canonical_params(params),
            "updated_at": now,
        }
        from pymongo import ReturnDocument

        doc = self._collection.find_one_and_update(
            {"slug": slug},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            doc = self._collection.find_one({"slug": slug})
        if doc is None:
            raise RuntimeError("Failed to save preset.")
        return Preset.from_document(doc)

    def delete_preset(self, slug: str) -> bool:
        normalized = str(slug or "").strip()
        if not normalized:
            return False
        result = self._collection.delete_one({"slug": normalized})
        return result.deleted_count > 0


def normalize_template_slug(raw: object) -> str:
    slug = str(raw or "").strip().lower()
    if not slug:
        raise ValueError("Template slug is required.")
    return slug


def canonical_params(params: Mapping[str, TemplateFormValue]) -> dict[str, str | list[str]]:
    canonical: dict[str, str | list[str]] = {}
    for key in sorted(params.keys(), key=lambda item: str(item)):
        normalized_key = _normalize_key(key)
        if not normalized_key:
            continue
        if normalized_key.lower() in _CONTROL_PARAM_KEYS:
            continue
        normalized_value = _normalize_form_value(params[key])
        if normalized_value is None:
            continue
        canonical[normalized_key] = normalized_value
    return canonical


def canonical_query_items(
    template_slug: str, params: Mapping[str, TemplateFormValue]
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = [("tpl", normalize_template_slug(template_slug))]
    for key, value in canonical_params(params).items():
        if isinstance(value, list):
            for item in value:
                items.append((key, item))
        else:
            items.append((key, value))
    return items


def canonical_query_string(template_slug: str, params: Mapping[str, TemplateFormValue]) -> str:
    return urlencode(canonical_query_items(template_slug, params), doseq=True)


def slug_from_query(canonical_query: str) -> str:
    if not canonical_query:
        raise ValueError("Canonical query string is required for slug hashing.")
    digest = hashlib.blake2b(canonical_query.encode("utf-8"), digest_size=8).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=")
    return encoded.decode("ascii")


def slug_for_params(template_slug: str, params: Mapping[str, TemplateFormValue]) -> str:
    return slug_from_query(canonical_query_string(template_slug, params))


def _normalize_key(value: object) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_form_value(value: TemplateFormValue) -> Optional[str | list[str]]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _normalize_string(value)
    if isinstance(value, Mapping):
        normalized = _normalize_json_value(value)
        if normalized is None:
            return None
        return _dump_json(normalized)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items: list[str] = []
        for item in value:
            normalized_item = _normalize_json_value(item)
            if normalized_item is None:
                continue
            if isinstance(normalized_item, (dict, list)):
                items.append(_dump_json(normalized_item))
            else:
                items.append(_stringify_scalar(normalized_item))
        return items or None
    normalized = _normalize_string(str(value))
    return normalized or None


def _normalize_string(value: str) -> Optional[str]:
    normalized = value.strip()
    return normalized or None


def _normalize_json_value(value: TemplateFormValue) -> Optional[object]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _normalize_string(value)
    if isinstance(value, Mapping):
        normalized_map: dict[str, object] = {}
        for key in sorted(value.keys(), key=lambda item: str(item)):
            normalized_key = _normalize_key(key)
            if not normalized_key:
                continue
            normalized_value = _normalize_json_value(value[key])
            if normalized_value is None:
                continue
            normalized_map[normalized_key] = normalized_value
        return normalized_map or None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items: list[object] = []
        for item in value:
            normalized_item = _normalize_json_value(item)
            if normalized_item is None:
                continue
            items.append(normalized_item)
        return items or None
    normalized_str = _normalize_string(str(value))
    return normalized_str or None


def _stringify_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _dump_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _resolve_database(config: MongoConfig) -> str:
    return config.database or DEFAULT_DB


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_pymongo():
    try:
        from pymongo import MongoClient
    except Exception as exc:
        raise RuntimeError(
            "pymongo is required for presets storage; install it with the printer service "
            "dependencies."
        ) from exc
    return MongoClient


__all__ = [
    "Preset",
    "PresetStore",
    "canonical_params",
    "canonical_query_items",
    "canonical_query_string",
    "normalize_template_slug",
    "slug_for_params",
    "slug_from_query",
]
