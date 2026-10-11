"""S2.11 / c33.content - content draft engine.

Source excerpt (verbatim): "gather posts... slightly altered it using ai and
post it".

ORIGINAL drafts inspired by supplied themes, with a near-duplicate check
against supplied sources. Posting stays manual; account creation and
autoposting are refused through the standing guard. Substitute for X3.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_THEMES = 256
MAX_SOURCES = 1024
COPY_THRESHOLD = 0.6

FRAMES = ("a field note on", "an honest build log about", "a checklist for",
          "a beginner's map to", "three mistakes in")


def _words(text):
    return frozenset(w.strip(".,;:!?()\"'").lower() for w in text.split() if w.strip())


def _jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def draft(themes, sources=None, post=False, create_accounts=False, accounts=None):
    """Original draft per supplied theme; near-duplicates of sources refused.

    create_accounts: False (no account path), True (bare request - refused,
    unverifiable), or a list of platforms to propose HER first official
    account on. The one-account-per-platform rule is enforced against the
    supplied `accounts` registry and within the request itself."""
    if post:
        policy.check("autopost", PREFIX)  # posting stays manual
    proposals = None
    if create_accounts is True:
        policy.check("fakeacct", PREFIX)  # bare request: cannot verify one-account rule
    elif create_accounts:
        if isinstance(create_accounts, bool) or not isinstance(create_accounts, (list, tuple)):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:create_accounts")
        if accounts is not None and (isinstance(accounts, bool)
                                     or not isinstance(accounts, (list, tuple))):
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:existing")
        registry = list(accounts) if accounts is not None else []
        proposals = []
        for platform in create_accounts:
            proposals.append(policy.check_account(platform, registry, PREFIX))
            registry.append(proposals[-1])  # two new on one platform refuse too
    if isinstance(themes, bool) or not isinstance(themes, (list, tuple)):
        raise ValueError("SOCIAL_REFUSED_BAD_TYPE:themes")
    if not themes:
        raise ValueError("SOCIAL_REFUSED_EMPTY:themes")
    if len(themes) > MAX_THEMES:
        raise ValueError("SOCIAL_REFUSED_OVERSIZE")
    cleaned = [policy.clean_text(t, PREFIX, "theme", 128) for t in themes]
    src_texts = []
    if sources is not None:
        if not isinstance(sources, (list, tuple)) or len(sources) > MAX_SOURCES:
            raise ValueError("SOCIAL_REFUSED_BAD_TYPE:sources")
        for s in sources:
            if not isinstance(s, dict):
                raise ValueError("SOCIAL_REFUSED_BAD_TYPE:source")
            policy.clean_text(s.get("id"), PREFIX, "source_id", 128)
            src_texts.append(policy.clean_text(s.get("text"), PREFIX, "source_text", 20000))
    src_words = [_words(t) for t in src_texts]
    drafts = []
    for i, theme in enumerate(cleaned):
        frame = FRAMES[i % len(FRAMES)]
        body = "%s %s: an original take, built from first-hand notes and her own angle" % (frame, theme)
        score = max((_jaccard(_words(body), sw) for sw in src_words), default=0.0)
        if score > COPY_THRESHOLD:
            raise ValueError("SOCIAL_REFUSED_COPY")
        drafts.append({"theme": theme, "draft": body, "originality": round(1.0 - score, 6)})
    out = {"drafts": drafts, "draft_count": len(drafts), "copy_threshold": COPY_THRESHOLD,
           "scope": policy.scope(
                ["original drafts inspired by themes", "near-duplicate check vs supplied sources",
                 "enforced one-account-per-platform proposals"],
                ["posting anywhere", "creating accounts herself (proposals only)",
                 "altering and reposting others' posts"],
                "supplied themes and source texts")}
    if proposals is not None:
        out["account_proposals"] = proposals
    return out


def report(themes, sources=None):
    return draft(themes, sources)
