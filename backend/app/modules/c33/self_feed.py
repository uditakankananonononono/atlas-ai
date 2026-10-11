"""S2.1 / c33.self_feed - feed-and-follow analyzer.

Source excerpt (verbatim): "analyse my feed across social media", "see my
likes and comments on social media", "see the people I follow and try to
create similar work/products they have built but better".

Parses her SUPPLIED official data exports or pasted lists; clusters liked
posts and followed accounts by theme; produces inspiration briefs as drafts.
Public info only about followed accounts. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_ITEMS = 100000
THEMES = {
    "beauty": ("makeup", "skincare", "fragrance", "gloss", "beauty", "lipstick"),
    "tech": ("app", "ai", "code", "software", "gadget", "startup"),
    "fashion": ("outfit", "fashion", "dress", "style", "aesthetic"),
    "study": ("study", "college", "exam", "school", "learning"),
    "business": ("business", "brand", "marketing", "money", "entrepreneur"),
    "art": ("art", "design", "drawing", "music", "anime"),
}


def _themes_of(text):
    low = text.lower()
    return {t for t, words in THEMES.items() if any(w in low for w in words)}


def analyze(export):
    """Cluster her supplied export; returns themes, counts and draft briefs."""
    if isinstance(export, bool) or not isinstance(export, dict):
        raise ValueError("SOCIAL_REFUSED_NOEXPORT")
    liked = export.get("liked")
    follows = export.get("follows")
    if not isinstance(liked, (list, tuple)) or not isinstance(follows, (list, tuple)):
        raise ValueError("SOCIAL_REFUSED_NOEXPORT")
    if len(liked) > MAX_ITEMS or len(follows) > MAX_ITEMS:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    theme_counts = {t: 0 for t in THEMES}
    for item in liked:
        if not isinstance(item, dict):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:liked")
        policy.clean_text(item.get("id"), PREFIX, "liked_id", 128)
        text = policy.clean_text(item.get("text"), PREFIX, "liked_text", 20000)
        for t in _themes_of(text):
            theme_counts[t] += 1
    handles = []
    for f in follows:
        if not isinstance(f, dict):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:follow")
        if f.get("private"):
            raise ValueError("SOCIAL_REFUSED_THIRDPARTYPRIVATE")  # public info only
        handles.append(policy.clean_text(f.get("handle"), PREFIX, "handle", 128))
    top = sorted((-c, t) for t, c in theme_counts.items() if c)
    briefs = [{"theme": t, "liked_count": -c,
               "draft": "similar-but-better draft: an original %s product building on the %d liked-post theme, improved in her own direction" % (t, -c)}
              for c, t in top]
    return {"theme_counts": theme_counts, "top_themes": [t for _, t in top],
            "liked_count": len(liked), "follow_count": len(follows),
            "briefs": briefs, "brief_count": len(briefs),
            "scope": policy.scope(
                ["theme clustering of supplied exports", "inspiration briefs as drafts"],
                ["reading any account directly", "private third-party data",
                 "copying any followed account's work"],
                "her official data export or pasted lists")}
