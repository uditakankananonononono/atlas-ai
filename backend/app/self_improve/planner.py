"""Turn a detected capability gap into a concrete, synthesizable feature plan."""
from __future__ import annotations

import re
from typing import Protocol

from .detector import CapabilityGap
from .plans import CAPABILITY_KINDS, FeaturePlan

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "by", "at", "from", "is", "it", "this", "that", "be", "as", "are",
    "was", "were", "not", "no", "can", "could", "should", "would", "unable",
    "failed", "error", "request", "user", "module",
})

_KIND_RULES: tuple[tuple[str, str], ...] = (
    (r"\bextract|pull out|parse\b", "field_extractor"),
    (r"\bscore|rank|prioriti[sz]e|rate\b", "scoring_rule"),
    (r"\balert|threshold|exceed|over limit|flag\b", "threshold_alert"),
    (r"\bgroup|aggregate|summar|count by|break ?down\b", "aggregator"),
    (r"\bformat|normalize|clean|rename|rewrite|convert\b", "text_transform"),
    (r"\bfilter|only|exclude|include|match\b", "keyword_filter"),
)

_DEFAULT_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "iso_date": r"(\d{4}-\d{2}-\d{2})",
    "number": r"(-?\d+(?:\.\d+)?)",
}


class ProposalRefiner(Protocol):
    """Optional enrichment hook (e.g. a local model via the shared layer).

    Default is NullRefiner: no model, no network, no cost. The engine works
    fully without a refiner; a refiner may only adjust description and
    parameters, never the kind whitelist.
    """

    def refine(self, plan: FeaturePlan, gap: CapabilityGap) -> FeaturePlan: ...


class NullRefiner:
    def refine(self, plan: FeaturePlan, gap: CapabilityGap) -> FeaturePlan:
        return plan


def _keywords_from(text: str, *, limit: int = 6) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9_+-]{2,}", text.lower())
    seen: list[str] = []
    for word in words:
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
    return seen[:limit]


def _name_from(signature: str) -> str:
    words = _keywords_from(signature, limit=3)
    base = "_".join(words) if words else "auto"
    name = re.sub(r"[^a-z0-9_]", "", base.lower())[:40].strip("_") or "auto"
    return f"auto_{name}"


class FeaturePlanner:
    def __init__(self, refiner: ProposalRefiner | None = None) -> None:
        self._refiner = refiner or NullRefiner()

    @staticmethod
    def choose_kind(gap: CapabilityGap) -> str:
        haystack = f"{gap.signature} {gap.detail}".lower()
        for pattern, kind in _KIND_RULES:
            if re.search(pattern, haystack):
                return kind
        return "keyword_filter"

    def plan(self, gap: CapabilityGap) -> FeaturePlan:
        kind = self.choose_kind(gap)
        keywords = _keywords_from(f"{gap.signature} {gap.detail}")
        params: dict = {}
        if kind == "keyword_filter":
            params = {"keywords": keywords or ["relevant"], "mode": "keep"}
        elif kind == "scoring_rule":
            params = {"weights": {k: 1.0 for k in (keywords or ["relevant"])}, "threshold": 1.0}
        elif kind == "text_transform":
            params = {"pattern": r"\s+", "replacement": " "}
        elif kind == "aggregator":
            params = {"group_by": "category", "op": "count", "value_field": "value"}
        elif kind == "threshold_alert":
            params = {"field": "value", "threshold": 0.0, "direction": "above"}
        elif kind == "field_extractor":
            params = {"fields": dict(_DEFAULT_PATTERNS)}
        plan = FeaturePlan(
            module_slug=gap.module_slug, name=_name_from(gap.signature),
            kind=kind, gap_signature=gap.signature,
            description=f"Auto-built {kind} for recurring gap: {gap.signature}",
            params=params,
        )
        if plan.kind not in CAPABILITY_KINDS:  # a hostile refiner cannot widen the whitelist
            raise ValueError(f"refiner returned illegal kind {plan.kind!r}")
        return self._refiner.refine(plan, gap)
