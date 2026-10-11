"""S2.2 / c33.corpus - public-post corpus analyzer.

Source excerpt (verbatim): "go through all posts ever on social media and
analyse them... that's where you'll learn how humans are like".

Topic, sentiment, emotion and virality features over a SUPPLIED public
research-dump corpus. Corpus size is reported honestly; nothing is scraped.
Stdlib only, offline, deterministic. Substitute for X2.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_POSTS = 100000
TOPICS = {
    "tech": ("ai", "app", "code", "software", "robot"),
    "beauty": ("makeup", "skincare", "gloss", "fragrance"),
    "politics": ("election", "policy", "government", "vote"),
    "sports": ("game", "match", "score", "team"),
}
POS = ("love", "great", "happy", "amazing", "best", "good")
NEG = ("hate", "bad", "worst", "angry", "sad", "terrible")
EMOTIONS = {
    "joy": ("love", "happy", "amazing"),
    "anger": ("hate", "angry", "furious"),
    "fear": ("scared", "afraid", "worried"),
}


def _count(text, words):
    return sum(text.count(w) for w in words)


def analyze(posts):
    """Feature analysis over supplied public posts; honest corpus size."""
    if isinstance(posts, bool) or not isinstance(posts, (list, tuple)):
        raise ValueError("SOCIAL_REFUSED_BAD_TYPE:posts")
    if not posts:
        raise ValueError("SOCIAL_REFUSED_EMPTY:posts")
    if len(posts) > MAX_POSTS:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    topic_counts = {t: 0 for t in TOPICS}
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    emotion_counts = {e: 0 for e in EMOTIONS}
    total_virality = 0
    for p in posts:
        if not isinstance(p, dict):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:post")
        policy.clean_text(p.get("id"), PREFIX, "id", 128)
        text = policy.clean_text(p.get("text"), PREFIX, "text", 20000).lower()
        likes = p.get("likes", 0)
        shares = p.get("shares", 0)
        for v, name in ((likes, "likes"), (shares, "shares")):
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError("SOCIAL_REFUSED_BAD_TYPE:" + name)
        for t in TOPICS:
            if _count(text, TOPICS[t]):
                topic_counts[t] += 1
        pos, neg = _count(text, POS), _count(text, NEG)
        sentiment_counts["positive" if pos > neg else "negative" if neg > pos else "neutral"] += 1
        for e in EMOTIONS:
            emotion_counts[e] += _count(text, EMOTIONS[e])
        total_virality += likes + shares
    n = len(posts)
    return {"corpus_size": n, "topic_counts": topic_counts,
            "sentiment_counts": sentiment_counts, "emotion_counts": emotion_counts,
            "avg_virality": round(total_virality / n, 6),
            "scope": policy.scope(
                ["topic/sentiment/emotion/virality features over a supplied corpus",
                 "honest corpus size"],
                ["scraping or bulk access to platform posts", "all posts ever"],
                "supplied public research dataset")}


def report(posts):
    return analyze(posts)
