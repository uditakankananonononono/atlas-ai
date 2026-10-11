"""S2.12 / c33.persona - persona-per-field voice profiles.

Source excerpt (verbatim): "replicate human essence and personality into
individual fields as suitable".

Voice/tone profiles per field built from SUPPLIED writing samples. Profiles
are style guidance, never impersonation of real people. Stdlib only,
offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_SAMPLES = 256
STOP = frozenset("a an the and or of to in on for with is are was were it its my i me you".split())
FORMAL = ("therefore", "however", "furthermore", "regarding", "thus")
INFORMAL = ("gonna", "wanna", "lol", "omg", "yeah", "kinda", "literally")


def _words(text):
    return [w.strip(".,;:!?()\"'").lower() for w in text.split() if w.strip(".,;:!?()\"'")]


def profile(field, samples, real_person=None):
    """Voice/tone profile for a field from supplied writing samples."""
    if real_person is not None:
        raise ValueError("SOCIAL_REFUSED_IMPERSONATE")  # style guidance, never a real person
    name = policy.clean_text(field, PREFIX, "field", 64)
    if isinstance(samples, bool) or not isinstance(samples, (list, tuple)):
        raise ValueError("SOCIAL_REFUSED_BAD_TYPE:samples")
    if not samples:
        raise ValueError("SOCIAL_REFUSED_EMPTY:samples")
    if len(samples) > MAX_SAMPLES:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    cleaned = [policy.clean_text(s, PREFIX, "sample", 50000) for s in samples]
    total_words = 0
    total_sentences = 0
    formal = 0
    informal = 0
    freq = {}
    for text in cleaned:
        words = _words(text)
        total_words += len(words)
        sentences = sum(text.count(c) for c in ".!?") or 1
        total_sentences += sentences
        formal += sum(words.count(w) for w in FORMAL)
        informal += sum(words.count(w) for w in INFORMAL)
        for w in words:
            if w not in STOP:
                freq[w] = freq.get(w, 0) + 1
    top = sorted((-c, w) for w, c in freq.items())[:5]
    avg_sentence = round(total_words / total_sentences, 6) if total_sentences else 0.0
    tone = "formal" if formal > informal else "informal" if informal > formal else "neutral"
    return {"field": name,
            "voice": {"avg_sentence_length": avg_sentence, "tone": tone,
                      "formal_markers": formal, "informal_markers": informal,
                      "top_words": [w for _, w in top]},
            "sample_count": len(cleaned),
            "guidance": "style guidance built from her supplied samples; not impersonation of any real person",
            "scope": policy.scope(
                ["voice/tone profiles per field", "computed style features"],
                ["impersonating real people", "capturing human essence"],
                "supplied writing samples")}


def report(field, samples):
    return profile(field, samples)
