"""S2.10 / c33.niches - viral-niche generator.

Source excerpt (verbatim): "Create new, viral apps, contents, trends etc on
thousands and millions of niches".

Enumerates niches as taxonomy x audience x format over SUPPLIED vocabularies,
scores each by supplied trend/competition numbers, outputs ranked drafts.
The count is computed and reported; "millions" is enumeration capacity only.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_NICHES = 10000
MAX_VOCAB = 64


def _vocab(values, name):
    if isinstance(values, bool) or not isinstance(values, (list, tuple)):
        raise ValueError("SOCIAL_REFUSED_BAD_TYPE:" + name)
    if not values:
        raise ValueError("SOCIAL_REFUSED_EMPTY:" + name)
    if len(values) > MAX_VOCAB:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    cleaned = [policy.clean_text(v, PREFIX, name, 64) for v in values]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("SOCIAL_REFUSED_DUPLICATE:" + name)
    return cleaned


def generate(taxonomy, audiences, formats, scores=None):
    """Enumerate and rank niches from supplied vocabularies and scores."""
    tax = _vocab(taxonomy, "taxonomy")
    aud = _vocab(audiences, "audiences")
    fmt = _vocab(formats, "formats")
    total = len(tax) * len(aud) * len(fmt)
    if total > MAX_NICHES:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    score_map = {}
    if scores is not None:
        if not isinstance(scores, dict):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:scores")
        for k, v in scores.items():
            policy.clean_text(k, PREFIX, "score_key", 64)
            if not isinstance(v, dict):
                raise ValueError("SOCIAL_REFUSED_BAD_TYPE:score")
            for field in ("trend", "competition"):
                val = v.get(field, 0)
                if isinstance(val, bool) or not isinstance(val, int):
                    raise ValueError("SOCIAL_REFUSED_BAD_TYPE:" + field)
            score_map[k] = {"trend": v.get("trend", 0), "competition": v.get("competition", 0)}
    niches = []
    for t in tax:
        for a in aud:
            for f in fmt:
                name = "%s for %s as %s" % (t, a, f)
                s = score_map.get(t, {"trend": 0, "competition": 0})
                niches.append({"niche": name, "theme": t, "audience": a, "format": f,
                               "trend": s["trend"], "competition": s["competition"],
                               "score": s["trend"] - s["competition"]})
    niches.sort(key=lambda n: (-n["score"], n["niche"]))
    return {"niches": niches, "niche_count": len(niches), "score_model": "trend - competition",
            "scope": policy.scope(
                ["taxonomy x audience x format enumeration", "supplied-number scoring",
                 "ranked drafts with computed count"],
                ["millions of live niches", "virality guarantees"],
                "supplied vocabularies and scores")}


def report(taxonomy, audiences, formats, scores=None):
    return generate(taxonomy, audiences, formats, scores)
