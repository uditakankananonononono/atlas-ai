from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .models import Paper


@dataclass(frozen=True, slots=True)
class ExtractedFinding:
    finding_id: str
    paper_id: str
    claim: str
    outcome: str
    effect: str | None
    population: str | None
    evidence_quote: str
    page_or_section: str | None
    extractor: str

    def __post_init__(self) -> None:
        if not all((self.finding_id.strip(), self.paper_id.strip(), self.claim.strip(), self.evidence_quote.strip(), self.extractor.strip())):
            raise ValueError("finding id, paper id, claim, quote, and extractor are required")


def build_evidence_table(findings: Iterable[ExtractedFinding], papers: Iterable[Paper]) -> tuple[dict, ...]:
    paper_map = {paper.paper_id: paper for paper in papers}
    rows = []
    seen = set()
    for finding in sorted(findings, key=lambda item: item.finding_id):
        if finding.finding_id in seen:
            raise ValueError(f"duplicate finding_id: {finding.finding_id}")
        seen.add(finding.finding_id)
        if finding.paper_id not in paper_map:
            raise ValueError(f"finding {finding.finding_id} cites unknown paper {finding.paper_id}")
        row = asdict(finding)
        row.update({"paper_title": paper_map[finding.paper_id].title,
                    "doi": paper_map[finding.paper_id].doi,
                    "source_url": paper_map[finding.paper_id].url})
        rows.append(row)
    return tuple(rows)
