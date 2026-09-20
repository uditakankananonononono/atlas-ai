from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.strip().rstrip(".,;)")
    return value or None


@dataclass(frozen=True, slots=True)
class Paper:
    paper_id: str
    title: str
    abstract: str = ""
    authors: tuple[str, ...] = ()
    published_at: str | None = None
    doi: str | None = None
    url: str | None = None
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.paper_id.strip() or not self.title.strip():
            raise ValueError("paper_id and title are required")
        object.__setattr__(self, "doi", normalize_doi(self.doi))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["authors"] = list(self.authors)
        return value


@dataclass(frozen=True, slots=True)
class SearchQuery:
    query_id: str
    text: str
    sources: tuple[str, ...] = ()
    since: str | None = None
    created_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.text.strip():
            raise ValueError("query_id and text are required")


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    gap_id: str
    kind: str
    statement: str
    supporting_paper_ids: tuple[str, ...]
    score: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Cluster:
    cluster_id: str
    label: str
    paper_ids: tuple[str, ...]
    keywords: tuple[str, ...]


def papers_by_id(papers: Iterable[Paper]) -> dict[str, Paper]:
    result: dict[str, Paper] = {}
    for paper in papers:
        if paper.paper_id in result:
            raise ValueError(f"duplicate paper_id: {paper.paper_id}")
        result[paper.paper_id] = paper
    return result
