"""S2.7 / c32.dossier - person-and-venture dossier.

Source excerpt (verbatim): "critically dig up every single thing about every
successful person in any field, every venture, every major news, event".

Dossier over SUPPLIED public sources with citations and a computed
completeness score. Public figures, public facts only; nothing is fetched.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
MAX_SOURCES = 128
MAX_FACTS_PER_DIM = 8
DIMENSIONS = {
    "background": ("born", "grew up", "early", "studied", "education"),
    "career": ("founded", "worked", "career", "role", "joined", "built"),
    "ventures": ("company", "venture", "startup", "business", "launched"),
    "recognition": ("award", "recognition", "prize", "ranked", "honor"),
    "recent_news": ("recently", "announced", "news", "this year", "latest"),
}


def _sentences(text):
    out, cur = [], []
    for ch in text:
        cur.append(ch)
        if ch in ".!?":
            s = "".join(cur).strip()
            if s:
                out.append(s)
            cur = []
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


def dossier(subject, sources, include_private=False):
    """Dossier on subject from supplied public sources, with citations."""
    if include_private:
        raise ValueError("TREND_REFUSED_PRIVATE")  # public figures, public facts only
    name = policy.clean_text(subject, PREFIX, "subject", 128)
    if isinstance(sources, bool) or not isinstance(sources, (list, tuple)):
        raise ValueError("TREND_REFUSED_BAD_TYPE:sources")
    if not sources:
        raise ValueError("TREND_REFUSED_EMPTY:sources")
    if len(sources) > MAX_SOURCES:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    tokens = [t.lower() for t in name.split()]
    dims = {}
    citation_count = 0
    for src in sources:
        if not isinstance(src, dict):
            raise ValueError("TREND_REFUSED_BAD_TYPE:source")
        url = policy.clean_text(src.get("url"), PREFIX, "url", 512)
        text = policy.clean_text(src.get("text"), PREFIX, "text", 200000)
        for s in _sentences(text):
            low = s.lower()
            if not any(t in low for t in tokens):
                continue
            for dim, keywords in DIMENSIONS.items():
                if any(k in low for k in keywords):
                    bucket = dims.setdefault(dim, [])
                    if len(bucket) < MAX_FACTS_PER_DIM:
                        bucket.append({"source": url, "fact": s})
                        citation_count += 1
    covered = sum(1 for d in dims.values() if d)
    return {"subject": name, "dimensions": dims,
            "completeness": round(covered / len(DIMENSIONS), 6),
            "dimensions_covered": covered, "dimension_count": len(DIMENSIONS),
            "citation_count": citation_count, "source_count": len(sources),
            "scope": policy.scope(
                ["cited dossier over supplied public sources", "computed completeness score"],
                ["fetching", "private facts", "every-single-thing coverage"],
                "supplied public sources")}
