"""Source-neutral parsing, deduplication, and merge rules."""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import replace
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from .models import Opportunity, Provenance, stable_digest

_SPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[a-z0-9]+")
_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(_TAG.sub(" ", str(value)))
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = clean_text(value)
    raw = raw.replace("Z", "+00:00")
    for candidate in (raw, raw[:10]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def parse_money(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return max(0, round(value))
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    return None if not match else max(0, round(float(match.group().replace(",", ""))))


def canonical_url(url: str) -> str:
    from urllib.parse import parse_qsl, urlencode
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in _TRACKING]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def make_provenance(source: str, source_id: str, source_url: str, raw: Any, fetched_at: datetime | None = None) -> Provenance:
    return Provenance(source, source_id, canonical_url(source_url), fetched_at or datetime.now(timezone.utc), stable_digest(raw))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()))


def duplicate_score(a: Opportunity, b: Opportunity) -> float:
    if any(p.source == q.source and p.source_id == q.source_id for p in a.provenance for q in b.provenance):
        return 1.0
    if canonical_url(a.canonical_url) == canonical_url(b.canonical_url):
        return 1.0
    title = SequenceMatcher(None, clean_text(a.title).lower(), clean_text(b.title).lower()).ratio()
    sponsors = SequenceMatcher(None, clean_text(a.sponsor).lower(), clean_text(b.sponsor).lower()).ratio()
    token_union = _tokens(a.title) | _tokens(b.title)
    jaccard = len(_tokens(a.title) & _tokens(b.title)) / max(1, len(token_union))
    close_match = a.close_date is None or b.close_date is None or abs((a.close_date - b.close_date).days) <= 7
    return (0.55 * title + 0.25 * jaccard + 0.20 * sponsors) * (1.0 if close_match else 0.75)


def _merge(a: Opportunity, b: Opportunity) -> Opportunity:
    # Prefer the richer/newer record for scalar text, retain the earliest open and latest close.
    primary, secondary = (a, b) if len(a.description) >= len(b.description) else (b, a)
    provenance = tuple({(p.source, p.source_id, p.raw_sha256): p for p in (*a.provenance, *b.provenance)}.values())
    updated = max((x for x in (a.updated_at, b.updated_at) if x is not None), default=None)
    return replace(
        primary,
        description=primary.description or secondary.description,
        open_date=min((x for x in (a.open_date, b.open_date) if x), default=None),
        close_date=max((x for x in (a.close_date, b.close_date) if x), default=None),
        amount_min=min((x for x in (a.amount_min, b.amount_min) if x is not None), default=None),
        amount_max=max((x for x in (a.amount_max, b.amount_max) if x is not None), default=None),
        countries=tuple(sorted(set(a.countries) | set(b.countries))),
        eligibility=tuple(sorted(set(a.eligibility) | set(b.eligibility))),
        tags=tuple(sorted(set(a.tags) | set(b.tags))),
        provenance=provenance,
        updated_at=updated,
    )


def deduplicate(items: Iterable[Opportunity], threshold: float = 0.84) -> list[Opportunity]:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    output: list[Opportunity] = []
    for candidate in items:
        for index, existing in enumerate(output):
            if duplicate_score(candidate, existing) >= threshold:
                output[index] = _merge(existing, candidate)
                break
        else:
            output.append(candidate)
    return output
