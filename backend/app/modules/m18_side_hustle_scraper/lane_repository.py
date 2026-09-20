"""Tenant-scoped persistence for Module 18.

Protocol + a real SQLite implementation (stdlib sqlite3) so every behaviour is
testable in this lane. The integrator swaps in the shared Postgres/SQLAlchemy
adapter behind the same protocol; all queries are tenant-scoped and the event
log is append-only either way.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Protocol

from .lane_freshness import SourceStatus, WatchedSource
from .lane_models import RawDocument, RightsClass, SourceKind, utcnow
from .lane_validation import ValidationReport


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


class DocumentRepository(Protocol):
    def save_document(self, tenant_id: str, doc: RawDocument, report: ValidationReport) -> tuple[str, bool]:
        """Persist an accepted document. Returns (doc_id, is_new)."""
        ...

    def get_by_hash(self, tenant_id: str, content_hash: str) -> Optional[RawDocument]:
        ...

    def known_fingerprints(self, tenant_id: str) -> dict[str, str]:
        """content_hash -> doc_id for accepted documents of this tenant."""
        ...

    def iter_documents(self, tenant_id: str, *, platform: Optional[str] = None,
                       kind: Optional[SourceKind] = None) -> Iterable[RawDocument]:
        ...

    def record_event(self, tenant_id: str, kind: str, payload: dict[str, Any]) -> int:
        ...

    def events(self, tenant_id: str, *, kind: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    tenant_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    platform TEXT NOT NULL,
    kind TEXT NOT NULL,
    rights TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    author TEXT,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    etag TEXT,
    last_modified TEXT,
    http_status INTEGER,
    content_hash TEXT NOT NULL,
    engagement TEXT NOT NULL DEFAULT '{}',
    meta TEXT NOT NULL DEFAULT '{}',
    quality_score REAL NOT NULL DEFAULT 0,
    scam_signals TEXT NOT NULL DEFAULT '[]',
    injection_flags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, doc_id),
    UNIQUE (tenant_id, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_platform ON documents (tenant_id, platform);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_canonical ON documents (tenant_id, canonical_url);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_kind ON events (tenant_id, kind);
CREATE TABLE IF NOT EXISTS freshness_state (
    tenant_id TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,
    interval_seconds REAL NOT NULL,
    last_checked_at TEXT,
    last_changed_at TEXT,
    etag TEXT,
    last_modified TEXT,
    content_hash TEXT,
    consecutive_unchanged INTEGER NOT NULL DEFAULT 0,
    consecutive_errors INTEGER NOT NULL DEFAULT 0,
    total_checks INTEGER NOT NULL DEFAULT 0,
    total_changes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'alive',
    PRIMARY KEY (tenant_id, url)
);
"""


class SQLiteDocumentRepository:
    """Real storage for tests and local runs; :memory: supported."""

    def __init__(self, path: str = ":memory:"):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def save_document(self, tenant_id: str, doc: RawDocument, report: ValidationReport) -> tuple[str, bool]:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not report.accepted:
            raise ValueError(f"refusing to persist rejected document: {report.reasons}")
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT doc_id FROM documents WHERE tenant_id=? AND content_hash=?",
                (tenant_id, report.content_hash),
            ).fetchone()
            if existing:
                return existing["doc_id"], False
            self._db.execute(
                """INSERT INTO documents
                   (tenant_id, doc_id, url, canonical_url, platform, kind, rights, title, text,
                    author, published_at, retrieved_at, etag, last_modified, http_status,
                    content_hash, engagement, meta, quality_score, scam_signals, injection_flags, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tenant_id, doc.id, doc.url, report.canonical_url, doc.platform, doc.kind.value,
                    doc.rights.value, doc.title, doc.text, doc.author, _dt(doc.published_at),
                    _dt(doc.retrieved_at) or _dt(utcnow()), doc.etag, doc.last_modified, doc.http_status,
                    report.content_hash, json.dumps(doc.engagement), json.dumps(doc.meta),
                    report.quality_score, json.dumps(list(report.scam_signals)),
                    json.dumps(list(report.injection_flags)), _dt(utcnow()),
                ),
            )
            self._event_locked(tenant_id, "document_saved", {"doc_id": doc.id, "content_hash": report.content_hash,
                                                             "platform": doc.platform, "url": report.canonical_url})
        return doc.id, True

    def get_by_hash(self, tenant_id: str, content_hash: str) -> Optional[RawDocument]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM documents WHERE tenant_id=? AND content_hash=?", (tenant_id, content_hash)
            ).fetchone()
        return self._row_to_doc(row) if row else None

    def get_by_id(self, tenant_id: str, doc_id: str) -> Optional[RawDocument]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM documents WHERE tenant_id=? AND doc_id=?", (tenant_id, doc_id)
            ).fetchone()
        return self._row_to_doc(row) if row else None

    def known_fingerprints(self, tenant_id: str) -> dict[str, str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT content_hash, doc_id FROM documents WHERE tenant_id=?", (tenant_id,)
            ).fetchall()
        return {r["content_hash"]: r["doc_id"] for r in rows}

    def iter_documents(self, tenant_id: str, *, platform: Optional[str] = None,
                       kind: Optional[SourceKind] = None) -> Iterable[RawDocument]:
        sql = "SELECT * FROM documents WHERE tenant_id=?"
        args: list[Any] = [tenant_id]
        if platform:
            sql += " AND platform=?"
            args.append(platform)
        if kind:
            sql += " AND kind=?"
            args.append(kind.value)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        return [self._row_to_doc(r) for r in rows]

    def record_event(self, tenant_id: str, kind: str, payload: dict[str, Any]) -> int:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        with self._lock, self._db:
            return self._event_locked(tenant_id, kind, payload)

    def _event_locked(self, tenant_id: str, kind: str, payload: dict[str, Any]) -> int:
        cur = self._db.execute(
            "INSERT INTO events (tenant_id, kind, payload, occurred_at) VALUES (?,?,?,?)",
            (tenant_id, kind, json.dumps(payload, default=str), _dt(utcnow())),
        )
        return int(cur.lastrowid)

    def events(self, tenant_id: str, *, kind: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT id, kind, payload, occurred_at FROM events WHERE tenant_id=?"
        args: list[Any] = [tenant_id]
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        return [{"id": r["id"], "kind": r["kind"], "payload": json.loads(r["payload"]),
                 "occurred_at": r["occurred_at"]} for r in rows]

    def count(self, tenant_id: str) -> int:
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) AS c FROM documents WHERE tenant_id=?", (tenant_id,)).fetchone()
        return int(row["c"])

    # --- FreshnessStore protocol -------------------------------------

    def upsert_watched(self, source: WatchedSource) -> None:
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO freshness_state
                   (tenant_id, url, kind, interval_seconds, last_checked_at, last_changed_at,
                    etag, last_modified, content_hash, consecutive_unchanged, consecutive_errors,
                    total_checks, total_changes, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (tenant_id, url) DO UPDATE SET
                    kind=excluded.kind, interval_seconds=excluded.interval_seconds,
                    last_checked_at=excluded.last_checked_at, last_changed_at=excluded.last_changed_at,
                    etag=excluded.etag, last_modified=excluded.last_modified,
                    content_hash=excluded.content_hash,
                    consecutive_unchanged=excluded.consecutive_unchanged,
                    consecutive_errors=excluded.consecutive_errors,
                    total_checks=excluded.total_checks, total_changes=excluded.total_changes,
                    status=excluded.status""",
                (
                    source.tenant_id, source.url, source.kind.value, source.interval_seconds,
                    _dt(source.last_checked_at), _dt(source.last_changed_at), source.etag,
                    source.last_modified, source.content_hash, source.consecutive_unchanged,
                    source.consecutive_errors, source.total_checks, source.total_changes,
                    source.status.value,
                ),
            )

    def get_watched(self, tenant_id: str, url: str) -> Optional[WatchedSource]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM freshness_state WHERE tenant_id=? AND url=?", (tenant_id, url)
            ).fetchone()
        return self._row_to_watched(row) if row else None

    def iter_watched(self, tenant_id: str) -> list[WatchedSource]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM freshness_state WHERE tenant_id=? ORDER BY url", (tenant_id,)
            ).fetchall()
        return [self._row_to_watched(r) for r in rows]

    @staticmethod
    def _row_to_watched(row: sqlite3.Row) -> WatchedSource:
        return WatchedSource(
            tenant_id=row["tenant_id"], url=row["url"], kind=SourceKind(row["kind"]),
            interval_seconds=row["interval_seconds"],
            last_checked_at=_parse(row["last_checked_at"]),
            last_changed_at=_parse(row["last_changed_at"]),
            etag=row["etag"], last_modified=row["last_modified"],
            content_hash=row["content_hash"],
            consecutive_unchanged=row["consecutive_unchanged"],
            consecutive_errors=row["consecutive_errors"],
            total_checks=row["total_checks"], total_changes=row["total_changes"],
            status=SourceStatus(row["status"]),
        )

    @staticmethod
    def _row_to_doc(row: sqlite3.Row) -> RawDocument:
        doc = RawDocument(
            url=row["url"],
            platform=row["platform"],
            kind=SourceKind(row["kind"]),
            rights=RightsClass(row["rights"]),
            title=row["title"],
            text=row["text"],
            author=row["author"],
            published_at=_parse(row["published_at"]),
            retrieved_at=_parse(row["retrieved_at"]) or utcnow(),
            etag=row["etag"],
            last_modified=row["last_modified"],
            http_status=row["http_status"],
            content_hash=row["content_hash"],
            engagement=json.loads(row["engagement"]),
            meta=json.loads(row["meta"]),
            id=row["doc_id"],
        )
        doc.meta.setdefault("canonical_url", row["canonical_url"])
        doc.meta.setdefault("quality_score", row["quality_score"])
        return doc
