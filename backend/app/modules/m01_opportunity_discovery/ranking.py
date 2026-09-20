"""Explainable deterministic opportunity ranking."""
from __future__ import annotations

import math
import re
from datetime import date

from .models import Opportunity, RankedOpportunity, SearchQuery

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def rank(opportunity: Opportunity, query: SearchQuery, *, today: date | None = None) -> RankedOpportunity:
    today = today or date.today()
    wanted = _tokens(query.text)
    title = _tokens(opportunity.title)
    body = _tokens(f"{opportunity.description} {' '.join(opportunity.tags)}")
    title_overlap = len(wanted & title) / max(1, len(wanted))
    body_overlap = len(wanted & body) / max(1, len(wanted))
    score = 55.0 * title_overlap + 20.0 * body_overlap
    reasons = []
    if title_overlap:
        reasons.append(f"title matches {round(100 * title_overlap)}% of query terms")
    if body_overlap:
        reasons.append(f"description/tags match {round(100 * body_overlap)}% of query terms")
    if query.kinds and opportunity.kind in query.kinds:
        score += 8
        reasons.append("requested opportunity type")
    if query.countries and set(map(str.upper, query.countries)) & set(map(str.upper, opportunity.countries)):
        score += 7
        reasons.append("requested geography")
    desired_eligibility = {x.lower() for x in query.eligibility}
    actual_eligibility = {x.lower() for x in opportunity.eligibility}
    if desired_eligibility and desired_eligibility & actual_eligibility:
        score += 8
        reasons.append("eligibility match")
    if query.min_amount is not None and opportunity.amount_max is not None and opportunity.amount_max >= query.min_amount:
        score += 4
        reasons.append("meets funding floor")
    if opportunity.close_date:
        days = (opportunity.close_date - today).days
        if days < 0:
            score -= 50
            reasons.append("deadline passed")
        else:
            score += min(8.0, 2.0 * math.log1p(days))
            reasons.append(f"{days} days until deadline")
    else:
        reasons.append("deadline not supplied by source")
    return RankedOpportunity(opportunity, round(max(0.0, min(100.0, score)), 3), tuple(reasons))


def rank_all(items: list[Opportunity], query: SearchQuery, *, today: date | None = None) -> list[RankedOpportunity]:
    ranked = [rank(item, query, today=today) for item in items]
    return sorted(ranked, key=lambda x: (-x.score, x.opportunity.close_date or date.max, x.opportunity.id))[: query.limit]
