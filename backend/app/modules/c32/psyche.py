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
