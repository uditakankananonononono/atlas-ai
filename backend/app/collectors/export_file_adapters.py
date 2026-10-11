"""Offline adapter over export files the caller already holds (CSV, JSON, JSONL).

Nothing here logs in, requests an export, scrapes, or opens a network connection: the
caller supplies a local file path and an explicit column mapping, and gets back the
normal ``CollectionBatch`` so the result can feed any job that drives the ``Collector``
protocol. No platform layout is assumed. ``PROFILES`` is empty on purpose: a named
profile may only be added for a layout confirmed against a real export, and none has
been. Every batch therefore reports ``layout_verified: False``.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
from typing import Any

from .base import CollectedItem, CollectionBatch

PROFILES: dict[str, dict[str, Any]] = {}
FORMATS = ("csv", "json", "jsonl")
DEFAULT_MAX_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_RECORDS = 500_000
MAX_REJECTED_LISTED = 50
RESERVED = frozenset({"provider", "source_file", "record_index", "kind", "platform"})
_CONFIG_KEYS = {"path", "format", "mapping", "record_path", "limit", "cursor", "max_bytes",
                "max_records", "kind", "platform"}
_MAPPING_KEYS = {"url", "external_id", "fields"}
_ARCHIVE_SUFFIXES = (".zip", ".gz", ".tgz", ".tar", ".7z", ".rar")
_MISSING = object()


class ExportAdapterError(ValueError):
    """Bad configuration, unreadable file, or a file that is not the declared format."""


def _pos_int(name: str, value: Any, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ExportAdapterError(f"{name} must be an integer >= {minimum}")
    return value


def _dig(obj: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return _MISSING
    return obj


def _validate(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ExportAdapterError("config must be an object")
    extra = set(config) - _CONFIG_KEYS
    if extra:
        raise ExportAdapterError(f"unknown config key(s) {sorted(extra)}")
    path = config.get("path")
    if not isinstance(path, (str, os.PathLike)) or not str(path).strip():
        raise ExportAdapterError("path is required")
    fmt = config.get("format")
    if fmt not in FORMATS:
        raise ExportAdapterError(f"format must be one of {FORMATS}")
    mapping = config.get("mapping")
    if not isinstance(mapping, dict) or not isinstance(mapping.get("url"), str) or not mapping["url"]:
        raise ExportAdapterError("mapping.url (the column or key holding each record's url) is required")
    extra = set(mapping) - _MAPPING_KEYS
    if extra:
        raise ExportAdapterError(f"unknown mapping key(s) {sorted(extra)}")
    ext = mapping.get("external_id")
    if ext is not None and (not isinstance(ext, str) or not ext):
        raise ExportAdapterError("mapping.external_id must be a non-empty string")
    fields = mapping.get("fields", {})
    if not isinstance(fields, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v
                                               for k, v in fields.items()):
        raise ExportAdapterError("mapping.fields must map output names to source names (strings)")
    clash = RESERVED & set(fields)
    if clash:
        raise ExportAdapterError(f"mapping.fields uses reserved output name(s) {sorted(clash)}")
    rp = config.get("record_path")
    if rp is not None and (not isinstance(rp, str) or not rp):
        raise ExportAdapterError("record_path must be a non-empty string")
    for label in ("kind", "platform"):
        if config.get(label) is not None and (not isinstance(config[label], str) or not config[label]):
            raise ExportAdapterError(f"{label} must be a non-empty string")
    out = {
        "path": os.fspath(path), "format": fmt, "url": mapping["url"], "external_id": ext,
        "fields": dict(fields), "record_path": rp,
        "max_bytes": _pos_int("max_bytes", config.get("max_bytes", DEFAULT_MAX_BYTES)),
        "max_records": _pos_int("max_records", config.get("max_records", DEFAULT_MAX_RECORDS)),
        "limit": None if config.get("limit") is None else _pos_int("limit", config["limit"]),
        "kind": config.get("kind"), "platform": config.get("platform"),
    }
    cur = config.get("cursor", 0)
    try:
        out["cursor"] = _pos_int("cursor", int(cur) if isinstance(cur, str) else cur, 0)
    except (ValueError, ExportAdapterError):
        raise ExportAdapterError("cursor must be a non-negative integer (or its string form)") from None
    return out


def _read_bytes(path: str, max_bytes: int) -> bytes:
    if not os.path.exists(path):
        raise ExportAdapterError(f"file not found: {os.path.basename(path)}")
    if not os.path.isfile(path):
        raise ExportAdapterError(f"not a regular file: {os.path.basename(path)}")
    if os.path.getsize(path) > max_bytes:
        raise ExportAdapterError(f"file larger than max_bytes={max_bytes}")
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ExportAdapterError(f"file larger than max_bytes={max_bytes}")
    if data[:4] == b"PK\x03\x04" or path.lower().endswith(_ARCHIVE_SUFFIXES):
        raise ExportAdapterError("archives are not read; extract the export and pass the file inside")
    return data


def _records(data: bytes, c: dict[str, Any]) -> list[Any]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExportAdapterError("file is not valid UTF-8") from exc
    fmt = c["format"]
    if fmt == "csv":
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""))
            header = reader.fieldnames or []
            need = [c["url"]] + ([c["external_id"]] if c["external_id"] else []) + list(c["fields"].values())
            for col in need:
                if col not in header:
                    raise ExportAdapterError(f"column '{col}' not found in the CSV header")
            rows = []
            for row in reader:
                rows.append(row)
                if len(rows) > c["max_records"]:
                    raise ExportAdapterError(f"more than max_records={c['max_records']} records")
            return rows
        except csv.Error as exc:
            raise ExportAdapterError(f"invalid CSV: {exc}") from exc
    if fmt == "jsonl":
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise ExportAdapterError(f"invalid JSON on line {n}") from exc
            if len(rows) > c["max_records"]:
                raise ExportAdapterError(f"more than max_records={c['max_records']} records")
        return rows
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise ExportAdapterError("file is not valid JSON") from exc
    if c["record_path"]:
        doc = _dig(doc, c["record_path"])
        if doc is _MISSING:
            raise ExportAdapterError(f"record_path '{c['record_path']}' not found")
    if not isinstance(doc, list):
        raise ExportAdapterError("records must be a JSON list (use record_path to point at one)")
    if len(doc) > c["max_records"]:
        raise ExportAdapterError(f"more than max_records={c['max_records']} records")
    return doc


def _get(rec: Any, key: str, csv_mode: bool) -> Any:
    if csv_mode:
        return rec.get(key)
    v = _dig(rec, key)
    return None if v is _MISSING else v


def _build(data: bytes, c: dict[str, Any]) -> tuple[list[CollectedItem], int, list[dict[str, Any]], int]:
    csv_mode = c["format"] == "csv"
    recs = _records(data, c)
    source = os.path.basename(c["path"])
    items: list[CollectedItem] = []
    rejected: list[dict[str, Any]] = []
    rejected_n = 0
    seen: set[str] = set()

    def reject(i: int, why: str) -> None:
        nonlocal rejected_n
        rejected_n += 1
        if len(rejected) < MAX_REJECTED_LISTED:
            rejected.append({"index": i, "reason": why})

    for i, rec in enumerate(recs):
        if not isinstance(rec, dict):
            reject(i, "record is not an object")
            continue
        url = _get(rec, c["url"], csv_mode)
        if not isinstance(url, str) or not url.strip():
            reject(i, "missing url")
            continue
        url = url.strip()
        if not (url.startswith("https://") or url.startswith("http://")):
            reject(i, "url must start with http:// or https://")
            continue
        fields = {out: _get(rec, src, csv_mode) for out, src in c["fields"].items()}
        if c["external_id"]:
            raw = _get(rec, c["external_id"], csv_mode)
            if raw is None or isinstance(raw, (dict, list)) or not str(raw).strip():
                reject(i, "missing external_id")
                continue
            ext = str(raw).strip()
        else:
            ext = hashlib.sha256(json.dumps([url, fields], sort_keys=True, default=str).encode()).hexdigest()[:16]
        if ext in seen:
            reject(i, "duplicate external_id")
            continue
        seen.add(ext)
        payload: dict[str, Any] = {"provider": "export_file", "source_file": source, "record_index": i}
        for label in ("kind", "platform"):
            if c[label]:
                payload[label] = c[label]
        payload.update(fields)
        items.append(CollectedItem(url, ext, payload))
    return items, len(recs), rejected, rejected_n


class ExportFileCollector:
    """Implements the Collector protocol over a local export file. No network, no side effects."""

    async def collect(self, config: dict[str, Any]) -> CollectionBatch:
        return await asyncio.to_thread(self._collect, config)

    def _collect(self, config: dict[str, Any]) -> CollectionBatch:
        c = _validate(config)
        data = _read_bytes(c["path"], c["max_bytes"])
        items, read, rejected, rejected_n = _build(data, c)
        start = c["cursor"]
        end = len(items) if c["limit"] is None else min(start + c["limit"], len(items))
        page = items[start:end] if start < len(items) else []
        nxt = str(end) if page and end < len(items) else None
        return CollectionBatch(
            items=page, requests=0, cursor=nxt,
            detail={
                "format": c["format"], "file_bytes": len(data),
                "file_sha256": hashlib.sha256(data).hexdigest(),
                "records_read": read, "records_accepted_in_file": len(items),
                "records_emitted": len(page), "records_rejected": rejected_n, "rejected": rejected,
                "layout_verified": False,
            },
        )
