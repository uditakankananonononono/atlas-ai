"""Brand-fit ranking: TF-IDF cosine over mission text plus audience-tag overlap.

Real computation, no LLM, no network. Every score carries the terms that produced it.
This is a lexical model: it cannot see synonyms ("scientist" vs "researcher").
Scores are relative to the candidate set given (IDF is computed over those candidates + the creator).
"""
from __future__ import annotations
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

STOP = frozenset("a an and are as at be by for from in is it of on or that the to with we our your their this these those into more most".split())
_TOK = re.compile(r"[a-z0-9]+")


def _stem(w: str) -> str:
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ers", ""), ("ed", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) + len(rep) >= 3 and not (suf == "s" and w.endswith("ss")):
            return w[: len(w) - len(suf)] + rep
    return w


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOK.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass(frozen=True)
class BrandFit:
    brand_id: str
    score: float  # 0..1
    text_cosine: float
    tag_overlap: float
    shared_terms: list[str] = field(default_factory=list)
    shared_tags: list[str] = field(default_factory=list)


def rank_brands(creator_mission: str, creator_tags: Sequence[str],
                candidates: Iterable[tuple[str, str, Sequence[str]]],
                tag_weight: float = 0.3) -> list[BrandFit]:
    """candidates: (brand_id, mission, audience_tags). Returns best-first; ties broken by brand_id."""
    if not 0 <= tag_weight <= 1:
        raise ValueError("tag_weight must be within [0, 1]")
    cands = list(candidates)
    ids = [c[0] for c in cands]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate brand_id")
    docs = [Counter(tokens(c[1])) for c in cands]
    cdoc = Counter(tokens(creator_mission))
    n = len(docs) + 1
    df: Counter = Counter()
    for d in docs + [cdoc]:
        df.update(d.keys())
    idf = {t: math.log((1 + n) / (1 + df[t])) + 1.0 for t in df}

    def vec(d: Counter) -> dict[str, float]:
        return {t: (1 + math.log(c)) * idf[t] for t, c in d.items()}

    def norm(v): return math.sqrt(sum(x * x for x in v.values()))
    cv = vec(cdoc); cn = norm(cv)
    ctags = {t.strip().lower() for t in creator_tags if t.strip()}
    out = []
    for (bid, _m, tags), d in zip(cands, docs):
        bv = vec(d); bn = norm(bv)
        shared = sorted(set(cv) & set(bv))
        cos = sum(cv[t] * bv[t] for t in shared) / (cn * bn) if cn and bn else 0.0
        btags = {t.strip().lower() for t in tags if t.strip()}
        st = sorted(ctags & btags)
        jac = len(st) / len(ctags | btags) if (ctags | btags) else 0.0
        score = (1 - tag_weight) * cos + tag_weight * jac
        out.append(BrandFit(bid, round(min(1.0, max(0.0, score)), 6), round(cos, 6), round(jac, 6), shared, st))
    return sorted(out, key=lambda f: (-f.score, f.brand_id))
