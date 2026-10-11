"""S2.4 / c32.teardown - pinterest-to-brand teardown.

Source excerpt (verbatim): "it is able to go to pinterest and it see suppose
A new fragrance brand, it thinks like ok what can I do? ... seeing what it's
made of, the founders history, sees how it can be improved, seeing how it's
getting marketed, why it is successful, what can we do to make it more
appealing and millions more analysis."

Fixed-dimension structured teardown over SUPPLIED brand page text. Nothing is
fetched; the analysis-dimension count is reported, never "millions". Affiliate
program signup is hers. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
MAX_TEXT = 200000
MAX_SOURCES = 64

DIMENSIONS = {
    "product_composition": ("made of", "ingredient", "composition", "material", "formula"),
    "founder_history": ("founder", "founded", "history", "started", "story"),
    "marketing_channels": ("marketed", "marketing", "campaign", "ads", "channel", "influencer"),
    "success_factors": ("successful", "success", "popular", "growth", "bestseller", "viral"),
    "improvement_hypotheses": ("improve", "better", "could", "hypothesis", "gap"),
    "appeal_levers": ("appealing", "appeal", "aesthetic", "packaging", "brand", "story"),
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


def teardown(doc):
    """Teardown of one supplied brand document; returns a structured report."""
    if isinstance(doc, bool) or not isinstance(doc, dict):
        raise ValueError("TREND_REFUSED_BAD_TYPE:doc")
    if doc.get("affiliate_signup"):
        raise ValueError("TREND_REFUSED_AUTOSIGNUP")  # signup is hers, never ours
    brand = policy.clean_text(doc.get("brand"), PREFIX, "brand", 128)
    text = policy.clean_text(doc.get("text"), PREFIX, "text", MAX_TEXT)
    sources = doc.get("sources", [])
    if not isinstance(sources, (list, tuple)) or len(sources) > MAX_SOURCES:
        raise ValueError("TREND_REFUSED_BAD_TYPE:sources")
    for s in sources:
        policy.clean_text(s, PREFIX, "source", 512)
    sentences = _sentences(text)
    dims = {}
    for name, keywords in DIMENSIONS.items():
        hits = [s for s in sentences if any(k in s.lower() for k in keywords)]
        dims[name] = hits[:8]
    return {"brand": brand, "dimensions": dims,
            "dimensions_covered": sum(1 for v in dims.values() if v),
            "dimension_count": len(DIMENSIONS),
            "sources_count": len(sources),
            "scope": policy.scope(
                ["fixed-checklist teardown over supplied text"],
                ["fetching brand pages", "affiliate signup", "founder history beyond supplied text"],
                "supplied brand page text/bundle")}
