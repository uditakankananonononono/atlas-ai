"""S2.9 / c32.psyche - emotion-psychology model.

Source excerpt (verbatim): "think with human emotions all, physchology and
all way human to the bone".

Lexicon + rule-based emotion and motive tagging over SUPPLIED text, with
documented validity limits. It never claims to feel. Stdlib only, offline,
deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
EMOTIONS = {
    "joy": ("happy", "joy", "love", "delighted", "excited"),
    "anger": ("angry", "furious", "rage", "annoyed", "mad"),
    "fear": ("afraid", "fear", "scared", "anxious", "worried"),
    "sadness": ("sad", "grief", "sorrow", "down", "lonely"),
    "surprise": ("surprised", "shocked", "amazed", "unexpected"),
    "trust": ("trust", "believe", "rely", "faith"),
}
MOTIVES = {
    "achievement": ("win", "achieve", "goal", "master", "succeed"),
    "affiliation": ("friend", "together", "belong", "community", "family"),
    "power": ("control", "lead", "power", "influence", "command"),
}
VALIDITY_LIMITS = ("Lexicon-and-rule counts over supplied text only. Tags are surface cues, "
                   "not measurement of any person's actual emotions or motives; no clinical, "
                   "diagnostic or truth value.")


def tag(text):
    """Tag emotions and motives in one supplied text."""
    body = policy.clean_text(text, PREFIX, "text", 200000)
    low = body.lower()
    emotions = {e: sum(low.count(w) for w in words) for e, words in EMOTIONS.items()}
    motives = {m: sum(low.count(w) for w in words) for m, words in MOTIVES.items()}
    dominant_emotion = max(EMOTIONS, key=lambda e: (emotions[e], )) if any(emotions.values()) else None
    dominant_emotion = None
    if any(emotions.values()):
        dominant_emotion = sorted((-v, k) for k, v in emotions.items() if v)[0][1]
    return {"emotions": emotions, "motives": motives, "dominant_emotion": dominant_emotion,
            "emotion_total": sum(emotions.values()), "motive_total": sum(motives.values()),
            "validity_limits": VALIDITY_LIMITS, "claims_feeling": False,
            "scope": policy.scope(
                ["lexicon/rule emotion and motive tagging", "documented validity limits"],
                ["feeling anything", "clinical or diagnostic claims"],
                "supplied text")}


def tag_evidence(text):
    """Whole-token cue evidence with negation; never a personality diagnosis.

    The legacy tag function is preserved for callers expecting raw substring
    counts. This path does not count 'mad' in 'made' or 'sad' in 'saddle'.
    """
    import re
    body = policy.clean_text(text, PREFIX, 'text', 200000, allow_ws=True)
    tokens = list(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", body.lower()))
    evidence = {'emotions': {}, 'motives': {}}
    for group, lexicon in (('emotions', EMOTIONS), ('motives', MOTIVES)):
        for category, words in lexicon.items():
            hits = []
            for i, token in enumerate(tokens):
                if token.group() not in words:
                    continue
                previous = tokens[max(0, i - 3):i]
                # Do not carry negation across a sentence boundary.
                previous = [p for p in previous if not any(c in body[p.end():token.start()] for c in '.!?;\n')]
                negated = any(p.group() in ('not', 'no', 'never', "isn't", "wasn't", "don't") for p in previous)
                hits.append({'cue': token.group(), 'start': token.start(), 'end': token.end(),
                             'negated': negated})
            evidence[group][category] = hits
    counts = {group: {category: sum(not h['negated'] for h in hits)
                      for category, hits in categories.items()}
              for group, categories in evidence.items()}
    return {**counts, 'evidence': evidence, 'claims_feeling': False, 'validity_limits': VALIDITY_LIMITS,
            'method': 'whole-token lexicon with three-token sentence-bounded negation'}
