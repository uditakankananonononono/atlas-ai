"""Seed registry of legal collection targets.

Conservative by design: only channel types whose legal path is settled are
seeded here, and RSS feeds ship empty - a feed URL enters the registry only
after it has been verified to resolve and to permit collection, matching the
project rule that unverified sites are never seeded. Tenants can extend the
registry; nothing here grants access to prohibited channels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .lane_models import SourceKind
from .lane_sources import ensure_legal_platform


@dataclass(frozen=True)
class RegistryEntry:
    kind: SourceKind
    platform: str
    target: str                               # subreddit name, dev.to tag, feed URL, ...
    note: str = ""


DEFAULT_SUBREDDITS: tuple[str, ...] = (
    "sidehustle",
    "Entrepreneur",
    "smallbusiness",
    "passive_income",
    "sweatystartup",
    "flipping",
)

DEFAULT_DEVTO_TAGS: tuple[str, ...] = (
    "indiehacking",
    "sideproject",
    "entrepreneur",
    "saas",
)


def default_registry() -> list[RegistryEntry]:
    entries = [
        RegistryEntry(kind=SourceKind.REDDIT_JSON, platform="reddit", target=sub,
                      note="public JSON search, identifying UA required")
        for sub in DEFAULT_SUBREDDITS
    ]
    entries += [
        RegistryEntry(kind=SourceKind.DEV_TO, platform="dev_to", target=tag,
                      note="public articles API")
        for tag in DEFAULT_DEVTO_TAGS
    ]
    entries.append(RegistryEntry(kind=SourceKind.HACKER_NEWS, platform="hacker_news",
                                 target="query", note="official Algolia search API"))
    # SourceKind.RSS: intentionally empty until a feed URL is verified.
    # SourceKind.YOUTUBE_DATA_API: query-driven, requires the configured API key.
    return entries


def validate_registry(entries: Sequence[RegistryEntry]) -> list[str]:
    """Returns problems; empty means the registry is fully legal."""
    problems: list[str] = []
    for entry in entries:
        try:
            ensure_legal_platform(entry.platform)
        except ValueError as exc:
            problems.append(str(exc))
        if entry.kind is SourceKind.RSS and not entry.target.startswith("https://"):
            problems.append(f"rss target must be an https feed url: {entry.target!r}")
    return problems
