"""Feed social signals into the M19 idea incubator.

Fresh observed work becomes captured ideas - the "think and generate ideas"
half of the owner's ask. Every harvested idea cites its source signal in
metadata, and each signal is harvested at most once (dedupe by source).
"""
from __future__ import annotations

from typing import Any

from app.modules.m19_idea_incubator.schemas import IdeaCreate

from .knowledge import KnowledgeStore

# Text cues that a post describes work worth thinking about, not noise.
_SIGNAL_TERMS = (
    "launch", "launched", "launching", "release", "released", "shipping", "shipped",
    "patent", "paper", "published", "built", "building", "open source", "open-source",
    "raised", "funding", "hiring", "announce", "announcing", "introducing", "prototype",
    "demo", "beta", "waitlist", "startup", "project",
)
_MAX_TEXT = 2000


def score_signal(text: str) -> float:
    """Transparent term-frequency score in [0, 1]; no hidden model."""
    lowered = (text or "").lower()
    if not lowered:
        return 0.0
    hits = sum(lowered.count(term) for term in _SIGNAL_TERMS)
    return min(1.0, hits / 4.0)


def _idea_for_signal(signal: dict[str, Any]) -> IdeaCreate:
    handle = signal.get("handle", "unknown")
    platform = signal.get("platform", "unknown")
    text = (signal.get("text") or "")[:_MAX_TEXT]
    url = signal.get("source_url", "")
    title = f"{platform}: {handle} - {(text[:60] or 'new work')}..."
    return IdeaCreate(
        title=title[:180],
        problem=f"Signal from the owner's network: {handle} on {platform} shared work that may "
                f"connect to the owner's interests. Observed text: {text[:1500]}",
        proposed_solution="Review the source, decide whether it connects to an existing idea or "
                          "deserves its own track, and park or reject it if not.",
        tags=["social-reading", platform, handle],
        metadata={"source": "social_reading", "signal_id": signal.get("id"),
                  "source_url": url, "platform": platform, "handle": handle,
                  "observed_at": signal.get("observed_at"), "signal_score": signal.get("signal_score")},
    )


def harvest_signals(store: KnowledgeStore, ledger: Any, tenant_id: str, *,
                    min_score: float = 0.25, limit: int = 25) -> dict[str, Any]:
    """Turn unharvested signals at or above min_score into captured M19 ideas.

    ``ledger`` is an M19 LedgerService (tenant-scoped repository + actor).
    Returns the created ideas and the signals now linked to them.
    """
    signals = store.list_signals(tenant_id, unharvested=True, limit=500)
    picked = [signal for signal in signals
              if (signal.get("signal_score") or 0) >= min_score][:max(1, min(limit, 100))]
    created = []
    for signal in picked:
        idea = ledger.create_idea(_idea_for_signal(signal))
        store.mark_harvested(tenant_id, [signal["id"]], idea.id)
        created.append({"idea_id": idea.id, "title": idea.title,
                        "signal_id": signal["id"], "source_url": signal.get("source_url", ""),
                        "signal_score": signal.get("signal_score", 0)})
    skipped = len(signals) - len(picked)
    return {"created": created, "created_count": len(created),
            "skipped_below_threshold_or_capped": skipped,
            "min_score": min_score,
            "boundary": "Ideas are captured for review, not endorsed; each cites its source signal. "
                        "Nothing here contacts any person."}
