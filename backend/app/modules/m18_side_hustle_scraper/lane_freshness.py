"""Freshness monitoring for watched sources.

A source is only as good as its last check. The monitor decides when each
watched URL owes a re-fetch (adaptive interval: slows down when a source stops
changing, speeds up when it moves), detects change via ETag/Last-Modified/
content hash, classifies how stale the evidence is, and feeds a decay
multiplier into the ranker. Dead sources (404/410 or repeated failures) stop
being fetched and stop propping up scores.

State lives in the repository (freshness_state table, tenant-scoped) so a
worker restart loses nothing; every transition is also written to the
append-only event log.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Mapping, Optional, Protocol, Sequence

from .lane_models import RawDocument, SourceKind, utcnow

HOUR = 3600.0
DAY = 86400.0


class FreshnessClass(str, Enum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"


class SourceStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"


DEFAULT_TTL: Mapping[SourceKind, float] = {
    SourceKind.RSS: 12 * HOUR,
    SourceKind.REDDIT_JSON: 24 * HOUR,
    SourceKind.HACKER_NEWS: 24 * HOUR,
    SourceKind.DEV_TO: 24 * HOUR,
    SourceKind.YOUTUBE_DATA_API: 48 * HOUR,
    SourceKind.PUBLIC_WEB: 72 * HOUR,
}

FACTOR_FOR_CLASS: Mapping[FreshnessClass, float] = {
    FreshnessClass.FRESH: 1.0,
    FreshnessClass.AGING: 0.85,
    FreshnessClass.STALE: 0.60,
    FreshnessClass.EXPIRED: 0.35,
}
DEAD_FACTOR = 0.20


@dataclass
class WatchedSource:
    tenant_id: str
    url: str
    kind: SourceKind
    interval_seconds: float
    last_checked_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_hash: Optional[str] = None
    consecutive_unchanged: int = 0
    consecutive_errors: int = 0
    total_checks: int = 0
    total_changes: int = 0
    status: SourceStatus = SourceStatus.ALIVE


@dataclass(frozen=True)
class ChangeRecord:
    url: str
    checked_at: datetime
    change_detected: bool
    not_modified: bool
    error: Optional[str]
    new_class: FreshnessClass
    new_interval_seconds: float
    status: SourceStatus


class FreshnessStore(Protocol):
    def upsert_watched(self, source: WatchedSource) -> None: ...
    def get_watched(self, tenant_id: str, url: str) -> Optional[WatchedSource]: ...
    def iter_watched(self, tenant_id: str) -> Sequence[WatchedSource]: ...
    def record_event(self, tenant_id: str, kind: str, payload: dict) -> int: ...


@dataclass
class FreshnessConfig:
    ttl_seconds: Mapping[SourceKind, float] = None  # defaults applied in __post_init__
    base_interval_seconds: float = 6 * HOUR
    min_interval_seconds: float = 1 * HOUR
    max_interval_seconds: float = 7 * DAY
    unchanged_growth: float = 1.5
    change_shrink: float = 0.5
    error_threshold: int = 4

    def __post_init__(self) -> None:
        if self.ttl_seconds is None:
            self.ttl_seconds = dict(DEFAULT_TTL)


class FreshnessMonitor:
    def __init__(self, store: FreshnessStore, config: FreshnessConfig | None = None,
                 *, clock: Callable[[], datetime] = utcnow):
        self.store = store
        self.config = config or FreshnessConfig()
        self.clock = clock

    def watch(self, tenant_id: str, url: str, kind: SourceKind, *,
              etag: Optional[str] = None, last_modified: Optional[str] = None,
              content_hash: Optional[str] = None) -> WatchedSource:
        existing = self.store.get_watched(tenant_id, url)
        if existing is not None:
            return existing
        source = WatchedSource(
            tenant_id=tenant_id, url=url, kind=kind,
            interval_seconds=self.config.base_interval_seconds,
            etag=etag, last_modified=last_modified, content_hash=content_hash,
            # A watch registered from a real collection has just been observed:
            # its evidence is FRESH now. A watch without captured content stays
            # unclassified (EXPIRED factor) until its first fetch.
            last_changed_at=self.clock() if content_hash is not None else None,
        )
        self.store.upsert_watched(source)
        self.store.record_event(tenant_id, "freshness_watch_added", {"url": url, "kind": kind.value})
        return source

    def unwatch(self, tenant_id: str, url: str) -> bool:
        source = self.store.get_watched(tenant_id, url)
        if source is None:
            return False
        source.status = SourceStatus.DEAD
        self.store.upsert_watched(source)
        self.store.record_event(tenant_id, "freshness_unwatched", {"url": url})
        return True

    def due_sources(self, tenant_id: str) -> list[WatchedSource]:
        now = self.clock()
        out: list[WatchedSource] = []
        for source in self.store.iter_watched(tenant_id):
            if source.status is SourceStatus.DEAD:
                continue
            if source.last_checked_at is None:
                out.append(source)
            elif (now - source.last_checked_at).total_seconds() >= source.interval_seconds:
                out.append(source)
        return out

    def _classify(self, source: WatchedSource) -> FreshnessClass:
        if source.last_changed_at is None:
            return FreshnessClass.EXPIRED
        ttl = self.config.ttl_seconds.get(source.kind, 24 * HOUR)
        age = (self.clock() - source.last_changed_at).total_seconds()
        if age < ttl:
            return FreshnessClass.FRESH
        if age < 2 * ttl:
            return FreshnessClass.AGING
        if age < 4 * ttl:
            return FreshnessClass.STALE
        return FreshnessClass.EXPIRED

    def classification(self, tenant_id: str, url: str) -> FreshnessClass:
        source = self.store.get_watched(tenant_id, url)
        if source is None:
            return FreshnessClass.EXPIRED
        return self._classify(source)

    def factor(self, tenant_id: str, url: str) -> float:
        source = self.store.get_watched(tenant_id, url)
        if source is None:
            return FACTOR_FOR_CLASS[FreshnessClass.EXPIRED]
        if source.status is SourceStatus.DEAD:
            return DEAD_FACTOR
        return FACTOR_FOR_CLASS[self._classify(source)]

    def factor_for_document(self, tenant_id: str, doc: RawDocument) -> float:
        return self.factor(tenant_id, doc.meta.get("canonical_url", doc.url))

    def record_fetch(self, tenant_id: str, url: str, *,
                     status: Optional[int] = None,
                     content_hash: Optional[str] = None,
                     etag: Optional[str] = None,
                     last_modified: Optional[str] = None,
                     not_modified: bool = False,
                     error: Optional[str] = None) -> ChangeRecord:
        source = self.store.get_watched(tenant_id, url)
        if source is None:
            source = self.watch(tenant_id, url, SourceKind.PUBLIC_WEB)
        now = self.clock()
        source.total_checks += 1
        change = False

        if error is not None or (status is not None and status >= 400 and status != 304):
            source.consecutive_errors += 1
            if status in (404, 410) or source.consecutive_errors >= self.config.error_threshold:
                source.status = SourceStatus.DEAD
                self.store.record_event(tenant_id, "freshness_source_dead",
                                        {"url": url, "reason": error or f"http_{status}"})
        else:
            source.consecutive_errors = 0
            changed_identity = (
                (etag is not None and source.etag is not None and etag != source.etag)
                or (content_hash is not None and source.content_hash is not None
                    and content_hash != source.content_hash)
                or (last_modified is not None and source.last_modified is not None
                    and last_modified != source.last_modified)
            )
            first_capture = source.content_hash is None and content_hash is not None
            if changed_identity or first_capture:
                change = True
                source.total_changes += 1
                source.consecutive_unchanged = 0
                source.last_changed_at = now
                source.interval_seconds = max(self.config.min_interval_seconds,
                                              source.interval_seconds * self.config.change_shrink)
                self.store.record_event(tenant_id, "freshness_change_detected",
                                        {"url": url, "content_hash": content_hash})
            else:
                source.consecutive_unchanged += 1
                source.interval_seconds = min(self.config.max_interval_seconds,
                                              source.interval_seconds * self.config.unchanged_growth)
            if etag is not None:
                source.etag = etag
            if last_modified is not None:
                source.last_modified = last_modified
            if content_hash is not None:
                source.content_hash = content_hash
        source.last_checked_at = now
        self.store.upsert_watched(source)
        return ChangeRecord(
            url=url, checked_at=now, change_detected=change, not_modified=not_modified,
            error=error, new_class=self._classify(source),
            new_interval_seconds=source.interval_seconds, status=source.status,
        )

    def report(self, tenant_id: str) -> dict:
        watched = list(self.store.iter_watched(tenant_id))
        by_class: dict[str, int] = {}
        dead = 0
        for source in watched:
            if source.status is SourceStatus.DEAD:
                dead += 1
                continue
            klass = self._classify(source)
            by_class[klass.value] = by_class.get(klass.value, 0) + 1
        return {
            "tenant_id": tenant_id,
            "watched": len(watched),
            "alive": len(watched) - dead,
            "dead": dead,
            "due_now": len(self.due_sources(tenant_id)),
            "by_class": by_class,
            "generated_at": self.clock().isoformat(),
        }
