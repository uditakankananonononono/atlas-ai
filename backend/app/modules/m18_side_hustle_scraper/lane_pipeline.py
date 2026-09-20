"""Synchronous pipeline tying the module together.

collect -> validate -> persist -> rank -> monitor freshness. This is the unit
Celery tasks call; the async FastAPI facade (service.py) wraps it in
asyncio.to_thread. All IO goes through injected collectors/fetchers, so the
whole pipeline is testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from .lane_freshness import ChangeRecord, FreshnessMonitor
from .lane_models import CollectionError, RawDocument, SourceKind
from .lane_ranking import BlueprintRanker, RankedDocument, RankUserContext
from .lane_repository import DocumentRepository
from .lane_sources import Collector, ensure_legal_platform
from .lane_validation import DocumentValidator, ValidationReport, shingles


@dataclass(frozen=True)
class PlatformReport:
    platform: str
    collected: int
    accepted_new: int
    accepted_duplicate: int
    rejected: int
    rejection_reasons: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CollectReport:
    tenant_id: str
    query: str
    platforms: tuple[PlatformReport, ...]
    documents_found: int
    documents_new: int
    documents_duplicate: int
    documents_rejected: int


@dataclass(frozen=True)
class RefreshReport:
    tenant_id: str
    sources_due: int
    sources_checked: int
    changes_detected: int
    dead_sources: tuple[str, ...]
    records: tuple[ChangeRecord, ...]


# A refetcher returns the observed state of one watched URL.
FetchObservation = Mapping[str, Any]  # keys: status, content_hash, etag, last_modified, not_modified, error
Refetcher = Callable[[str, SourceKind], FetchObservation]


class CollectionPipeline:
    def __init__(
        self,
        repository: DocumentRepository,
        validator: DocumentValidator,
        ranker: BlueprintRanker,
        monitor: FreshnessMonitor,
        collectors: Mapping[str, Collector],
    ):
        self.repository = repository
        self.validator = validator
        self.ranker = ranker
        self.monitor = monitor
        self.collectors = dict(collectors)

    def run_collection(self, tenant_id: str, query: str, platforms: Sequence[str],
                       limit_per_platform: int = 20) -> CollectReport:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not query or not query.strip():
            raise ValueError("query is required")
        reports: list[PlatformReport] = []
        found = new = dup = rejected = 0
        known_hashes = self.repository.known_fingerprints(tenant_id)
        known_shingles: dict[str, frozenset[str]] = {}
        for content_hash in known_hashes:
            stored = self.repository.get_by_hash(tenant_id, content_hash)
            if stored is not None:
                known_shingles[content_hash] = shingles(stored.title + "\n" + stored.text)

        for platform in platforms:
            ensure_legal_platform(platform)
            collector = self.collectors.get(platform)
            if collector is None:
                reports.append(PlatformReport(
                    platform=platform, collected=0, accepted_new=0, accepted_duplicate=0,
                    rejected=0, rejection_reasons=(),
                    errors=(f"collector_not_configured:{platform}",),
                ))
                continue
            docs, errors = collector.collect(query, limit_per_platform)
            found += len(docs)
            p_new = p_dup = p_rej = 0
            reasons: list[str] = []
            for doc in docs:
                report = self.validator.validate(doc, known_hashes=known_hashes,
                                                 known_shingles=known_shingles)
                if report.accepted:
                    _, is_new = self.repository.save_document(tenant_id, doc, report)
                    if is_new:
                        p_new += 1
                        known_hashes[report.content_hash] = doc.id
                        known_shingles[report.content_hash] = shingles(doc.title + "\n" + doc.text)
                        self.monitor.watch(tenant_id, report.canonical_url, doc.kind,
                                           etag=doc.etag, last_modified=doc.last_modified,
                                           content_hash=report.content_hash)
                    else:
                        p_dup += 1
                elif report.duplicate_of or any(r.startswith("near_duplicate") for r in report.reasons):
                    # re-collecting something already stored is a duplicate, not a rejection
                    p_dup += 1
                else:
                    p_rej += 1
                    reasons.extend(report.reasons)
            new += p_new
            dup += p_dup
            rejected += p_rej
            reports.append(PlatformReport(
                platform=platform, collected=len(docs), accepted_new=p_new,
                accepted_duplicate=p_dup, rejected=p_rej,
                rejection_reasons=tuple(sorted(set(reasons))),
                errors=tuple(f"{e.reason}" + (f"({e.status})" if e.status else "") for e in errors),
            ))
        self.repository.record_event(tenant_id, "collection_run", {
            "query": query, "platforms": list(platforms), "found": found,
            "new": new, "duplicates": dup, "rejected": rejected,
        })
        return CollectReport(
            tenant_id=tenant_id, query=query, platforms=tuple(reports),
            documents_found=found, documents_new=new,
            documents_duplicate=dup, documents_rejected=rejected,
        )

    def ranked(self, tenant_id: str, query: str, user: Optional[RankUserContext] = None,
               platforms: Optional[Sequence[str]] = None) -> list[RankedDocument]:
        docs: list[RawDocument] = []
        if platforms:
            for platform in platforms:
                docs.extend(self.repository.iter_documents(tenant_id, platform=platform))
        else:
            docs = list(self.repository.iter_documents(tenant_id))
        scam_map: dict[str, Sequence[str]] = {}
        quality_map: dict[str, float] = {}
        for doc in docs:
            quality_map[doc.id] = float(doc.meta.get("quality_score", 0.5))
        ranker = BlueprintRanker(
            self.ranker.config, clock=self.ranker.clock,
            scam_signals=scam_map, quality_scores=quality_map,
            freshness_factor=lambda d: self.monitor.factor_for_document(tenant_id, d),
        )
        return ranker.rank(query, docs, user=user)

    def run_refresh(self, tenant_id: str, refetcher: Refetcher, *,
                    limit: int = 50) -> RefreshReport:
        """Re-check due sources through the injected refetcher. The integrator
        wires per-kind refetchers (RSS conditional GET, API re-queries)."""
        due = self.monitor.due_sources(tenant_id)[:limit]
        records: list[ChangeRecord] = []
        dead: list[str] = []
        changes = 0
        for source in due:
            observation = refetcher(source.url, source.kind)
            record = self.monitor.record_fetch(
                tenant_id, source.url,
                status=observation.get("status"),
                content_hash=observation.get("content_hash"),
                etag=observation.get("etag"),
                last_modified=observation.get("last_modified"),
                not_modified=bool(observation.get("not_modified", False)),
                error=observation.get("error"),
            )
            records.append(record)
            if record.change_detected:
                changes += 1
            if record.status.value == "dead":
                dead.append(source.url)
        self.repository.record_event(tenant_id, "freshness_refresh", {
            "checked": len(records), "changes": changes, "dead": list(dead),
        })
        return RefreshReport(
            tenant_id=tenant_id, sources_due=len(due), sources_checked=len(records),
            changes_detected=changes, dead_sources=tuple(dead), records=tuple(records),
        )
