from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Iterable

from .lane_models import CorpusDocument, GroundingHit, Opportunity

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _excerpt(text: str, query_terms: set[str], limit: int = 360) -> str:
    clean = " ".join(text.split())
    lower = clean.lower()
    starts = [lower.find(term) for term in query_terms if lower.find(term) >= 0]
    pivot = min(starts) if starts else 0
    start = max(0, pivot - 80)
    end = min(len(clean), start + limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(clean) else ""
    return prefix + clean[start:end].strip() + suffix


class GrantCorpus:
    """Small deterministic corpus store.

    Production adapters can hydrate it from Postgres/vector search. All returned hits
    retain source identity and observation time so generated claims remain auditable.
    """

    def __init__(
        self,
        opportunities: Iterable[Opportunity] = (),
        documents: Iterable[CorpusDocument] = (),
    ) -> None:
        self._opportunities = {item.id: item for item in opportunities}
        self._documents = {item.id: item for item in documents}

    def get_opportunity(self, opportunity_id: str, *, as_of: datetime) -> Opportunity:
        item = self._opportunities.get(opportunity_id)
        if item is None or item.observed_at > as_of:
            raise KeyError(f"opportunity not available as of {as_of.isoformat()}: {opportunity_id}")
        return item

    def search(
        self,
        query: str,
        *,
        as_of: datetime,
        limit: int = 8,
        required_tags: set[str] | None = None,
    ) -> tuple[GroundingHit, ...]:
        if limit <= 0:
            return ()
        terms = _tokens(query)
        if not terms:
            return ()
        query_counts = Counter(terms)
        visible = [
            d for d in self._documents.values()
            if d.observed_at <= as_of and (not required_tags or required_tags.issubset(set(d.tags)))
        ]
        if not visible:
            return ()
        doc_tokens = {d.id: _tokens(f"{d.title} {d.text} {' '.join(d.tags)}") for d in visible}
        doc_freq = Counter()
        for tokens in doc_tokens.values():
            doc_freq.update(set(tokens))
        results: list[GroundingHit] = []
        n = len(visible)
        for doc in visible:
            counts = Counter(doc_tokens[doc.id])
            score = 0.0
            for term, qtf in query_counts.items():
                if counts[term]:
                    idf = math.log(1 + (n + 1) / (doc_freq[term] + 1))
                    score += (1 + math.log(counts[term])) * idf * qtf
            if score <= 0:
                continue
            results.append(GroundingHit(
                document_id=doc.id,
                title=doc.title,
                source_url=doc.source_url,
                excerpt=_excerpt(doc.text, set(terms)),
                score=round(score, 6),
                observed_at=doc.observed_at,
            ))
        return tuple(sorted(results, key=lambda h: (-h.score, h.document_id))[:limit])
