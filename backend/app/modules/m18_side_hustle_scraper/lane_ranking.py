"""Explainable multi-signal ranking for collected blueprint evidence.

The score is 0-100 and every point is accounted for: the breakdown lists each
signal, its weight, its raw value and its contribution, so the UI and the audit
ledger can show *why* one blueprint outranks another instead of asserting it.

Signals:
- relevance: BM25 of the query against title+text
- recency: exponential decay with a configurable half-life
- authority: per-platform source trust weights
- engagement: log-scaled community scrutiny, percentile-normalized per platform
- quality: the validator's evidence-quality score
- corroboration: independent platforms describing the same blueprint
- user fit: skill overlap and excluded-category penalty
- scam penalty: subtracts points per detected signal

A freshness_factor hook lets the freshness monitor decay stale evidence
without the ranker knowing how freshness is computed.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Mapping, Optional, Sequence

from .lane_models import RawDocument, utcnow
from .lane_validation import shingles, jaccard

_WORD_RE = re.compile(r"[a-z0-9]+")

DEFAULT_AUTHORITY: Mapping[str, float] = {
    "reddit": 0.70,
    "hacker_news": 0.80,
    "youtube": 0.75,
    "dev_to": 0.65,
    "rss": 0.60,
    "public_web": 0.50,
}


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def bm25_score(query_terms: Sequence[str], doc_tokens: Sequence[str],
               avg_len: float, doc_freqs: Mapping[str, int], corpus_size: int,
               k1: float = 1.5, b: float = 0.75) -> float:
    if not query_terms or not doc_tokens or corpus_size == 0:
        return 0.0
    tf: dict[str, int] = {}
    for tok in doc_tokens:
        tf[tok] = tf.get(tok, 0) + 1
    score = 0.0
    length_norm = 1 - b + b * (len(doc_tokens) / max(avg_len, 1e-9))
    for term in set(query_terms):
        f = tf.get(term, 0)
        if f == 0:
            continue
        df = doc_freqs.get(term, 0)
        idf = math.log(1 + (corpus_size - df + 0.5) / (df + 0.5))
        score += idf * (f * (k1 + 1)) / (f + k1 * length_norm)
    return score


@dataclass(frozen=True)
class RankUserContext:
    skills: tuple[str, ...] = ()
    excluded_categories: tuple[str, ...] = ()
    budget: float = 0.0
    hours_per_week: float = 5.0
    country: Optional[str] = None


@dataclass(frozen=True)
class SignalContribution:
    signal: str
    weight: float
    raw_value: float
    contribution: float
    note: str = ""


@dataclass(frozen=True)
class RankedDocument:
    doc_id: str
    url: str
    platform: str
    title: str
    score: float                      # 0-100
    rank: int
    breakdown: tuple[SignalContribution, ...]
    cluster_id: str
    corroborating_platforms: tuple[str, ...]
    scam_penalty: float = 0.0


@dataclass
class RankingConfig:
    weight_relevance: float = 0.30
    weight_recency: float = 0.15
    weight_authority: float = 0.15
    weight_engagement: float = 0.15
    weight_quality: float = 0.15
    weight_corroboration: float = 0.05
    weight_user_fit: float = 0.05
    recency_half_life_days: float = 90.0
    scam_penalty_per_signal: float = 10.0
    scam_penalty_cap: float = 30.0
    cluster_similarity: float = 0.5
    authority: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_AUTHORITY))
    unknown_platform_authority: float = 0.4

    def total_weight(self) -> float:
        return (self.weight_relevance + self.weight_recency + self.weight_authority +
                self.weight_engagement + self.weight_quality + self.weight_corroboration +
                self.weight_user_fit)


def cluster_documents(docs: Sequence[RawDocument], similarity: float = 0.5) -> dict[str, str]:
    """Union-find clustering by shingle similarity. Returns doc_id -> cluster_id."""
    parent = {d.id: d.id for d in docs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    shingle_map = {d.id: shingles(d.title + "\n" + d.text) for d in docs}
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            if jaccard(shingle_map[a.id], shingle_map[b.id]) >= similarity:
                union(a.id, b.id)
    return {d.id: find(d.id) for d in docs}


class BlueprintRanker:
    def __init__(self, config: RankingConfig | None = None, *,
                 clock: Callable[[], datetime] = utcnow,
                 scam_signals: Optional[Mapping[str, Sequence[str]]] = None,
                 quality_scores: Optional[Mapping[str, float]] = None,
                 freshness_factor: Optional[Callable[[RawDocument], float]] = None):
        self.config = config or RankingConfig()
        self.clock = clock
        self._scam_signals = scam_signals or {}
        self._quality = quality_scores or {}
        self._freshness_factor = freshness_factor

    def _recency(self, doc: RawDocument) -> float:
        basis = doc.published_at or doc.retrieved_at
        age_days = max(0.0, (self.clock() - basis).total_seconds() / 86400.0)
        return 0.5 ** (age_days / self.config.recency_half_life_days)

    def _engagement_norm(self, docs: Sequence[RawDocument]) -> dict[str, float]:
        """Percentile-normalized log engagement within each platform, so a
        reddit score and a YouTube view count are comparable."""
        by_platform: dict[str, list[tuple[str, float]]] = {}
        for d in docs:
            value = (d.engagement.get("score", 0.0) + d.engagement.get("comments", 0.0) +
                     d.engagement.get("views", 0.0) / 100.0 + d.engagement.get("likes", 0.0) / 10.0)
            by_platform.setdefault(d.platform, []).append((d.id, math.log1p(max(0.0, value))))
        out: dict[str, float] = {}
        for platform, rows in by_platform.items():
            values = sorted(v for _, v in rows)
            for doc_id, v in rows:
                rank = sum(1 for x in values if x <= v) / len(values)
                out[doc_id] = rank
        return out

    def _user_fit(self, doc: RawDocument, user: Optional[RankUserContext]) -> tuple[float, str]:
        if user is None:
            return 0.5, "no_user_context"
        text = (doc.title + " " + doc.text).lower()
        for category in user.excluded_categories:
            if category.lower() in text:
                return 0.0, f"excluded_category:{category}"
        if not user.skills:
            return 0.5, "no_skills_listed"
        hits = sum(1 for s in user.skills if s.lower() in text)
        return min(1.0, hits / max(1, len(user.skills)) * 2), f"skill_hits:{hits}"

    def rank(self, query: str, docs: Sequence[RawDocument],
             user: Optional[RankUserContext] = None) -> list[RankedDocument]:
        if not docs:
            return []
        cfg = self.config
        query_terms = _tokens(query)
        tokenized = {d.id: _tokens(d.title + " " + d.text) for d in docs}
        avg_len = sum(len(t) for t in tokenized.values()) / len(tokenized)
        doc_freqs: dict[str, int] = {}
        for toks in tokenized.values():
            for term in set(toks):
                doc_freqs[term] = doc_freqs.get(term, 0) + 1
        engagement = self._engagement_norm(docs)
        clusters = cluster_documents(docs, cfg.cluster_similarity)
        cluster_platforms: dict[str, set[str]] = {}
        for d in docs:
            cluster_platforms.setdefault(clusters[d.id], set()).add(d.platform)

        raw_scores: dict[str, tuple[float, list[SignalContribution], float]] = {}
        max_bm25 = max((bm25_score(query_terms, tokenized[d.id], avg_len, doc_freqs, len(docs)) for d in docs), default=0.0) or 1.0
        for d in docs:
            bm = bm25_score(query_terms, tokenized[d.id], avg_len, doc_freqs, len(docs)) / max_bm25
            rec = self._recency(d)
            auth = cfg.authority.get(d.platform, cfg.unknown_platform_authority)
            eng = engagement[d.id]
            qual = self._quality.get(d.id, d.meta.get("quality_score", 0.5))
            corro = min(1.0, (len(cluster_platforms[clusters[d.id]]) - 1) / 2.0)
            fit, fit_note = self._user_fit(d, user)
            freshness = self._freshness_factor(d) if self._freshness_factor else 1.0
            parts = [
                SignalContribution("relevance", cfg.weight_relevance, round(bm, 4), cfg.weight_relevance * bm),
                SignalContribution("recency", cfg.weight_recency, round(rec, 4), cfg.weight_recency * rec),
                SignalContribution("authority", cfg.weight_authority, round(auth, 4), cfg.weight_authority * auth),
                SignalContribution("engagement", cfg.weight_engagement, round(eng, 4), cfg.weight_engagement * eng),
                SignalContribution("quality", cfg.weight_quality, round(qual, 4), cfg.weight_quality * qual),
                SignalContribution("corroboration", cfg.weight_corroboration, round(corro, 4), cfg.weight_corroboration * corro),
                SignalContribution("user_fit", cfg.weight_user_fit, round(fit, 4), cfg.weight_user_fit * fit, note=fit_note),
            ]
            scam = self._scam_signals.get(d.id, ())
            penalty = min(cfg.scam_penalty_cap, cfg.scam_penalty_per_signal * len(scam)) / 100.0
            total = sum(p.contribution for p in parts) / cfg.total_weight()
            total = max(0.0, total * freshness - penalty)
            raw_scores[d.id] = (total, parts, penalty * 100.0)

        ordered = sorted(docs, key=lambda d: raw_scores[d.id][0], reverse=True)
        ranked: list[RankedDocument] = []
        for position, d in enumerate(ordered, start=1):
            total, parts, penalty = raw_scores[d.id]
            ranked.append(RankedDocument(
                doc_id=d.id,
                url=d.meta.get("canonical_url", d.url),
                platform=d.platform,
                title=d.title,
                score=round(total * 100.0, 2),
                rank=position,
                breakdown=tuple(parts),
                cluster_id=clusters[d.id],
                corroborating_platforms=tuple(sorted(cluster_platforms[clusters[d.id]])),
                scam_penalty=round(penalty, 2),
            ))
        return ranked
