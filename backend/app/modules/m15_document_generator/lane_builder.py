"""Build immutable documents from API-friendly mappings."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from .lane_models import Claim, Document, DocumentError, Evidence, Section, Source


class DocumentBuilder:
    """Parse an untrusted outline while rejecting silent schema mistakes."""

    _DOCUMENT_FIELDS = {"title", "subtitle", "metadata", "sources", "sections", "created_at"}
    _SOURCE_FIELDS = {"id", "title", "content", "url", "author", "published_at", "metadata"}
    _SECTION_FIELDS = {"heading", "level", "prose", "claims"}
    _CLAIM_FIELDS = {"text", "evidence"}
    _EVIDENCE_FIELDS = {"source_id", "quote", "start", "end"}

    def build(self, payload: Mapping[str, Any]) -> Document:
        self._fields(payload, self._DOCUMENT_FIELDS, "document")
        sources = tuple(self._source(value, i) for i, value in enumerate(self._array(payload, "sources", ())))
        sections = tuple(self._section(value, i) for i, value in enumerate(self._array(payload, "sections")))
        created_at = payload.get("created_at")
        return Document(
            title=self._string(payload, "title"),
            subtitle=self._optional_string(payload, "subtitle"),
            sections=sections,
            sources=sources,
            metadata=self._mapping(payload.get("metadata", {}), "document.metadata"),
            created_at=self._datetime(created_at, "document.created_at") if created_at is not None else None,
        ) if created_at is not None else Document(
            title=self._string(payload, "title"),
            subtitle=self._optional_string(payload, "subtitle"),
            sections=sections,
            sources=sources,
            metadata=self._mapping(payload.get("metadata", {}), "document.metadata"),
        )

    def _source(self, value: Any, index: int) -> Source:
        path = f"sources[{index}]"
        data = self._mapping(value, path)
        self._fields(data, self._SOURCE_FIELDS, path)
        published = data.get("published_at")
        return Source(
            id=self._string(data, "id", path), title=self._string(data, "title", path),
            content=self._string(data, "content", path),
            url=self._optional_string(data, "url", path),
            author=self._optional_string(data, "author", path),
            published_at=self._datetime(published, f"{path}.published_at") if published is not None else None,
            metadata=self._mapping(data.get("metadata", {}), f"{path}.metadata"),
        )

    def _section(self, value: Any, index: int) -> Section:
        path = f"sections[{index}]"
        data = self._mapping(value, path)
        self._fields(data, self._SECTION_FIELDS, path)
        claims = tuple(self._claim(item, f"{path}.claims[{i}]") for i, item in enumerate(self._array(data, "claims", (), path)))
        level = data.get("level", 2)
        if isinstance(level, bool) or not isinstance(level, int):
            raise DocumentError(f"{path}.level must be an integer")
        return Section(self._string(data, "heading", path), claims, level, self._optional_string(data, "prose", path))

    def _claim(self, value: Any, path: str) -> Claim:
        data = self._mapping(value, path)
        self._fields(data, self._CLAIM_FIELDS, path)
        evidence = tuple(self._evidence(item, f"{path}.evidence[{i}]") for i, item in enumerate(self._array(data, "evidence", (), path)))
        return Claim(self._string(data, "text", path), evidence)

    def _evidence(self, value: Any, path: str) -> Evidence:
        data = self._mapping(value, path)
        self._fields(data, self._EVIDENCE_FIELDS, path)
        start, end = data.get("start"), data.get("end")
        for name, offset in (("start", start), ("end", end)):
            if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int)):
                raise DocumentError(f"{path}.{name} must be an integer")
        return Evidence(self._string(data, "source_id", path), self._string(data, "quote", path), start, end)

    @staticmethod
    def _fields(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
        unknown = set(value) - allowed
        if unknown:
            raise DocumentError(f"unknown fields at {path}: {sorted(unknown)}")

    @staticmethod
    def _mapping(value: Any, path: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise DocumentError(f"{path} must be an object")
        return value

    def _array(self, value: Mapping[str, Any], key: str, default: Any = None, path: str = "document") -> Sequence[Any]:
        result = value.get(key, default)
        if result is None:
            raise DocumentError(f"{path}.{key} is required")
        if isinstance(result, (str, bytes)) or not isinstance(result, Sequence):
            raise DocumentError(f"{path}.{key} must be an array")
        return result

    @staticmethod
    def _string(value: Mapping[str, Any], key: str, path: str = "document") -> str:
        result = value.get(key)
        if not isinstance(result, str):
            raise DocumentError(f"{path}.{key} must be a string")
        return result

    @staticmethod
    def _optional_string(value: Mapping[str, Any], key: str, path: str = "document") -> str | None:
        result = value.get(key)
        if result is not None and not isinstance(result, str):
            raise DocumentError(f"{path}.{key} must be a string or null")
        return result

    @staticmethod
    def _datetime(value: Any, path: str) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DocumentError(f"{path} must be an ISO 8601 datetime") from exc
        raise DocumentError(f"{path} must be an ISO 8601 datetime")
