"""S2.6 / c32.ideate - original-thinking engine.

Source excerpt (verbatim): "able to think originally (train models
specifically for this purpose)", "merge cool and weird ideas together in a
similar way to how humans brainstorm", "make fiction into reality".

Combinatorial recombination of SUPPLIED concepts (pairs x SCAMPER-style
operations) with a novelty score against a supplied prior-art index. Training
data export is a record; training itself is a compute purchase (guard).
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
MAX_CONCEPTS = 64
MAX_PRIOR_ART = 4096
OPS = ("substitute", "combine", "adapt", "modify", "eliminate", "reverse")


def _words(text):
    return frozenset(w.strip(".,;:!?()\"'").lower() for w in text.split() if w.strip())


def _jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def ideate(concepts, prior_art=None, train=False):
    """Recombine supplied concepts; returns ranked ideas and counts."""
    if train:
        policy.check("spend", PREFIX)  # training is a compute purchase
    if isinstance(concepts, bool) or not isinstance(concepts, (list, tuple)):
        raise ValueError("TREND_REFUSED_BAD_TYPE:concepts")
    if len(concepts) < 2:
        raise ValueError("TREND_REFUSED_TOO_FEW:concepts")
    if len(concepts) > MAX_CONCEPTS:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    cleaned = [policy.clean_text(c, PREFIX, "concept", 256) for c in concepts]
    prior = []
    if prior_art is not None:
        if not isinstance(prior_art, (list, tuple)) or len(prior_art) > MAX_PRIOR_ART:
            raise ValueError("TREND_REFUSED_BAD_TYPE:prior_art")
        prior = [policy.clean_text(p, PREFIX, "prior_art", 512) for p in prior_art]
    prior_words = frozenset().union(*(_words(p) for p in prior)) if prior else frozenset()
    ideas = []
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            for op in OPS:
                idea = "%s: %s x %s" % (op, cleaned[i], cleaned[j])
                novelty = 1.0 - _jaccard(_words(idea), prior_words)
                ideas.append({"pair": [cleaned[i], cleaned[j]], "op": op,
                              "idea": idea, "novelty": round(novelty, 6)})
    ideas.sort(key=lambda d: (-d["novelty"], d["idea"]))
    return {"ideas": ideas, "idea_count": len(ideas),
            "concept_count": len(cleaned), "prior_art_count": len(prior),
            "scope": policy.scope(
                ["combinatorial recombination", "novelty scoring vs supplied prior art",
                 "training-data export as record"],
                ["model training (compute purchase)", "fiction made real"],
                "supplied concept list and prior-art index")}
