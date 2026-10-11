"""S2.8 / c32.thought - human-thought corpus analyzer.

Source excerpt (verbatim): "Analyse intelligent human thinking process
across media from podcasts, books, audio, music etc all forms".

Reasoning-move tagging over SUPPLIED transcripts/text/lyrics. Audio itself is
not transcribed offline (no bundled ASR); audio entries are refused and the
limit is reported. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
MAX_TEXTS = 10000
MOVES = {
    "analogy": ("like a", "as if", "similar to", "reminds"),
    "inversion": ("opposite", "in reverse", "instead", "backwards"),
    "first_principles": ("first principles", "fundamental", "from scratch", "why is"),
    "narrative": ("story", "journey", "once", "chapter"),
    "heuristic": ("rule of thumb", "usually", "tends to", "as a rule"),
    "systems": ("feedback", "loop", "system", "emerges", "network"),
}
KINDS = ("transcript", "text", "lyrics")


def analyze(texts):
    """Tag reasoning moves in supplied texts; returns per-doc tags and totals."""
    if isinstance(texts, bool) or not isinstance(texts, (list, tuple)):
        raise ValueError("TREND_REFUSED_BAD_TYPE:texts")
    if not texts:
        raise ValueError("TREND_REFUSED_EMPTY:texts")
    if len(texts) > MAX_TEXTS:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    docs = []
    totals = {k: 0 for k in MOVES}
    for t in texts:
        if not isinstance(t, dict):
            raise ValueError("TREND_REFUSED_BAD_TYPE:text")
        kind = t.get("kind", "text")
        if kind == "audio":
            raise ValueError("TREND_REFUSED_AUDIO")  # offline: no bundled ASR
        if kind not in KINDS:
            raise ValueError("TREND_REFUSED_BAD_KIND:" + str(kind)[:64])
        tid = policy.clean_text(t.get("id"), PREFIX, "id", 64)
        body = policy.clean_text(t.get("text"), PREFIX, "text", 200000)
        low = body.lower()
        tags = {move: sum(low.count(k) for k in keys) for move, keys in MOVES.items()}
        docs.append({"id": tid, "kind": kind, "moves": tags,
                     "move_total": sum(tags.values())})
        for k, v in tags.items():
            totals[k] += v
    docs.sort(key=lambda d: (-d["move_total"], d["id"]))
    return {"docs": docs, "doc_count": len(docs), "move_totals": totals,
            "scope": policy.scope(
                ["reasoning-move tagging over supplied transcripts/text/lyrics"],
                ["audio transcription (no bundled ASR offline)", "all forms of media"],
                "supplied transcripts/text/lyrics")}
