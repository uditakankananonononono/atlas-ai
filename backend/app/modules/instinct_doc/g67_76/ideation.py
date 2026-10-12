"""Group 69: novelty-scored idea generation from an ingested corpus.

Pairs every two supplied topics that each appear in at least min_df corpus
documents (no source-cluster check is done), then scores each pair's novelty
by how rarely the two terms co-occur in the corpus (a PMI-style rarity score
computed here) and emits build tickets. Heuristic combinatorial
ideation with a computed novelty score; not a trained creativity model.
"""
from __future__ import annotations
import itertools, math, re
from collections import Counter


def _norm(t):
    return " " + " ".join(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", t.lower())) + " "


def generate(docs, topics, k=10, min_df=2):
    """docs: list of str; topics: list of str, single or multi-word (phrase match on
    word boundaries, case-insensitive)."""
    if not isinstance(docs, list) or not all(isinstance(d, str) for d in docs):
        raise ValueError("IDEATION_REFUSED_DOCS")
    if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
        raise ValueError("IDEATION_REFUSED_TOPICS")
    for name, v, lo in (("k", k, 0), ("min_df", min_df, 1)):
        if isinstance(v, bool) or not isinstance(v, int) or v < lo:
            raise ValueError("IDEATION_REFUSED_%s" % name.upper())
    normdocs = [_norm(d) for d in docs]
    seen, labels = set(), {}
    for t in topics:
        n = _norm(t)
        if n.strip() and n not in seen:
            seen.add(n)
            labels[n] = t.strip()
    has = {n: {j for j, d in enumerate(normdocs) if n in d} for n in labels}
    df = {n: len(v) for n, v in has.items()}
    n_docs = max(len(docs), 1)
    cand = [n for n in labels if df[n] >= min_df]
    ideas = []
    for a, b in itertools.combinations(cand, 2):
        co = len(has[a] & has[b])
        expected = df[a] * df[b] / n_docs
        novelty = 1.0 / (1.0 + co) * math.log1p(expected)  # rare pairing of common terms
        ideas.append({"pair": (labels[a], labels[b]), "cooccurrence": co, "novelty": round(novelty, 4),
                      "_docs": sorted(has[a] | has[b])})
    ideas.sort(key=lambda i: (-i["novelty"], i["pair"]))
    for i in ideas[:k]:
        a, b = i["pair"]
        i["ticket"] = {"title": "Prototype: %s x %s" % (a, b),
                       "acceptance": ["write a one-page problem statement linking %s and %s" % (a, b),
                                      "find 3 corpus documents mentioning each side",
                                      "ship a runnable prototype with a test"],
                       "evidence_docs": i["_docs"][:5]}
    for i in ideas:
        i.pop("_docs")
    return ideas[:k]
