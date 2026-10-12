"""Group 69: novelty-scored idea generation from an ingested corpus.

Pairs high-weight topics across different source clusters, then scores each
pair's novelty by how rarely the two terms co-occur in the corpus (PMI-style
rarity, computed here) and emits build tickets. Heuristic combinatorial
ideation with measured novelty; not a trained creativity model.
"""
from __future__ import annotations
import itertools, math, re
from collections import Counter


def _terms(t):
    return set(re.findall(r"[a-z][a-z\-]{3,}", t.lower()))


def generate(docs, topics, k=10, min_df=2):
    """docs: list of text; topics: list of topic strings (e.g. interest_signals.rank)."""
    sets = [_terms(d) for d in docs]
    df = Counter(t for s in sets for t in s)
    n = max(len(sets), 1)
    cand = [t for t in topics if df[t] >= min_df]
    ideas = []
    for a, b in itertools.combinations(cand, 2):
        co = sum(1 for s in sets if a in s and b in s)
        expected = df[a] * df[b] / n
        novelty = 1.0 / (1.0 + co) * math.log1p(expected)  # rare pairing of common terms
        ideas.append({"pair": (a, b), "cooccurrence": co, "novelty": round(novelty, 4)})
    ideas.sort(key=lambda i: (-i["novelty"], i["pair"]))
    for i in ideas[:k]:
        a, b = i["pair"]
        i["ticket"] = {"title": "Prototype: %s x %s" % (a, b),
                       "acceptance": ["write a one-page problem statement linking %s and %s" % (a, b),
                                      "find 3 corpus documents mentioning each side",
                                      "ship a runnable prototype with a test"],
                       "evidence_docs": [j for j, s in enumerate(sets) if a in s or b in s][:5]}
    return ideas[:k]
