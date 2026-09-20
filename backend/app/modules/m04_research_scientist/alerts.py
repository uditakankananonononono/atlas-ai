from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from .models import Paper

AlertKind = Literal["new_publication", "retraction", "correction", "expression_of_concern"]


@dataclass(frozen=True, slots=True)
class ScholarlyAlert:
    alert_id: str
    kind: AlertKind
    paper_id: str
    title: str
    reason: str
    severity: Literal["info", "warning", "critical"]


_TAGS: tuple[tuple[AlertKind, re.Pattern[str], str], ...] = (
    ("retraction", re.compile(r"\b(retract(?:ed|ion)|withdrawn)\b", re.I), "critical"),
    ("expression_of_concern", re.compile(r"\bexpression of concern\b", re.I), "warning"),
    ("correction", re.compile(r"\b(correction|corrigendum|erratum)\b", re.I), "warning"),
)


def classify_alerts(new_papers: Iterable[Paper]) -> tuple[ScholarlyAlert, ...]:
    """Classify supplied new records; no title match is treated as proof beyond the source record."""
    alerts = []
    for paper in sorted(new_papers, key=lambda p: p.paper_id):
        searchable = " ".join((paper.title, str(paper.metadata.get("publication_type", "")),
                               str(paper.metadata.get("status", ""))))
        matched = False
        for kind, pattern, severity in _TAGS:
            if pattern.search(searchable):
                alerts.append(ScholarlyAlert(f"{kind}:{paper.paper_id}", kind, paper.paper_id, paper.title,
                                             f"source record is labelled as {kind.replace('_', ' ')}", severity))
                matched = True
                break
        if not matched:
            alerts.append(ScholarlyAlert(f"new_publication:{paper.paper_id}", "new_publication", paper.paper_id,
                                         paper.title, "first observed for this surveillance query", "info"))
    return tuple(alerts)
