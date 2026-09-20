"""Drafting compliance engine for the Social Media Manager.

Pure, deterministic checks applied to every platform draft before any
approval request is filed. Two goals:

1. Platform correctness: captions fit the platform's hard limits, X/Twitter
   threads are split correctly, carousel sizes stay inside bounds, image
   posts carry alt text.
2. Disclosure compliance: sponsored content must carry an unambiguous paid
   partnership disclosure ("#ad" or "Paid partnership") before it can be
   scheduled. Engagement-bait phrasing and unverifiable superlative claims
   are flagged as warnings for the human reviewer.

Everything here is a pure function - no network, no LLM, no clock - so the
whole engine is testable offline and its verdicts are reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# -- platform limits -----------------------------------------------------------

#: Hard limits from each platform's official documentation.
PLATFORM_LIMITS: dict[str, dict[str, int]] = {
    "instagram": {"caption_chars": 2200, "max_hashtags": 30, "max_carousel_slides": 10, "min_carousel_slides": 2},
    "twitter": {"caption_chars": 280, "max_hashtags": 5, "max_thread_chunks": 25},
    "tiktok": {"caption_chars": 2200, "max_hashtags": 12},
    "linkedin": {"caption_chars": 3000, "max_hashtags": 15},
}

#: Disclosure markers accepted for sponsored content (FTC/ASCI-style norms).
_DISCLOSURE_RE = re.compile(r"(#ad\b|#sponsored\b|paid partnership)", re.IGNORECASE)

#: Phrases that make platform reviewers and audiences distrust a post.
_ENGAGEMENT_BAIT_RE = re.compile(
    r"\b(like (and|&) (share|subscribe)|comment below\b|tag (a friend|someone|three friends)|"
    r"follow (us|me) (for|to)|share (this|to) (win|for a chance))\b",
    re.IGNORECASE,
)

#: Superlative claims a small account cannot substantiate.
_UNVERIFIABLE_CLAIM_RE = re.compile(
    r"\b(world'?s (best|first|largest)|#1\b|guaranteed (results?|growth)|"
    r"scientifically proven|100% (effective|guaranteed))\b",
    re.IGNORECASE,
)

_HASHTAG_RE = re.compile(r"(?<!\w)#\w+")


@dataclass(frozen=True)
class ComplianceIssue:
    """One finding. ``error`` blocks scheduling; ``warning`` informs review."""

    code: str
    severity: str  # "error" | "warning"
    message: str


def count_hashtags(text: str) -> int:
    return len(_HASHTAG_RE.findall(text))


def check_caption(
    platform: str,
    text: str,
    *,
    sponsored: bool = False,
    hashtag_count: int | None = None,
) -> list[ComplianceIssue]:
    """Apply platform limits and disclosure rules to one caption."""
    limits = PLATFORM_LIMITS.get(platform)
    issues: list[ComplianceIssue] = []
    if limits is None:
        return [ComplianceIssue("unknown_platform", "error", f"no limits defined for {platform}")]

    limit = limits["caption_chars"]
    if platform != "twitter" and len(text) > limit:
        issues.append(
            ComplianceIssue(
                "caption_too_long",
                "error",
                f"{platform} captions are limited to {limit} characters; this draft has {len(text)}",
            )
        )

    tags = count_hashtags(text) if hashtag_count is None else hashtag_count
    max_tags = limits["max_hashtags"]
    if tags > max_tags:
        issues.append(
            ComplianceIssue(
                "too_many_hashtags",
                "error",
                f"{platform} allows at most {max_tags} hashtags; this draft has {tags}",
            )
        )

    if platform == "instagram" and re.search(r"https?://", text):
        issues.append(
            ComplianceIssue(
                "link_not_clickable",
                "warning",
                "links in Instagram captions are not clickable; move the call-to-action to the bio link",
            )
        )

    if sponsored and not _DISCLOSURE_RE.search(text):
        issues.append(
            ComplianceIssue(
                "missing_disclosure",
                "error",
                "sponsored content must carry an unambiguous disclosure ('#ad' or 'Paid partnership')",
            )
        )

    bait = _ENGAGEMENT_BAIT_RE.search(text)
    if bait:
        issues.append(
            ComplianceIssue(
                "engagement_bait",
                "warning",
                f"engagement-bait phrasing ({bait.group(0)!r}) is downranked by platform ranking systems",
            )
        )

    claim = _UNVERIFIABLE_CLAIM_RE.search(text)
    if claim:
        issues.append(
            ComplianceIssue(
                "unverifiable_claim",
                "warning",
                f"superlative claim {claim.group(0)!r} needs evidence or softer wording before publishing",
            )
        )

    return issues


def check_format(
    platform: str,
    format: str,
    *,
    media_count: int = 0,
    alt_texts: int = 0,
) -> list[ComplianceIssue]:
    """Validate the media/format shape of one draft."""
    issues: list[ComplianceIssue] = []
    limits = PLATFORM_LIMITS.get(platform)
    if limits is None:
        return [ComplianceIssue("unknown_platform", "error", f"no limits defined for {platform}")]

    if format == "carousel":
        if platform != "instagram":
            issues.append(
                ComplianceIssue("unsupported_format", "error", f"{platform} does not support carousel posts")
            )
        else:
            if media_count > limits["max_carousel_slides"]:
                issues.append(
                    ComplianceIssue(
                        "carousel_too_large",
                        "error",
                        f"Instagram carousels are limited to {limits['max_carousel_slides']} slides; "
                        f"this draft references {media_count} media items",
                    )
                )
            if 0 < media_count < limits["min_carousel_slides"]:
                issues.append(
                    ComplianceIssue(
                        "carousel_too_small",
                        "error",
                        "an Instagram carousel needs at least 2 slides",
                    )
                )

    if format.startswith("video") and platform not in {"tiktok", "instagram"}:
        issues.append(
            ComplianceIssue("unsupported_format", "error", f"{platform} does not take {format} via this pipeline")
        )

    # Image/video posts need alt text for accessibility on every platform
    # that supports it; missing alt text is a review warning, not a blocker.
    if media_count > 0 and alt_texts < media_count and platform in {"instagram", "twitter", "linkedin"}:
        issues.append(
            ComplianceIssue(
                "missing_alt_text",
                "warning",
                f"{media_count - alt_texts} media item(s) have no alt text; add descriptions for accessibility",
            )
        )

    return issues


def split_x_thread(text: str, *, limit: int = 280) -> list[str]:
    """Split long copy into numbered X/Twitter thread chunks.

    Greedy word-wrap at the character limit, reserving room for the
    `` i/n`` numbering suffix. Words longer than the limit are hard-split.
    Returns the text unchanged (single chunk) when it already fits.
    """
    if len(text) <= limit:
        return [text]
    # Reserve the maximum suffix width (" 25/25" is 6 chars) up front so
    # every chunk stays inside the limit once numbered.
    budget = limit - 8
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        while len(word) > budget:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:budget])
            word = word[budget:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= budget:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    total = len(chunks)
    return [f"{chunk} {index}/{total}" for index, chunk in enumerate(chunks, start=1)]


def validate_draft(
    platform: str,
    format: str,
    text: str,
    *,
    sponsored: bool = False,
    media_count: int = 0,
    alt_texts: int = 0,
) -> list[ComplianceIssue]:
    """Full pre-scheduling check for one platform draft."""
    issues = check_format(platform, format, media_count=media_count, alt_texts=alt_texts)
    if format == "thread" and platform == "twitter":
        chunks = split_x_thread(text)
        if len(chunks) > PLATFORM_LIMITS["twitter"]["max_thread_chunks"]:
            issues.append(
                ComplianceIssue(
                    "thread_too_long",
                    "error",
                    f"X threads are limited to {PLATFORM_LIMITS['twitter']['max_thread_chunks']} posts; "
                    f"this draft needs {len(chunks)}",
                )
            )
        issues.extend(check_caption(platform, text, sponsored=sponsored))
    else:
        issues.extend(check_caption(platform, text, sponsored=sponsored))
    return issues


def is_blocking(issues: list[ComplianceIssue]) -> bool:
    """True when any finding must stop the draft from being scheduled."""
    return any(issue.severity == "error" for issue in issues)
