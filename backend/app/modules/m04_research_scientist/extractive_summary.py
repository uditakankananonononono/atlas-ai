"""Extractive paper summary (M04 row 217), HEURISTIC and offline.

Picks existing sentences from the supplied title and abstract by TF-IDF centrality (sum of
term weights, length-normalised) and returns them verbatim in original order, with positions.
It does not paraphrase, infer, or check claims, and it cannot summarise text that is not in
the abstract (no full-text access). Sentence splitting is a regex plus a short abbreviation list
(Fig., et al., e.g., i.e., vs., Eq., ...); other abbreviations can still split wrongly.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .research_loop import key_terms

_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
MAX_CHARS = 50_000


_ABBREV = re.compile(r"(?:\b(?:Fig|Figs|Eq|Eqs|No|vs|al|e\.g|i\.e|cf|approx|Dr|Prof|Ref|Sec|Tab)\.)$")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SPLIT.split(" ".join(text.split())) if p.strip()]
    out: list[str] = []
    for p in parts:
        if out and _ABBREV.search(out[-1]):
            out[-1] = out[-1] + " " + p  # a known abbreviation ended the previous piece: rejoin
        else:
            out.append(p)
    return out


def summarize(title: str, abstract: str, max_sentences: int = 3) -> dict:
    if not 1 <= max_sentences <= 10:
        raise ValueError("max_sentences 1-10")
    if len(abstract) > MAX_CHARS or len(title) > 1000:
        raise ValueError("input too long")
    sents = split_sentences(abstract)
    if not sents:
        raise ValueError("abstract has no sentences")
    toks = [key_terms(s) for s in sents]
    df = Counter(t for ts in toks for t in set(ts))
    n = len(sents)
    title_terms = set(key_terms(title))
    scores = []
    for i, ts in enumerate(toks):
        if not ts:
            scores.append(0.0); continue
        w = sum((1 + math.log(1 + c)) * math.log(1 + n / df[t]) * (2.0 if t in title_terms else 1.0)
                for t, c in Counter(ts).items())
        scores.append(w / math.sqrt(len(ts)))
    ranked = sorted(range(n), key=lambda i: (-scores[i], i))[:max_sentences]
    chosen = sorted(ranked)
    return {"method": "extractive TF-IDF sentence ranking; verbatim sentences; not abstractive; no claim checking",
            "sentence_count": n, "selected": [{"index": i, "text": sents[i], "score": round(scores[i], 4)} for i in chosen],
            "coverage": f"{len(chosen)} of {n} abstract sentences", "source": "title+abstract only"}
