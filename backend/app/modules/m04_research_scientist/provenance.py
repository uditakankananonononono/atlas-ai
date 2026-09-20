from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from .models import EvidenceGap, Paper


@dataclass(frozen=True, slots=True)
class EvidenceAudit:
    paper_id: str
    has_locator: bool
    has_abstract: bool
    has_date: bool
    issues: tuple[str, ...]


def audit_evidence(papers: Iterable[Paper]) -> tuple[EvidenceAudit, ...]:
    audits = []
    for paper in sorted(papers, key=lambda p: p.paper_id):
        issues = []
        locator = bool(paper.doi)
        if paper.url:
            parsed = urlparse(paper.url)
            locator = locator or (parsed.scheme in {"http", "https"} and bool(parsed.netloc))
            if parsed.scheme not in {"http", "https"}:
                issues.append("non-public URL scheme")
        if not locator:
            issues.append("no public locator")
        if not paper.abstract.strip():
            issues.append("abstract unavailable")
        if not paper.published_at:
            issues.append("publication date unavailable")
        audits.append(EvidenceAudit(paper.paper_id, locator, bool(paper.abstract.strip()), bool(paper.published_at), tuple(issues)))
    return tuple(audits)


def validate_gap_support(gaps: Iterable[EvidenceGap], papers: Iterable[Paper]) -> None:
    known = {paper.paper_id for paper in papers}
    for gap in gaps:
        unknown = set(gap.supporting_paper_ids) - known
        if unknown:
            raise ValueError(f"gap {gap.gap_id} cites unknown papers: {sorted(unknown)}")
        if not 0 <= gap.score <= 1:
            raise ValueError(f"gap {gap.gap_id} score must be between 0 and 1")
